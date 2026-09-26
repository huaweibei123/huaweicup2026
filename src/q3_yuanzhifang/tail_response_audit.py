"""One guarded real-graph response audit; no plan, derive, Step, or E0 call."""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from .construct import SharingIndex
from .tail_response_model import analyze as response
from .tail_stair_model import analyze as stair
from evaluation_validation import read_capacity_config


def full_dag_finishes(ops, original_succ, schedules, tail, cuts):
    """Independent uncompressed DAG propagation, retaining all tail skip edges."""
    edges = {u: set(original_succ.get(u, ())) for u in ops}
    for seq in schedules:
        previous = {}
        for u in seq:
            pipe = ops[u]["pipe"]
            if pipe in previous:
                edges[previous[pipe]].add(u)
            previous[pipe] = u
    degrees = dict.fromkeys(ops, 0)
    for targets in edges.values():
        for v in targets:
            degrees[v] += 1
    ready = deque(u for u in ops if degrees[u] == 0)
    start = dict.fromkeys(ops, 0)
    finish = {}
    while ready:
        u = ready.popleft()
        finish[u] = start[u] + ops[u]["cycles"]
        for v in edges[u]:
            start[v] = max(start[v], finish[u])
            degrees[v] -= 1
            if degrees[v] == 0:
                ready.append(v)
    if len(finish) != len(ops):
        raise ValueError("uncompressed compute/FIFO DAG has a cycle")
    return dict(core_finish=[max(finish[u] for u in seq) for seq in schedules],
                tail_finish=[finish[tail[r - 1]] for r in cuts[1:]],
                bound=max(finish.values()), vertex_count=len(finish))


def main():
    body_start = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    raw = args.graph.read_bytes()
    index = SharingIndex(json.loads(raw))
    schedules, reference = stair(index, args.cores, read_capacity_config(args.config))
    tail = index.components[-1]
    response_start = time.perf_counter()
    compressed = response(index.ops, index.succ, schedules, tail)
    response_seconds = time.perf_counter() - response_start
    oracle_start = time.perf_counter()
    oracle = full_dag_finishes(index.ops, index.succ, schedules, tail, reference["cuts"])
    oracle_seconds = time.perf_counter() - oracle_start
    tail_finish = [max(x["C"], r + x["D"]) for x, r in
                   zip(compressed["coeffs"], compressed["arrival"])]
    checks = dict(cuts=compressed["cuts"] == reference["cuts"],
                  bound=compressed["bound"] == reference["lower_bound_cycles"] == oracle["bound"],
                  core_finish=compressed["finish"] == oracle["core_finish"],
                  tail_finish=tail_finish == oracle["tail_finish"],
                  arrivals=compressed["arrival"] == [0, *oracle["tail_finish"][:-1]],
                  cross_edges=compressed["cross_core_edge_count"] ==
                              reference["edge_counts"]["cross_core_original"])
    result = dict(schema="q3-tail-response-audit-v1", checks=checks,
                  status="ok" if all(checks.values()) else "mismatch",
                  graph_sha256=hashlib.sha256(raw).hexdigest(),
                  config_sha256=hashlib.sha256(args.config.read_bytes()).hexdigest(),
                  cores=args.cores, jobs=len(index.components), response=compressed,
                  oracle=oracle, reference=dict(bound=reference["lower_bound_cycles"],
                      cuts=reference["cuts"], h=reference["h"],
                      first_wave_sizes=reference["first_wave_sizes"],
                      workload_peak_cycles=reference["workload_peak_cycles"]),
                  response_body_seconds=response_seconds,
                  oracle_body_seconds=oracle_seconds,
                  analysis_body_seconds=time.perf_counter() - body_start,
                  completed_at_utc=datetime.now(timezone.utc).isoformat(),
                  timing_scope="Diagnostic section timings only; not a solver speedup or repeated benchmark.",
                  calls=dict(static_case_analysis=1, compute_order_construction=1,
                      response_compression=1, uncompressed_dag_readback=1,
                      submission_constructor=0, derive=0, Step=0, E0=0, E1=0, E2=0),
                  limitation="One fixed stair order in the zero-COPY, zero-extra-lag compute/FIFO relaxation; no official feasibility or achievable score claim.")
    print(json.dumps(result, sort_keys=True))
    if not all(checks.values()):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
