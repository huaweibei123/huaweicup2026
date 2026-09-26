# 本程序及代码是在人工智能工具辅助下完成的。
# 代码生成主要使用 GPT-6 系列模型辅助。
# 工具名称：GPT-6 Astra；版本/型号：gpt-6-astra。
# 开发机构/公司：OpenAI；版本颁布日期：2026-09-03。
# 日期指 Astra 模型发布日，不是安装日或知识截止日。
# 本展示版仅新增声明，原始程序内容保持不变。
# 依据：竞赛人工智能工具及输出使用规定（2026）第5条。

"""Exact two-label connectivity cut and a baseline-safe Pipe load guard.

This module handles an abstract weighted hypergraph only. It does not construct
or evaluate a hardware schedule. Unit IDs are integers or strings.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable, Mapping

Unit = int | str


@dataclass(frozen=True)
class Hyperedge:
    pins: frozenset[Unit]
    fixed_cores: frozenset[int]
    weight: int


@dataclass(frozen=True)
class CutResult:
    labels: dict[Unit, int]
    cost: int
    flow: int
    offset: int


@dataclass(frozen=True)
class GuardedCutResult:
    labels: dict[Unit, int]
    cost: int
    loads: dict[int, dict[str, int]]
    anchored: frozenset[Unit]
    flow_calls: int


def _key(unit: Unit) -> tuple[str, str]:
    if type(unit) not in (int, str):
        raise TypeError('unit IDs must be int or str')
    return type(unit).__name__, str(unit)


def _prepare(units: Iterable[Unit], edges: Iterable[Hyperedge], a: int, b: int):
    if type(a) is not int or type(b) is not int or a == b:
        raise ValueError('a and b must be distinct integer labels')
    order = sorted(set(units), key=_key)
    if len({_key(u) for u in order}) != len(order):
        raise ValueError('unit IDs have ambiguous stable keys')
    universe = set(order)
    rows = tuple(edges)
    for edge in rows:
        if not isinstance(edge, Hyperedge):
            raise TypeError('edges must be Hyperedge instances')
        if not edge.pins and not edge.fixed_cores:
            raise ValueError('empty hyperedge')
        if not edge.pins <= universe:
            raise ValueError('edge pin is outside free units')
        if type(edge.weight) is not int or edge.weight < 0:
            raise ValueError('edge weight must be a nonnegative integer')
        if any(type(c) is not int for c in edge.fixed_cores):
            raise ValueError('fixed cores must be integer labels')
    return order, rows


def connectivity_cost(labels: Mapping[Unit, int], edges: Iterable[Hyperedge]) -> int:
    """Independently evaluate the requested connectivity objective."""
    total = 0
    for edge in edges:
        if not edge.pins and not edge.fixed_cores:
            raise ValueError('empty hyperedge')
        cores = set(edge.fixed_cores)
        cores.update(labels[u] for u in edge.pins)
        total += edge.weight * (len(cores) - 1)
    return total


class _Dinic:
    def __init__(self, n: int):
        self.graph: list[list[list[int]]] = [[] for _ in range(n)]

    def add(self, u: int, v: int, capacity: int) -> None:
        forward = [v, len(self.graph[v]), capacity]
        reverse = [u, len(self.graph[u]), 0]
        self.graph[u].append(forward)
        self.graph[v].append(reverse)

    def maxflow(self, source: int, sink: int) -> tuple[int, set[int]]:
        graph = self.graph
        n = len(graph)
        total = 0
        while True:
            level = [-1] * n
            level[source] = 0
            queue = deque([source])
            while queue:
                u = queue.popleft()
                for v, _, capacity in graph[u]:
                    if capacity and level[v] < 0:
                        level[v] = level[u] + 1
                        queue.append(v)
            if level[sink] < 0:
                break
            cursor = [0] * n
            while True:
                vertices = [source]
                path: list[tuple[int, int]] = []
                while vertices and vertices[-1] != sink:
                    u = vertices[-1]
                    while cursor[u] < len(graph[u]):
                        v, _, capacity = graph[u][cursor[u]]
                        if capacity and level[v] == level[u] + 1:
                            break
                        cursor[u] += 1
                    if cursor[u] == len(graph[u]):
                        vertices.pop()
                        if path:
                            parent, arc = path.pop()
                            cursor[parent] = arc + 1
                    else:
                        arc = cursor[u]
                        path.append((u, arc))
                        vertices.append(graph[u][arc][0])
                if not vertices:
                    break
                pushed = min(graph[u][arc][2] for u, arc in path)
                for u, arc in path:
                    edge = graph[u][arc]
                    edge[2] -= pushed
                    graph[edge[0]][edge[1]][2] += pushed
                total += pushed
        reachable = {source}
        queue = deque([source])
        while queue:
            u = queue.popleft()
            for v, _, capacity in graph[u]:
                if capacity and v not in reachable:
                    reachable.add(v)
                    queue.append(v)
        return total, reachable


def binary_hypercut(
    units: Iterable[Unit], edges: Iterable[Hyperedge], a: int, b: int,
    anchors: Mapping[Unit, int] | None = None,
) -> CutResult:
    """Minimize sum(weight * (number of touched cores - 1)) exactly.

