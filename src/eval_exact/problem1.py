"""Problem-1 exact candidate with indexed task-boundary construction.

The event simulator is loaded byte-for-byte from the frozen official module. This
module replaces only its private task builder inside an isolated module instance;
the official files in ``data/raw`` remain untouched.
"""

from __future__ import annotations

import math
from typing import Any

from ._official import load_problem1

_runtime = load_problem1("_huaweicup_eval_exact_problem1")

_STEP3_GRAPH_KEYS = ("ops", "tensors", "edges", "seq_ext")
_FLAT_VALUE_TYPES = (type(None), bool, int, float, str)
_step3_globals = _runtime.prepare_step3_execution.__globals__
_official_step3_deepcopy = _step3_globals["deepcopy"]


def _copy_step3_extended_graph(ext_graph: Any) -> Any:
    """Copy the frozen flat graph schema, falling back for any schema drift.

    Validation and copying are fused so the guard does not scan every record a
    second time. Returning through the saved official copier is important for a
    future nested field: a shallow copy must never leak an alias to the input.
    """
    if type(ext_graph) is not dict or tuple(ext_graph) != _STEP3_GRAPH_KEYS:
        return _official_step3_deepcopy(ext_graph)
    containers = tuple(ext_graph[key] for key in _STEP3_GRAPH_KEYS)
    if any(type(value) is not list for value in containers) or len(
        {id(value) for value in containers}
    ) != len(containers):
        return _official_step3_deepcopy(ext_graph)
    copied = {}
    seen_records: set[int] = set()
    for key in ("ops", "tensors", "edges"):
        records = ext_graph[key]
        copied_records = []
        for record in records:
            record_id = id(record)
            if type(record) is not dict or record_id in seen_records:
                return _official_step3_deepcopy(ext_graph)
            seen_records.add(record_id)
            copied_record = {}
            for field, value in record.items():
                if type(field) is not str or type(value) not in _FLAT_VALUE_TYPES:
                    return _official_step3_deepcopy(ext_graph)
                copied_record[field] = value
            copied_records.append(copied_record)
        copied[key] = copied_records
    seq_ext = ext_graph["seq_ext"]
    if any(type(op_id) is not int for op_id in seq_ext):
        return _official_step3_deepcopy(ext_graph)
    copied["seq_ext"] = list(seq_ext)
    return copied


# ``prepare_step3_execution`` belongs to this candidate's isolated support
# bundle, so replacing its global leaves the frozen source and oracle untouched.
_step3_globals["deepcopy"] = _copy_step3_extended_graph


def _index_task_boundaries(
    tensor_by_id: dict[int, dict[str, Any]],
    producers: dict[int, set[int]],
    consumers: dict[int, set[int]],
    direct_edges: list[dict[str, int]],
    op_by_id: dict[int, dict[str, Any]],
    mapping: dict[int, int],
    task_ids: list[int],
) -> tuple[
    dict[int, set[int]],
    dict[int, list[dict[str, int]]],
    dict[int, set[int]],
    dict[int, bool],
]:
    """Build indexes that the oracle recomputes by scanning every tensor/task."""
    touched_by_task = {task_id: set() for task_id in task_ids}
    eligible_consumers: dict[int, set[int]] = {}
    has_copy_out: dict[int, bool] = {}

    for tensor_id in tensor_by_id:
        tensor_producers = producers.get(tensor_id, set())
        tensor_consumers = consumers.get(tensor_id, set())
        eligible_consumers[tensor_id] = {
            op_id for op_id in tensor_consumers if op_id in mapping
        }
        has_copy_out[tensor_id] = any(
            op_id in op_by_id and op_by_id[op_id].get("op") == "COPY_OUT"
            for op_id in tensor_consumers
        )
        for op_id in tensor_producers | tensor_consumers:
            task_id = mapping.get(op_id)
            if task_id is not None:
                touched_by_task[task_id].add(tensor_id)

    direct_edges_by_task = {task_id: [] for task_id in task_ids}
    for edge in direct_edges:
        source_task = mapping.get(edge["source"])
        if source_task is not None and mapping.get(edge["target"]) == source_task:
            direct_edges_by_task[source_task].append(edge)

    return (
        touched_by_task,
        direct_edges_by_task,
        eligible_consumers,
        has_copy_out,
    )


