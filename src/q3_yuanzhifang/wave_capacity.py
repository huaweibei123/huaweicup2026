"""Guarded complete-job, capacity-sized waves; no online evaluation."""
from __future__ import annotations

import argparse
import json
from math import ceil
from pathlib import Path

from .active_stages import build as active_build
from .construct import SharingIndex, derive_multicore_plan
from evaluation_validation import read_bandwidth_config, read_capacity_config

SPACES = ("L1", "UB")


def structure(index, cores):
    """Return one template's complete tensor lifetimes, or a guard reason."""
    jobs = index.components
    if not 1 <= cores <= 5 or len(jobs) < cores or not jobs:
        return None, "jobs_or_cores"
    length = len(jobs[0])
    if not length or any(len(job) != length for job in jobs):
        return None, "job_length_mismatch"
    position = {u: (j, p) for j, job in enumerate(jobs) for p, u in enumerate(job)}
    for job in jobs:
        if any(v not in index.succ[u] for u, v in zip(job, job[1:])):
            return None, "nonserial_job"
    for p in range(length):
        template = tuple(index.ops[jobs[0][p]][key] for key in ("op", "pipe", "cycles"))
        if (template[1] not in ("PIPE_M", "PIPE_V") or type(template[2]) is not int or template[2] <= 0 or
                any(tuple(index.ops[job[p]][key] for key in ("op", "pipe", "cycles")) != template
                    for job in jobs[1:])):
            return None, "compute_template_mismatch"
    for u in position:
        if any(v in position and position[v][0] != position[u][0] for v in index.succ[u]):
            return None, "interjob_compute_dependency"
    edge_signatures = [{(position[u][1], position[v][1]) for u in job
                        for v in index.succ[u] if v in position and position[v][0] == j}
                       for j, job in enumerate(jobs)]
    if any(edges != edge_signatures[0] for edges in edge_signatures[1:]):
        return None, "compute_dependency_template_mismatch"

    graph = index.graph
    ops = {o["id"]: o for o in graph["ops"]}
    tensors = {t["id"]: t for t in graph["tensors"]}
    inbound, outbound = {t: [] for t in tensors}, {t: [] for t in tensors}
    raw_inputs = {u: [] for u in ops}
    for edge in graph["edges"]:
        a, b = edge["source"], edge["target"]
        if b in raw_inputs:
            raw_inputs[b].append(a)
        if a in tensors and b in ops:
            outbound[a].append(b)
        elif a in ops and b in tensors:
            inbound[b].append(a)
    weights = [[0] * length for _ in SPACES]
    private_signatures = [[] for _ in jobs]
    private_lifetimes = [[] for _ in jobs]
    common = set(index.inputs[0]).intersection(*index.inputs[1:])
    if not common:
        return None, "no_common_input"
    for tid, tensor in tensors.items():
        space, size = tensor["pos"], tensor["size"]
        if space not in (*SPACES, "DDR"):
            return None, "unknown_tensor_space"
        producers = [position[u] for u in inbound[tid] if u in position]
        consumers = [position[u] for u in outbound[tid] if u in position]
        copy_producers = tuple(sorted((ops[u]["op"], ops[u]["pipe"], ops[u]["cycles"])
                                      for u in inbound[tid] if u in ops and u not in position))
        copy_consumers = tuple(sorted((ops[u]["op"], ops[u]["pipe"], ops[u]["cycles"])
                                      for u in outbound[tid] if u in ops and u not in position))
        if not producers and not consumers:
            if space != "DDR":
                return None, "unattached_private_tensor"
            continue  # raw backing at an original COPY endpoint
        if space == "DDR":
            return None, "direct_compute_ddr"
        if tid in common:
            if producers or len(consumers) != len(jobs) or len({j for j, _ in consumers}) != len(jobs) or len({p for _, p in consumers}) != 1:
                return None, "common_input_consumers"
            if copy_consumers or len(copy_producers) > 1:
                return None, "common_input_copy_semantics"
            if copy_producers:
                copy_id = next(u for u in inbound[tid] if u in ops and u not in position)
                copy = ops[copy_id]
                sources = raw_inputs[copy_id]
                if (copy["op"] != "COPY_IN" or copy["pipe"] != "PIPE_MTE2" or
                        len(sources) != 1 or sources[0] not in tensors or
                        tensors[sources[0]]["pos"] != "DDR" or inbound[sources[0]] or
                        outbound[sources[0]] != [copy_id]):
                    return None, "common_input_copy_semantics"
            weights[SPACES.index(space)][consumers[0][1]] += size
            continue
        owners = {j for j, _ in producers + consumers}
        if len(owners) != 1:
            return None, "shared_writable_or_partial_input"
        owner = next(iter(owners))
        pp = tuple(sorted(p for _, p in producers))
        cp = tuple(sorted(p for _, p in consumers))
        if len(pp) > 1:
            return None, "multiple_private_compute_producers"
        if (not pp and (cp != (0,) or copy_consumers)) or (not cp and (pp != (length-1,) or copy_producers)):
            return None, "private_endpoint_position"
        if pp and cp and max(pp) > min(cp):
            return None, "private_producer_after_consumer"
        incident = pp + cp
        first, last = min(incident), max(incident)
        signature = (space, size, pp, cp, copy_producers, copy_consumers)
        private_signatures[owner].append(signature)
        private_lifetimes[owner].append((space, size, first, last))
    signature = sorted(private_signatures[0])
    if any(sorted(s) != signature for s in private_signatures[1:]):
        return None, "private_tensor_template_mismatch"
    return dict(jobs=jobs, length=length, weights=weights,
                lifetimes=private_lifetimes[0], common=common), None


