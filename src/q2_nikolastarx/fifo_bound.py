"""Static P2 lower bound for a fixed singleton plan; never runs a scheduler.

This is a necessary makespan bound conditional on successful execution under
the frozen official P2 semantics, not a plan-validity or global-optimality
certificate. See docs/a/q2-nikolastarx/FIFO_BOUND.md for the reconstruction
proof and the distinction between validation edges D_val and retained
execution dependencies D_exec.
"""
from __future__ import annotations

import heapq

from .dag_direct import DAGIndex, PIPES
from .direct import derive_multicore_plan, validate_graph
from stub_multicore_cut_and_schedule import MulticoreCutError


def _unsupported(code, reason, guard=None):
    return {
        "supported": False,
        "reason_code": code,
        "reason": reason,
        "makespan_lower_bound_cycles": None,
        "official_execution_validated": False,
        "reconstruction_guard": guard or {},
    }


def fixed_fifo_lower_bound(graph, plan):
    """Certify the longest compute path for exactly this singleton candidate.

    Original COPY operations are excluded. Only eligible-to-eligible direct
    edges, eligible tensor producer-to-consumer edges, and adjacent eligible
    operations on each (core, pipe) are used. Original tensors must have at
    most one eligible producer; uncertain reconstruction domains abstain.

    ``supported`` means these static checks/proof apply. It does not mean the
    expanded COPY, memory, or global execution graph has passed E0 validation.
    Neither the graph nor plan is mutated. This function invokes only input
    validation and indexing helpers, never a solver or evaluator.
    """
    guard = {
        "frozen_semantics": "official P2, one slot per core/pipe",
        "conditional_on_successful_official_execution": True,
    }
    try:
        validate_graph(graph)
        if any(not isinstance(op.get("op"), str) for op in graph["ops"]):
            raise ValueError("every operation must have a string op type")
        index = DAGIndex(graph)
    except (TypeError, ValueError, KeyError, OverflowError) as error:
        return _unsupported("invalid_or_unindexable_graph", str(error), guard)
    guard["input_graph_validated"] = True
    try:
        view = derive_multicore_plan(graph, plan)
    except (TypeError, ValueError, KeyError, OverflowError, MulticoreCutError) as error:
        return _unsupported("invalid_plan_structure", str(error), guard)
    guard["plan_structure_validated"] = True
    if any(len(nodes) != 1 for nodes in view["nodes_by_subgraph"].values()):
        return _unsupported(
            "non_singleton_plan", "each subgraph must contain exactly one eligible op", guard)
    guard["singleton_subgraphs"] = True
    multi = sorted(tid for tid, producers in index.producers.items()
                   if len(producers) > 1)
    if multi:
        guard["multiple_eligible_producer_tensor_ids"] = multi
        return _unsupported(
            "multiple_eligible_tensor_producers",
            "reconstruction proof requires at most one eligible producer per original tensor",
            guard)
    guard["at_most_one_eligible_producer_per_tensor"] = True

    # index.succ is D_val: COPY contraction is appropriate for validating a
    # plan, but is not in general an execution dependency after P2 rebuilding.
    exec_succ = {u: set() for u in index.ops}
    reasons = {}

    def execution_edge(u, v, reason):
        exec_succ[u].add(v)
        reasons.setdefault((u, v), set()).add(reason)

    for v, incoming in index.direct_inputs.items():
        for u, _ in incoming:
            execution_edge(u, v, "original_direct")
    for tid, producers in index.producers.items():
        for u in producers:
            for v in index.consumers.get(tid, ()):
                execution_edge(u, v, "original_tensor")
    removed_only = sorted((u, v) for u in index.ops
                          for v in index.succ[u] - exec_succ[u])
    guard.update({
        "d_val_edge_count": sum(map(len, index.succ.values())),
        "d_exec_edge_count": sum(map(len, exec_succ.values())),
        "omitted_copy_contraction_edge_count": len(removed_only),
        "omitted_copy_contraction_edge_examples": [list(edge) for edge in removed_only[:8]],
        "execution_edge_rule": "eligible direct edges and single-producer tensor incidences only",
    })

    succ = {u: set(vs) for u, vs in exec_succ.items()}
    pred = {u: set() for u in index.ops}
    group_op = {group: nodes[0] for group, nodes in view["nodes_by_subgraph"].items()}
    owner, pipe_work = {}, []
    duration = {u: max(1, op["cycles"]) for u, op in index.ops.items()}
    fifo_count, fifo_new_count = 0, 0
    for core, sequence in view["core_orders"].items():
        by_pipe = {pipe: [] for pipe in PIPES}
        for group in sequence:
            u = group_op[group]
            owner[u] = core
            by_pipe[index.ops[u]["pipe"]].append(u)
        for pipe, ops in by_pipe.items():
            pipe_work.append({"core": core, "pipe": pipe, "op_count": len(ops),
                              "cycles": sum(duration[u] for u in ops)})
            for u, v in zip(ops, ops[1:]):
                fifo_count += 1
                fifo_new_count += v not in succ[u]
                succ[u].add(v)
                reasons.setdefault((u, v), set()).add("fixed_compute_fifo")
    for u, successors in succ.items():
        for v in successors:
            pred[v].add(u)
    guard.update({"fifo_adjacent_edge_count": fifo_count,
                  "fifo_new_edge_count": fifo_new_count,
                  "fixed_graph_edge_count": sum(map(len, succ.values()))})

    degree = {u: len(pred[u]) for u in index.ops}
    ready = [u for u in index.ops if degree[u] == 0]
    heapq.heapify(ready)
    finish, previous = {}, {}
    while ready:
        u = heapq.heappop(ready)
        source = max(pred[u], key=lambda v: (finish[v], -v), default=None)
        previous[u] = source
        finish[u] = duration[u] + (0 if source is None else finish[source])
        for v in succ[u]:
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, v)
    if len(finish) != len(index.ops):
        guard["fixed_compute_graph_acyclic"] = False
        guard["unresolved_op_ids"] = sorted(u for u in index.ops if u not in finish)
        return _unsupported(
            "cyclic_fixed_compute_graph",
            "D_exec plus fixed compute FIFO has a cycle; no finite DAG certificate returned",
            guard)
    guard["fixed_compute_graph_acyclic"] = True
    last = max(finish, key=lambda u: (finish[u], -u), default=None)
    lower = 0 if last is None else finish[last]
    path = []
    while last is not None:
        path.append(last)
        last = previous[last]
    path.reverse()
    work_bound = max((row["cycles"] for row in pipe_work), default=0)
    return {
        "supported": True,
        "bound_scope": "this singleton candidate's fixed assignment and compute FIFO only",
        "makespan_lower_bound_cycles": lower,
        "assigned_pipe_work_lower_bound_cycles": work_bound,
        "improvement_over_assigned_pipe_work_cycles": lower - work_bound,
        "eligible_ops": len(index.ops),
        "core_count": view["num_cores"],
        "per_core_pipe_work": pipe_work,
        "critical_path": [
            {"op_id": u, "core": owner[u], "pipe": index.ops[u]["pipe"],
             "duration_cycles": duration[u], "relaxed_finish_cycles": finish[u]}
            for u in path
        ],
        "critical_path_edges": [
            {"source": u, "target": v, "reasons": sorted(reasons[u, v])}
            for u, v in zip(path, path[1:])
        ],
        "reconstruction_guard": guard,
        "official_execution_validated": False,
    }
