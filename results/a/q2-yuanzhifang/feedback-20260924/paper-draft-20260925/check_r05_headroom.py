"""Check frozen R05 path witnesses and arithmetic; never construct or score plans."""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
SOURCE = 'afabca83ffa941f988cae0680a4d99760018d580'
STATIC = 'results/a/q2-nikolastarx/pro-r05-pair-static-20260925'
RECOVERED = 'results/a/q2-nikolastarx/pro-r05-recovered-20260925'
CURRENT = 'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee/cases-001-010/003-k2'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    inputs = []

    def frozen(path, compressed=False):
        raw = subprocess.check_output(['git', 'show', f'{SOURCE}:{path}'], cwd=ROOT)
        record = {'commit': SOURCE, 'path': path, 'bytes': len(raw), 'sha256': sha(raw)}
        if compressed:
            raw = gzip.decompress(raw)
            record['uncompressed_sha256'] = sha(raw)
        inputs.append(record)
        return raw

    report = json.loads(frozen(f'{STATIC}/report.json'))
    receipt = json.loads(frozen(f'{RECOVERED}/receipt.json'))
    cell = json.loads(frozen(f'{CURRENT}/cell.json'))
    graph_path = ROOT / 'data/raw/a/official/data/case_003.json'
    graph_raw = graph_path.read_bytes()
    assert sha(graph_raw) == report['graph_sha256'] == receipt['graph_sha256'] == cell['graph_sha256']
    inputs.append({'path': graph_path.relative_to(ROOT).as_posix(), 'bytes': len(graph_raw),
                   'sha256': sha(graph_raw), 'kind': 'read-only official input'})
    config_raw = (ROOT / 'data/raw/a/official/data/config.txt').read_bytes()
    assert sha(config_raw) == receipt['config_sha256'] == cell['config_sha256']
    assert sha(frozen('src/q2_nikolastarx/fifo_bound.py')) == report['bound_source_sha256']
    assert sha(frozen('scripts/q2_r05_pair_static_bounds.py')) == report['script_sha256']
    graph = json.loads(graph_raw)
    ops = {op['id']: op for op in graph['ops']}
    tensors = {t['id']: t for t in graph['tensors']}
    assert len(ops) == len(graph['ops']) and len(tensors) == len(graph['tensors'])
    assert not (set(ops) & set(tensors))
    eligible = {u for u, op in ops.items() if op['op'] not in ('COPY_IN', 'COPY_OUT')}
    assert len(eligible) == receipt['eligible_ops']
    assert all(type(ops[u]['cycles']) is int for u in eligible)
    duration = {u: max(1, ops[u]['cycles']) for u in eligible}
    producers, consumers = defaultdict(set), defaultdict(set)
    direct = []
    reasons = defaultdict(set)
    for edge in graph['edges']:
        u, v = edge['source'], edge['target']
        if u in ops and v in tensors:
            producers[v].add(u)
        elif u in tensors and v in ops:
            consumers[u].add(v)
        elif u in eligible and v in eligible and u != v:
            direct.append((u, v, max(0, int(edge.get('data_size', 0)))))
            reasons[u, v].add('original_direct')
    for tid, tensor in tensors.items():
        assert 'logical_tid' not in tensor and type(tensor['size']) is int and tensor['size'] >= 0
        assert len(producers[tid]) <= 1
        for u in producers[tid] & eligible:
            for v in consumers[tid] & eligible:
                reasons[u, v].add('original_tensor')

    def plan_details(raw):
        plan = json.loads(raw)
        assert set(plan) == {'node_to_subgraph', 'core_schedules'}
        mapping = {int(u): group for u, group in plan['node_to_subgraph'].items()}
        assert set(mapping) == eligible and len(set(mapping.values())) == len(mapping)
        inverse = {group: u for u, group in mapping.items()}
        assert len(plan['core_schedules']) == 2
        groups = [g for row in plan['core_schedules'] for g in row]
        assert len(groups) == len(set(groups)) == len(eligible) and set(groups) == set(inverse)
        owner, fifo, work = {}, set(), defaultdict(lambda: [0, 0])
        for core, row in enumerate(plan['core_schedules']):
            last = {}
            for group in row:
                u = inverse[group]
                pipe = ops[u]['pipe']
                owner[u] = core
                work[core, pipe][0] += 1
                work[core, pipe][1] += duration[u]
                if pipe in last:
                    fifo.add((last[pipe], u))
                last[pipe] = u
        base_bytes = 0
        for tid, tensor in tensors.items():
            ps, cs = producers[tid] & eligible, consumers[tid] & eligible
            if not (ps or cs):
                continue
            size = tensor['size']
            if ps:
                producer = next(iter(ps))
                base_bytes += 2 * size * len({owner[u] for u in cs} - {owner[producer]})
                if not cs or any(ops[u]['op'] == 'COPY_OUT' for u in consumers[tid]):
                    base_bytes += size
            else:
                base_bytes += size * len({owner[u] for u in cs})
        base_bytes += sum(2 * size for u, v, size in direct if owner[u] != owner[v])
        return owner, fifo, work, base_bytes

    official_raw = frozen(f'{CURRENT}/result.json.gz', True)
    assert sha(official_raw) == report['comparator_result_sha256'] == cell['official']['result_sha256']
    official = json.loads(official_raw)
    assert cell['status'] == 'accepted' and official['scene'] == 'B' and official['num_cores'] == 2
    incumbent = official['makespan']
    assert incumbent == cell['official']['makespan'] == 245150
    movement = official['data_movement_bytes']
    assert movement['spill_added_copy_bytes'] == cell['official']['movement']['spill_added_copy_bytes'] == 0
    current_raw = frozen(f'{CURRENT}/plan.json.gz', True)
    assert sha(current_raw) == report['comparator_plan_sha256'] == cell['plan_sha256']
    current_bytes = plan_details(current_raw)[3]
    assert current_bytes == report['comparator_scheduled_copy_bytes'] == movement['scheduled_copy_bytes'] == 4262874
    rows = []
    for row in report['records']:
        name = row['name']
        path = ('results/a/q2-nikolastarx/pro-r04-review-20260925/static-003-k2/seed-plan.json.gz'
                if name == 'seed' else f'{RECOVERED}/recovered-raw-plan.json.gz')
        raw = frozen(path, True)
        assert sha(raw) == row['plan_json_sha256'] == receipt[f'{name}_plan_json_sha256']
        owner, fifo, work, byte_count = plan_details(raw)
        bound_raw = frozen(f'{STATIC}/{name}-fifo-bound.json.gz', True)
        assert sha(bound_raw) == row['bound_json_sha256']
        bound = json.loads(bound_raw)
        assert bound['supported'] and not bound['official_execution_validated']
        assert bound['core_count'] == 2 and bound['eligible_ops'] == len(eligible)
        assert bound['reconstruction_guard']['conditional_on_successful_official_execution']
        assert len(bound['per_core_pipe_work']) == 8
        assert {(r['core'], r['pipe']) for r in bound['per_core_pipe_work']} == {
            (c, p) for c in range(2) for p in ('PIPE_M', 'PIPE_V', 'PIPE_MTE2', 'PIPE_MTE3')}
        for item in bound['per_core_pipe_work']:
            assert work[item['core'], item['pipe']] == [item['op_count'], item['cycles']]
        assert max(v[1] for v in work.values()) == row['assigned_pipe_lower_bound_cycles'] == bound['assigned_pipe_work_lower_bound_cycles']
        path_nodes, path_edges = bound['critical_path'], bound['critical_path_edges']
        assert len(path_edges) == len(path_nodes) - 1
        assert len({x['op_id'] for x in path_nodes}) == len(path_nodes)
        running = 0
        for item in path_nodes:
            u = item['op_id']
            assert u in eligible and item['core'] == owner[u] and item['pipe'] == ops[u]['pipe']
            assert item['duration_cycles'] == duration[u]
            running += duration[u]
            assert item['relaxed_finish_cycles'] == running
        for left, right, edge in zip(path_nodes, path_nodes[1:], path_edges):
            pair = (left['op_id'], right['op_id'])
            expected = reasons[pair] | ({'fixed_compute_fifo'} if pair in fifo else set())
            assert expected and (edge['source'], edge['target']) == pair
            assert set(edge['reasons']) == expected
        assert running == bound['makespan_lower_bound_cycles'] == row['fixed_fifo_lower_bound_cycles']
        headroom = max(Fraction(0), Fraction(incumbent - running, incumbent))
        assert abs(float(headroom) - row['maximum_fractional_M_reduction']) < 1e-14
        assert row['existing_c665_official_M_cycles'] == incumbent
        assert row['rules_out_strict_gain_against_current'] == (running >= incumbent)
        rows.append({'name': name, 'pre_step2_bytes_recomputed': byte_count,
                     'assigned_pipe_bound': row['assigned_pipe_lower_bound_cycles'],
                     'fixed_fifo_path_bound': running, 'path_nodes_verified': len(path_nodes),
                     'max_fractional_M_reduction_exact': str(headroom),
                     'max_fractional_M_reduction': float(headroom)})
    by_name = {r['name']: r for r in rows}
    assert by_name['seed']['pre_step2_bytes_recomputed'] == 6351422
    assert by_name['recovered']['pre_step2_bytes_recomputed'] == receipt['independent_pre_step2_transfer_bytes'] == 5207554
    output = {'source_commit': SOURCE, 'inputs': inputs, 'rows': rows,
              'current_c665': {'official_M_cycles': incumbent, 'pre_step2_bytes_recomputed': current_bytes,
                               'official_scheduled_copy_bytes': movement['scheduled_copy_bytes'], 'spill_bytes': 0},
              'old_seed_to_recovered_fractional_byte_reduction':
                  float(Fraction(6351422 - 5207554, 6351422)),
              'new_calls': {'constructor': 0, 'solver': 0, 'Step2': 0, 'Step3': 0, 'E0': 0, 'E1': 0, 'E2': 0},
              'limits': ['Checks two saved compute/FIFO path witnesses against graph and plan, not a fresh longest-path computation or official validity check.',
                         'A path gives a necessary bound for successful execution of that exact plan; it does not constrain alternative owners or orders.',
                         'Byte counts are pre-Step2 except the separately identified saved official c665 result.',
                         'No candidate construction, preparation or evaluator is invoked.']}
    path = Path(__file__).with_name('r05-headroom-check.json')
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'output': path.relative_to(ROOT).as_posix(), 'sha256': sha(path.read_bytes()),
                      'rows': rows, 'current_c665': output['current_c665'], 'new_calls': output['new_calls']}))


if __name__ == '__main__':
    main()
