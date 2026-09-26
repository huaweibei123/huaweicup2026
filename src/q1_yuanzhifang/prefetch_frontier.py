"""Guarded intact-chain packing with a fixed, early-released root core.

Stage G hypothesis: move more *whole* chains onto the previous root's core,
which may activate earlier. This preserves large internal tensors, but its
benefit under the official processor-sharing DDR remains an E0 hypothesis.
No scoring, Task compiler, stored cases or measured-result table is used.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from construct import OFFICIAL, _build_op_adjacency, topo
from diagnose import lower_bounds, read_scene_a_config
from fork_frontier import construct as fallback_construct
from star_frontier import guarded_stages
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


def construct(graph, cores, waits, *, startup_cores=5, fuse_reductions=False):
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("cores must be an integer in 1..5")
    if type(startup_cores) is not int or startup_cores not in (4, 5):
        raise ValueError("startup_cores must be 4 or 5")
    if type(fuse_reductions) is not bool:
        raise ValueError("fuse_reductions must be a boolean")
    guarded, reason = (guarded_stages(graph) if cores == 5
                       else (None, "five-core template only"))
    if guarded is None:
        plan, info = fallback_construct(
            graph, cores, same_wait=waits["task_same_core_wait_cycles"],
            cross_wait=waits["task_cross_core_wait_cycles"])
        return plan, {"selected": "fork-fallback", "reason": reason, "fallback": info}

    mapping, orders, tasks = {}, [[] for _ in range(5)], []
    full_pred, full_succ = _build_op_adjacency(graph) if fuse_reductions else ({}, {})

    def add(core, nodes, stage, phase, chains, fused=0):
        task = len(tasks)
        for u in nodes:
            if u in mapping:
                raise AssertionError("duplicate compute assignment")
            mapping[u] = task
        orders[core].append(task)
        tasks.append({"id": task, "core": core, "stage": stage, "phase": phase,
                      "ops": len(nodes), "intact_chains": chains, "fused_reductions": fused})

    for index, entry in enumerate(guarded["rounds"]):
        branches = entry["chains"]
        first = (3, 3, 3, 3, 0) if startup_cores == 4 else (3, 3, 2, 2, 2)
        counts = first if index == 0 else (4, 2, 2, 2, 2)
        tail = set(entry["tail"])
        tail_order = topo(tail, {u: full_succ[u] & tail for u in tail}) if fuse_reductions else []
        fused_all = set()
        offset = 0
        for core, count in enumerate(counts):
            chosen = branches[offset:offset + count]
            offset += count
            if not count:
                continue
            nodes = [u for chain in chosen for u in chain]
            members = set(nodes)
            fused = []
            # Topological closure only adds an entire reduction subtree whose
            # inputs already belong to this one frontier Task. Thus this Task
            # never gains a dependency on another frontier in the same phase.
            for u in tail_order:
                if full_pred[u] <= members:
                    nodes.append(u)
                    members.add(u)
                    fused.append(u)
            if fused_all.intersection(fused):
                raise AssertionError("reduction assigned to more than one frontier")
            fused_all.update(fused)
            add(core, nodes, entry["stage"], 0, count, len(fused))
        assert offset == len(branches)
        remaining = sorted(tail - fused_all)
        if not remaining or entry["root"] not in remaining:
            raise AssertionError("distributed frontier must retain its common root tail")
        add(0, remaining, entry["stage"], 1, 0)

    plan = {"node_to_subgraph": {u: mapping[u] for u in sorted(mapping)},
            "core_schedules": orders}
    view = derive_multicore_plan(graph, plan)
    validate_task_order(view)
    rank = {t["id"]: (t["stage"], t["phase"]) for t in tasks}
    edges = list(view["dependency_pairs"]) + [(a, b) for seq in orders for a, b in zip(seq, seq[1:])]
    if any(rank[a] >= rank[b] for a, b in edges):
        raise AssertionError("joint Task edges must strictly advance stage/phase")
    for entry in guarded["rounds"]:
        for chain in entry["chains"]:
            if len({mapping[u] for u in chain}) != 1:
                raise AssertionError("chain was split")
    model = lower_bounds(graph, plan, waits)
    variant = ("four-core-start" if startup_cores == 4 else "fixed-root-four-two")
    variant += "-subtrees-v1" if fuse_reductions else "-v1"
    return plan, {"algorithm_id": "q1-guarded-intact-prefetch",
                  "variant": variant, "selected": "intact-prefetch-frontier",
                  "reason": reason, "rounds": len(guarded["rounds"]),
                  "heavy_cycles": guarded["heavy_cycles"], "add_cycles": guarded["add_cycles"],
                  "task_count": len(tasks), "tasks": tasks, "tail_core": 0,
                  "first_chain_counts": list(first), "later_chain_counts": [4, 2, 2, 2, 2],
                  "fuse_reductions": fuse_reductions,
                  "fused_reduction_count": sum(t["fused_reductions"] for t in tasks),
                  "model_r_cycles": model["task_gate_lower_bound_cycles"],
                  "scope": "Fixed intact-chain structure; R omits all COPY/FIFO/memory costs. Official E0 must test the prefetch hypothesis; no general improvement claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--config", type=Path, default=OFFICIAL / "data/config.txt")
    parser.add_argument("--diagnostics", type=Path)
    parser.add_argument("--startup-cores", type=int, choices=(4, 5), default=5)
    parser.add_argument("--fuse-reductions", action="store_true")
    args = parser.parse_args()
    plan, info = construct(json.loads(args.graph.read_bytes()), args.cores,
                           read_scene_a_config(str(args.config)), startup_cores=args.startup_cores,
                           fuse_reductions=args.fuse_reductions)
    for path, value in ((args.output, plan), (args.diagnostics, info)):
        if path:
            with path.open("x", encoding="utf-8", newline="\n") as out:
                json.dump(value, out, separators=(",", ":"))
                out.write("\n")


if __name__ == "__main__":
    main()
