"""Plan-independent necessary bounds for the frozen official P3 semantics.

This does not find an optimum. COPY service bounds require unaliased original
tensor cache identities. It never adds cross-core delay to unknown placement.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import heapq
import json
import math
from pathlib import Path
import time

from .baseline import ROOT
from multicore_cut_evaluate_problem_1 import _original_tensor_views
from evaluation_validation import read_bandwidth_config


def bound_graph(graph, cores, bandwidth):
    if cores < 1 or bandwidth <= 0:
        raise ValueError('positive cores and bandwidth required')
    all_ops = {o['id']: o for o in graph['ops']}
    ops = {u: o for u, o in all_ops.items() if o['op'] not in ('COPY_IN', 'COPY_OUT')}
    tensors = {t['id']: t for t in graph['tensors']}
    producers, consumers, direct = _original_tensor_views(graph)
    if any(len(writers) > 1 for writers in producers.values()):
        raise ValueError('bound proof requires at most one original producer per tensor')
    pred = {u: set() for u in ops}
    for t, readers in consumers.items():
        ps = producers[t] & ops.keys()
        for u in readers & ops.keys():
            pred[u].update(ps - {u})
    for edge in direct:
        u, v = edge['source'], edge['target']
        if u in ops and v in ops:
            pred[v].add(u)
    succ = {u: set() for u in ops}
    for v, ps in pred.items():
        for u in ps:
            succ[u].add(v)
    inputs = {t: consumers[t] & ops.keys() for t in tensors
              if consumers[t] & ops.keys() and not producers[t] & ops.keys()}
    outputs = {t: producers[t] & ops.keys() for t in tensors
               if producers[t] & ops.keys()
               and (not consumers[t] & ops.keys()
                    or any(all_ops[u]['op'] == 'COPY_OUT' for u in consumers[t]))}
    unaliased = all('logical_tid' not in t for t in tensors.values())
    release = defaultdict(int)
    if unaliased:
        for t, readers in inputs.items():
            for u in readers:
                release[u] = max(release[u], max(1, math.ceil(tensors[t]['size'] / bandwidth)))
    work = defaultdict(int)
    for o in ops.values():
        work[o['pipe']] += max(1, o['cycles'])
    degree = {u: len(ps) for u, ps in pred.items()}
    ready = [u for u in ops if not degree[u]]
    heapq.heapify(ready)
    finish, compute_finish, parent = {}, {}, {}
    while ready:
        u = heapq.heappop(ready)
        duration = max(1, ops[u]['cycles'])
        p = max(pred[u], key=lambda v: finish[v], default=None)
        parent[u] = p if p is not None and finish[p] >= release[u] else None
        finish[u] = max(release[u], finish[p] if p is not None else 0) + duration
        compute_finish[u] = max((compute_finish[v] for v in pred[u]), default=0) + duration
        for v in succ[u]:
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, v)
    if len(finish) != len(ops):
        raise ValueError('original eligible computation has a cycle')
    cp = max(compute_finish.values(), default=0)
    io_cp = max(finish.values(), default=0)
    mandatory_ddr = None
    if unaliased:
        io_cp = max([io_cp] + [max(finish[u] for u in ps) +
                                max(1, math.ceil(tensors[t]['size'] / bandwidth))
                                for t, ps in outputs.items()])
        mandatory_ddr = sum(max(1, math.ceil(tensors[t]['size'] / bandwidth))
                            for t in list(inputs) + list(outputs))
    pipe = max((math.ceil(w / cores) for w in work.values()), default=0)
    return dict(cores=cores, eligible_ops=len(ops), pipe_work=dict(work),
                compute_work_bound=pipe, compute_critical_path_bound=cp,
                cold_input_output_path_bound=io_cp if unaliased else None,
                mandatory_ddr_service_bound=mandatory_ddr,
                unaliased_tensor_guard=unaliased,
                lower_bound_cycles=max(pipe, cp, io_cp, mandatory_ddr or 0))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--graph-dir', type=Path, required=True)
    ap.add_argument('--config', type=Path, default=ROOT / 'data/raw/a/official/data/config.txt')
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    start = time.perf_counter()
    rows = []
    bw = read_bandwidth_config(args.config)
    for path in sorted(args.graph_dir.glob('case_*.json')):
        raw = path.read_bytes()
        graph = json.loads(raw)
        # Independent values expose the full requested 1..5 core domain.
        rows.extend(dict(case_id=path.stem.split('_')[1], graph_sha256=hashlib.sha256(raw).hexdigest(),
                         **bound_graph(graph, k, bw)) for k in range(1, 6))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(
        method='plan-independent P3 necessary bounds; no optimum claim and zero evaluator calls',
        config_sha256=hashlib.sha256(args.config.read_bytes()).hexdigest(),
        analysis_wall_seconds=time.perf_counter()-start, rows=rows), indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(rows=len(rows), analysis_wall_seconds=time.perf_counter()-start)))


if __name__ == '__main__':
    main()
