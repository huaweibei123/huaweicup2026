"""Coarse task-event E2 prototype.

This is the second E2 algorithm direction.  Unlike ``model.evaluate``, which
combines aggregate pipe/dependency bounds with one global transfer penalty,
this module performs two deterministic scheduling passes:

1. list-schedule the operations inside each task against per-pipe readiness;
2. propagate those task durations through dependency and core-order events.

Boundary copies are charged to the task that performs them and rounded one
copy at a time.  The result is still an uncalibrated estimate: Step2 spills,
the full Step3 execution graph, copy/compute overlap, and DDR contention are
not simulated.  In particular, this model does not claim the official Pipe
head-of-line blocking behavior that FORM still lists as an unprobed boundary.
"""

from __future__ import annotations

import math
from typing import Any

from ..eval_exact._official import OFFICIAL_CODE_HASH
from .model import (
    PIPES,
    PlanView,
    ProxyContext,
    _topological_order,
    validate_plan,
)


def _task_compute_cycles(context: ProxyContext, view: PlanView) -> dict[int, float]:
    """List-schedule each task's operations on one slot per official pipe."""
    internal_predecessors = {
        task_id: {op_id: [] for op_id in view.nodes_by_subgraph[task_id]}
        for task_id in view.subgraph_ids
    }
    internal_edges = {task_id: set() for task_id in view.subgraph_ids}
    for source, target in context.dependency_edges:
        source_task = view.mapping[source]
        target_task = view.mapping[target]
        if source_task == target_task:
            internal_edges[source_task].add((source, target))
            internal_predecessors[source_task][target].append(source)

    durations: dict[int, float] = {}
    for task_id in view.subgraph_ids:
        nodes = set(view.nodes_by_subgraph[task_id])
        order = _topological_order(
            nodes, internal_edges[task_id], f"task {task_id} operation graph"
        )
        pipe_ready = {pipe: 0.0 for pipe in PIPES}
        finish: dict[int, float] = {}
        for op_id in order:
            dependency_ready = max(
                (
                    finish[predecessor]
                    for predecessor in internal_predecessors[task_id][op_id]
                ),
                default=0.0,
            )
            pipe = context.op_pipe[op_id]
            start = max(dependency_ready, pipe_ready[pipe])
            end = start + max(1.0, context.op_cycles[op_id])
            finish[op_id] = end
            pipe_ready[pipe] = end
        durations[task_id] = max(finish.values(), default=0.0)
    return durations


def _boundary_copy_cycles(
    context: ProxyContext, view: PlanView
) -> tuple[dict[int, int], dict[int, int], dict[int, int], dict[int, int]]:
    """Charge and round each generated task-boundary copy independently."""
    input_bytes = {task_id: 0 for task_id in view.subgraph_ids}
    output_bytes = {task_id: 0 for task_id in view.subgraph_ids}
    input_cycles = {task_id: 0 for task_id in view.subgraph_ids}
    output_cycles = {task_id: 0 for task_id in view.subgraph_ids}

    for flow in context.tensor_flows:
        producer_tasks = {view.mapping[op_id] for op_id in flow.producers}
        consumer_tasks = {view.mapping[op_id] for op_id in flow.consumers}
        for task_id in producer_tasks | consumer_tasks:
            has_local_producer = task_id in producer_tasks
            has_local_consumer = task_id in consumer_tasks
            input_boundary = has_local_consumer and not has_local_producer
            output_boundary = has_local_producer and (
                flow.has_copy_out
                or not consumer_tasks
                or bool(consumer_tasks - {task_id})
            )
            copy_cycles = max(1, math.ceil(flow.size / context.bandwidth))
            if input_boundary:
                input_bytes[task_id] += flow.size
                input_cycles[task_id] += copy_cycles
            if output_boundary:
                output_bytes[task_id] += flow.size
                output_cycles[task_id] += copy_cycles

    return input_bytes, output_bytes, input_cycles, output_cycles


