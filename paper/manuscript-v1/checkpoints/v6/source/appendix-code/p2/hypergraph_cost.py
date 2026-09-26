"""Exact pre-Step2 original COPY bytes for the unique-producer physical domain.

This is a placement cost, not a Makespan bound or an evaluator. No scheduling,
capacity, spill, or memory contention is represented.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Mapping


class UnsupportedHypergraph(ValueError):
    """The exact connectivity reduction does not apply to this graph."""


@dataclass(frozen=True)
class Edge:
    pins: frozenset[int]
    weight: int


class HypergraphCost:
    def __init__(self, graph: dict, eligible_ids):
        original = {op['id']: op for op in graph['ops']}
        eligible = set(eligible_ids)
        expected = {u for u, op in original.items() if op['op'] not in {'COPY_IN', 'COPY_OUT'}}
        if eligible != expected:
            raise UnsupportedHypergraph('eligible IDs must equal all original non-COPY operations')
        tensors = {t['id']: t for t in graph['tensors']}
        for tensor in tensors.values():
            if 'logical_tid' in tensor:
                raise UnsupportedHypergraph('logical tensor alias')
            if type(tensor['size']) is not int or tensor['size'] < 0:
                raise UnsupportedHypergraph('tensor size must be a nonnegative integer')
        producers, consumers = defaultdict(set), defaultdict(set)
        direct = []
        for edge in graph['edges']:
            src, dst = edge['source'], edge['target']
            if src in original and dst in tensors:
                producers[dst].add(src)
            elif src in tensors and dst in original:
                consumers[src].add(dst)
            elif src in eligible and dst in eligible and src != dst:
                direct.append(edge)  # Preserve duplicate direct edges.
        if any(len(ps) > 1 for ps in producers.values()):
            raise UnsupportedHypergraph('physical tensor has multiple original producers')
        self.eligible = frozenset(eligible)
        self.edges: list[Edge] = []
        self.constant_bytes = 0
        incidence = defaultdict(list)

        def add(pins, weight):
            if pins and weight:
                edge_id = len(self.edges)
                self.edges.append(Edge(frozenset(pins), weight))
                for u in pins:
                    incidence[u].append(edge_id)

        for tid in sorted(tensors):
            size = tensors[tid]['size']
            ps = producers[tid] & eligible
            cs = consumers[tid] & eligible
            if not (ps or cs):
                continue
            if ps:
                producer = next(iter(ps))
                if any(original[u]['op'] == 'COPY_OUT' for u in consumers[tid]) or not cs:
                    self.constant_bytes += size
                add(cs | {producer}, 2 * size)
            else:
                self.constant_bytes += size
                add(cs, size)
        for edge in direct:
            try:
                size = max(0, int(edge.get('data_size', 0)))
            except (TypeError, ValueError, OverflowError) as error:
                raise UnsupportedHypergraph('invalid direct edge data_size') from error
            add({edge['source'], edge['target']}, 2 * size)
        self.incidence = {u: tuple(incidence[u]) for u in eligible}

    def state(self, op_to_core: Mapping[int, int]) -> HypergraphState:
        if set(op_to_core) != self.eligible or any(type(c) is not int or c < 0 for c in op_to_core.values()):
            raise ValueError('assignment must map every eligible op to a nonnegative integer core')
        assignment = dict(op_to_core)
        counts = [Counter(assignment[u] for u in edge.pins) for edge in self.edges]
        total = self.constant_bytes + sum(edge.weight * (len(count) - 1)
                                          for edge, count in zip(self.edges, counts))
        return HypergraphState(self, assignment, counts, total)


class HypergraphState:
    def __init__(self, model, assignment, counts, total_bytes):
        self.model = model
        self.assignment = assignment
        self.counts = counts
        self.total_bytes = total_bytes

    def _move(self, group, source, target):
        pins = set(group)
        if not pins or not pins <= self.model.eligible or source == target:
            raise ValueError('move requires a nonempty eligible group and distinct cores')
        if type(source) is not int or type(target) is not int or source < 0 or target < 0:
            raise ValueError('core IDs must be nonnegative integers')
        if any(self.assignment[u] != source for u in pins):
            raise ValueError('all moving pins must currently share source core')
        touched = Counter(e for u in pins for e in self.model.incidence[u])
        delta = sum(self.model.edges[e].weight *
                    ((self.counts[e][target] == 0) - (self.counts[e][source] == moved))
                    for e, moved in touched.items())
        return pins, touched, delta

    def delta(self, group, source: int, target: int) -> int:
        """Exact byte change, inspecting only edges incident to moving pins."""
        return self._move(group, source, target)[2]

    def apply(self, group, source: int, target: int) -> int:
        """Move original pins in place and return exact byte change."""
        pins, touched, delta = self._move(group, source, target)
        for e, moved in touched.items():
            counts = self.counts[e]
            counts[source] -= moved
            if counts[source] == 0:
                del counts[source]
            counts[target] += moved
        for u in pins:
            self.assignment[u] = target
        self.total_bytes += delta
        return delta
