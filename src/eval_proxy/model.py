"""Static rank-only E2 prototype.

This module intentionally does not report a makespan. It validates the public
plan structure, then computes a deterministic screening score while marking the
execution checks that Step2/Step3 would be required to prove.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Any

from ..eval_exact._official import (
    OFFICIAL_CODE_HASH,
    load_problem1_bundle,
)


_, _OFFICIAL_SUPPORT = load_problem1_bundle("_huaweicup_eval_proxy_support")
validate_graph = _OFFICIAL_SUPPORT["evaluation_validation"].validate_graph
validate_task_order = _OFFICIAL_SUPPORT["evaluation_validation"].validate_task_order
PIPES = _OFFICIAL_SUPPORT["schedule_step3"].PIPES
EXCLUDED_COPY_TYPES = _OFFICIAL_SUPPORT[
    "stub_multicore_cut_and_schedule"
].EXCLUDED_COPY_TYPES
_build_op_adjacency = _OFFICIAL_SUPPORT[
    "stub_multicore_cut_and_schedule"
]._build_op_adjacency
_contract_excluded_copy_nodes = _OFFICIAL_SUPPORT[
    "stub_multicore_cut_and_schedule"
]._contract_excluded_copy_nodes


class ProxyPlanError(ValueError):
    """The candidate plan fails a structural check used by the proxy."""


class ProxyUnsupportedError(ValueError):
    """The requested capability is outside this first prototype."""


@dataclass(frozen=True)
class TensorFlow:
    tensor_id: int
    size: int
    position: str
    producers: tuple[int, ...]
    consumers: tuple[int, ...]
    has_copy_out: bool


@dataclass(frozen=True)
class ProxyContext:
    problem: int
    bandwidth: float
    capacity: dict[str, int]
    cross_core_wait: int
    same_core_wait: int
    eligible_ids: tuple[int, ...]
    op_cycles: dict[int, float]
    op_pipe: dict[int, str]
    dependency_edges: tuple[tuple[int, int], ...]
    tensor_flows: tuple[TensorFlow, ...]
    original_copy_bytes: int
    graph_hash: str
    config_hash: str


@dataclass(frozen=True)
class PlanView:
    mapping: dict[int, int]
    subgraph_ids: tuple[int, ...]
    nodes_by_subgraph: dict[int, tuple[int, ...]]
    core_orders: dict[int, tuple[int, ...]]
    core_by_subgraph: dict[int, int]
    dependency_pairs: tuple[tuple[int, int], ...]
    subgraph_topological_order: tuple[int, ...]
    num_cores: int


def prepare_graph(
    graph: dict[str, Any],
    *,
    problem: int,
    bandwidth: float,
    capacity: dict[str, int],
    cross_core_wait: int,
    same_core_wait: int,
    graph_hash: str = "",
    config_hash: str = "",
) -> ProxyContext:
    """Validate and index one graph for repeated plan scoring."""
    if problem != 1:
        raise ProxyUnsupportedError(
            "E2 v0 supports problem 1 only; problems 2/3 remain explicit unsupported"
        )
    validate_graph(graph)
    if bandwidth <= 0:
        raise ValueError("bandwidth must be positive")

    op_by_id = {op["id"]: op for op in graph["ops"]}
    tensor_by_id = {tensor["id"]: tensor for tensor in graph["tensors"]}
    eligible_ids = tuple(
        sorted(
            op_id
            for op_id, op in op_by_id.items()
            if op.get("op") not in EXCLUDED_COPY_TYPES
        )
    )
    _, full_succs = _build_op_adjacency(graph)
    _, contracted_succs = _contract_excluded_copy_nodes(eligible_ids, full_succs)
    dependency_edges = tuple(
        sorted(
            (source, target)
            for source in eligible_ids
            for target in contracted_succs[source]
            if source != target
        )
    )

    op_ids = set(op_by_id)
    producers: dict[int, set[int]] = {}
    consumers: dict[int, set[int]] = {}
    for edge in graph["edges"]:
        source, target = edge["source"], edge["target"]
        if source in op_ids and target not in op_ids:
            producers.setdefault(target, set()).add(source)
        elif source not in op_ids and target in op_ids:
            consumers.setdefault(source, set()).add(target)
    eligible = set(eligible_ids)
    tensor_flows = tuple(
        TensorFlow(
            tensor_id=tensor["id"],
            size=tensor["size"],
            position=tensor["pos"],
            producers=tuple(sorted(producers.get(tensor["id"], set()) & eligible)),
            consumers=tuple(sorted(consumers.get(tensor["id"], set()) & eligible)),
            has_copy_out=any(
                op_by_id[op_id].get("op") == "COPY_OUT"
                for op_id in consumers.get(tensor["id"], set())
            ),
        )
        for tensor in graph["tensors"]
    )
    original_copy_bytes = 0
    for op_id, op in op_by_id.items():
        if op.get("op") == "COPY_IN":
            tensor_ids = [
                edge["target"]
                for edge in graph["edges"]
                if edge["source"] == op_id and edge["target"] in tensor_by_id
            ]
        elif op.get("op") == "COPY_OUT":
            tensor_ids = [
                edge["source"]
                for edge in graph["edges"]
                if edge["target"] == op_id and edge["source"] in tensor_by_id
            ]
        else:
            continue
        original_copy_bytes += sum(
            tensor_by_id[tensor_id]["size"] for tensor_id in tensor_ids
        )
    return ProxyContext(
        problem=problem,
        bandwidth=float(bandwidth),
        capacity=dict(capacity),
        cross_core_wait=cross_core_wait,
        same_core_wait=same_core_wait,
        eligible_ids=eligible_ids,
        op_cycles={op_id: float(op_by_id[op_id]["cycles"]) for op_id in eligible_ids},
        op_pipe={op_id: op_by_id[op_id]["pipe"] for op_id in eligible_ids},
        dependency_edges=dependency_edges,
        tensor_flows=tensor_flows,
        original_copy_bytes=original_copy_bytes,
        graph_hash=graph_hash,
        config_hash=config_hash,
    )


def _topological_order(
    nodes: set[int], edges: set[tuple[int, int]], label: str
) -> tuple[int, ...]:
    successors = {node: set() for node in nodes}
    indegree = {node: 0 for node in nodes}
    for source, target in edges:
        if target not in successors[source]:
            successors[source].add(target)
            indegree[target] += 1
    ready = [node for node in nodes if indegree[node] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        node = heapq.heappop(ready)
        order.append(node)
        for target in sorted(successors[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                heapq.heappush(ready, target)
    if len(order) != len(nodes):
        raise ProxyPlanError(f"{label} contains a cycle")
    return tuple(order)


def validate_plan(context: ProxyContext, plan: dict[str, Any]) -> PlanView:
    """Validate the public plan fields without claiming execution feasibility."""
    required_fields = {"node_to_subgraph", "core_schedules"}
    if not isinstance(plan, dict) or set(plan) != required_fields:
        raise ProxyPlanError(
            f"multicore plan must contain exactly {sorted(required_fields)}"
        )
    raw_mapping = plan["node_to_subgraph"]
    if not isinstance(raw_mapping, dict):
        raise ProxyPlanError("node_to_subgraph must be an object")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in raw_mapping.values()
    ):
        raise ProxyPlanError("subgraph ids must be non-negative integers")
    mapping: dict[int, int] = {}
    for raw_node_id, subgraph_id in raw_mapping.items():
        if type(raw_node_id) is int:
            node_id = raw_node_id
        elif (
            isinstance(raw_node_id, str)
            and raw_node_id.isascii()
            and raw_node_id.isdecimal()
        ):
            node_id = int(raw_node_id)
        else:
            raise ProxyPlanError("node_to_subgraph keys must be integer op ids")
        if node_id in mapping:
            raise ProxyPlanError("node_to_subgraph contains duplicate integer op ids")
        mapping[node_id] = subgraph_id
    eligible = set(context.eligible_ids)
    if set(mapping) != eligible:
        missing = sorted(eligible - set(mapping))
        extra = sorted(set(mapping) - eligible)
        raise ProxyPlanError(
            "node_to_subgraph must exactly cover non-COPY ops; "
            f"missing={missing[:20]} extra={extra[:20]}"
        )

    schedules = plan["core_schedules"]
    if not isinstance(schedules, list) or not schedules:
        raise ProxyPlanError("core_schedules must be a non-empty list")
    if any(not isinstance(order, list) for order in schedules):
        raise ProxyPlanError("each core_schedules entry must be a subgraph id list")
    if any(
        not isinstance(value, int) or isinstance(value, bool)
        for order in schedules
        for value in order
    ):
        raise ProxyPlanError("core schedule values must be integers")

    subgraph_ids = set(mapping.values())
    scheduled = [value for order in schedules for value in order]
    if len(scheduled) != len(set(scheduled)) or set(scheduled) != subgraph_ids:
        raise ProxyPlanError("core schedules must cover every subgraph exactly once")
    core_orders = {core_id: tuple(order) for core_id, order in enumerate(schedules)}
    core_by_subgraph = {
        subgraph_id: core_id
        for core_id, order in core_orders.items()
        for subgraph_id in order
    }
    nodes_by_subgraph = {subgraph_id: [] for subgraph_id in subgraph_ids}
    for node_id, subgraph_id in mapping.items():
        nodes_by_subgraph[subgraph_id].append(node_id)
    frozen_nodes = {
        subgraph_id: tuple(sorted(node_ids))
        for subgraph_id, node_ids in nodes_by_subgraph.items()
    }
    dependency_pairs = {
        (mapping[source], mapping[target])
        for source, target in context.dependency_edges
        if mapping[source] != mapping[target]
    }
    topo = _topological_order(subgraph_ids, dependency_pairs, "subgraph graph")
    for source, target in dependency_pairs:
        if core_by_subgraph[source] == core_by_subgraph[target]:
            core_id = core_by_subgraph[source]
            positions = {
                subgraph_id: index
                for index, subgraph_id in enumerate(core_orders[core_id])
            }
            if positions[source] >= positions[target]:
                raise ProxyPlanError(
                    f"dependency order violation on core {core_id}: {source} -> {target}"
                )

    official_view = {
        "core_orders": {core: list(order) for core, order in core_orders.items()},
        "dependency_pairs": sorted(dependency_pairs),
        "subgraph_ids": sorted(subgraph_ids),
    }
    try:
        validate_task_order(official_view)
    except Exception as error:
        raise ProxyPlanError(str(error)) from error

    return PlanView(
        mapping=mapping,
        subgraph_ids=tuple(sorted(subgraph_ids)),
        nodes_by_subgraph=frozen_nodes,
        core_orders=core_orders,
        core_by_subgraph=core_by_subgraph,
        dependency_pairs=tuple(sorted(dependency_pairs)),
        subgraph_topological_order=topo,
        num_cores=len(schedules),
    )


def _dependency_bound(context: ProxyContext, view: PlanView, task_duration):
    edge_lag: dict[tuple[int, int], float] = {}
    for source, target in view.dependency_pairs:
        lag = (
            context.same_core_wait
            if view.core_by_subgraph[source] == view.core_by_subgraph[target]
            else context.cross_core_wait
        )
        edge_lag[(source, target)] = max(edge_lag.get((source, target), 0), lag)
    for _, order in view.core_orders.items():
        for source, target in zip(order, order[1:]):
            edge_lag[(source, target)] = max(
                edge_lag.get((source, target), 0), context.same_core_wait
            )
    nodes = set(view.subgraph_ids)
    topo = _topological_order(nodes, set(edge_lag), "task schedule")
    predecessors = {node: [] for node in nodes}
    for (source, target), lag in edge_lag.items():
        predecessors[target].append((source, lag))
    finish = {}
    for node in topo:
        release = max(
            (finish[source] + lag for source, lag in predecessors[node]), default=0
        )
        finish[node] = release + task_duration[node]
    return max(finish.values(), default=0)


def evaluate(context: ProxyContext, plan: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic rank-only response for one plan."""
    view = validate_plan(context, plan)
    core_pipe = {
        core_id: {pipe: 0.0 for pipe in PIPES} for core_id in range(view.num_cores)
    }
    task_pipe = {
        task_id: {pipe: 0.0 for pipe in PIPES} for task_id in view.subgraph_ids
    }
    for op_id in context.eligible_ids:
        task_id = view.mapping[op_id]
        core_id = view.core_by_subgraph[task_id]
        pipe = context.op_pipe[op_id]
        cycles = context.op_cycles[op_id]
        core_pipe[core_id][pipe] += cycles
        task_pipe[task_id][pipe] += cycles
    task_duration = {
        task_id: max(loads.values(), default=0) for task_id, loads in task_pipe.items()
    }
    pipe_bound = max(
        (max(loads.values(), default=0) for loads in core_pipe.values()), default=0
    )
    dependency_bound = _dependency_bound(context, view, task_duration)

    task_boundary_copy_bytes = 0
    cross_task_tensor_count = 0
    cross_core_tensor_count = 0
    same_core_cross_task_tensor_count = 0
    working_set_by_task = {task_id: {"L1": 0, "UB": 0} for task_id in view.subgraph_ids}
    for flow in context.tensor_flows:
        producer_tasks = {view.mapping[op_id] for op_id in flow.producers}
        consumer_tasks = {view.mapping[op_id] for op_id in flow.consumers}
        touched_tasks = producer_tasks | consumer_tasks
        for task_id in touched_tasks:
            position = "UB" if flow.position == "DDR" else flow.position
            if position in working_set_by_task[task_id]:
                working_set_by_task[task_id][position] += flow.size
            has_local_producer = task_id in producer_tasks
            has_local_consumer = task_id in consumer_tasks
            input_boundary = has_local_consumer and not has_local_producer
            output_boundary = has_local_producer and (
                flow.has_copy_out
                or not consumer_tasks
                or bool(consumer_tasks - {task_id})
            )
            task_boundary_copy_bytes += flow.size * (
                int(input_boundary) + int(output_boundary)
            )

        cross_task_pairs = {
            (source, target)
            for source in producer_tasks
            for target in consumer_tasks
            if source != target
        }
        if cross_task_pairs:
            cross_task_tensor_count += 1
        if any(
            view.core_by_subgraph[source] != view.core_by_subgraph[target]
            for source, target in cross_task_pairs
        ):
            cross_core_tensor_count += 1
        if any(
            view.core_by_subgraph[source] == view.core_by_subgraph[target]
            for source, target in cross_task_pairs
        ):
            same_core_cross_task_tensor_count += 1

    partition_added_copy_bytes = task_boundary_copy_bytes - context.original_copy_bytes
    transfer_score = task_boundary_copy_bytes / context.bandwidth
    rank_score = max(pipe_bound, dependency_bound) + transfer_score

    total_by_core = {
        core_id: sum(loads.values()) for core_id, loads in core_pipe.items()
    }
    nonzero = [value for value in total_by_core.values() if value > 0]
    imbalance = max(nonzero) / (sum(nonzero) / len(nonzero)) if nonzero else 0.0
    risk_flags = [
        "execution_unchecked",
        "spill_unmodeled",
        "step3_order_ignored",
        "ddr_contention_aggregated",
        "uncalibrated_rank_score",
    ]
    if cross_task_tensor_count:
        risk_flags.append("task_boundary_copy_timing_aggregated")
    if any(not order for order in view.core_orders.values()):
        risk_flags.append("empty_core")
    if imbalance > 1.5:
        risk_flags.append("high_core_imbalance")
    if any(
        value > context.capacity.get(position, 0)
        for by_position in working_set_by_task.values()
        for position, value in by_position.items()
    ):
        risk_flags.append("capacity_pressure")

    return {
        "interface": "internal-e2-v0",
        "engine": "proxy-rank-v0",
        "engine_version": "0.1.0",
        "contract_version": "v1.0-draft-internal",
        "official_code_hash": OFFICIAL_CODE_HASH,
        "capability": "rank_only",
        "status": "ok",
        "numeric_kind": "none",
        "checks": {"input": "pass", "plan": "pass", "execution": "unchecked"},
        "problem": context.problem,
        "num_cores": view.num_cores,
        "rank_score": rank_score,
        "components": {
            "pipe_load_bound": pipe_bound,
            "task_dependency_bound": dependency_bound,
            "original_copy_bytes": context.original_copy_bytes,
            "task_boundary_copy_bytes": task_boundary_copy_bytes,
            "partition_added_copy_bytes": partition_added_copy_bytes,
            "partition_transfer_score": transfer_score,
            "cross_task_tensor_count": cross_task_tensor_count,
            "cross_core_tensor_count": cross_core_tensor_count,
            "same_core_cross_task_tensor_count": same_core_cross_task_tensor_count,
            "core_total_cycles": total_by_core,
            "core_imbalance_ratio": imbalance,
            "static_working_set_by_task": working_set_by_task,
        },
        "risk_flags": risk_flags,
        "identity": {
            "graph_hash": context.graph_hash,
            "config_hash": context.config_hash,
        },
    }


