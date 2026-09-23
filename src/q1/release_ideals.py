"""Pure Q1 split-construction kernels, not an evaluator or makespan model.

The caller must supply the official COPY-contracted computation DAG, a valid
parent augmented Task DAG, and release labels bound to that exact parent.
No local execution schedule or DDR backing is inherited by a split.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import heapq
from typing import Mapping


@dataclass(frozen=True)
class Net:
    tensor: int
    pins: frozenset[int]
    weight: int


def topological(predecessors: Mapping[int, set[int]]) -> list[int]:
    nodes = set(predecessors)
    if any(not set(pred) <= nodes for pred in predecessors.values()):
        raise ValueError('Predecessors must be internal to this Task')
    successors = {v: [] for v in nodes}
    degree = {v: len(pred) for v, pred in predecessors.items()}
    for v, pred in predecessors.items():
        for u in pred:
            successors[u].append(v)
    ready = [v for v in nodes if degree[v] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in successors[u]:
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, v)
    if len(order) != len(nodes):
        raise ValueError('Computation dependency cycle')
    return order


def is_ideal(members, predecessors) -> bool:
    chosen = set(members)
    return chosen <= set(predecessors) and all(set(predecessors[v]) <= chosen for v in chosen)


def closure(anchors, predecessors) -> frozenset[int]:
    pending = list(anchors)
    if not set(pending) <= set(predecessors):
        raise ValueError('Unknown output anchor')
    selected = set()
    while pending:
        v = pending.pop()
        if v not in selected:
            selected.add(v)
            pending.extend(predecessors[v])
    return frozenset(selected)


def release_labels(predecessors, external_release, core_floor=0) -> dict[int, int]:
    """Propagate gates only, without adding cycles or treating DDR as ready."""
    if not set(external_release) <= set(predecessors):
        raise ValueError('External release contains unknown operation')
    labels = {}
    for v in topological(predecessors):
        labels[v] = max([core_floor, external_release.get(v, core_floor)] +
                        [labels[u] for u in predecessors[v]])
    return labels


def threshold_buckets(labels) -> list[tuple[int, frozenset[int]]]:
    """Incremental buckets; avoids materializing every full plan or ideal."""
    groups = {}
    for v, value in labels.items():
        groups.setdefault(value, set()).add(v)
    return [(value, frozenset(groups[value])) for value in sorted(groups)]


def tensor_views(graph):
    ops = {op['id']: op for op in graph['ops']}
    tensors = {t['id']: t for t in graph['tensors']}
    producers = {t: set() for t in tensors}
    consumers = {t: set() for t in tensors}
    for edge in graph['edges']:
        u, v = edge['source'], edge['target']
        if u in ops and v in tensors:
            producers[v].add(u)
        elif u in tensors and v in ops:
            consumers[u].add(v)
    return ops, tensors, producers, consumers


def split_nets(graph, compute_ids, parent_members) -> list[Net]:
    """Exact *pre-spill* Q1 boundary-byte increments for one Task bisection.

    Raw tensor identity follows the official builder. Never coalesce pins by
    logical_tid, DDR backing, or COPY contraction. Multiple producers are an
    explicitly unsupported domain, not silently approximated.
    """
    compute_ids, members = set(compute_ids), set(parent_members)
    ops, tensors, producers, consumers = tensor_views(graph)
    eligible = {v for v, op in ops.items() if op['op'] not in {'COPY_IN', 'COPY_OUT'}}
    if not members <= compute_ids or compute_ids != eligible:
        raise ValueError('Task members must be eligible compute operations')
    if any(ops[v]['op'] in {'COPY_IN', 'COPY_OUT'} for v in compute_ids):
        raise ValueError('COPY operations cannot be submitted Task members')
    nets = []
    for tid, tensor in tensors.items():
        prod, cons = producers[tid], consumers[tid]
        if len(prod) > 1:
            raise ValueError('Single-producer tensor guard failed')
        size = tensor['size']
        if not isinstance(size, int) or size < 0:
            raise ValueError('Tensor size must be a nonnegative integer')
        local_prod = prod & members
        local_cons = cons & members
        if local_prod:
            eligible_cons = cons & compute_ids
            already_exported = (any(ops[v]['op'] == 'COPY_OUT' for v in cons)
                                or not eligible_cons or bool(eligible_cons - members))
            pins = local_prod | local_cons
            weight = (2 - int(already_exported)) * size
        else:
            pins, weight = local_cons, size
        if len(pins) >= 2 and weight:
            nets.append(Net(tid, frozenset(pins), weight))
    return nets


def cut_bytes(nets, chosen) -> int:
    chosen = set(chosen)
    return sum(net.weight for net in nets if net.pins & chosen and net.pins - chosen)


def threshold_costs(nets, labels) -> list[tuple[int, int]]:
    """All maximal threshold ideal costs via net min/max label intervals."""
    values = sorted(set(labels.values()))
    deltas = dict.fromkeys(values, 0)
    for net in nets:
        lo, hi = min(labels[v] for v in net.pins), max(labels[v] for v in net.pins)
        if lo < hi:
            deltas[lo] += net.weight
            deltas[hi] -= net.weight
    total, rows = 0, []
    for value in values:
        total += deltas[value]
        rows.append((value, total))
    return rows


def partial_ideal(predecessors, nets, work, *, upper=None, forced=(),
                  price_numerator=1, price_denominator=1) -> dict:
    """Minimize denominator * cut bytes - numerator * additive work.

    Lawler hyperedge expansion and reversed dependency arcs. This scalar
    proxy is exact within its domain; it is not a time bound or safe pruning
    rule. Empty/full solutions are returned so the caller can reject them.
    SciPy's Dinic max-flow is loaded only when this optional branch is used.
    """
    order = topological(predecessors)
    nodes = set(order)
    upper = nodes if upper is None else set(upper)
    forced = set(forced)
    if not is_ideal(upper, predecessors) or not is_ideal(forced, predecessors) or not forced <= upper:
        raise ValueError('Require ideal forced subset of ideal upper bound')
    if set(work) != nodes or any(not isinstance(w, int) or w <= 0 for w in work.values()):
        raise ValueError('Require a positive integer additive work for every node')
    if (not isinstance(price_numerator, int) or price_numerator < 0
            or not isinstance(price_denominator, int) or price_denominator <= 0):
        raise ValueError('Require a nonnegative rational price')
    if any(not net.pins <= nodes or not isinstance(net.weight, int) or net.weight < 0 for net in nets):
        raise ValueError('Invalid hyperedge domain')
    finite = sum(net.weight * price_denominator for net in nets) + sum(work.values()) * price_numerator
    # Conservative bound protects both merged arcs and total flow across
    # SciPy integer-capacity implementations; no float/rounding approximation.
    if finite >= 2**30:
        raise ValueError('Integer capacity guard: reduce exact rational scale or skip this price')
    inf = finite + 1
    index = {v: i+2 for i, v in enumerate(order)}
    edges = {}
    def add(u, v, cap):
        if cap:
            edges[u, v] = edges.get((u, v), 0) + cap
    for v in order:
        add(0, index[v], price_numerator * work[v])
        if v in forced:
            add(0, index[v], inf)
        if v not in upper:
            add(index[v], 1, inf)
        for u in predecessors[v]:
            add(index[v], index[u], inf)
    for i, net in enumerate(nets):
        a, b = 2 + len(order) + 2*i, 3 + len(order) + 2*i
        add(a, b, price_denominator * net.weight)
        for v in net.pins:
            add(index[v], a, inf)
            add(b, index[v], inf)
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import maximum_flow
    n = 2 + len(order) + 2*len(nets)
    matrix = csr_matrix(([cap for cap in edges.values()],
                         ([u for u,v in edges], [v for u,v in edges])), shape=(n,n), dtype='int64')
    flow = maximum_flow(matrix, 0, 1, method='dinic')
    residual = (matrix - flow.flow).tocsr()
    reached, queue = {0}, deque([0])
    while queue:
        u = queue.popleft()
        for pos in range(residual.indptr[u], residual.indptr[u+1]):
            v = int(residual.indices[pos])
            if residual.data[pos] > 0 and v not in reached:
                reached.add(v); queue.append(v)
    selected = frozenset(v for v in order if index[v] in reached)
    assert is_ideal(selected, predecessors) and forced <= selected <= upper
    byte_cost = cut_bytes(nets, selected)
    work_sum = sum(work[v] for v in selected)
    objective = price_denominator * byte_cost - price_numerator * work_sum
    assert objective == int(flow.flow_value) - price_numerator * sum(work.values())
    return {'members':sorted(selected), 'boundary_added_bytes':byte_cost, 'additive_work':work_sum,
            'scaled_objective':objective, 'proper_nonempty':bool(selected) and selected != nodes,
            'scope':'Exact boundary/work scalar subproblem, not makespan dominance'}
