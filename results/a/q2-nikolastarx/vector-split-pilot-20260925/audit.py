"""Read existing single-cell evidence and fixed old comparator; never score."""
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
HOME = Path(__file__).resolve().parent
SOURCE = 'd1cb26fe04cd7f0a49c053fde8b0e97d3c9b5780'
RUNNER = 'c970e6a8215307f864d87f56fcfd3b3989306ed3'
OLD = '81219bf923524fb60616e39b5ad2dced67aec3e2'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    data = Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)


def git_bytes(commit, path):
    return subprocess.check_output(['git', 'show', commit+':'+path], cwd=ROOT)


def main():
    run = HOME/'run'; cell = run/'016-k5/016-k5'
    batch, receipt = read(run/'batch.json'), read(cell/'run.json')
    feed_path = run/'016-k5/board-feed-016-k5.json'
    feed = read(feed_path)
    assert len(feed['records']) == 1
    row = feed['records'][0]
    context = read(run/'016-k5/context.json')
    assert batch['source_commit'] == context['source_commit'] == row['solver_commit'] == SOURCE
    assert batch['runner_commit'] == context['runner_commit'] == RUNNER
    assert batch['status'] == 'completed' and receipt['status'] == 'ok'
    assert receipt['calls'] == {'solver': 1, 'E0': 1, 'E1': 0, 'E2': 0}
    manifest = read(cell/'manifest.json')
    for path, entry in manifest.items():
        data = (cell/path).read_bytes()
        assert sha(data) == entry['sha256'] and len(data) == entry['bytes'], path
    for entry in row['artifacts'].values():
        assert sha((ROOT/entry['path']).read_bytes()) == entry['sha256'], entry['path']
    archive = read(cell/'archive.json')['compression']
    for entry in archive.values():
        data = (cell/entry['stored']).read_bytes(); raw = gzip.decompress(data)
        assert sha(data) == entry['stored_sha256'] and len(data) == entry['stored_bytes']
        assert sha(raw) == entry['raw_sha256'] and len(raw) == entry['raw_bytes']
    process_rows = []
    for path in run.rglob('process.json'):
        proc = read(path)
        assert proc['status'] == 'ok' and proc['exit_code'] == 0 and proc['surviving_pids'] == []
        try:
            os.kill(proc['pid'], 0)
        except ProcessLookupError:
            pass
        else:
            raise AssertionError('recorded process still exists: '+str(proc['pid']))
        process_rows.append({'path': str(path.relative_to(ROOT)), 'pid': proc['pid'], 'exited': True})
    assert len(process_rows) == 3
    result, plan, online = read(cell/'final/result.json.gz'), read(cell/'plan.json'), read(cell/'online/solver.json')
    assert online['calls'] == {'E0': 0, 'E1': 0, 'E2': 0} and len(online['attempts']) == 1
    assert (cell/'plan.json').read_bytes() == (cell/'online/vector_split/plan.json').read_bytes()
    static = json.loads(git_bytes('87ad59cfb6636cf264017df3758a4f858e64afe9',
        'results/a/q2-nikolastarx/vector-split-static-20260925/report.json'))
    assert sha((cell/'plan.json').read_bytes()) == static['plan_sha256']
    graph_path = ROOT/'data/raw/a/official/data/case_016.json'
    assert sha(graph_path.read_bytes()) == static['input_sha256']
    graph = read(graph_path)
    eligible = {o['id'] for o in graph['ops'] if o['op'] not in ('COPY_IN', 'COPY_OUT')}
    inverse = {sg: int(u) for u, sg in plan['node_to_subgraph'].items()}
    owners = {inverse[sg]: c for c, word in enumerate(plan['core_schedules']) for sg in word}
    assert set(owners) == eligible
    producers, consumers = defaultdict(set), defaultdict(set)
    for edge in graph['edges']:
        a, b = edge['source'], edge['target']
        if a in eligible: producers[b].add(a)
        if b in eligible: consumers[a].add(b)
    large_pairs = 0
    for tensor in graph['tensors']:
        t = tensor['id']
        if tensor['size'] == 32768 and producers[t] and consumers[t]:
            assert len(producers[t]) == 1
            source = owners[next(iter(producers[t]))]
            large_pairs += len({owners[u] for u in consumers[t]} - {source})
    assert large_pairs == 610
    assert result['scene'] == 'B' and result['num_cores'] == 5
    assert result['makespan'] == row['metrics']['makespan_cycles'] == receipt['makespan_cycles']
    movement = result['data_movement_bytes']
    assert movement['added_copy_bytes'] == row['metrics']['extra_ddr_bytes']
    assert movement['spill_added_copy_bytes'] == row['metrics']['spill_bytes'] == 0
    old_path = 'results/a/q2-nikolastarx/direct-pilot-20260924/run/016-k5/final/result.json.gz'
    old_raw = git_bytes(OLD, old_path); old = json.loads(gzip.decompress(old_raw))
    assert old['scene'] == 'B' and old['num_cores'] == 5 and old['makespan'] == 2240622
    lower = online['attempts'][0]['detail']['fixed_plan_bound']['makespan_lower_bound_cycles']
    report = {'observed_at': datetime.now(timezone.utc).isoformat(), 'source_commit': SOURCE,
        'runner_commit': RUNNER, 'old_data_commit': OLD, 'old_result_path': old_path,
        'old_result_stored_sha256': sha(old_raw), 'old_makespan': old['makespan'],
        'new_makespan': result['makespan'], 'makespan_reduction_fraction': 1-result['makespan']/old['makespan'],
        'old_movement': old['data_movement_bytes'], 'new_movement': movement,
        'solver_seconds': row['metrics']['solver_wall_seconds'],
        'final_e0_seconds': row['metrics']['evaluation_wall_seconds'],
        'aggregate_seconds': batch['aggregate_wall_seconds'], 'calls': receipt['calls'],
        'online_calls': online['calls'], 'large_crossing_pairs': large_pairs,
        'large_vector_added_copy_bytes': 2*32768*large_pairs,
        'fixed_candidate_lower_bound': lower, 'official_minus_bound': result['makespan']-lower,
        'manifest_entries_verified': len(manifest), 'feed_refs_verified': len(row['artifacts']),
        'compression_roundtrips_verified': len(archive), 'processes': process_rows,
        'feed_sha256': sha(feed_path.read_bytes()), 'static_plan_exact_match': True,
        'scope': 'One official development cell; no full-suite or global optimality claim. Audit adds zero evaluations.'}
    (run/'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    (run/'SUMMARY.md').write_text(f'''# Controlled split: one official P2 result

016 / five cores: **{old['makespan']:,} → {result['makespan']:,} cycles**, reduction **{100*report['makespan_reduction_fraction']:.4f}%**. Extra DDR **{old['data_movement_bytes']['added_copy_bytes']:,} → {movement['added_copy_bytes']:,} B**; spill remains zero. This is a Makespan/movement tradeoff, not all-metric dominance.

One solver **{report['solver_seconds']:.6f} s**, one external unchanged E0 **{report['final_e0_seconds']:.6f} s**; aggregate **{report['aggregate_seconds']:.6f} s**. No online E0/E1/E2, no retry, all three process IDs exited. Source `{SOURCE}`, runner `{RUNNER}`; reference data `{OLD}` was read, not rerun. The exact final plan matches the earlier static plan hash.

The proposed 610 large tensor crossings account for {report['large_vector_added_copy_bytes']:,} added bytes. The fixed-plan lower bound is {lower:,}; its gap to official time is {report['official_minus_bound']:,}. The bound is not global, and the original compute-touch memory proxy alone did not prove zero spill. This actual E0 run establishes zero spill for this plan/input/config only.

All 14 raw manifest entries, four feed references and two compressed byte roundtrips passed. This script adds zero scoring. Full-suite b7 results and Pro r02 pending theory are separate; central feed admission and Git byte verification are recorded separately.
''')
    print(json.dumps({k: report[k] for k in ('new_makespan','makespan_reduction_fraction','feed_sha256')}))


if __name__ == '__main__':
    main()
