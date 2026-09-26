"""P1 fork stages with in-tree subtree frontiers and a shared reduction tail.

Stage rank increases after every fork. Each induced stage therefore has
outdegree at most one. Contract its serial chains, peel oversized root packets
into a tail, and pack the remaining disjoint subtrees across cores. Structural
proof and limitations are in docs/a/q1-yuanzhifang/FORK_FRONTIER.md.
No local Task compiler or E0/E1/E2 scoring is called during construction.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import heapq
import json
from pathlib import Path

from construct import OFFICIAL, topo, _build_op_adjacency, _contract_excluded_copy_nodes
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order
from multicore_cut_evaluate_problem_1 import read_scene_a_config


def add_work(target, source):
    for pipe, cost in source.items():
        target[pipe] = target.get(pipe, 0) + cost


def stage_units(graph, cores, grain):
    ops = {o["id"]: o for o in graph["ops"] if o["op"] not in {"COPY_IN", "COPY_OUT"}}
    _, full = _build_op_adjacency(graph)
    pred, succ = _contract_excluded_copy_nodes(sorted(ops), full)
    order = topo(ops, succ)
    rank = {}
    for u in order:
        rank[u] = max((rank[p] + int(len(succ[p]) > 1) for p in pred[u]), default=0)
    local_pred = {u: {p for p in pred[u] if rank[p] == rank[u]} for u in ops}
    local_succ = {u: {v for v in succ[u] if rank[v] == rank[u]} for u in ops}
    if any(len(v) > 1 for v in local_succ.values()):
        raise AssertionError("Fork rank failed to produce in-tree forests")
    parent = {u: u for u in ops}

    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u

    for u in order:
        for v in local_succ[u]:
            if len(local_pred[v]) == 1:
                a, b = find(u), find(v)
                parent[max(a, b)] = min(a, b)
    chains = defaultdict(list)
    for u in order:
        chains[find(u)].append(u)
    cpred = {g: set() for g in chains}
    csucc = {g: set() for g in chains}
    work = {}
    for g, nodes in chains.items():
        work[g] = {}
        for u in nodes:
            add_work(work[g], {ops[u]["pipe"]: max(1, ops[u]["cycles"])})
            for v in local_succ[u]:
                h = find(v)
                if h != g:
                    csucc[g].add(h)
                    cpred[h].add(g)
    chain_order = topo(chains, csucc)
    subtree_work = {}
    stages = defaultdict(list)
    totals = defaultdict(dict)
    for g in chain_order:
        stage = rank[g]
        stages[stage].append(g)
        add_work(totals[stage], work[g])
        subtree_work[g] = dict(work[g])
        for p in cpred[g]:
            add_work(subtree_work[g], subtree_work[p])
    units, by_stage = {}, {}
    for stage in sorted(stages):
        roots = [g for g in stages[stage] if not csucc[g]]
        threshold = max(1, (max(totals[stage].values()) + cores * grain - 1) // (cores * grain))
        queue = [(-max(subtree_work[g].values()), g) for g in roots]
        heapq.heapify(queue)
        frontier, tail = [], []
        while queue:
            neg_cost, g = heapq.heappop(queue)
            if -neg_cost > threshold and cpred[g]:
                tail.extend(chains[g])
                for p in sorted(cpred[g]):
                    heapq.heappush(queue, (-max(subtree_work[p].values()), p))
            else:
                frontier.append(g)
        for root in frontier:
            nodes, stack = [], [root]
            while stack:
                g = stack.pop()
                nodes.extend(chains[g])
                stack.extend(sorted(cpred[g], reverse=True))
            units[root] = {"nodes": nodes, "work": subtree_work[root], "stage": stage, "phase": 0}
        tail_id = None
        if tail:
            tail_id, tail_work = min(tail), {}
            for u in tail:
                add_work(tail_work, {ops[u]["pipe"]: max(1, ops[u]["cycles"])})
            if tail_id in units:
                raise AssertionError("Tail/frontier node sets overlap")
            units[tail_id] = {"nodes": tail, "work": tail_work, "stage": stage, "phase": 1}
        by_stage[stage] = {"frontier": frontier, "tail": tail_id, "threshold": threshold}
    unit_of = {u: g for g, item in units.items() for u in item["nodes"]}
    if len(unit_of) != len(ops) or sum(len(x["nodes"]) for x in units.values()) != len(ops):
        raise AssertionError("Each original compute op must occur exactly once")
    upred = {g: set() for g in units}
    for u in order:
        for v in succ[u]:
            a, b = unit_of[u], unit_of[v]
            if a != b:
                upred[b].add(a)
                if (units[a]["stage"], units[a]["phase"]) >= (units[b]["stage"], units[b]["phase"]):
                    raise AssertionError("Unit dependency violates stage/phase order")
    return ops, units, unit_of, upred, by_stage


def construct(graph, cores, grain=4, same_wait=100, cross_wait=1000, frontier_tasks="core"):
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("cores must be an integer in 1..5")
    if type(grain) is not int or grain < 1:
        raise ValueError("grain must be a positive integer")
    if frontier_tasks not in {"core", "unit"}:
        raise ValueError("frontier_tasks must be core or unit")
    ops, units, unit_of, upred, stages = stage_units(graph, cores, grain)
    sizes = {t["id"]: t["size"] for t in graph["tensors"]}
    producers, consumers = defaultdict(set), defaultdict(set)
    for e in graph["edges"]:
        a, b = e["source"], e["target"]
        if a in ops and b in sizes:
            producers[b].add(unit_of[a])
        elif a in sizes and b in ops:
            consumers[a].add(unit_of[b])
    inputs = defaultdict(set)
    for tensor, users in consumers.items():
        for g in users - producers[tensor]:
            inputs[g].add(tensor)
    schedules, mapping = [[] for _ in range(cores)], {}
    core_end = [0] * cores
    unit_core, unit_end, tasks = {}, {}, []

    def estimate(core, members, loads):
        start = core_end[core] + (same_wait if schedules[core] else 0)
        for g in members:
            for p in upred[g]:
                # Distinct units in the same phase are an antichain. Every
                # upstream unit is already scheduled, never another member.
                start = max(start, unit_end[p] + (cross_wait if unit_core[p] != core else 0))
        return start + max(loads.values(), default=0)

    def append_task(core, members, loads, stage, phase):
        task = len(tasks)
        end = estimate(core, members, loads)
        nodes = [u for g in members for u in units[g]["nodes"]]
        for g in members:
            unit_core[g], unit_end[g] = core, end
        for u in nodes:
            mapping[u] = task
        schedules[core].append(task)
        core_end[core] = end
        tasks.append({"task": task, "core": core, "stage": stage, "phase": phase,
                      "units": len(members), "ops": len(nodes), "estimated_finish": end})

    for stage, data in stages.items():
        bins, loads, shared = [[] for _ in range(cores)], [{} for _ in range(cores)], [set() for _ in range(cores)]
        bin_release = [core_end[k] + (same_wait if schedules[k] else 0) for k in range(cores)]
        frontier = sorted(data["frontier"], key=lambda g: (-max(units[g]["work"].values()), -sum(units[g]["work"].values()), g))
        if frontier_tasks == "unit":
            # One complete independent subtree per Task. This deliberately
            # changes boundary/readiness granularity, never splits a chain,
            # and keeps the whole reduction tail as one later Task. The same
            # stage/phase proof applies; it does not promise less DDR or E0.
            for g in frontier:
                core = min(range(cores), key=lambda k: (estimate(k, [g], units[g]["work"]), k))
                append_task(core, [g], units[g]["work"], stage, 0)
            tail = data["tail"]
            if tail is not None:
                core = min(range(cores), key=lambda k: (estimate(k, [tail], units[tail]["work"]), k))
                append_task(core, [tail], units[tail]["work"], stage, 1)
            continue
        for g in frontier:
            release = [max((unit_end[p] + (cross_wait if unit_core[p] != k else 0) for p in upred[g]), default=0)
                       for k in range(cores)]
            def key(core):
                combined = dict(loads[core])
                add_work(combined, units[g]["work"])
                return (max(bin_release[core], release[core]) + max(combined.values(), default=0),
                        sum(sizes[t] for t in inputs[g] - shared[core]), len(bins[core]), core)
            core = min(range(cores), key=key)
            bins[core].append(g)
            bin_release[core] = max(bin_release[core], release[core])
            add_work(loads[core], units[g]["work"])
            shared[core].update(inputs[g])
        for core, members in enumerate(bins):
            if members:
                append_task(core, members, loads[core], stage, 0)
        tail = data["tail"]
        if tail is not None:
            core = min(range(cores), key=lambda k: (estimate(k, [tail], units[tail]["work"]), k))
            append_task(core, [tail], units[tail]["work"], stage, 1)
    plan = {"node_to_subgraph": {u: mapping[u] for u in sorted(mapping)}, "core_schedules": schedules}
    validate_task_order(derive_multicore_plan(graph, plan))
    return plan, {"variant": "fork-stage-frontier", "grain": grain, "frontier_tasks": frontier_tasks, "stages": len(stages),
                  "unit_count": len(units), "task_count": len(tasks), "tasks": tasks,
                  "scope": "Graph-only construction and structural validation; estimates omit DDR and actual FIFO. Final E0 required."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("graph", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--cores", type=int, required=True)
    p.add_argument("--grain", type=int, default=4)
    p.add_argument("--frontier-tasks", choices=("core", "unit"), default="core")
    p.add_argument("--config", type=Path, default=OFFICIAL / "data/config.txt")
    p.add_argument("--diagnostics", type=Path)
    args = p.parse_args()
    config = read_scene_a_config(str(args.config))
    plan, diagnostics = construct(json.loads(args.graph.read_bytes()), args.cores, args.grain,
                                  config["task_same_core_wait_cycles"], config["task_cross_core_wait_cycles"], args.frontier_tasks)
    for path, value in ((args.output, plan), (args.diagnostics, diagnostics)):
        if path:
            with path.open("x", encoding="utf-8", newline="\n") as out:
                json.dump(value, out, separators=(",", ":"))
                out.write("\n")


if __name__ == "__main__":
    main()
