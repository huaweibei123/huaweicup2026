"""Fixed-plan P2 bounds; no global E0 evaluation and no plan search.

Compiles the frozen local pipeline (including actual Step2 spills and Step3
memory dependencies), validates the global DAG, and computes L <= M <= U.
The bound is plan-specific except for the separate eligible-compute bound.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import heapq
import json
from pathlib import Path
import sys
from typing import Any

FROZEN_AGG = 'de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0'
FROZEN_CONFIG = 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'
OFFICIAL_FILES = (
    'contest_io.py', 'evaluation_validation.py',
    'multicore_cut_evaluate_problem_1.py', 'multicore_cut_evaluate_problem_2.py',
    'multicore_cut_evaluate_problem_3.py', 'schedule_step1.py',
    'schedule_step2.py', 'schedule_step3.py', 'singlecore_evaluate.py',
    'stub_multicore_cut_and_schedule.py',
)

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check_identity(root: Path) -> dict[str, str]:
    directory = root / 'data/raw/a/official/code'
    text = ''.join(f'code/{name}\t{sha(directory/name)}\n' for name in sorted(OFFICIAL_FILES))
    aggregate = hashlib.sha256(text.encode()).hexdigest()
    config_hash = sha(root / 'data/raw/a/official/data/config.txt')
    if aggregate != FROZEN_AGG or config_hash != FROZEN_CONFIG:
        raise ValueError('Frozen code/config hash mismatch; bounds not evaluated under another identity.')
    return {'official_code_aggregate_sha256': aggregate, 'config_sha256': config_hash}

def compute_bounds(graph: dict[str, Any], plan: dict[str, Any], cfg: dict[str, Any], delay: int) -> dict[str, Any]:
    from multicore_cut_evaluate_problem_2 import _build_scene_b_tasks
    from schedule_step3 import _op_duration, _uses_ddr_bandwidth
    from evaluation_validation import validate_execution
    tasks, links, _, traffic, view = _build_scene_b_tasks(graph, plan, **cfg)
    validate_execution(tasks, links)
    weight: dict[tuple[int, int], int] = {}
    ddr: set[tuple[int, int]] = set()
    succ: dict[tuple[int, int], dict[tuple[int, int], int]] = defaultdict(dict)
    indegree: dict[tuple[int, int], int] = {}
    pipe_load: dict[tuple[int, str], int] = defaultdict(int)
    for core, task in tasks.items():
        for op_id, op in task['op_by_id'].items():
            node = (core, op_id)
            duration = _op_duration(op, task['in_tids'], task['out_tids'], task['tensor_by_id'], cfg['bandwidth'])
            weight[node] = duration
            indegree[node] = 0
            pipe_load[core, op['pipe']] += duration
            if _uses_ddr_bandwidth(op, task['in_tids'], task['out_tids'], task['tensor_by_id']):
                ddr.add(node)
    def add_edge(a: tuple[int, int], b: tuple[int, int], lag: int = 0) -> None:
        if b not in succ[a]:
            indegree[b] += 1
        succ[a][b] = max(lag, succ[a].get(b, 0))
    for core, task in tasks.items():
        for op_id, predecessors in task['op_preds'].items():
            for p in predecessors:
                add_edge((core, p), (core, op_id))
        for order in task['pipe_ops'].values():
            for a, b in zip(order, order[1:]):
                add_edge((core, a), (core, b))
    for link in links:
        add_edge((link['source_core'], link['source_copy_out_id']),
                 (link['target_core'], link['target_copy_in_id']), delay)
    k = view['num_cores']
    earliest = {v: 0 for v in weight}
    latest_bound = dict(earliest)
    ready = [v for v, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    visited = 0
    while ready:
        u = heapq.heappop(ready)
        visited += 1
        low_end = earliest[u] + weight[u]
        high_end = latest_bound[u] + weight[u] * (2*k if u in ddr else 1)
        for v, lag in succ[u].items():
            earliest[v] = max(earliest[v], low_end + lag)
            latest_bound[v] = max(latest_bound[v], high_end + lag)
            indegree[v] -= 1
            if indegree[v] == 0:
                heapq.heappush(ready, v)
    if visited != len(weight):
        raise ValueError('Compiled global graph is cyclic.')
    W = sum(weight[v] for v in ddr)
    P = max(pipe_load.values(), default=0)
    C = max((earliest[v] + weight[v] for v in weight), default=0)
    U = max((latest_bound[v] + weight[v]*(2*k if v in ddr else 1) for v in weight), default=0)
    compute_load: dict[str, int] = defaultdict(int)
    for op in graph['ops']:
        if op['op'] not in ('COPY_IN', 'COPY_OUT'):
            compute_load[op['pipe']] += max(1, op['cycles'])
    universal = max(((v+k-1)//k for v in compute_load.values()), default=0)
    return {
        'scope': 'L and U are for this fixed compiled plan, not the optimum over repartition/reordering.',
        'num_cores': k,
        'universal_eligible_compute_load_LB': universal,
        'plan_specific_DDR_service_LB': W,
        'plan_specific_pipe_LB': P,
        'plan_specific_compiled_CP_LB': C,
        'plan_specific_L': max(W, P, C),
        'plan_specific_conservative_U': U,
        'upper_bound_copy_slowdown_factor': 2*k,
        'compiled_op_count': len(weight),
        'compiled_edge_count': sum(map(len, succ.values())),
        'ddr_copy_count': len(ddr),
        'data_movement_bytes': traffic,
        'global_E0_calls': 0,
    }

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence-root', type=Path, required=True)
    ap.add_argument('--graph', type=Path, required=True)
    ap.add_argument('--plan', type=Path, required=True)
    ap.add_argument('--reference-plan', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    root = a.evidence_root.resolve()
    identity = check_identity(root)
    sys.path.insert(0, str(root / 'data/raw/a/official/code'))
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    config_path = root / 'data/raw/a/official/data/config.txt'
    cfg = read_evaluation_config(config_path)
    delay = read_scene_b_config(config_path)['cross_core_copy_delay_cycles']
    graph = json.loads(a.graph.read_bytes())
    plan = json.loads(a.plan.read_bytes())
    result: dict[str, Any] = {
        'identity': identity, 'graph_sha256': sha(a.graph),
        'candidate_plan_sha256': sha(a.plan),
        'candidate': compute_bounds(graph, plan, cfg, delay),
    }
    if a.reference_plan:
        reference = json.loads(a.reference_plan.read_bytes())
        result['reference_plan_sha256'] = sha(a.reference_plan)
        result['reference'] = compute_bounds(graph, reference, cfg, delay)
        result['certified_strict_improvement'] = (
            result['candidate']['plan_specific_conservative_U'] < result['reference']['plan_specific_L'])
        result['comparison_scope'] = 'Only these two fixed plans; not a universal algorithm or optimality claim.'
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(a.output), 'L': result['candidate']['plan_specific_L'],
                      'U': result['candidate']['plan_specific_conservative_U'],
                      'certified_strict_improvement': result.get('certified_strict_improvement')}, ensure_ascii=False))

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(f'ERROR: {error}')
