"""Read-only zero-lag compute/FIFO lower bound for the frozen single-tail layout."""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
from math import ceil
from pathlib import Path
import time

from .construct import SharingIndex
from .wave_capacity import SPACES, model, structure
from .wave_tail import partition_tail
from evaluation_validation import read_capacity_config


def longest_path(ops, original_succ, schedules):
    """Longest weighted path in original compute DAG plus same-pipe FIFO edges."""
    vertices = set(ops)
    listed = [u for seq in schedules for u in seq]
    if len(listed) != len(vertices) or set(listed) != vertices:
        raise ValueError("compute schedules must cover each eligible op exactly once")
    edges = {u: {} for u in vertices}
    owners = {u: c for c, seq in enumerate(schedules) for u in seq}
    for u, targets in original_succ.items():
        for v in targets:
            if u in vertices and v in vertices:
                edges[u].setdefault(v, set()).add("original")
    for seq in schedules:
        previous = {}
        for u in seq:
            pipe = ops[u]["pipe"]
            if pipe not in ("PIPE_M", "PIPE_V"):
                raise ValueError("only guarded M/V compute ops are supported")
            if pipe in previous:
                edges[previous[pipe]].setdefault(u, set()).add("fifo")
            previous[pipe] = u
    indegree = {u: 0 for u in vertices}
    for targets in edges.values():
        for v in targets:
            indegree[v] += 1
    ready = deque(u for u in ops if indegree[u] == 0)
    distance = {u: 0 for u in vertices}
    predecessor = {u: None for u in vertices}
    seen = 0
    while ready:
        u = ready.popleft()
        seen += 1
        finished = distance[u] + ops[u]["cycles"]
        for v in edges[u]:
            if finished > distance[v]:
                distance[v], predecessor[v] = finished, u
            indegree[v] -= 1
            if indegree[v] == 0:
                ready.append(v)
    if seen != len(vertices):
        raise ValueError("original dependency and FIFO edges form a cycle")
    endpoint = max(ops, key=lambda u: (distance[u] + ops[u]["cycles"], -u))
    bound = distance[endpoint] + ops[endpoint]["cycles"]
    path = []
    u = endpoint
    while u is not None:
        path.append(u)
        u = predecessor[u]
    path.reverse()
    edge_counts = dict(original=0, fifo=0, both=0, cross_core_original=0)
    for u, targets in edges.items():
        for v, kinds in targets.items():
            edge_counts["both" if len(kinds) == 2 else next(iter(kinds))] += 1
            if "original" in kinds and owners[u] != owners[v]:
                edge_counts["cross_core_original"] += 1
    path_edges = [dict(source=u, target=v, kinds=sorted(edges[u][v]),
                       cross_core=owners[u] != owners[v])
                  for u, v in zip(path, path[1:])]
    return dict(lower_bound_cycles=bound, path=path, path_edges=path_edges,
                path_cross_core_edges=sum(e["cross_core"] for e in path_edges),
                edge_counts=edge_counts, vertex_count=len(vertices))


def analyze(index, cores, capacity):
    data, reason = structure(index, cores)
    if reason:
        raise ValueError("structure guard failed: " + reason)
    jobs, length = data["jobs"], data["length"]
    if cores < 2 or len(jobs) % cores != 1 or length < cores:
        raise ValueError("single-tail shape guard failed")
    q = len(jobs) // cores
    bmax, footprint = model(data, capacity, q + 1)
    if bmax is None or bmax < 2:
        raise ValueError("capacity wave guard failed")
    count = ceil((q + 1) / bmax)
    if count > q:
        raise ValueError("empty full-job wave")
    sizes = [q // count + (i < q % count) for i in range(count)]
    if sizes[-1] + 1 > bmax:
        raise ValueError("tail wave width guard failed")
    template = jobs[0]
    m = [index.ops[u]["cycles"] if index.ops[u]["pipe"] == "PIPE_M" else 0 for u in template]
    v = [index.ops[u]["cycles"] if index.ops[u]["pipe"] == "PIPE_V" else 0 for u in template]
    frontier = footprint["frontier"]
    boundary = [sum(frontier[r][h] for r in range(len(SPACES))) for h in range(length + 1)]
    cuts, objective = partition_tail(m, v, cores, q, boundary)
    schedules = []
    for c in range(cores):
        group = [jobs[j] for j in range(c, q * cores, cores)]
        sequence, offset = [], 0
        for wave_no, size in enumerate(sizes):
            wave = group[offset:offset + size]
            offset += size
            for p in range(length):
                sequence.extend(job[p] for job in wave)
                if wave_no == count - 1 and cuts[c] <= p < cuts[c + 1]:
                    sequence.append(jobs[-1][p])
        schedules.append(sequence)
    result = longest_path(index.ops, index.succ, schedules)
    workloads = [dict(M=q * sum(m) + sum(m[cuts[c]:cuts[c + 1]]),
                      V=q * sum(v) + sum(v[cuts[c]:cuts[c + 1]]))
                 for c in range(cores)]
    if objective[0] != max(max(w.values()) for w in workloads):
        raise ValueError("DP/workload mismatch")
    result.update(cuts=cuts, wave_sizes=sizes, bmax=bmax, wave_count=count,
                  jobs=len(jobs), cores=cores, workload_peak_cycles=objective[0],
                  boundary_proxy_bytes=objective[1], per_core_work_cycles=workloads,
                  method="original eligible-compute DAG plus per-core M/V FIFO, zero extra cross-core lag",
                  limitations="No plan built or written; COPY/spill/Cache and transfer latency omitted; fixed-layout necessary bound only")
    return result


def main():
    start = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("graph", type=Path)
    ap.add_argument("--cores", type=int, required=True)
    ap.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[2] / "data/raw/a/official/data/config.txt")
    ap.add_argument("--incumbent", type=int, help="same-identity incumbent Makespan; comparison only")
    args = ap.parse_args()
    raw = args.graph.read_bytes()
    result = analyze(SharingIndex(json.loads(raw)), args.cores,
                     read_capacity_config(args.config))
    root = Path(__file__).resolve().parents[2]
    sources = ("src/q3_yuanzhifang/tail_fifo_bound.py", "src/q3_yuanzhifang/wave_tail.py",
               "src/q3_yuanzhifang/wave_capacity.py", "src/q3_yuanzhifang/construct.py",
               "src/q3_yuanzhifang/baseline.py")
    result.update(graph_sha256=hashlib.sha256(raw).hexdigest(),
                  config_sha256=hashlib.sha256(args.config.read_bytes()).hexdigest(),
                  source_sha256={name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                 for name in sources},
                  started_at_utc=started_at,
                  analyzed_at_utc=datetime.now(timezone.utc).isoformat(),
                  analysis_body_wall_seconds=time.perf_counter() - start,
                  costs="Case-specific static analysis; report separately, never reuse outside a future cold solver clock",
                  timing_scope="Body timer excludes interpreter startup/imports; external process wall must be reported separately",
                  calls=dict(candidate_compute_order_analysis=1, submission_constructor=0,
                             submission_write=0, derive=0, step=0, E0=0, E1=0, E2=0))
    if args.incumbent is not None:
        if args.incumbent <= 0:
            ap.error("incumbent must be positive")
        result["incumbent_cycles"] = args.incumbent
        result["fixed_layout_cannot_beat_incumbent"] = result["lower_bound_cycles"] >= args.incumbent
        result["incumbent_note"] = "Bound crossing incumbent safely prunes this fixed layout; lower bound is not achievable-score claim"
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