def _build_scene_a_tasks_indexed(graph_json, plan, bandwidth, capacity):
    """Equivalent task builder using one graph-wide boundary indexing pass."""
    plan_view = _runtime.derive_multicore_plan(graph_json, plan)
    _runtime.validate_task_order(plan_view)
    op_by_id = {op["id"]: op for op in graph_json["ops"]}
    tensor_by_id = {tensor["id"]: tensor for tensor in graph_json["tensors"]}
    mapping = plan_view["mapping"]
    producers, consumers, direct_edges = _runtime._original_tensor_views(graph_json)
    core_by_task = plan_view["core_by_subgraph"]
    pred_tasks = plan_view["subgraph_preds"]

    (
        touched_by_task,
        direct_edges_by_task,
        eligible_consumers_by_tensor,
        has_copy_out_by_tensor,
    ) = _index_task_boundaries(
        tensor_by_id,
        producers,
        consumers,
        direct_edges,
        op_by_id,
        mapping,
        plan_view["subgraph_ids"],
    )

    next_op_id = max([op["id"] for op in graph_json["ops"]] + [0]) + 1
    next_tensor_id = (
        max([tensor["id"] for tensor in graph_json["tensors"]] + [10000]) + 1
    )
    used_ids = set(op_by_id) | set(tensor_by_id)

    def new_boundary_ids():
        nonlocal next_op_id, next_tensor_id
        while next_tensor_id in used_ids:
            next_tensor_id += 1
        ddr_id = next_tensor_id
        used_ids.add(ddr_id)
        next_tensor_id += 1
        while next_op_id in used_ids:
            next_op_id += 1
        copy_id = next_op_id
        used_ids.add(copy_id)
        next_op_id += 1
        return ddr_id, copy_id

    tasks = {}
    cross_task_traffic = 0
    task_graph_copy_traffic = 0
    spill_copy_traffic = 0

    for task_id in plan_view["subgraph_ids"]:
        task_op_ids = set(plan_view["nodes_by_subgraph"][task_id])
        ops = [dict(op_by_id[op_id]) for op_id in sorted(task_op_ids)]
        tensors, edges = [], []

        for tensor_id in sorted(touched_by_task[task_id]):
            tensor = dict(tensor_by_id[tensor_id])
            local_producers = producers.get(tensor_id, set()) & task_op_ids
            local_consumers = consumers.get(tensor_id, set()) & task_op_ids
            eligible_consumers = eligible_consumers_by_tensor[tensor_id]
            input_boundary = bool(local_consumers) and not bool(local_producers)
            output_boundary = bool(local_producers) and (
                has_copy_out_by_tensor[tensor_id]
                or not eligible_consumers
                or bool(eligible_consumers - task_op_ids)
            )

            if tensor.get("pos") == "DDR":
                tensor["pos"] = "UB"
            tensors.append(tensor)
            for producer_id in sorted(local_producers):
                edges.append({"source": producer_id, "target": tensor_id})
            for consumer_id in sorted(local_consumers):
                edges.append({"source": tensor_id, "target": consumer_id})

            if input_boundary:
                ddr_id, copy_id = new_boundary_ids()
                tensors.append({"id": ddr_id, "pos": "DDR", "size": tensor["size"]})
                ops.append(
                    {
                        "id": copy_id,
                        "op": "COPY_IN",
                        "pipe": "PIPE_MTE2",
                        "cycles": max(1, math.ceil(tensor["size"] / bandwidth)),
                    }
                )
                edges.extend(
                    [
                        {"source": ddr_id, "target": copy_id},
                        {"source": copy_id, "target": tensor_id},
                    ]
                )
            if output_boundary:
                ddr_id, copy_id = new_boundary_ids()
                tensors.append({"id": ddr_id, "pos": "DDR", "size": tensor["size"]})
                ops.append(
                    {
                        "id": copy_id,
                        "op": "COPY_OUT",
                        "pipe": "PIPE_MTE3",
                        "cycles": max(1, math.ceil(tensor["size"] / bandwidth)),
                    }
                )
                edges.extend(
                    [
                        {"source": tensor_id, "target": copy_id},
                        {"source": copy_id, "target": ddr_id},
                    ]
                )
                remote_consumer_tasks = {
                    mapping[op_id]
                    for op_id in eligible_consumers
                    if mapping[op_id] != task_id
                }
                cross_task_traffic += tensor["size"] * len(remote_consumer_tasks)

        edges.extend(dict(edge) for edge in direct_edges_by_task[task_id])
        graph = {"ops": ops, "tensors": tensors, "edges": edges}
        task_graph_copy_traffic += _runtime._copy_traffic_bytes(graph)
        seq = _runtime.step1_schedule(graph)
        result2 = _runtime.step2_spill_insertion(graph, seq, capacity=capacity)
        spill_copy_traffic += sum(
            spill["size"] * (1 + int(spill["spill_out_copies_data"]))
            for spill in result2["spill_records"]
        )
        ext_graph = _runtime._build_extended_graph(graph, result2)
        prepared = _runtime.prepare_step3_execution(
            ext_graph, capacity=capacity, bandwidth=bandwidth
        )
        prepared.update(
            {
                "task_id": task_id,
                "core_id": core_by_task[task_id],
                "pred_tasks": pred_tasks[task_id],
            }
        )
        tasks[task_id] = prepared

    original_copy_traffic = _runtime._copy_traffic_bytes(graph_json)
    partition_added_traffic = task_graph_copy_traffic - original_copy_traffic
    traffic = {
        "original_graph_copy_bytes": original_copy_traffic,
        "scheduled_copy_bytes": task_graph_copy_traffic + spill_copy_traffic,
        "added_copy_bytes": partition_added_traffic + spill_copy_traffic,
        "partition_added_copy_bytes": partition_added_traffic,
        "spill_added_copy_bytes": spill_copy_traffic,
    }
    return tasks, cross_task_traffic, traffic, plan_view


_runtime._build_scene_a_tasks = _build_scene_a_tasks_indexed


def evaluate_scene_a(
    graph_json,
    plan,
    bandwidth,
    capacity,
    cross_core_wait,
    same_core_wait,
    max_iter=1_000_000,
):
    """Run the frozen simulator with the indexed task builder."""
    return _runtime.evaluate_scene_a(
        graph_json,
        plan,
        bandwidth,
        capacity,
        cross_core_wait,
        same_core_wait,
        max_iter=max_iter,
    )


read_scene_a_config = _runtime.read_scene_a_config
