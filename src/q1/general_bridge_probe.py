"""Research-only one-bridge Task relocation on an arbitrary valid core order.

One present-input baseline yields at most one candidate. This module never runs
Task compilation, E1, E0, E2, or a historical-plan lookup.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from copy import deepcopy
import json
from pathlib import Path
import time

from src.q1 import branch_aid as aid
from evaluation_validation import read_required_settings

ALGORITHM_ID = "q1-general-bridge-static-queue-v2"
MAX_TASKS = aid.TASK_LIMIT
SOFT_SECONDS = 10.0


def _height(view):
    """Data-DAG height only; core order need not advance height."""
    degree = {t: len(ps) for t, ps in view["subgraph_preds"].items()}
    ready = deque(sorted(t for t, n in degree.items() if n == 0))
    height = {t: 0 for t in ready}
    seen = 0
    while ready:
        task = ready.popleft()
        seen += 1
        for nxt in sorted(view["subgraph_succs"][task]):
            height[nxt] = max(height.get(nxt, 0), height[task] + 1)
            degree[nxt] -= 1
            if degree[nxt] == 0:
                ready.append(nxt)
    if seen != len(degree):
        raise aid.UnsupportedStructure("baseline Task data DAG is cyclic")
    return height


def _peak(work):
    return max(work.values(), default=0)


def _nearby_work(view, ops, core, slot):
    """Local-work tie break, not an execution-time prediction."""
    order = view["core_orders"][core]
    adjacent = order[max(0, slot - 1):min(len(order), slot + 1)]
    loads = [aid._work(view["nodes_by_subgraph"][task], ops) for task in adjacent]
    total = Counter()
    for load in loads:
        total.update(load)
    return _peak(total), sum(total.values())


def _data_edges(mapping, succ, tasks):
    """Build one quotient Task data graph for all slots of one donor."""
    edges = {task: set() for task in tasks}
    for u, following in succ.items():
        source = mapping[u]
        for v in following:
            target = mapping[v]
            if source != target:
                edges[source].add(target)
    return edges


def _acyclic_with_orders(data_edges, schedules):
    """Kahn check on data edges plus adjacent same-core order edges."""
    edges = {task: set(targets) for task, targets in data_edges.items()}
    for order in schedules:
        for before, after in zip(order, order[1:]):
            edges[before].add(after)
    degree = {task: 0 for task in edges}
    for targets in edges.values():
        for target in targets:
            degree[target] += 1
    ready = deque(task for task, n in degree.items() if n == 0)
    seen = 0
    while ready:
        task = ready.popleft()
        seen += 1
        for target in edges[task]:
            degree[target] -= 1
            if degree[target] == 0:
                ready.append(target)
    return seen == len(degree)


def _queue_projection(data_edges, schedules, durations, same_wait, cross_wait):
    """Static critical path with core queues; no Task compilation or scoring.

    Pipe peak is only a duration proxy. Data and core-order arcs carry the
    scene-A release waits, with the larger wait winning on duplicate arcs.
    """
    core = {task: c for c, order in enumerate(schedules) for task in order}
    arcs = {task: {} for task in core}
    for source, targets in data_edges.items():
        for target in targets:
            wait = cross_wait if core[source] != core[target] else 0
            arcs[source][target] = max(arcs[source].get(target, 0), wait)
    for order in schedules:
        for source, target in zip(order, order[1:]):
            arcs[source][target] = max(arcs[source].get(target, 0), same_wait)
    degree = {task: 0 for task in core}
    for targets in arcs.values():
        for target in targets:
            degree[target] += 1
    ready = deque(task for task, n in degree.items() if n == 0)
    starts = {task: 0 for task in ready}
    topo = []
    while ready:
        task = ready.popleft()
        topo.append(task)
        end = starts[task] + durations[task]
        for target, wait in arcs[task].items():
            starts[target] = max(starts.get(target, 0), end + wait)
            degree[target] -= 1
            if degree[target] == 0:
                ready.append(target)
    if len(topo) != len(core):
        raise aid.UnsupportedStructure("static queue graph is cyclic")
    tail = {}
    for task in reversed(topo):
        tail[task] = durations[task] + max(
            (wait + tail[target] for target, wait in arcs[task].items()),
            default=0)
    return {"starts": starts, "makespan": max(
        (starts[t] + durations[t] for t in core), default=0), "tail": tail}


def _queue_screen(base, candidate, downstream):
    """Require the donor continuation to fit its old static path slack."""
    delay = candidate["starts"][downstream] - base["starts"][downstream]
    slack = base["makespan"] - (
        base["starts"][downstream] + base["tail"][downstream])
    return (candidate["makespan"] <= base["makespan"] and delay <= slack,
            delay, slack)


def construct(graph, cores, base_plan):
    """Try one structurally ranked X/Y/J relocation; return baseline on refusal.

    No case identifier or result appears in the rule. Only the supplied graph,
    baseline Task graph, op Pipe work, and static tensor boundary are read.
    """
    started = time.monotonic()
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("cores must be an integer in 1..5")
    baseline = deepcopy(base_plan)
    info = {"algorithm_id": ALGORITHM_ID, "status": "unsupported",
            "selected": "base", "scope": "structural only; no Task compilation or scoring",
            "scoring_calls": {"E1": 0, "E0": 0, "E2": 0},
            "task_limit": MAX_TASKS, "soft_seconds": SOFT_SECONDS}
    try:
        if len(baseline.get("core_schedules", [])) != cores:
            raise aid.UnsupportedStructure("baseline core count differs from requested cores")
        if cores == 1:
            raise aid.UnsupportedStructure("one core has no helper")
        view = aid.derive_multicore_plan(graph, baseline)
        aid.validate_task_order(view)
        if len(view["subgraph_ids"]) + 2 > MAX_TASKS:
            raise aid.UnsupportedStructure("baseline leaves no room for two Tasks")
        ops = {op["id"]: op for op in graph["ops"] if op["op"] not in aid.COPY}
        _, full_succ = aid._build_op_adjacency(graph)
        pred, succ = aid._contract_excluded_copy_nodes(sorted(ops), full_succ)
        direct_succ = {u: full_succ[u] & ops.keys() for u in ops}
        all_ops = {op["id"] for op in graph["ops"]}
        tensors = {tensor["id"] for tensor in graph["tensors"]}
        producers = defaultdict(set)
        for edge in graph["edges"]:
            if edge["source"] in all_ops and edge["target"] in tensors:
                producers[edge["target"]].add(edge["source"])
        if any(len(ps) > 1 for ps in producers.values()):
            raise aid.UnsupportedStructure("an original tensor has multiple producers")
        height = _height(view)
        mapping = view["mapping"]
        bandwidth = aid.read_bandwidth_config(
            aid.ROOT / "data/raw/a/official/data/config.txt")
        old_boundary = aid._boundary(graph, mapping, bandwidth)
        waits = read_required_settings(
            aid.ROOT / "data/raw/a/official/data/config.txt",
            "multicore_scene_a",
            ("task_cross_core_wait_cycles", "task_same_core_wait_cycles"))
        cross_wait = int(waits["task_cross_core_wait_cycles"])
        same_wait = int(waits["task_same_core_wait_cycles"])
        old_durations = {t: _peak(aid._work(view["nodes_by_subgraph"][t], ops))
                         for t in view["subgraph_ids"]}
        base_orders = [view["core_orders"][c] for c in range(cores)]
        base_queue = _queue_projection(view["subgraph_succs"],
                                       base_orders, old_durations,
                                       same_wait, cross_wait)
        old_tasks = len(view["subgraph_ids"])
        next_id = max(view["subgraph_ids"]) + 1
        choices = []
        witnessed = 0
        acyclic_slots = 0
        queue_rejected = 0
        for task in sorted(view["subgraph_ids"]):
            if time.monotonic() - started > SOFT_SECONDS:
                raise aid.UnsupportedStructure("structural soft time budget exceeded")
            members = set(view["nodes_by_subgraph"][task])
            packets = aid._packets(members, pred, succ)
            witness = aid._witness(task, members, packets, pred, succ,
                                   direct_succ, ops, height, mapping,
                                   time.monotonic())
            if witness is None:
                continue
            witnessed += 1
            x, y, j = witness["X"], witness["Y"], witness["J"]
            original = aid._work(members, ops)
            pieces = {name: aid._work(nodes, ops) for name, nodes in
                      (("X", x), ("Y", y), ("J", j))}
            gain = _peak(original) - max(map(_peak, pieces.values()))
            if gain <= 0:
                continue
            candidate_mapping = dict(mapping)
            for u in x:
                candidate_mapping[u] = next_id + 1
            for u in j:
                candidate_mapping[u] = next_id
            # Y retains the original Task id. Check complete old Task coverage.
            if x | y | j != members or x & y or x & j or y & j:
                continue
            data_edges = _data_edges(candidate_mapping, succ,
                                     set(view["subgraph_ids"]) | {next_id, next_id + 1})
            new_boundary = aid._boundary(graph, candidate_mapping, bandwidth)
            delta = {key: new_boundary.get(key, 0) - old_boundary.get(key, 0)
                     for key in sorted(old_boundary.keys() | new_boundary.keys())}
            donor = view["core_by_subgraph"][task]
            donor_order = view["core_orders"][donor]
            donor_index = donor_order.index(task)
            downstream = (donor_order[donor_index + 1]
                          if donor_index + 1 < len(donor_order) else None)
            durations = dict(old_durations)
            durations[task] = _peak(pieces["Y"])
            durations[next_id] = _peak(pieces["J"])
            durations[next_id + 1] = _peak(pieces["X"])
            # The new J immediately follows retained Y on the donor core.
            for helper in range(cores):
                if helper == donor:
                    continue
                helper_order = view["core_orders"][helper]
                for slot in range(len(helper_order) + 1):
                    schedules = [list(view["core_orders"][c]) for c in range(cores)]
                    index = schedules[donor].index(task)
                    schedules[donor].insert(index + 1, next_id)
                    schedules[helper].insert(slot, next_id + 1)
                    if not _acyclic_with_orders(data_edges, schedules):
                        continue
                    acyclic_slots += 1
                    projected = _queue_projection(data_edges, schedules,
                                                  durations, same_wait,
                                                  cross_wait)
                    if downstream is not None:
                        acceptable, delay, slack = _queue_screen(
                            base_queue, projected, downstream)
                    else:
                        acceptable = projected["makespan"] <= base_queue["makespan"]
                        delay = slack = None
                    if not acceptable:
                        queue_rejected += 1
                        continue
                    projected_gain = (base_queue["makespan"] -
                                      projected["makespan"])
                    # A queue tie with no COPY-service saving has no positive
                    # signal in either static proxy; keep the exact baseline.
                    if projected_gain == 0 and delta.get("service_cycles", 0) >= 0:
                        queue_rejected += 1
                        continue
                    local = _nearby_work(view, ops, helper, slot)
                    # Prefer projected global critical-path relief. Static COPY
                    # and donor relief then discriminate candidates; this is
                    # still a proxy and never a quality claim.
                    key = (-projected_gain, delta.get("service_cycles", 0),
                           delta.get("bytes", 0), -gain, *local,
                           task, helper, slot)
                    choices.append((key, task, witness, candidate_mapping,
                                    schedules, delta, old_boundary,
                                    new_boundary, original, pieces,
                                    projected["makespan"], delay, slack))
        info["census"] = {"old_tasks": old_tasks,
                          "bridge_witnessed_tasks": witnessed,
                          "acyclic_insertion_slots": acyclic_slots,
                          "feasible_insertion_slots": len(choices),
                          "queue_rejected_slots": queue_rejected}
        if not choices:
            raise aid.UnsupportedStructure(
                "no bridge witness with positive Pipe reduction, acyclic insertion, and acceptable static queue projection")
        selected = min(choices, key=lambda item: item[0])
        (key, task, witness, new_mapping, schedules, delta, old_boundary,
         new_boundary, original, pieces, projected_makespan,
         downstream_delay, downstream_slack) = selected
        plan = {"node_to_subgraph": new_mapping, "core_schedules": schedules}
        edges = aid._task_dag(new_mapping, schedules, succ)
        # Official structural guards are required even after the local DAG
        # certificate; they check complete coverage and official contraction.
        aid.validate_task_order(aid.derive_multicore_plan(graph, plan))
        if time.monotonic() - started > SOFT_SECONDS:
            raise aid.UnsupportedStructure("structural soft time budget exceeded")
        info.update(status="candidate-unscored", selected="general-bridge",
                    donor_task=task, donor_core=view["core_by_subgraph"][task],
                    helper_core=key[-2], helper_slot=key[-1],
                    join=witness["join"], export_pred=witness["export_pred"],
                    piece_sizes={name: len(witness[name]) for name in ("X", "Y", "J")},
                    old_task_pipe_work=dict(original),
                    new_piece_pipe_work={name: dict(work) for name, work in pieces.items()},
                    task_local_peak_reduction=(
                        _peak(original) - max(map(_peak, pieces.values()))),
                    static_queue_baseline_makespan=base_queue["makespan"],
                    static_queue_candidate_makespan=projected_makespan,
                    static_queue_projected_gain=base_queue["makespan"] - projected_makespan,
                    static_downstream_start_delay=downstream_delay,
                    static_downstream_slack=downstream_slack,
                    selection_rule="require no static queue makespan increase and downstream delay within baseline path slack; reject a tie without COPY-service saving; then max static global queue relief, min COPY service/bytes, max Task-local Pipe relief, min nearby helper work, deterministic IDs",
                    old_boundary=old_boundary, new_boundary=new_boundary,
                    boundary_delta=delta, augmented_dag_edges=edges,
                    warning="Task compilation, FIFO/MEM/spill, E1/E0/E2 and Makespan remain unverified")
        return plan, info
    except aid.UnsupportedStructure as exc:
        info["reason"] = str(exc)
        return baseline, info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--base-plan", type=Path, required=True)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text())
    base = json.loads(args.base_plan.read_text())
    plan, info = construct(graph, args.cores, base)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "candidate-plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, sort_keys=True) + "\n")
    (args.output_dir / "diagnostics.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": info["status"], "reason": info.get("reason"),
                      "selected": info["selected"], "census": info.get("census")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
