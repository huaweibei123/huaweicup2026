"""Necessary Makespan bound for one fixed, validated P1 plan.

This models mandatory original work, Task boundary copies, Task release gates,
and the single DDR service resource. It does not model spilling or schedule a
Task. Consequently it is not a bound on the global optimum over other plans.
"""

import heapq
import math
from collections import defaultdict

from stub_multicore_cut_and_schedule import derive_multicore_plan


def plan_lower_bound(graph, plan, bandwidth, same_wait, cross_wait):
    """Return component bounds and per-Task diagnostics for a fixed P1 plan.

    Assumes the frozen evaluator's successful execution semantics. In
    particular boundary durations mirror its floating division expression.
    """
    for name, value, minimum in (("bandwidth", bandwidth, 1),
                                 ("same_wait", same_wait, 0),
                                 ("cross_wait", cross_wait, 0)):
        if type(value) is not int or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")

    view = derive_multicore_plan(graph, plan)
    mapping = view["mapping"]
    ids = view["subgraph_ids"]
    ops = {op["id"]: op for op in graph["ops"]}
    producers, consumers = defaultdict(set), defaultdict(set)
    for edge in graph["edges"]:
        source, target = edge["source"], edge["target"]
        if source in ops and target not in ops:
            producers[target].add(source)
        elif source not in ops and target in ops:
            consumers[source].add(target)

    work = {task: defaultdict(int) for task in ids}
    reads = {task: [] for task in ids}
    writes = {task: [] for task in ids}
    for op_id, task in mapping.items():
        op = ops[op_id]
        work[task][op["pipe"]] += max(1, op["cycles"])

    ddr = 0
    service_by_tensor = {}
    for tensor in graph["tensors"]:
        tid = tensor["id"]
        source_tasks = {mapping[op] for op in producers[tid] if op in mapping}
        target_tasks = {mapping[op] for op in consumers[tid] if op in mapping}
        original_copy_out = any(ops[op].get("op") == "COPY_OUT"
                                for op in consumers[tid])
        service = max(1, math.ceil(tensor["size"] / bandwidth))
        service_by_tensor[tid] = service
        for task in target_tasks - source_tasks:
            reads[task].append(tid)
            work[task]["PIPE_MTE2"] += service
            ddr += service
        for task in source_tasks:
            if original_copy_out or not target_tasks or target_tasks - {task}:
                writes[task].append(tid)
                work[task]["PIPE_MTE3"] += service
                ddr += service

    durations = {}
    tasks = {}
    for task in ids:
        copy_in = sum(service_by_tensor[tid] for tid in reads[task])
        copy_out = sum(service_by_tensor[tid] for tid in writes[task])
        duration = max(max(work[task].values(), default=0), copy_in + copy_out)
        durations[task] = duration
        tasks[task] = {"pipe_work": dict(work[task]), "copy_in_tensors": sorted(reads[task]),
                       "copy_out_tensors": sorted(writes[task]),
                       "copy_in_service": copy_in, "copy_out_service": copy_out,
                       "duration_bound": duration}

    # Edge weights are release waits after predecessor completion. A duplicate
    # dependency and adjacent order edge contributes only the stronger gate.
    successors = {task: {} for task in ids}
    for source, target in view["dependency_pairs"]:
        weight = cross_wait if view["core_by_subgraph"][source] != view["core_by_subgraph"][target] else 0
        successors[source][target] = max(successors[source].get(target, 0), weight)
    for order in view["core_orders"].values():
        for source, target in zip(order, order[1:]):
            successors[source][target] = max(successors[source].get(target, 0), same_wait)

    indegree = {task: 0 for task in ids}
    for next_tasks in successors.values():
        for target in next_tasks:
            indegree[target] += 1
    ready = [task for task in ids if indegree[task] == 0]
    heapq.heapify(ready)
    start = {task: 0 for task in ids}
    visited = 0
    while ready:
        task = heapq.heappop(ready)
        visited += 1
        tasks[task]["earliest_start_bound"] = start[task]
        finish = start[task] + durations[task]
        tasks[task]["earliest_finish_bound"] = finish
        for target, wait in successors[task].items():
            start[target] = max(start[target], finish + wait)
            indegree[target] -= 1
            if indegree[target] == 0:
                heapq.heappush(ready, target)
    if visited != len(ids):
        raise ValueError("augmented Task schedule contains a cycle")
    dag = max((tasks[task]["earliest_finish_bound"] for task in ids), default=0)
    return {"bound": max(dag, ddr), "task_dag": dag, "mandatory_ddr": ddr,
            "tasks": tasks, "proof_scope": "fixed plan, not global optimum"}
