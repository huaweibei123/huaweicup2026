"""Pure-compute binary reduction-tree constructor. NOT an official evaluator.

Model: fixed operation durations and pipes; one slot per (core, pipe);
FIFO = per-core word projected onto each pipe; remote dependency lag=delta.
No COPY cost, L1/UB, backing, Cache, bandwidth or Step3 memory-reuse edges.

Time-only DP is exact for the LOCAL / sequential-team / disjoint-team witness
family documented in the accompanying answer, not globally optimal scheduling.
Emitted JSON has singleton subgraphs and exactly the two submission fields.
A graph-to-this-model adapter must independently verify every contracted edge.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
import heapq
from typing import Mapping, Sequence

NEG = None  # exact negative infinity; all finite arithmetic uses Python integers


def rowmax(rows):
    return [max((r[j] for r in rows if r[j] is not None), default=None)
            for j in range(len(rows[0]))]


def rowmul(row, matrix):
    return [max((a + matrix[i][j] for i, a in enumerate(row)
                 if a is not None and matrix[i][j] is not None), default=None)
            for j in range(len(matrix[0]))]


def matmul(left, right):
    return [rowmul(row, right) for row in left]


def identity(d):
    return [[0 if i == j else None for j in range(d)] for i in range(d)]


@dataclass(frozen=True)
class Node:
    id: int
    cycles: int
    pipe: str


@dataclass
class Model:
    nodes: Mapping[int, Node]
    children: Mapping[int, Sequence[int]]
    # A fixed DFS child order is part of the LOCAL family. It can be supplied
    # by a separately checked memory-oriented child-ordering routine.
    edge_payload: Mapping[tuple[int, int], int] | None = None

    def validate(self):
        if not self.nodes:
            raise ValueError('empty tree')
        parents = {}
        for v, node in self.nodes.items():
            if type(v) is not int or node.id != v:
                raise ValueError('IDs must be matching integers')
            if type(node.cycles) is not int or node.cycles < 1 or not node.pipe:
                raise ValueError('positive integer durations and a pipe are required')
            ch = list(self.children.get(v, ()))
            if len(ch) > 2 or len(ch) != len(set(ch)):
                raise ValueError('this implementation requires an actual binary tree')
            for u in ch:
                if u not in self.nodes or u in parents:
                    raise ValueError('unknown child, duplicate parent or non-forest')
                parents[u] = v
        if set(self.children) - set(self.nodes):
            raise ValueError('unknown parent')
        roots = set(self.nodes) - set(parents)
        if len(roots) != 1:
            raise ValueError('constructor expects one tree, not a forest')
        root = next(iter(roots))
        order, seen, stack = [], set(), [(root, False)]
        while stack:
            v, expanded = stack.pop()
            if expanded:
                order.append(v)
            else:
                if v in seen:
                    raise ValueError('cycle or repeated node')
                seen.add(v)
                stack.append((v, True))
                stack.extend((u, False) for u in reversed(self.children.get(v, ())))
        if seen != set(self.nodes):
            raise ValueError('disconnected cycle')
        return root, order


def local_signatures(model: Model, order: Sequence[int]):
    """Exact max-plus resource signatures for each fixed-DFS closed subtree.

    State = [constant zero, all input pipe-availability times].
    R[v] maps state to output availability; f[v] maps state to root finish.
    Keeping f for each child is essential; do not replace it by max(all pipes),
    which can incorrectly wait for an unrelated earlier job.
    """
    pipes = sorted({node.pipe for node in model.nodes.values()})
    pidx = {p: i + 1 for i, p in enumerate(pipes)}
    dim = len(pipes) + 1
    R, f, duration = {}, {}, {}
    for v in order:
        avail = identity(dim)
        child_finishes = []
        for u in model.children.get(v, ()):
            child_finishes.append(rowmul(f[u], avail))
            avail = matmul(R[u], avail)
        row = rowmax([avail[pidx[model.nodes[v].pipe]], avail[0], *child_finishes])
        row = [None if a is None else a + model.nodes[v].cycles for a in row]
        avail[pidx[model.nodes[v].pipe]] = row
        R[v], f[v] = avail, row
        duration[v] = max(a for a in row if a is not None)  # state all zero
    return pipes, R, f, duration


def construct(model: Model, cores: int, delta: int = 500):
    """Return (two-field singleton plan, metadata) without official evaluation."""
    if type(cores) is not int or cores < 1:
        raise ValueError('positive core count required')
    if type(delta) is not int or delta < 0:
        raise ValueError('nonnegative integer lag required')
    root, order = model.validate()
    _, _, _, local = local_signatures(model, order)
    H, choice = {}, {}
    for v in order:
        ch = list(model.children.get(v, ()))
        w = model.nodes[v].cycles
        for q in range(1, cores + 1):
            candidates = [(local[v], ('LOCAL',))]
            if q > 1:
                candidates.append((H[v, q - 1], ('LESS',)))
            if len(ch) == 1:
                candidates.append((H[ch[0], q] + w, ('UNARY',)))
            elif len(ch) == 2:
                a, b = ch
                candidates.append((H[a, q] + H[b, q] + w, ('SEQ',)))
                for i in range(1, q):
                    A, B = H[a, i], H[b, q - i]
                    candidates.append((max(A, B + delta) + w, ('PAR_A', i)))
                    candidates.append((max(A + delta, B) + w, ('PAR_B', i)))
            # Stable tie break prefers LOCAL, then fewer cores, then SEQ.
            H[v, q], choice[v, q] = min(candidates, key=lambda item: item[0])

    words = [[] for _ in range(cores)]
    stack = [('EMIT', root, cores, tuple(range(cores)))]
    while stack:
        action, v, q, team = stack.pop()
        if action == 'APPEND':
            words[team[0]].append(v)
            continue
        tag, *params = choice[v, q]
        ch = list(model.children.get(v, ()))
        if tag == 'LOCAL':
            todo = [(v, False)]
            while todo:
                x, done = todo.pop()
                if done:
                    words[team[0]].append(x)
                else:
                    todo.append((x, True))
                    todo.extend((u, False) for u in reversed(model.children.get(x, ())))
        elif tag == 'LESS':
            stack.append(('EMIT', v, q - 1, team[:-1]))
        else:
            stack.append(('APPEND', v, q, team))
            if tag == 'UNARY':
                stack.append(('EMIT', ch[0], q, team))
            elif tag == 'SEQ':
                stack.extend([('EMIT', ch[1], q, team), ('EMIT', ch[0], q, team)])
            else:
                i = params[0]
                if tag == 'PAR_A':
                    ta, tb = team[:i], team[i:]
                else:
                    tb, ta = team[:q-i], team[q-i:]
                stack.extend([('EMIT', ch[1], q-i, tb), ('EMIT', ch[0], i, ta)])
    # Stable IDs can be changed to match Index.order by the caller.
    mapping = {str(v): i for i, v in enumerate(sorted(model.nodes))}
    plan = {'node_to_subgraph': mapping,
            'core_schedules': [[mapping[str(v)] for v in word] for word in words]}
    exact = evaluate_abstract(model, words, delta)
    if exact['makespan'] > H[root, cores]:
        raise AssertionError('emission violates its abstract witness bound')
    owners = {v: c for c, word in enumerate(words) for v in word}
    cuts = [(u, v) for v in model.nodes for u in model.children.get(v, ())
            if owners[u] != owners[v]]
    return plan, {'abstract_only': True, 'abstract_witness_upper': H[root, cores],
                  'abstract_fifo_makespan': exact['makespan'], 'words': words,
                  'cut_edges': cuts,
                  'cut_payload_bytes': (None if model.edge_payload is None else
                      sum(model.edge_payload[e] for e in cuts)),
                  'official_evaluated': False}


def evaluate_abstract(model: Model, words: Sequence[Sequence[int]], delta=500):
    """Exact longest path for the supplied compute model, not an E0 substitute."""
    flattened = [v for word in words for v in word]
    if len(flattened) != len(set(flattened)) or set(flattened) != set(model.nodes):
        raise ValueError('words must cover every operation once')
    owner = {v: c for c, word in enumerate(words) for v in word}
    succ = {v: {} for v in model.nodes}
    pred = {v: {} for v in model.nodes}
    def add(u, v, lag):
        succ[u][v] = max(succ[u].get(v, 0), lag)
        pred[v][u] = succ[u][v]
    for v in model.nodes:
        for u in model.children.get(v, ()):
            add(u, v, delta if owner[u] != owner[v] else 0)
    for word in words:
        last = {}
        for v in word:
            pipe = model.nodes[v].pipe
            if pipe in last:
                add(last[pipe], v, 0)
            last[pipe] = v
    degree = {v: len(pred[v]) for v in model.nodes}
    ready = [v for v in model.nodes if not degree[v]]
    heapq.heapify(ready)
    finishes, starts = {}, {}
    while ready:
        v = heapq.heappop(ready)
        starts[v] = max((finishes[u] + lag for u, lag in pred[v].items()), default=0)
        finishes[v] = starts[v] + model.nodes[v].cycles
        for t in succ[v]:
            degree[t] -= 1
            if not degree[t]:
                heapq.heappush(ready, t)
    if len(finishes) != len(model.nodes):
        raise ValueError('enhanced compute graph contains a cycle')
    return {'makespan': max(finishes.values()), 'start': starts, 'finish': finishes}


def step2_interval_peak(tensors, edges, seq):
    """Exact NO-SPILL interval peak on the SAME pre-Step2 Task graph/sequence.

    Not applicable to raw compute-only JSON, post-spill logical IDs, or a
    hypothetical timing witness. Does not certify Step3 memory-reuse overhead.
    'pos' is kept literal (L1 / UB); DDR is excluded. Every use, including COPY
    consumers and producers, counts; closed intervals include alloc-before-free.
    """
    if len(seq) != len(set(seq)):
        raise ValueError('duplicate operation in sequence')
    op_step = {v: i for i, v in enumerate(seq)}
    by_id = {t['id']: t for t in tensors}
    uses = defaultdict(list)
    for e in edges:
        s, t = e['source'], e['target']
        if s in op_step and t in by_id:
            uses[t].append(op_step[s])
        elif t in op_step and s in by_id:
            uses[s].append(op_step[t])
    events = {p: defaultdict(int) for p in ('L1', 'UB')}
    for tid, positions in uses.items():
        tensor = by_id[tid]
        pos = tensor['pos']
        if pos == 'DDR':
            continue
        if pos not in events:
            raise ValueError('unknown managed memory position')
        lo, hi = min(positions), max(positions)
        events[pos][lo] += tensor['size']
        events[pos][hi + 1] -= tensor['size']
    peaks = {}
    for pos, changes in events.items():
        used = peak = 0
        for step in range(len(seq)):
            used += changes.get(step, 0)
            peak = max(peak, used)
        peaks[pos] = peak
    return peaks
