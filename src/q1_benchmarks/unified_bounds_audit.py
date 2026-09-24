"""Join frozen v1 official results with existing static global bounds, without scoring."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[2]
BOUNDS = 'results/a/q1-lower-bounds-20260924/static_bounds.json'
BOUNDS_SHA = '743712b16b804ed72120ccad0b33652c16cf65d61e0691bea85ae26f28f4f8b8'
FEED = 'results/a/q1-unified-full500-20260925-s59/20260924T1810Z-s59ee/board-feed-500.json'
FEED_SHA = '7a3964740f35902829ae16daee3f8ce9baeeba25cfc376a03e594f54a44e68ce'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_checked(path, expected):
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise ValueError(f'Identity mismatch: {path.name}')
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def audit(feed_root):
    bounds = load_checked(ROOT / BOUNDS, BOUNDS_SHA)
    feed = load_checked(feed_root / FEED, FEED_SHA)
    code = bounds['code_identity']
    if digest((ROOT / 'src/q1/lower_bounds.py').read_bytes()) != code['implementation_sha256']:
        raise ValueError('Lower-bound source has changed')
    for name, sha in code['official_source_sha256'].items():
        if digest((ROOT / 'data/raw/a/official/code' / name).read_bytes()) != sha:
            raise ValueError('Official lower-bound assumptions changed')
    manifest = json.loads((ROOT / 'docs/a/source-manifest.json').read_bytes())
    by_key = {}
    for case in bounds['cases']:
        case_id = Path(case['input_member']).stem.removeprefix('case_')
        for item in case['bounds']:
            key = (case_id, item['cores'])
            if key in by_key:
                raise ValueError('Duplicate static bound')
            by_key[key] = (case['input_sha256'], item)
    rows, denominators, seen = [], {}, set()
    for record in feed['records']:
        key = record['case_id'], record['cores']
        if key in seen:
            raise ValueError('Duplicate official cell')
        seen.add(key)
        sha, bound = by_key[key]
        identity = record['identity']
        if (record['status'] != 'ok' or record['problem'] != 'P1'
                or record['solver_commit'] != '48faef6f1386c3dc7d037674a38af29d533ba774'
                or record['run_id'] != '20260924T1810Z-s59ee'
                or identity['graph_sha256'] != sha
                or identity['config_sha256'] != code['config_sha256']
                or identity['official_sha256'] != manifest['official_code_hash']):
            raise ValueError('Cannot compare different inputs or semantics')
        baseline = record['baseline']
        for field in ('graph_sha256', 'config_sha256', 'official_sha256'):
            if baseline[field] != identity[field]:
                raise ValueError('Baseline identity mismatch')
        source = baseline['result']
        cache_key = source['path'], source['sha256']
        if cache_key not in denominators:
            denominators[cache_key] = load_checked(feed_root / source['path'], source['sha256'])['makespan']
        b = denominators[cache_key]
        u, l = record['metrics']['makespan_cycles'], bound['lower_bound_cycles']
        if not (b > 0 and u > 0 and l > 0):
            raise ValueError('Nonpositive value')
        rows.append(dict(case=key[0], cores=key[1], official_makespan=u,
                         global_lower_bound=l, bound_violated=l > u,
                         speedup=b/u, speedup_upper_bound=b/l,
                         relative_optimality_gap_upper=u/l-1,
                         possible_fractional_reduction_upper=1-l/u,
                         extra_speedup_upper=b/l-b/u,
                         solver_wall_seconds=record['metrics']['solver_wall_seconds']))
    if len(rows) != 500 or seen != set(by_key):
        raise ValueError('Need exactly the same full500 scope')
    groups = []
    for cores in range(1, 6):
        group = [x for x in rows if x['cores'] == cores]
        groups.append(dict(cores=cores, count=len(group),
                          observed_mean_speedup=statistics.mean(x['speedup'] for x in group),
                          mean_speedup_upper_bound=statistics.mean(x['speedup_upper_bound'] for x in group),
                          relative_gap_at_most={str(t): sum(x['relative_optimality_gap_upper'] <= t for x in group)
                                                for t in (0.01, 0.05, 0.10)},
                          largest_unresolved_bounds=sorted(group, key=lambda x: -x['extra_speedup_upper'])[:10]))
    return dict(kind='static_bound_comparison_not_a_new_performance_batch',
                sources=dict(bounds=dict(path=BOUNDS, sha256=BOUNDS_SHA, code_identity=code),
                             official_feed=dict(path=FEED, sha256=FEED_SHA,
                                                data_commit='a765899917cbb068c84aeedcf6aca174443f435f')),
                calls=dict(solver=0, E0=0, E1=0, E2=0),
                violations=[x for x in rows if x['bound_violated']], groups=groups, rows=rows,
                interpretation='A small U/L proves limited remaining reduction under stated bounds. '
                'A large U/L may reflect loose bounds, not attainable gain. '
                'This is known-set evidence and no global optimality certificate.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--feed-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError('Refuse to overwrite audit')
    result = audit(args.feed_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as out:
        json.dump(result, out, indent=2)
        out.write('\n')
    print(json.dumps({'violations': len(result['violations']),
                      'groups': [{k:v for k,v in x.items() if k != 'largest_unresolved_bounds'}
                                 for x in result['groups']]}))
    return int(bool(result['violations']))


if __name__ == '__main__':
    raise SystemExit(main())
