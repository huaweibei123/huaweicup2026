"""P1 direct split-chain template for guarded homogeneous fork/join stages.

Model-R idea: archived Pro message 4f80a045, section 4.2. This implementation
reads actual graph structure; it never chooses by filename or stored scores.
It preserves the Stage C constructor for graphs outside the exact guard.
Real DDR/FIFO/memory costs are NOT represented by the model certificate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from construct import OFFICIAL, _build_op_adjacency, _contract_excluded_copy_nodes, topo
from fork_frontier import stage_units, construct as fallback_construct
from diagnose import lower_bounds, read_scene_a_config
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


def guarded_stages(graph):
    ops, units, _, _, stages = stage_units(graph, 5, 4)
    full_pred, full_succ = _build_op_adjacency(graph)
    pred = {u: full_pred[u] & ops.keys() for u in ops}
    succ = {u: full_succ[u] & ops.keys() for u in ops}
    c_pred, c_succ = _contract_excluded_copy_nodes(sorted(ops), full_succ)
    if pred != c_pred or succ != c_succ:
        return None, "COPY-contracted and retained compute dependencies differ"
    previous, result, parameters = None, [], None
    for stage, entry in stages.items():
        if len(entry["frontier"]) != 12 or entry["tail"] is None:
            return None, "require twelve serial frontier chains and one reduction tail"
        chains = [topo(units[g]["nodes"], {u: succ[u] & set(units[g]["nodes"])
                                         for u in units[g]["nodes"]}) for g in sorted(entry["frontier"])]
        tail = set(units[entry["tail"]]["nodes"])
        if len(tail) != 11 or any(len(chain) != 4 for chain in chains):
            return None, "require four operations per chain and eleven reductions"
        heavy = {u for chain in chains for u in chain}
        costs_h = {(ops[u]["pipe"], max(1, ops[u]["cycles"])) for u in heavy}
        costs_t = {(ops[u]["pipe"], max(1, ops[u]["cycles"])) for u in tail}
        if len(costs_h) != 1 or len(costs_t) != 1:
            return None, "require homogeneous chain and reduction durations"
        ph, pt = next(iter(costs_h)), next(iter(costs_t))
        if ph[0] != "PIPE_V" or pt[0] != "PIPE_V":
            return None, "single PIPE_V model required"
        if parameters is None:
            parameters = (ph[1], pt[1])
        elif parameters != (ph[1], pt[1]):
            return None, "round durations differ"
        for chain in chains:
            for index, u in enumerate(chain):
                expected = {chain[index - 1]} if index else ({previous} if previous is not None else set())
                if pred[u] != expected:
                    return None, "unexpected retained predecessor of chain operation"
                if index < 3 and succ[u] != {chain[index + 1]}:
                    return None, "chain has a branch before its last operation"
            if len(succ[chain[-1]]) != 1 or not succ[chain[-1]] <= tail:
                return None, "each heavy leaf must enter exactly one reduction"
        roots = [u for u in tail if not succ[u] & tail]
        if len(roots) != 1:
            return None, "reduction does not have one root"
        root = roots[0]
        for u in tail:
            if len(pred[u]) != 2 or not pred[u] <= heavy | tail:
                return None, "reduction is not a binary tree over the heavy leaves"
            if u != root and (len(succ[u]) != 1 or not succ[u] <= tail):
                return None, "internal reduction branches or leaves its stage"
        if previous is not None and succ[previous] != {chain[0] for chain in chains}:
            return None, "previous root does not fork to exactly this round"
        result.append({"stage": stage, "chains": chains, "tail": sorted(tail), "root": root})
        previous = root
    if not result or succ[previous]:
        return None, "missing complete fork/join rounds or trailing operations"
    return {"rounds": result, "heavy_cycles": parameters[0], "add_cycles": parameters[1]}, "guard passed"


def construct(graph, cores, waits):
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("cores must be an integer in 1..5")
    if cores != 5:
        plan, info = fallback_construct(graph, cores, same_wait=waits["task_same_core_wait_cycles"],
                                        cross_wait=waits["task_cross_core_wait_cycles"])
        return plan, {"selected": "fork-fallback", "reason": "five-core template only", "fallback": info}
    guarded, reason = guarded_stages(graph)
    if guarded is None:
        plan, info = fallback_construct(graph, cores, same_wait=waits["task_same_core_wait_cycles"],
                                        cross_wait=waits["task_cross_core_wait_cycles"])
        return plan, {"selected": "fork-fallback", "reason": reason, "fallback": info}
    mapping, orders, tasks = {}, [[] for _ in range(5)], []

    def add(core, nodes, stage, phase):
        task = len(tasks)
        for u in nodes:
            if u in mapping:
                raise AssertionError("duplicate compute assignment")
            mapping[u] = task
        orders[core].append(task)
        tasks.append({"id": task, "core": core, "stage": stage, "phase": phase, "ops": len(nodes)})

    for index, entry in enumerate(guarded["rounds"]):
        b, stage = entry["chains"], entry["stage"]
        if index == 0:
            first = [b[0] + b[1], b[2] + b[3], b[4] + b[5], b[10][:2], b[11][:2]]
            second = [b[10][2:], b[11][2:], [], b[6] + b[7], b[8] + b[9]]
        else:
            first = [b[0] + b[1], b[2] + b[3], b[8][:3] + b[9][:3], b[10][:1], b[11][:1]]
            second = [b[8][3:], b[9][3:], b[10][1:] + b[11][1:], b[4] + b[5], b[6] + b[7]]
        for phase, group in enumerate((first, second)):
            for core, nodes in enumerate(group):
                if nodes:
                    add(core, nodes, stage, phase)
        add(2, entry["tail"], stage, 2)
    plan = {"node_to_subgraph": {u: mapping[u] for u in sorted(mapping)}, "core_schedules": orders}
    view = derive_multicore_plan(graph, plan)
    validate_task_order(view)
    phases = {t["id"]: (t["stage"], t["phase"]) for t in tasks}
    edges = list(view["dependency_pairs"]) + [(a, b) for order in orders for a, b in zip(order, order[1:])]
    if any(phases[a] >= phases[b] for a, b in edges):
        raise AssertionError("joint Task edges must strictly advance stage/phase")
    model = lower_bounds(graph, plan, waits)
    return plan, {"algorithm_id": "q1-guarded-split-chain-star", "variant": "twelve-four-fixed-tail-v1",
                  "selected": "split-chain-star", "reason": reason,
                  "rounds": len(guarded["rounds"]), "heavy_cycles": guarded["heavy_cycles"],
                  "add_cycles": guarded["add_cycles"], "task_count": len(tasks), "tasks": tasks,
                  "model_r_cycles": model["task_gate_lower_bound_cycles"],
                  "scope": "Exact compute-and-Task-gate R timing because all compute uses one Pipe; no COPY/FIFO/memory performance claim. Final unchanged E0 required.",
                  "idea_source": "AI chats/P1-fork-join-yuanzhifang/20260924T163500Z-assistant-4f80a045.md section 4.2"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--config", type=Path, default=OFFICIAL / "data/config.txt")
    parser.add_argument("--diagnostics", type=Path)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_bytes())
    plan, info = construct(graph, args.cores, read_scene_a_config(str(args.config)))
    for path, obj in ((args.output, plan), (args.diagnostics, info)):
        if path:
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(obj, handle, separators=(",", ":")); handle.write("\n")


if __name__ == "__main__":
    main()
