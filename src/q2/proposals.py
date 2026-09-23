"""Small deterministic proposal families; all costs are heuristics, not E0."""
from __future__ import annotations

from collections import Counter, defaultdict
import heapq
import itertools
import sys

from .construct import OFFICIAL


class GraphIndex:
    def __init__(self, graph):
        self.graph = graph
        sys.path.insert(0, str(OFFICIAL))
        try:
            from stub_multicore_cut_and_schedule import _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan
        finally:
            sys.path.pop(0)
        self.validate = derive_multicore_plan
        self.ops = {o['id']: o for o in graph['ops'] if o['op'] not in {'COPY_IN', 'COPY_OUT'}}
        _, full = _build_op_adjacency(graph)
        self.preds, self.succs = _contract_excluded_copy_nodes(sorted(self.ops), full)
        self.tensors = {t['id']: t for t in graph['tensors']}
        self.touch = {o: set() for o in self.ops}
        for edge in graph['edges']:
            a, b = edge['source'], edge['target']
            if a in self.ops and b in self.tensors:
                self.touch[a].add(b)
            if b in self.ops and a in self.tensors:
                self.touch[b].add(a)
        self.weights = {o: max(1, data['cycles']) for o, data in self.ops.items()}
        self.topo = self.order('id')
        self.tail = {}
        for o in reversed(self.topo):
            self.tail[o] = self.weights[o] + max((self.tail[s] for s in self.succs[o]), default=0)

    def order(self, policy, assignment=None):
        degree = {o: len(self.preds[o]) for o in self.ops}
        ready = [o for o in self.ops if degree[o] == 0]
        heapq.heapify(ready)
        ordered = []
        seen = set()
        remaining = Counter()
        if policy == 'frontier':
            for op in self.ops:
                remaining.update((assignment[op], t) for t in self.touch[op])

        def priority(op):
            if policy == 'critical':
                return (-self.tail[op], op)
            if policy == 'finish':
                return (self.tail[op], op)
            if policy == 'reverse-id':
                return (-op,)
            if policy == 'frontier':
                pairs = [(assignment[op], t) for t in self.touch[op]]
                delta = sum(self.tensors[t]['size'] for c, t in pairs if (c, t) not in seen)
                delta -= sum(self.tensors[t]['size'] for c, t in pairs if remaining[c, t] == 1)
                return (delta, self.tail[op], op)
            return (op,)

        while ready:
            # Bounded lookahead is a deliberate quality limitation, not a theorem.
            window = [heapq.heappop(ready) for _ in range(min(32, len(ready)))]
            chosen = min(window, key=priority)
            for op in window:
                if op != chosen:
                    heapq.heappush(ready, op)
            ordered.append(chosen)
            if policy == 'frontier':
                for t in self.touch[chosen]:
                    pair = assignment[chosen], t
                    seen.add(pair)
                    remaining[pair] -= 1
            for successor in sorted(self.succs[chosen]):
                degree[successor] -= 1
                if degree[successor] == 0:
                    heapq.heappush(ready, successor)
        if len(ordered) != len(self.ops):
            raise ValueError('dependency cycle in contracted graph')
        return ordered

    def packet_assignment(self, kind, policy, communication):
        parent = {o: o for o in self.ops}

        def find(op):
            while parent[op] != op:
                parent[op] = parent[parent[op]]
                op = parent[op]
            return op

        def union(a, b):
            a, b = find(a), find(b)
            parent[max(a, b)] = min(a, b)

        if kind in {'chain', 'component'}:
            for op in self.topo:
                for nxt in self.succs[op]:
                    if kind == 'component' or (len(self.succs[op]) == 1 and len(self.preds[nxt]) == 1):
                        union(op, nxt)
        else:
            for i in range(0, len(self.topo), 64):
                for op in self.topo[i:i+64]:
                    union(self.topo[i], op)
        packets = defaultdict(list)
        for op in self.topo:
            packets[find(op)].append(op)
        packet_preds, packet_succs = defaultdict(set), defaultdict(set)
        for op in self.topo:
            for nxt in self.succs[op]:
                a, b = find(op), find(nxt)
                if a != b:
                    packet_preds[b].add(a)
                    packet_succs[a].add(b)
        ready = [p for p in packets if not packet_preds[p]]
        degree = {p: len(packet_preds[p]) for p in packets}
        loads = [Counter() for _ in range(4)]
        assigned, ordering = {}, []
        while ready:
            packet = min(ready, key=lambda p: (-max(self.tail[o] for o in packets[p]), p)
                         if policy == 'critical' else (p,))
            ready.remove(packet)
            work = Counter()
            for op in packets[packet]:
                work[self.ops[op]['pipe']] += self.weights[op]

            def score(core):
                load = max((loads[core][pipe] + value for pipe, value in work.items()), default=0)
                # This penalty is not spill accounting or a true communication duration.
                cut = sum(assigned[p] != core for p in packet_preds[packet])
                return (load + communication * 500 * cut, sum(loads[core].values()), core)

            core = min(range(4), key=score)
            assigned[packet] = core
            loads[core].update(work)
            ordering.extend(packets[packet])
            for nxt in sorted(packet_succs[packet]):
                degree[nxt] -= 1
                if degree[nxt] == 0:
                    ready.append(nxt)
        if len(ordering) != len(self.ops):
            raise ValueError('packet contraction creates a cycle')
        return {o: assigned[find(o)] for o in self.ops}, {o: find(o) for o in self.ops}, ordering

    def plan(self, assignment, order, grain=1, packets=None):
        schedules = [[] for _ in range(4)]
        op_group = {}
        if packets is not None:
            ids = {}
            for op in order:
                packet = packets[op]
                if packet not in ids:
                    ids[packet] = len(ids)
                    schedules[assignment[op]].append(ids[packet])
                op_group[op] = ids[packet]
        else:
            counts, last, next_id = [0]*4, [None]*4, 0
            for op in order:
                core = assignment[op]
                if counts[core] % grain == 0:
                    last[core] = next_id
                    next_id += 1
                    schedules[core].append(last[core])
                op_group[op] = last[core]
                counts[core] += 1
        # Preserve baseline's deterministic original topological mapping iteration order.
        plan = {'node_to_subgraph': {str(o): op_group[o] for o in self.topo},
                'core_schedules': schedules}
        self.validate(self.graph, plan)
        return plan


def specifications(method):
    if method == 'M1':
        return [dict(kind=k, policy=p, communication=c, grain=g)
                for k, p, c, g in itertools.product(
                    ('chain', 'component', 'topo64'), ('id', 'critical'), (0, 1), ('packet', 'singleton'))]
    if method == 'M2':
        return [dict(policy=p, grain=g) for g, p in itertools.product(
            (1, 2, 4, 8, 16, 64), ('id', 'critical', 'finish', 'frontier', 'reverse-id'))]
    return []


def propose(index, method, specification, baseline):
    if method == 'M1':
        assignment, packets, order = index.packet_assignment(
            specification['kind'], specification['policy'], specification['communication'])
        return index.plan(assignment, order, packets=packets if specification['grain'] == 'packet' else None)
    group_core = {g: c for c, schedule in enumerate(baseline['core_schedules']) for g in schedule}
    assignment = {int(o): group_core[g] for o, g in baseline['node_to_subgraph'].items()}
    order = index.order(specification['policy'], assignment)
    return index.plan(assignment, order, grain=specification['grain'])
