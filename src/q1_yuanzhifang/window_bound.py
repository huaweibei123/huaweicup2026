"""Universal retained-compute release/tail resource windows, O(V log V).

No plan, simulator or COPY contraction. This implements the audited window
lemma in Pro message 4f80a045 section 3.1; it is not its attachment code.
"""
from __future__ import annotations

from collections import defaultdict

from construct import _build_op_adjacency, topo


class _PrefixMax:
    """Prefix add and nonempty prefix maximum; ties select the smaller index."""

    def __init__(self, values):
        self.n = len(values)
        self.value, self.lazy, self.index = ([0] * (4 * self.n) for _ in range(3))

        def build(node, lo, hi):
            if hi - lo == 1:
                self.value[node], self.index[node] = values[lo], lo
            else:
                mid = (lo + hi) // 2
                build(node * 2, lo, mid); build(node * 2 + 1, mid, hi)
                self._pull(node)

        build(1, 0, self.n)

    def _pull(self, node):
        child = node * 2
        if self.value[child + 1] > self.value[child]:
            child += 1
        self.value[node], self.index[node] = self.value[child], self.index[child]

    def _apply(self, node, amount):
        self.value[node] += amount
        self.lazy[node] += amount

    def _push(self, node):
        if self.lazy[node]:
            self._apply(node * 2, self.lazy[node])
            self._apply(node * 2 + 1, self.lazy[node])
            self.lazy[node] = 0

    def add(self, stop, amount):
        def visit(node, lo, hi):
            if hi <= stop:
                self._apply(node, amount)
                return
            self._push(node)
            mid = (lo + hi) // 2
            visit(node * 2, lo, mid)
            if stop > mid:
                visit(node * 2 + 1, mid, hi)
            self._pull(node)

        visit(1, 0, self.n)

    def maximum(self, stop):
        def visit(node, lo, hi):
            if hi <= stop:
                return self.value[node], self.index[node]
            self._push(node)
            mid = (lo + hi) // 2
            left = visit(node * 2, lo, mid)
            if stop <= mid:
                return left
            right = visit(node * 2 + 1, mid, hi)
            return left if left[0] >= right[0] else right

        return visit(1, 0, self.n)


def resource_window_bound(jobs, cores):
    """jobs are (id, release lower bound, duration, post-completion tail).

    All jobs must consume the SAME resource type with capacity `cores`.
    Release and tail must be universal lower bounds, not plan predictions.
    """
    if type(cores) is not int or cores < 1:
        raise ValueError("Positive integer capacity required")
    jobs = list(jobs)
    if any(any(type(x) is not int for x in (r, d, q)) or r < 0 or d <= 0 or q < 0
           for _, r, d, q in jobs):
        raise ValueError("Nonnegative integer release/tail and positive duration required")
    if not jobs:
        return {"lower_bound_cycles": 0, "witness": None}
    qs = sorted({q for _, _, _, q in jobs})
    qindex = {q: i for i, q in enumerate(qs)}
    tree = _PrefixMax([cores * q for q in qs])
    ordered = sorted(jobs, key=lambda job: -job[1])
    i, active_stop, best, witness = 0, 0, -1, None
    while i < len(ordered):
        release = ordered[i][1]
        while i < len(ordered) and ordered[i][1] == release:
            _, _, duration, tail = ordered[i]
            stop = qindex[tail] + 1
            tree.add(stop, duration)
            active_stop = max(active_stop, stop)
            i += 1
        # Larger q coordinates still describe an EMPTY set. Their bare k*q
        # value must never contribute to the lower bound.
        value, index = tree.maximum(active_stop)
        bound = release + (value + cores - 1) // cores
        if bound > best:
            best, witness = bound, {"release_cycles": release, "tail_cycles": qs[index]}
    a, b = witness["release_cycles"], witness["tail_cycles"]
    members = [d for _, r, d, q in jobs if r >= a and q >= b]
    witness.update(operation_count=len(members), work_cycles=sum(members))
    assert members and best == a + b + (sum(members) + cores - 1) // cores
    return {"lower_bound_cycles": best, "witness": witness}


def lower_bound(graph, cores):
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("cores must be an integer in 1..5")
    ops = {o["id"]: o for o in graph["ops"] if o["op"] not in {"COPY_IN", "COPY_OUT"}}
    full_pred, full_succ = _build_op_adjacency(graph)
    pred = {u: full_pred[u] & ops.keys() for u in ops}
    succ = {u: full_succ[u] & ops.keys() for u in ops}
    order = topo(ops, succ)
    duration = {u: max(1, ops[u]["cycles"]) for u in ops}
    release, tail, jobs = {}, {}, defaultdict(list)
    for u in order:
        release[u] = max((release[p] + duration[p] for p in pred[u]), default=0)
    for u in reversed(order):
        tail[u] = max((duration[v] + tail[v] for v in succ[u]), default=0)
        jobs[ops[u]["pipe"]].append((u, release[u], duration[u], tail[u]))
    reports = {pipe: resource_window_bound(items, cores) for pipe, items in sorted(jobs.items())}
    return {"cores": cores, "compute_ops": len(ops), "pipe_windows": reports,
            "lower_bound_cycles": max((r["lower_bound_cycles"] for r in reports.values()), default=0),
            "scope": "Universal retained-compute release/tail windows per Pipe; ignores COPY, DDR, gates, spill and FIFO. No COPY contraction, no attainability claim."}
