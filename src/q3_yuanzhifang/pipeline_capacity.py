"""Cold-setup chain partition with explicit shared-residence constraints.

The constraint reserves the whole stage's common inputs plus its largest
single-operation noncommon footprint. This is a structural working-set model,
not a guarantee of zero official spills: prefetch and overlapping lifetimes
can require more memory. One candidate, no internal evaluation or search loop.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .active_stages import stage_structure
from .construct import SharingIndex, derive_multicore_plan
from .pipeline_stages import build as pipeline_build
from evaluation_validation import read_bandwidth_config, read_capacity_config

SPACES = ("L1", "UB")


def partition(weights, setups, shared, local, capacities, stages, jobs):
    """Exact constrained cold-setup abstraction; None means no feasible split."""
    n, resources = len(weights), len(capacities)
    if (not n or len(setups) != n or len(shared) != n or len(local) != n
            or any(w <= 0 for w in weights) or any(q < 0 for q in setups)
            or not 1 <= stages <= n or type(jobs) is not int or jobs < 1
            or not resources or any(c < 0 for c in capacities)
            or any(len(row) != resources or any(b < 0 for b in row)
                   for rows in (shared, local) for row in rows)):
        raise ValueError("inconsistent positive work/nonnegative memory partition")
    work, cold, resident = [0], [0], [[0] * resources]
    for w, q, row in zip(weights, setups, shared):
        work.append(work[-1] + w)
        cold.append(cold[-1] + q)
        resident.append([a + b for a, b in zip(resident[-1], row)])
    dp = [[math.inf] * (n + 1) for _ in range(stages + 1)]
    parent = [[None] * (n + 1) for _ in range(stages + 1)]
    dp[0][0] = 0
    for s in range(1, stages + 1):
        for end in range(s, n + 1):
            maximum = [0] * resources
            best = (math.inf, n)
            for start in range(end - 1, s - 2, -1):
                maximum = [max(a, b) for a, b in zip(maximum, local[start])]
                if any(resident[end][r] - resident[start][r] + maximum[r] > capacities[r]
                       for r in range(resources)):
                    # Earlier starts only increase resident bytes and maxima.
                    break
                candidate = max(dp[s-1][start],
                                cold[end] + (jobs-1) * (work[end] - work[start]))
                if (candidate, start) < best:
                    best = candidate, start
            if math.isfinite(best[0]):
                dp[s][end], parent[s][end] = best
    if not math.isfinite(dp[stages][n]):
        return None
    cuts, end = [n], n
    for s in range(stages, 0, -1):
        end = parent[s][end]
        cuts.append(end)
    return list(reversed(cuts)), work[-1] + dp[stages][n]


def build(index, cores, bandwidth, capacity):
    if type(cores) is not int or not 1 <= cores <= 5 or bandwidth <= 0:
        raise ValueError("official cores 1..5 and positive bandwidth required")
    capacities = [capacity[s] for s in SPACES]
    if any(type(c) is not int or c < 0 for c in capacities):
        raise ValueError("nonnegative integer L1/UB capacities required")
    jobs, views = index.components, stage_structure(index)
    reason = None
    if (views is None or len(jobs[0]) > 512 or len(jobs) < cores
            or any(o["pipe"] not in ("PIPE_M", "PIPE_V") or
                   type(o["cycles"]) is not int or o["cycles"] <= 0
                   for o in index.ops.values())):
        reason = "homogeneous_positive_compute_guard"
    else:
        common, _, consumers = views
        positions = len(jobs[0])
        location = {u: pos for job in jobs for pos, u in enumerate(job)}
        tensors = {t["id"]: t for t in index.graph["tensors"]}
        by_position = [[] for _ in range(positions)]
        for tid in sorted(common):
            used = {location[u] for u in consumers[tid] if u in location}
            if len(used) != 1:
                reason = "shared_input_reused_at_multiple_positions"
                break
            by_position[next(iter(used))].append(tid)
        if any(t["pos"] not in (*SPACES, "DDR") for t in tensors.values()):
            reason = "unsupported_tensor_memory_space"
        elif any(tensors[t]["pos"] == "DDR" for t in common):
            # E0 materializes a compute-facing DDR tensor in local UB. Counting
            # its raw DDR bytes as zero would understate shared residence.
            reason = "shared_ddr_input_requires_ub_materialization_model"
    if reason is not None:
        plan, meta = pipeline_build(index, cores, bandwidth)
        return plan, dict(guard=False, selected="pipeline_fallback", reason=reason, fallback=meta)

    incident = {u: set() for u in index.ops}
    for edge in index.graph["edges"]:
        a, b = edge["source"], edge["target"]
        if a in incident and b in tensors and b not in common:
            incident[a].add(b)
        if b in incident and a in tensors and a not in common:
            incident[b].add(a)
    shared = [[sum(index.sizes[t] for t in ts if tensors[t]["pos"] == space)
               for space in SPACES] for ts in by_position]
    local = [[max(sum(index.sizes[t] for t in incident[job[p]]
                      if tensors[t]["pos"] == space) for job in jobs)
              for space in SPACES] for p in range(positions)]
    weights = [index.duration(u) for u in jobs[0]]
    setup = [sum(math.ceil(index.sizes[t] / bandwidth) for t in ts) for ts in by_position]
    stages = min(cores, positions)
    answer = partition(weights, setup, shared, local, capacities, stages, len(jobs))
    if answer is None:
        plan, meta = pipeline_build(index, cores, bandwidth)
        return plan, dict(guard=False, selected="pipeline_fallback",
                          reason="no_partition_fits_shared_residence_model", fallback=meta)
    cuts, modeled = answer
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules = [[mapping[str(u)] for job in jobs for u in job[left:right]]
                 for left, right in zip(cuts, cuts[1:])]
    schedules.extend([] for _ in range(cores-stages))
    plan = dict(node_to_subgraph=mapping, core_schedules=schedules)
    derive_multicore_plan(index.graph, plan)
    rows = []
    for left, right in zip(cuts, cuts[1:]):
        resident = [sum(row[r] for row in shared[left:right]) for r in range(len(SPACES))]
        scratch = [max(row[r] for row in local[left:right]) for r in range(len(SPACES))]
        rows.append(dict(shared_input_bytes=dict(zip(SPACES, resident)),
                         single_op_noncommon_bytes=dict(zip(SPACES, scratch)),
                         modeled_required_bytes=dict(zip(SPACES, [a+b for a, b in zip(resident, scratch)]))))
    return plan, dict(guard=True, selected="pipeline_capacity", requested_cores=cores,
        active_cores=stages, jobs=len(jobs), positions=positions, cuts=cuts,
        stage_compute_cycles=[sum(weights[l:r]) for l, r in zip(cuts, cuts[1:])],
        stage_first_job_setup_cycles=[sum(setup[l:r]) for l, r in zip(cuts, cuts[1:])],
        modeled_cold_flowshop_cycles=modeled, capacity=capacity, stage_memory=rows,
        assumption="serial stage cold-setup model with L1/UB shared-residence constraints; raw DDR COPY endpoints excluded; not an E0 bound or zero-spill certificate")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[2] /
                        "data/raw/a/official/data/config.txt")
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    index = SharingIndex(json.loads(args.graph.read_text(encoding="utf-8")))
    plan, metadata = build(index, args.cores, read_bandwidth_config(args.config),
                           read_capacity_config(args.config))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(metadata, sort_keys=True))


if __name__ == "__main__":
    main()