def _failure_response(context, request_id, status, message):
    plan_check = "fail" if status == "invalid" else "unchecked"
    return {
        "request_id": request_id,
        "interface": "internal-e2-v0",
        "engine": "proxy-rank-v0",
        "engine_version": "0.1.0",
        "contract_version": "v1.0-draft-internal",
        "official_code_hash": OFFICIAL_CODE_HASH,
        "capability": "rank_only",
        "status": status,
        "numeric_kind": "none",
        "checks": {
            "input": "pass",
            "plan": plan_check,
            "execution": "unchecked",
        },
        "problem": context.problem,
        "message": str(message),
        "risk_flags": ["execution_unchecked"],
        "identity": {
            "graph_hash": context.graph_hash,
            "config_hash": context.config_hash,
        },
    }


def evaluate_batch(context: ProxyContext, requests):
    """Return one correlated response per structurally valid batch request."""
    materialized = list(requests)
    seen = set()
    for request in materialized:
        if not isinstance(request, dict):
            raise ProxyPlanError("each batch request must be an object")
        request_id = request.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise ProxyPlanError("each batch request needs a non-empty request_id")
        if request_id in seen:
            raise ProxyPlanError(f"duplicate request_id: {request_id}")
        seen.add(request_id)

    responses = []
    for request in materialized:
        request_id = request["request_id"]
        try:
            response = evaluate(context, request.get("plan"))
            response["request_id"] = request_id
        except ProxyPlanError as error:
            response = _failure_response(context, request_id, "invalid", error)
        except ProxyUnsupportedError as error:
            response = _failure_response(context, request_id, "unsupported", error)
        except Exception as error:
            response = _failure_response(context, request_id, "error", error)
        responses.append(response)
    return responses