def model(data, capacity, largest_group):
    length = data["length"]
    frontier_delta = [[0] * (length+2) for _ in SPACES]
    active_delta = [[0] * (length+1) for _ in SPACES]
    for space, size, first, last in data["lifetimes"]:
        r = SPACES.index(space)
        frontier_delta[r][first+1] += size
        frontier_delta[r][last+1] -= size
        active_delta[r][first] += size
        active_delta[r][last+1] -= size
    frontier = [[0] * (length+1) for _ in SPACES]
    active = [[0] * length for _ in SPACES]
    for r in range(len(SPACES)):
        running = 0
        for h in range(length+1):
            running += frontier_delta[r][h]
            frontier[r][h] = running
        running = 0
        for p in range(length):
            running += active_delta[r][p]
            active[r][p] = running
    bmax = largest_group
    for r, space in enumerate(SPACES):
        if type(capacity.get(space)) is not int or capacity[space] < 0:
            raise ValueError("invalid configured capacity: " + space)
        for p in range(length):
            headroom = capacity[space] - data["weights"][r][p] - active[r][p]
            if headroom < 0:
                return None, dict(frontier=frontier, active=active, reason="single_job_footprint_exceeds_capacity")
            demand = max(frontier[r][p], frontier[r][p+1])
            if demand:
                bmax = min(bmax, 1 + headroom // demand)
    return bmax, dict(frontier=frontier, active=active)


def build(index, cores, bandwidth, capacity, mode="capacity"):
    if mode not in ("capacity", "full"):
        raise ValueError("mode must be capacity or full")
    data, reason = structure(index, cores)
    if reason:
        plan, fallback = active_build(index, cores, bandwidth)
        return plan, dict(guard=False, selected="active_fallback", reason=reason, fallback=fallback)
    jobs, length = data["jobs"], data["length"]
    groups = [jobs[c::cores] for c in range(cores)]
    largest = max(map(len, groups))
    bmax, footprint = model(data, capacity, largest)
    if bmax is None:
        plan, fallback = active_build(index, cores, bandwidth)
        return plan, dict(guard=False, selected="active_fallback", reason=footprint["reason"], fallback=fallback)
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules, wave_sizes = [], []
    for group in groups:
        n = len(group)
        count = 1 if mode == "full" else ceil(n / bmax)
        sizes = [n // count + (i < n % count) for i in range(count)]
        wave_sizes.append(sizes)
        sequence, offset = [], 0
        for size in sizes:
            wave = group[offset:offset+size]
            offset += size
            for p in range(length):
                sequence.extend(mapping[str(job[p])] for job in wave)
        schedules.append(sequence)
    plan = dict(node_to_subgraph=mapping, core_schedules=schedules)
    derive_multicore_plan(index.graph, plan)
    shared_bytes = sum(map(sum, data["weights"]))
    full_fit = all(data["weights"][r][p] + footprint["active"][r][p] +
                   (len(group)-1) * max(footprint["frontier"][r][p], footprint["frontier"][r][p+1]) <= capacity[space]
                   for group in groups for r, space in enumerate(SPACES) for p in range(length))
    return plan, dict(guard=True, selected="wave_capacity", mode=mode, requested_cores=cores,
        active_cores=cores, jobs=len(jobs), positions=length, bmax=bmax, wave_sizes=wave_sizes,
        W=dict(zip(SPACES, data["weights"])), A=dict(zip(SPACES, footprint["active"])),
        F=dict(zip(SPACES, footprint["frontier"])), capacity=dict(capacity),
        shared_weight_bytes=shared_bytes,
        conditional_shared_read_bound_bytes=shared_bytes * sum(map(len, wave_sizes)),
        shared_L1_exceeds_k_capacity=sum(data["weights"][0]) > cores * capacity["L1"],
        modeled_full_wave_fit=full_fit,
        assumption="Static working-set envelope and conditional shared-read bound; neither zero-spill nor E0 Makespan bound")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[2] / "data/raw/a/official/data/config.txt")
    parser.add_argument("--mode", choices=("capacity", "full"), default="capacity")
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    index = SharingIndex(graph)
    plan, meta = build(index, args.cores, read_bandwidth_config(args.config), read_capacity_config(args.config), args.mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(meta, sort_keys=True))


if __name__ == "__main__":
    main()
