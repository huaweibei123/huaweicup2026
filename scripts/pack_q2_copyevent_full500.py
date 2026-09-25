"""Build a portable full-grid source/input capsule from explicit Git commits.

This only verifies and packages bytes. It never constructs or evaluates a plan.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOLVER = '295ec9cf4351b77f5c6fffe8fbb23e8bc8d2f323'
E2 = '603b0741e21c449d3db652ebd67c94f2dc014cc9'
BASE = '60afc38b327680fbda0ff10182e3e05a01edd72d'
FEED = 'results/a/q2-nikolastarx/active-core-full500-20260925-s59/20260924T1910Z-s59ee/board-feed-500-with-runtime-notes.json'
FEED_SHA = '0b850686966d1d7c1ce1a8babb1655051756b42f9a59d5c6f6becd6a87f2f99c'
E2_MANIFEST = 'results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json'
RUNNER = 'scripts/q2_copyevent_linux_full500.py'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def blob(commit, path):
    return subprocess.check_output(['git', 'show', commit + ':' + path], cwd=ROOT)


def decode(raw):
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


def make_baseline():
    raw = blob(BASE, FEED)
    if sha(raw) != FEED_SHA:
        raise ValueError('baseline feed differs')
    rows = decode(raw)['records']
    by_case = {r['case_id']: r for r in rows if r['cores'] == 1}
    if len(rows) != 500 or set(by_case) != {f'{i:03d}' for i in range(1, 101)}:
        raise ValueError('baseline coverage differs')
    records = []
    for case, row in sorted(by_case.items()):
        ref = row['baseline']['result']
        truth_raw = blob(BASE, ref['path'])
        if sha(truth_raw) != ref['sha256']:
            raise ValueError('baseline result identity differs: ' + case)
        truth = decode(truth_raw)
        # The shared board denominator is the official singlecore CLI result.
        # That CLI labels its result scene A, including for P2 comparisons.
        if (truth['scene'] != 'A' or truth.get('execution_mode') != 'singlecore'
                or truth['num_cores'] != 1 or truth['makespan'] <= 0):
            raise ValueError('wrong baseline scene/cores')
        records.append({'case': case, 'makespan': truth['makespan'],
                        'scene': truth['scene'], 'execution_mode': truth['execution_mode'],
                        'graph_sha256': row['identity']['graph_sha256'],
                        'config_sha256': row['identity']['config_sha256'],
                        'result': {**ref, 'commit': BASE}})
    return {'scope': 'report-only official single-core denominators; no solver input',
            'source_commit': BASE, 'feed_path': FEED, 'feed_sha256': FEED_SHA,
            'records': records}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runner-commit', required=True)
    ap.add_argument('--raw-root', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    runner_commit = subprocess.check_output(['git', 'rev-parse', a.runner_commit],
                                            cwd=ROOT, text=True).strip()
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', SOLVER,
                                    'src/q2_nikolastarx'], cwd=ROOT, text=True).splitlines()
    paths = [p for p in paths if p.endswith('.py')]
    files = {p: blob(SOLVER, p) for p in paths}
    for name in ('pyproject.toml', 'uv.lock', 'README.md', 'docs/a/source-manifest.json',
                 E2_MANIFEST, 'scripts/e2_linux_native.py'):
        files[name] = blob(SOLVER, name)
    files[RUNNER] = blob(runner_commit, RUNNER)
    files['fixed-p2-manifest.json'] = files[E2_MANIFEST]
    e2 = json.loads(files[E2_MANIFEST])
    for path, expected in e2['e2_sources'].items():
        raw = blob(E2, path)
        if sha(raw) != expected:
            raise ValueError('E2 source identity differs: ' + path)
        files['e2-src/' + path] = raw
    official = json.loads(files['docs/a/source-manifest.json'])
    source = {r['path']: r for r in official['files']}
    required = ['data/config.txt'] + [f'data/case_{i:03d}.json' for i in range(1, 101)]
    required += [p for p in source if p.startswith('code/') and p.endswith('.py')]
    for name in required:
        raw = (a.raw_root / name).read_bytes()
        if sha(raw) != source[name]['sha256'] or len(raw) != source[name]['bytes']:
            raise ValueError('frozen official bytes differ: ' + name)
        files['data/raw/a/official/' + name] = raw
    baseline = make_baseline()
    for row in baseline['records']:
        if (row['graph_sha256'] != source[f"data/case_{row['case']}.json"]['sha256'] or
                row['config_sha256'] != source['data/config.txt']['sha256']):
            raise ValueError('baseline denominator is for other input/config')
    files['singlecore-baseline.json'] = encoded(baseline)
    manifest = {
        'schema': 'q2-copyevent-linux-full500-v1',
        'scope': 'one frozen algorithm, 100 graphs x cores 1-5; cold processes',
        'solver_source_commit': SOLVER, 'runner_source_commit': runner_commit,
        'e2_source_commit': E2,
        'solver_module': 'src.q2_nikolastarx.adaptive_copyevent_guarded',
        'solver_sources': {p: sha(files[p]) for p in paths},
        'official_source_manifest_sha256': sha(files['docs/a/source-manifest.json']),
        'official_code_hash': official['official_code_hash'],
        'singlecore_baseline': {'path': 'singlecore-baseline.json',
                                'sha256': sha(files['singlecore-baseline.json'])},
        'coordinates': [[f'{i:03d}', k] for i in range(1, 101) for k in range(1, 6)],
        'limits': {'workers': 2, 'cells': 500, 'E2_api': 2000,
                   'E0_independent': 500, 'retries': 0, 'batch_seconds': 7200,
                   'solver_seconds': 180, 'e0_seconds': 180,
                   'rss_bytes_per_cell': 4 << 30, 'rss_bytes_total': 8 << 30},
        'files': {name: sha(raw) for name, raw in sorted(files.items())},
    }
    files['capsule-manifest.json'] = encoded(manifest)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(a.output, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, raw in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 9, 25, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(entry, raw)
    a.output.with_suffix('.manifest.json').write_bytes(files['capsule-manifest.json'])
    print(json.dumps({'capsule_sha256': sha(a.output.read_bytes()),
                      'manifest_sha256': sha(files['capsule-manifest.json']),
                      'bytes': a.output.stat().st_size, 'files': len(files),
                      'solver_commit': SOLVER, 'runner_commit': runner_commit}))


if __name__ == '__main__':
    main()
