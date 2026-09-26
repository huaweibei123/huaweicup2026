"""Guarded single-tail split with capacity-sized waves; no online E0."""
from __future__ import annotations

import argparse
import json
from math import ceil
from pathlib import Path

from .active_stages import build as active_build
from .construct import SharingIndex, derive_multicore_plan
from .wave_capacity import SPACES, model, structure
from evaluation_validation import read_bandwidth_config, read_capacity_config


def partition_tail(m_cycles, v_cycles, cores, full_jobs, boundary_bytes):
    """Two O(k L²) passes: minimax workload, then least cut bytes at that peak."""
    length = len(m_cycles)
    if not 2 <= cores <= length or len(v_cycles) != length or len(boundary_bytes) != length + 1:
        raise ValueError("invalid tail partition dimensions")
    pm, pv = [0], [0]
    for m, v in zip(m_cycles, v_cycles):
        pm.append(pm[-1] + m)
        pv.append(pv[-1] + v)
    base_m, base_v = full_jobs * pm[-1], full_jobs * pv[-1]
    peak = [[None] * (length + 1) for _ in range(cores + 1)]
    peak[0][0] = 0
    for j in range(1, cores + 1):
        for end in range(j, length - (cores - j) + 1):
            for start in range(j - 1, end):
                previous = peak[j - 1][start]
                if previous is None:
                    continue
                segment = max(base_m + pm[end] - pm[start],
                              base_v + pv[end] - pv[start])
                value = max(previous, segment)
                if peak[j][end] is None or value < peak[j][end]:
                    peak[j][end] = value
    threshold = peak[cores][length]
    best = [[None] * (length + 1) for _ in range(cores + 1)]
    parent = [[None] * (length + 1) for _ in range(cores + 1)]
    best[0][0] = 0
    for j in range(1, cores + 1):
        for end in range(j, length - (cores - j) + 1):
            for start in range(j - 1, end):
                previous = best[j - 1][start]
                if previous is None:
                    continue
                segment = max(base_m + pm[end] - pm[start],
                              base_v + pv[end] - pv[start])
                if segment > threshold:
                    continue
                value = previous + (boundary_bytes[start] if j > 1 else 0)
                if best[j][end] is None or value < best[j][end]:
                    best[j][end], parent[j][end] = value, start
    cuts, end = [length], length
    for j in range(cores, 0, -1):
        end = parent[j][end]
        cuts.append(end)
    cuts.reverse()
    return cuts, (threshold, best[cores][length])


def build(index, cores, bandwidth, capacity):
    def fallback(reason):
        plan, detail = active_build(index, cores, bandwidth)
        return plan, dict(guard=False, selected="active_fallback", reason=reason, fallback=detail)

    data, reason = structure(index, cores)
    if reason:
        return fallback(reason)
    jobs, length = data["jobs"], data["length"]
    if cores < 2 or len(jobs) % cores != 1 or length < cores:
        return fallback("single_tail_shape")
    q = len(jobs) // cores
    bmax, footprint = model(data, capacity, q + 1)
    if bmax is None:
        return fallback(footprint["reason"])
    if bmax < 2:
        return fallback("insufficient_wave_width")
    wave_count = ceil((q + 1) / bmax)
    if wave_count > q:
        return fallback("empty_full_job_wave")
    sizes = [q // wave_count + (i < q % wave_count) for i in range(wave_count)]
    if sizes[-1] + 1 > bmax:
        return fallback("tail_wave_over_capacity_proxy")

    template = jobs[0]
    m = [index.ops[u]["cycles"] if index.ops[u]["pipe"] == "PIPE_M" else 0 for u in template]
    v = [index.ops[u]["cycles"] if index.ops[u]["pipe"] == "PIPE_V" else 0 for u in template]
    boundary = [sum(footprint["frontier"][r][h] for r in range(len(SPACES)))
                for h in range(length + 1)]
    cuts, objective = partition_tail(m, v, cores, q, boundary)
    full_groups = [[jobs[j] for j in range(c, q * cores, cores)] for c in range(cores)]
    tail = jobs[-1]
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules = []
    for c, group in enumerate(full_groups):
        sequence, offset = [], 0
        for wave_no, size in enumerate(sizes):
            wave = group[offset:offset + size]
            offset += size
            for p in range(length):
                position_ops = [job[p] for job in wave]
                if wave_no == wave_count - 1 and cuts[c] <= p < cuts[c + 1]:
                    position_ops.append(tail[p])
                sequence.extend(mapping[str(u)] for u in position_ops)
        schedules.append(sequence)
    plan = dict(node_to_subgraph=mapping, core_schedules=schedules)
    derive_multicore_plan(index.graph, plan)
    pm, pv = [0], [0]
    for mc, vc in zip(m, v):
        pm.append(pm[-1] + mc)
        pv.append(pv[-1] + vc)
    workload = [dict(M=q * pm[-1] + pm[cuts[c + 1]] - pm[cuts[c]],
                     V=q * pv[-1] + pv[cuts[c + 1]] - pv[cuts[c]])
                for c in range(cores)]
    return plan, dict(guard=True, selected="wave_tail", active_cores=cores,
                      jobs=len(jobs), positions=length, full_jobs_per_core=q,
                      full_job_ids_by_core=[[c + i * cores for i in range(q)] for c in range(cores)],
                      tail_job_id=len(jobs) - 1, cuts=cuts,
                      tail_owner_intervals=[[cuts[c], cuts[c + 1]] for c in range(cores)],
                      bmax=bmax, wave_count=wave_count, full_job_wave_sizes=sizes,
                      final_wave_tail_occupancy=sizes[-1] + 1,
                      per_core_compute_work_cycles=workload,
                      minimax_compute_work_cycles=objective[0],
                      boundary_proxy_bytes=objective[1],
                      W=dict(zip(SPACES, data["weights"])),
                      A=dict(zip(SPACES, footprint["active"])),
                      F=dict(zip(SPACES, footprint["frontier"])),
                      capacity=dict(capacity), internal_e0_calls=0,
                      assumption="Compute workload and capacity envelope are proxies; no unconditional shared-read, DDR, or Makespan bound")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[2] / "data/raw/a/official/data/config.txt")
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    index = SharingIndex(graph)
    plan, meta = build(index, args.cores, read_bandwidth_config(args.config), read_capacity_config(args.config))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(meta, sort_keys=True))


if __name__ == "__main__":
    main()
