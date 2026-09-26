"""Two structural P1 constructions, selected without a simulator or case IDs.

The selector adds the fixed-plan compute/Task-gate lower bound and mandatory
boundary DDR service. This conservative overlap heuristic is NOT itself a
lower/upper bound or an E0 prediction. The exact two candidates and tie rule
are fixed; there is no parameter sweep, training, or stored plan lookup.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

from construct import OFFICIAL
from diagnose import lower_bounds, read_scene_a_config
from fork_frontier import construct as fork_construct
from upstream_bounded.bounded_tasks import construct as bounded_construct
from evaluation_validation import read_bandwidth_config


def boundary_cost(graph, plan, bandwidth):
    """Count mandatory COPYs exactly as E0 Task reconstruction, before spills.

    Each tensor is considered once, using sets of producer/consumer Tasks.
    Different output producer Tasks each emit their own boundary copy. A Task
    with a local producer does not acquire an input COPY for that tensor.
    Direct op edges are gates but carry no tensor bytes.
    """
    if type(bandwidth) is not int or bandwidth <= 0:
        raise ValueError("Positive integer DDR bandwidth required")
    mapping = {int(u): t for u, t in plan["node_to_subgraph"].items()}
    all_ops = {o["id"]: o for o in graph["ops"]}
    producers, consumers = defaultdict(set), defaultdict(set)
    for edge in graph["edges"]:
        u, v = edge["source"], edge["target"]
        if u in all_ops and v not in all_ops:
            producers[v].add(u)
        elif u not in all_ops and v in all_ops:
            consumers[u].add(v)
    service, size, count, by_task = 0, 0, 0, defaultdict(lambda: defaultdict(int))
    original_copy_bytes = 0
    sizes = {t["id"]: t["size"] for t in graph["tensors"]}
    for tensor, nbytes in sizes.items():
        ps = {mapping[u] for u in producers[tensor] if u in mapping}
        cs = {mapping[u] for u in consumers[tensor] if u in mapping}
        original_out = any(all_ops[u]["op"] == "COPY_OUT" for u in consumers[tensor])
        original_copy_bytes += nbytes * (sum(all_ops[u]["op"] == "COPY_IN" for u in producers[tensor])
                                         + sum(all_ops[u]["op"] == "COPY_OUT" for u in consumers[tensor]))
        duration = max(1, (nbytes + bandwidth - 1) // bandwidth)
        for task in cs - ps:
            by_task[task]["input_bytes"] += nbytes
            by_task[task]["input_service_cycles"] += duration
            size += nbytes; service += duration; count += 1
        for task in ps:
            if original_out or not cs or cs - {task}:
                by_task[task]["output_bytes"] += nbytes
                by_task[task]["output_service_cycles"] += duration
                size += nbytes; service += duration; count += 1
    return {"boundary_ddr_service_cycles": service, "boundary_copy_bytes": size,
            "boundary_copy_count": count, "original_copy_bytes": original_copy_bytes,
            "partition_added_copy_bytes": size - original_copy_bytes,
            "by_task": {t: dict(values) for t, values in sorted(by_task.items())},
            "scope": "Exact mandatory Task-boundary COPY count/service before spill; not total actual DDR or Makespan."}


def cost(graph, plan, waits, bandwidth):
    gate = lower_bounds(graph, plan, waits)
    boundary = boundary_cost(graph, plan, bandwidth)
    return {"serialized_resource_proxy_cycles": gate["task_gate_lower_bound_cycles"]
            + boundary["boundary_ddr_service_cycles"],
            "gate": gate, "boundary": boundary}


def construct(graph, cores, waits, bandwidth):
    # The original captain implementation is pinned and attributed. Its plan
    # insertion order is preserved, enabling exact-byte identity checks.
    baseline, base_info = bounded_construct(graph, cores, packet_factor=4,
                                            trigger_ops=4096, chunk_ops=1024)
    info = {"algorithm_id": "q1-two-structure-ddr-selector",
            "variant": "bounded-or-fork-gate-plus-ddr-v1",
            "candidate_count": 1, "selected": "bounded",
            "scope": "Two direct structural constructions; no E0/E1/E2 or local Task compilation. Selection heuristic has no dominance guarantee."}
    if cores == 1:
        info.update(reason="one core: preserve pinned bounded baseline", bounded=base_info)
        return baseline, info
    fork, fork_info = fork_construct(graph, cores, grain=4,
                                    same_wait=waits["task_same_core_wait_cycles"],
                                    cross_wait=waits["task_cross_core_wait_cycles"], frontier_tasks="core")
    base_cost, fork_cost = cost(graph, baseline, waits, bandwidth), cost(graph, fork, waits, bandwidth)
    # Same units (cycles), coefficient exactly one. Prefer the pinned baseline
    # on a tie. This is intentionally not a fit to exposed evaluation scores.
    select_fork = fork_cost["serialized_resource_proxy_cycles"] < base_cost["serialized_resource_proxy_cycles"]
    info.update(candidate_count=2, selected="fork" if select_fork else "bounded",
                costs={"bounded": base_cost, "fork": fork_cost},
                bounded=base_info, fork=fork_info,
                reason="strictly smaller compute/gate plus mandatory-DDR proxy; ties retain bounded")
    return (fork if select_fork else baseline), info


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("graph", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--cores", type=int, required=True)
    p.add_argument("--config", type=Path, default=OFFICIAL / "data/config.txt")
    p.add_argument("--diagnostics", type=Path)
    args = p.parse_args()
    waits = read_scene_a_config(str(args.config))
    bandwidth = read_bandwidth_config(str(args.config))
    graph = json.loads(args.graph.read_bytes())
    plan, info = construct(graph, args.cores, waits, bandwidth)
    for path, value in ((args.output, plan), (args.diagnostics, info)):
        if path:
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(value, handle, separators=(",", ":"))
                handle.write("\n")


if __name__ == "__main__":
    main()