Source side has label a. Runtime is the usual Dinic O(V²E) worst case;
    all traversal is iterative, and integer capacities are unbounded Python ints.
    """
    order, rows = _prepare(units, edges, a, b)
    fixed = dict(anchors or {})
    if not set(fixed) <= set(order) or any(label not in (a, b) for label in fixed.values()):
        raise ValueError('anchors must assign known units to a or b')
    finite_sum = sum(edge.weight * (int(a not in edge.fixed_cores) +
                                    int(b not in edge.fixed_cores)) for edge in rows)
    infinity = finite_sum + 1
    source, sink = 0, 1
    index = {unit: i + 2 for i, unit in enumerate(order)}
    flow_graph = _Dinic(len(order) + 2 + 2 * len(rows))
    next_node = len(order) + 2
    offset = 0
    for edge in rows:
        offset += edge.weight * (len(edge.fixed_cores) - 1)
        if not edge.pins or edge.weight == 0:
            continue
        # OR(any pin is a): x_a -> auxiliary -> sink.
        if a not in edge.fixed_cores:
            auxiliary = next_node
            next_node += 1
            for unit in edge.pins:
                flow_graph.add(index[unit], auxiliary, infinity)
            flow_graph.add(auxiliary, sink, edge.weight)
        # OR(any pin is b): source -> auxiliary -> x_b.
        if b not in edge.fixed_cores:
            auxiliary = next_node
            next_node += 1
            flow_graph.add(source, auxiliary, edge.weight)
            for unit in edge.pins:
                flow_graph.add(auxiliary, index[unit], infinity)
    for unit, label in fixed.items():
        if label == a:
            flow_graph.add(source, index[unit], infinity)
        else:
            flow_graph.add(index[unit], sink, infinity)
    flow, reachable = flow_graph.maxflow(source, sink)
    if flow >= infinity:
        raise AssertionError('a feasible anchored labeling must avoid infinite arcs')
    labels = {unit: a if index[unit] in reachable else b for unit in order}
    cost = connectivity_cost(labels, rows)
    if cost != offset + flow:
        raise AssertionError('flow reduction disagrees with direct connectivity cost')
    return CutResult(labels, cost, flow, offset)


def load_guarded_cut(
    units: Iterable[Unit], edges: Iterable[Hyperedge], a: int, b: int,
    initial: Mapping[Unit, int], work: Mapping[Unit, Mapping[str, int]],
    outside: Mapping[int, Mapping[str, int]], caps: Mapping[int, Mapping[str, int]],
) -> GuardedCutResult:
    """Repeatedly anchor incoming movers until caller-supplied Pipe caps hold.

    Requires the initial assignment to satisfy every supplied cap. Does not
    bound official makespan, memory, spill, or schedule legality.
    """
    order, rows = _prepare(units, edges, a, b)
    if set(initial) != set(order) or any(label not in (a, b) for label in initial.values()):
        raise ValueError('initial must label every unit with a or b')
    if set(work) != set(order):
        raise ValueError('work must have one record per unit')
    pipes = set(caps.get(a, {})) | set(caps.get(b, {}))
    for core in (a, b):
        if core not in caps:
            raise ValueError('both cores need caps')
        if set(caps[core]) != pipes:
            raise ValueError('both cores need the same Pipe caps')
        if any(type(v) is not int or v < 0 for v in caps[core].values()):
            raise ValueError('caps must be nonnegative integers')
        if any(pipe not in pipes or type(v) is not int or v < 0
               for pipe, v in outside.get(core, {}).items()):
            raise ValueError('outside work must be nonnegative and use capped Pipes')
    for unit in order:
        if any(pipe not in pipes or type(v) is not int or v < 0
               for pipe, v in work[unit].items()):
            raise ValueError('unit work must be nonnegative and use capped Pipes')

    def loads(labels: Mapping[Unit, int]) -> dict[int, dict[str, int]]:
        result = {core: {pipe: outside.get(core, {}).get(pipe, 0) for pipe in pipes}
                  for core in (a, b)}
        for unit in order:
            for pipe, amount in work[unit].items():
                result[labels[unit]][pipe] += amount
        return result

    baseline_loads = loads(initial)
    if any(baseline_loads[c][p] > caps[c][p] for c in (a, b) for p in pipes):
        raise ValueError('initial assignment violates a Pipe cap')
    baseline_cost = connectivity_cost(initial, rows)
    anchored: dict[Unit, int] = {}
    for call in range(1, len(order) + 2):
        cut = binary_hypercut(order, rows, a, b, anchored)
        current_loads = loads(cut.labels)
        violations = [(c, p) for c in (a, b) for p in sorted(pipes)
                      if current_loads[c][p] > caps[c][p]]
        if not violations:
            if cut.cost > baseline_cost:
                raise AssertionError('baseline is feasible for every anchored cut')
            return GuardedCutResult(cut.labels, cut.cost, current_loads,
                                    frozenset(anchored), call)
        core, pipe = violations[0]
        movers = [unit for unit in order if cut.labels[unit] == core
                  and initial[unit] != core and work[unit].get(pipe, 0) > 0]
        if not movers:
            raise AssertionError('overload without a positive incoming mover')
        chosen = min(movers, key=lambda u: (-work[u][pipe], _key(u)))
        anchored[chosen] = initial[chosen]
    raise AssertionError('load guard exceeded its finite anchoring bound')
