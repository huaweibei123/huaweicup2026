# 本程序及代码是在人工智能工具辅助下完成的。
# 代码生成主要使用 GPT-6 系列模型辅助。
# 工具名称：GPT-6 Astra；版本/型号：gpt-6-astra。
# 开发机构/公司：OpenAI；版本颁布日期：2026-09-03。
# 日期指 Astra 模型发布日，不是安装日或知识截止日。
# 本展示版仅新增声明，原始程序内容保持不变。
# 依据：竞赛人工智能工具及输出使用规定（2026）第5条。

"""R6 single-candidate branch aid; structural construction only, never scores.

The caller must supply a baseline built from *this* graph. No case ID, saved
result, timeline, or prior performance enters the selection rule.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from copy import deepcopy
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))
from evaluation_validation import read_bandwidth_config, validate_task_order
from stub_multicore_cut_and_schedule import (
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)

COPY = {"COPY_IN", "COPY_OUT"}
TASK_LIMIT = 320
EXTRA_SECONDS = 2.0  # Soft check, not a process or evaluator hard timeout.


class UnsupportedStructure(ValueError):
    """This particular baseline lies outside the proved R6 construction domain."""


def _check_time(start):
    if time.monotonic() - start > EXTRA_SECONDS:
        raise UnsupportedStructure("structural soft time budget exceeded")


def _work(members, ops):
    result = Counter()
    for node in members:
        op = ops[node]
        result[op["pipe"]] += max(1, op["cycles"])
    return result


def _wave_domain(view, cores):
    """Contracted Task DAG height; reject any implicit within-wave core order."""
    preds, succs = view["subgraph_preds"], view["subgraph_succs"]
    degree = {task: len(ps) for task, ps in preds.items()}
    ready = deque(sorted(task for task, count in degree.items() if not count))
    height = {task: 0 for task in ready}
    seen = 0
    while ready:
        task = ready.popleft()
        seen += 1
        for nxt in sorted(succs[task]):
            height[nxt] = max(height.get(nxt, 0), height[task] + 1)
            degree[nxt] -= 1
            if degree[nxt] == 0:
                ready.append(nxt)
    if seen != len(preds):
        raise UnsupportedStructure("baseline Task data DAG is cyclic")
    waves = defaultdict(dict)
    for core in range(cores):
        last = -1
        for task in view["core_orders"][core]:
            h = height[task]
            if h <= last or core in waves[h]:
                raise UnsupportedStructure("core order does not strictly advance Task height")
            waves[h][core] = task
            last = h
    return height, dict(waves)


def _packets(task_nodes, pred, succ):
    """Independent undirected compute components inside one original Task."""
    remain = set(task_nodes)
    packets = []
    for root in sorted(task_nodes):
        if root not in remain:
            continue
        remain.remove(root)
        stack, found = [root], {root}
        while stack:
            u = stack.pop()
            for v in (pred[u] | succ[u]) & remain:
                remain.remove(v)
                found.add(v)
                stack.append(v)
        packets.append(found)
    return packets


def _bridge_tree(packet, pred, succ, ops):
    """One iterative Tarjan pass, then one block-tree work accumulation."""
    adj = {u: (pred[u] | succ[u]) & packet for u in packet}
    tin, low, parent, bridges = {}, {}, {}, set()
    clock = 0
    for root in sorted(packet):
        if root in tin:
            continue
        parent[root] = None
        tin[root] = low[root] = clock
        clock += 1
        stack = [(root, iter(sorted(adj[root])))]
        while stack:
            u, neighbors = stack[-1]
            try:
                v = next(neighbors)
            except StopIteration:
                stack.pop()
                p = parent[u]
                if p is not None:
                    low[p] = min(low[p], low[u])
                    if low[u] > tin[p]:
                        bridges.add(frozenset((p, u)))
                continue
            if v == parent[u]:
                continue
            if v not in tin:
                parent[v] = u
                tin[v] = low[v] = clock
                clock += 1
                stack.append((v, iter(sorted(adj[v]))))
            else:
                low[u] = min(low[u], tin[v])
    block, members = {}, []
    for root in sorted(packet):
        if root in block:
            continue
        index = len(members)
        block[root] = index
        found = {root}
        stack = [root]
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if frozenset((u, v)) not in bridges and v not in block:
                    block[v] = index
                    found.add(v)
                    stack.append(v)
        members.append(found)
    tree = [set() for _ in members]
    for edge in bridges:
        a, b = tuple(edge)
        tree[block[a]].add(block[b])
        tree[block[b]].add(block[a])
    sinks = [u for u in packet if not (succ[u] & packet)]
    if len(sinks) != 1:
        raise UnsupportedStructure("packet lacks a unique internal sink")
    root = block[sinks[0]]
    block_parent = {root: None}
    order = [root]
    for b in order:
        for other in sorted(tree[b]):
            if other not in block_parent:
                block_parent[other] = b
                order.append(other)
    if len(order) != len(members):
        raise UnsupportedStructure("packet bridge tree is disconnected")
    subtree = [_work(group, ops) for group in members]
    for b in reversed(order[1:]):
        subtree[block_parent[b]].update(subtree[b])
    return bridges, block, block_parent, subtree, sinks[0]


def _cone(start, packet, pred, succ, forbidden_edge):
    """Materialize only the chosen bridge side, once per selected donor."""
    found, stack = {start}, [start]
    while stack:
        u = stack.pop()
        for v in (pred[u] | succ[u]) & packet:
            if frozenset((u, v)) == forbidden_edge:
                continue
            if v not in found:
                found.add(v)
                stack.append(v)
    return found


def _descendants(join, packet, succ):
    found, stack = {join}, [join]
    while stack:
        u = stack.pop()
        for v in succ[u] & packet:
            if v not in found:
                found.add(v)
                stack.append(v)
    return found


def _witness(task, members, packets, pred, succ, direct_succ, ops,
             height, node_task, start):
    choices = []
    for packet in packets:
        _check_time(start)
        try:
            bridges, block, parent, subtree, sink = _bridge_tree(packet, pred, succ, ops)
        except UnsupportedStructure:
            continue
        # Direct compute edges must agree exactly with COPY-contracted edges
        # inside the selected packet, including direction.
        if any((succ[u] & packet) != (direct_succ[u] & packet) for u in packet):
            continue
        for j in sorted(packet):
            incoming = sorted(pred[j] & packet)
            if len(incoming) != 2:
                continue
            if any(frozenset((p, j)) not in bridges or
                   parent[block[p]] != block[j] for p in incoming):
                continue
            sizes = {p: max(subtree[block[p]].values(), default=0) for p in incoming}
            choices.append((min(sizes.values()), j, incoming, sizes, packet, sink))
    if not choices:
        return None
    _, join, incoming, sizes, packet, sink = min(choices, key=lambda x: (-x[0], x[1]))
    exported_pred = min(incoming, key=lambda p: (sizes[p], -p))
    X = _cone(exported_pred, packet, pred, succ, frozenset((exported_pred, join)))
    J = _descendants(join, packet, succ)
    Y = members - X - J
    if not X or not Y or not J or X & J or X | Y | J != members:
        return None
    if any(p in packet and p not in X for u in X for p in pred[u]):
        return None
    if any(v in packet and v not in J for u in J for v in succ[u]):
        return None
    # Verify the full original Task, not only the selected packet. Other
    # independent packets remain in Y.
    for u in members:
        for v in succ[u]:
            if v not in members:
                continue
            a = "X" if u in X else "Y" if u in Y else "J"
            b = "X" if v in X else "Y" if v in Y else "J"
            if a != b and (a, b) not in {("X", "J"), ("Y", "J")}:
                return None
    for group in (X, Y):
        for u in group:
            if any(height[node_task[p]] >= height[task]
                   for p in pred[u] if p not in members):
                return None
    return {"task": task, "join": join, "sink": sink, "X": X, "Y": Y,
            "J": J, "export_pred": exported_pred, "work": _work(X, ops)}


def _boundary(graph, mapping, bandwidth):
    """Exact static Task COPY instances under official scene-A predicates.

    This excludes Step2 spill and does not compile a Task. A direct op-op edge
    has no tensor size and is never invented as a DDR transfer.
    """
    ops = {op["id"]: op for op in graph["ops"]}
    tensors = {tensor["id"]: tensor for tensor in graph["tensors"]}
    producers, consumers = defaultdict(set), defaultdict(set)
    for edge in graph["edges"]:
        src, dst = edge["source"], edge["target"]
        if src in ops and dst in tensors:
            producers[dst].add(src)
        elif src in tensors and dst in ops:
            consumers[src].add(dst)
    count = Counter()
    for tid, tensor in tensors.items():
        ps, cs = producers[tid], consumers[tid]
        producer_tasks = {mapping[u] for u in ps if u in mapping}
        consumer_tasks = {mapping[u] for u in cs if u in mapping}
        has_copy_out = any(ops[u]["op"] == "COPY_OUT" for u in cs)
        incoming = len(consumer_tasks - producer_tasks)
        if has_copy_out or not consumer_tasks or len(consumer_tasks) > 1:
            outgoing = len(producer_tasks)
        else:
            outgoing = len(producer_tasks - consumer_tasks)
        instances = incoming + outgoing
        count["copy_in_instances"] += incoming
        count["copy_out_instances"] += outgoing
        count["bytes"] += instances * tensor["size"]
        count["service_cycles"] += instances * max(
            1, math.ceil(tensor["size"] / bandwidth))
    return dict(count)


def _task_dag(mapping, schedules, succ):
    """Kahn certificate for data plus every adjacent same-core order edge."""
    tasks = {task for order in schedules for task in order}
    edges = {task: set() for task in tasks}
    for u, after in succ.items():
        for v in after:
            if mapping[u] != mapping[v]:
                edges[mapping[u]].add(mapping[v])
    for order in schedules:
        for a, b in zip(order, order[1:]):
            edges[a].add(b)
    degree = {task: 0 for task in tasks}
    for targets in edges.values():
        for task in targets:
            degree[task] += 1
    ready = deque(sorted(task for task, count in degree.items() if not count))
    visited = 0
    while ready:
        u = ready.popleft()
        visited += 1
        for v in sorted(edges[u]):
            degree[v] -= 1
            if not degree[v]:
                ready.append(v)
    if visited != len(tasks):
        raise UnsupportedStructure("new Task data plus core-order DAG is cyclic")
    return sum(map(len, edges.values()))


def _raw_task_pipe_lower_bound(mapping, ops):
    tasks = defaultdict(Counter)
    for node, task in mapping.items():
        op = ops[node]
        tasks[task][op["pipe"]] += max(1, op["cycles"])
    return max((max(work.values()) for work in tasks.values()), default=0)


def construct(graph, cores, base_plan):
    """Return one R6 plan and diagnostics; never invoke solver, E1, E0 or E2.

    ``base_plan`` is the caller's present-input baseline, not a saved result.
    Unsupported structure returns a copy of it with an explicit reason.
    The caller must perform E1/spill checks and its own quality guard later.
    """
    start = time.monotonic()
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("cores must be an integer in 1..5")
    baseline = deepcopy(base_plan)
    info = {"algorithm_id": "q1-branch-aid-r6", "status": "unsupported",
            "selected": "base", "scope": "structural construction only; no scoring",
            "task_limit": TASK_LIMIT, "extra_seconds_soft": EXTRA_SECONDS,
            "scoring_calls": {"E1": 0, "E0": 0, "E2": 0}}
    try:
        if len(baseline.get("core_schedules", [])) != cores:
            raise UnsupportedStructure("baseline core count differs from requested cores")
        view = derive_multicore_plan(graph, baseline)
        validate_task_order(view)
        if len(view["subgraph_ids"]) >= TASK_LIMIT:
            raise UnsupportedStructure("baseline leaves no room under the Task cap")
        height, waves = _wave_domain(view, cores)
        ops = {op["id"]: op for op in graph["ops"] if op["op"] not in COPY}
        _, full_succ = _build_op_adjacency(graph)
        pred, succ = _contract_excluded_copy_nodes(sorted(ops), full_succ)
        # Direct graph has the same op/tensor expansion but no traversal
        # through COPY nodes. The selected packet must agree with contracted.
        direct_succ = {u: full_succ[u] & ops.keys() for u in ops}
        all_op_ids = {op["id"] for op in graph["ops"]}
        tensor_ids = {tensor["id"] for tensor in graph["tensors"]}
        producers = defaultdict(set)
        for edge in graph["edges"]:
            if edge["source"] in all_op_ids and edge["target"] in tensor_ids:
                producers[edge["target"]].add(edge["source"])
        if any(len(ps) > 1 for ps in producers.values()):
            raise UnsupportedStructure("an original tensor has multiple compute producers")
        old_mapping = view["mapping"]
        if cores == 1:
            raise UnsupportedStructure("one core has no helper")
        next_id = max(view["subgraph_ids"], default=-1) + 1
        pieces = {}
        wave_diag = []
        for h in sorted(waves):
            _check_time(start)
            by_core = waves[h]
            members = {core: set(view["nodes_by_subgraph"][task])
                       for core, task in by_core.items()}
            packets = {core: _packets(group, pred, succ)
                       for core, group in members.items()}
            if any(len([u for u in packet if not (succ[u] & packet)]) != 1
                   or any((succ[u] & packet) != (direct_succ[u] & packet)
                          for u in packet)
                   for groups in packets.values() for packet in groups):
                continue
            # Every component in this actual height wave must be independent
            # of every other component, even across different old Tasks.
            node_wave = {u: core for core, group in members.items() for u in group}
            if any(v in node_wave and node_wave[v] != node_wave[u]
                   for u in node_wave for v in succ[u]):
                raise UnsupportedStructure("same-height old Tasks have a compute edge")
            loads = {core: _work(group, ops) for core, group in members.items()}
            for core in range(cores):
                loads.setdefault(core, Counter())
            total = Counter()
            for load in loads.values():
                total.update(load)
            if not total:
                continue
            pstar = min(total, key=lambda p: (-total[p], p))
            donors = [c for c in by_core if cores * loads[c][pstar] > total[pstar]]
            # R6 requires each helper's old L to be an actual independent
            # Task in this same wave; an idle core has no such witness.
            helpers = [c for c in by_core
                       if cores * loads[c][pstar] < total[pstar]]
            if not donors or not helpers:
                continue
            found = []
            for core in sorted(donors):
                task = by_core[core]
                witness = _witness(task, members[core], packets[core],
                                   pred, succ, direct_succ, ops,
                                   height, old_mapping, start)
                if witness is not None:
                    witness["core"] = core
                    found.append(witness)
            if not found:
                continue
            # Sort all eligible exports once, then greedily place each on a
            # different-role helper. A helper may receive multiple X Tasks.
            found.sort(key=lambda w: (-max(w["work"].values()), w["export_pred"]))
            new_loads = {c: Counter(loads[c]) for c in range(cores)}
            placement = defaultdict(list)
            for w in found:
                new_loads[w["core"]].subtract(w["work"])
                def key(c):
                    after = new_loads[c] + w["work"]
                    return max(after.values(), default=0), sum(after.values()), c
                helper = min(helpers, key=key)
                new_loads[helper].update(w["work"])
                placement[helper].append(w)
                w["helper"] = helper
            old_max = max(max(loads[c].values(), default=0) for c in range(cores))
            new_max = max(max(new_loads[c].values(), default=0) for c in range(cores))
            if new_max >= old_max:
                continue
            if len(view["subgraph_ids"]) + 2 * (len(pieces) + len(found)) > max(TASK_LIMIT, len(view["subgraph_ids"])):
                continue
            for export_order, w in enumerate(found):
                task = w["task"]
                pieces[task] = {"Y": task, "J": next_id, "X": next_id + 1,
                                "Y_nodes": w["Y"], "J_nodes": w["J"],
                                "X_nodes": w["X"], "helper": w["helper"],
                                "wave": h, "join": w["join"],
                                "export_order": export_order}
                next_id += 2
            wave_diag.append({"height": h, "dominant_pipe": pstar,
                              "old_max_pipe_work": old_max,
                              "new_max_pipe_work": new_max,
                              "donors": sorted(w["core"] for w in found),
                              "helpers": {str(c): [w["task"] for w in ws]
                                          for c, ws in sorted(placement.items())}})
        if not pieces:
            raise UnsupportedStructure("no wave passed the single bridge-join batch rule")
        new_mapping = dict(old_mapping)
        for old, p in pieces.items():
            for label in ("X", "Y", "J"):
                for node in p[label + "_nodes"]:
                    new_mapping[node] = p[label]
        exports_by_slot = defaultdict(list)
        # pieces were inserted by increasing wave and export_order.
        for p in pieces.values():
            exports_by_slot[(p["wave"], p["helper"])].append(p["X"])
        schedules = [[] for _ in range(cores)]
        for h in sorted(waves):
            by_core = waves[h]
            for core in range(cores):
                schedules[core].extend(exports_by_slot[(h, core)])
                if core in by_core:
                    old = by_core[core]
                    schedules[core].append(old)
                    if old in pieces:
                        schedules[core].append(pieces[old]["J"])
        if set(new_mapping) != set(ops) or len({t for order in schedules for t in order}) > max(TASK_LIMIT, len(view["subgraph_ids"])):
            raise UnsupportedStructure("coverage or Task budget failed")
        _check_time(start)
        edges = _task_dag(new_mapping, schedules, succ)
        plan = {"node_to_subgraph": new_mapping, "core_schedules": schedules}
        try:
            validate_task_order(derive_multicore_plan(graph, plan))
        except (ValueError, RuntimeError) as exc:
            raise UnsupportedStructure(f"final official plan/order guard failed: {exc}") from exc
        bandwidth = read_bandwidth_config(ROOT / "data/raw/a/official/data/config.txt")
        old_boundary = _boundary(graph, old_mapping, bandwidth)
        new_boundary = _boundary(graph, new_mapping, bandwidth)
        _check_time(start)
        info.update(status="candidate-unscored", selected="branch-aid",
                    waves=wave_diag, split_tasks=len(pieces),
                    tasks=sum(map(len, schedules)), augmented_dag_edges=edges,
                    task_raw_pipe_lower_bound=_raw_task_pipe_lower_bound(new_mapping, ops),
                    old_boundary=old_boundary, new_boundary=new_boundary,
                    boundary_delta={k: new_boundary.get(k, 0) - old_boundary.get(k, 0)
                                    for k in sorted(old_boundary.keys() | new_boundary.keys())},
                    warning="Task compilation, FIFO/MEM/spill, E1 and E0 remain unverified")
        return plan, info
    except UnsupportedStructure as exc:
        info["reason"] = str(exc)
        return baseline, info