def _task_event_schedule(
    context: ProxyContext,
    view: PlanView,
    task_duration: dict[int, float],
) -> tuple[float, dict[int, float], dict[int, float], dict[tuple[int, int], int]]:
    """Propagate task completion events through waits and core serialization."""
    edge_lag: dict[tuple[int, int], int] = {}
    for source, target in view.dependency_pairs:
        lag = (
            context.same_core_wait
            if view.core_by_subgraph[source] == view.core_by_subgraph[target]
            else context.cross_core_wait
        )
        edge_lag[(source, target)] = max(edge_lag.get((source, target), 0), lag)
    for order in view.core_orders.values():
        for source, target in zip(order, order[1:]):
            edge_lag[(source, target)] = max(
                edge_lag.get((source, target), 0), context.same_core_wait
            )

    nodes = set(view.subgraph_ids)
    order = _topological_order(nodes, set(edge_lag), "coarse task-event graph")
    predecessors = {task_id: [] for task_id in view.subgraph_ids}
    for (source, target), lag in edge_lag.items():
        predecessors[target].append((source, lag))

    start: dict[int, float] = {}
    finish: dict[int, float] = {}
    for task_id in order:
        start[task_id] = max(
            (finish[predecessor] + lag for predecessor, lag in predecessors[task_id]),
            default=0.0,
        )
        finish[task_id] = start[task_id] + task_duration[task_id]
    return max(finish.values(), default=0.0), start, finish, edge_lag


def evaluate_event(context: ProxyContext, plan: dict[str, Any]) -> dict[str, Any]:
    """Estimate Problem 1 makespan with the coarse task-event direction."""
    view = validate_plan(context, plan)
    compute_cycles = _task_compute_cycles(context, view)
    (
        input_bytes,
        output_bytes,
        input_copy_cycles,
        output_copy_cycles,
    ) = _boundary_copy_cycles(context, view)
    task_duration = {
        task_id: (
            input_copy_cycles[task_id]
            + compute_cycles[task_id]
            + output_copy_cycles[task_id]
        )
        for task_id in view.subgraph_ids
    }
    estimate, task_start, task_finish, edge_lag = _task_event_schedule(
        context, view, task_duration
    )

    risk_flags = [
        "execution_unchecked",
        "spill_unmodeled",
        "step3_approximated_by_local_list_schedule",
        "pipe_head_blocking_unmodeled",
        "copy_compute_overlap_unmodeled",
        "ddr_contention_unmodeled",
        "uncalibrated_makespan_estimate",
    ]
    if any(not order for order in view.core_orders.values()):
        risk_flags.append("empty_core")

    return {
        "interface": "internal-e2-v0",
        "engine": "proxy-task-event-v0",
        "engine_version": "0.1.0",
        "algorithm_direction": "coarse_task_event_list_schedule",
        "contract_version": "v1.0-draft-internal",
        "official_code_hash": OFFICIAL_CODE_HASH,
        "capability": "makespan_estimate",
        "status": "ok",
        "numeric_kind": "estimate",
        "checks": {"input": "pass", "plan": "pass", "execution": "unchecked"},
        "problem": context.problem,
        "num_cores": view.num_cores,
        "metrics": {"makespan": estimate},
        "components": {
            "task_compute_cycles": compute_cycles,
            "task_input_copy_bytes": input_bytes,
            "task_output_copy_bytes": output_bytes,
            "task_input_copy_cycles": input_copy_cycles,
            "task_output_copy_cycles": output_copy_cycles,
            "task_duration_cycles": task_duration,
            "task_start_cycles": task_start,
            "task_finish_cycles": task_finish,
            "task_edge_wait_cycles": {
                f"{source}->{target}": lag
                for (source, target), lag in sorted(edge_lag.items())
            },
        },
        "risk_flags": risk_flags,
        "identity": {
            "graph_hash": context.graph_hash,
            "config_hash": context.config_hash,
        },
    }
