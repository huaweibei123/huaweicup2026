"""Resource-window lower bounds on independently certified necessary jobs.

A job is a triple ``(r, d, q)``: release lower bound, required service, and
necessary tail after completion. For a resource of capacity ``c``, every
nonempty S = {jobs with r >= R and q >= Q} gives the necessary inequality
``makespan >= R + Q + ceil(sum(d in S) / c)``. A zero-service job still denotes
a necessary completion event, so its release and tail remain constraints.

The maximum threshold window is found in O(J log J) time and O(J) space.
Witness verification is O(J), and verifies the stated window, not maximality.
Neither operation proves that caller-supplied jobs are necessary in every
legal plan. In particular, candidate-specific FIFO or memory edges must not
be used to supply a purported universal lower bound.

Source: the double-threshold argument in the archived Pro research,
``AI chats/P1多Pipe链构造证明/附件/r1-p1_s6607/RESEARCH_NOTE.md``, section 9.
This module is an independent implementation; it does not import that bundle,
parse contest graphs, call a solver/evaluator, or change a submitted plan.
"""

from bisect import bisect_right
from collections.abc import Iterable, Mapping

_KIND = "necessary-resource-window-v1"
_FIELDS = {
    "kind", "capacity", "job_count", "empty", "r_threshold", "q_threshold",
    "selected_count", "selected_work", "bound",
}


def _validated_jobs(jobs: Iterable[tuple[int, int, int]], capacity: int):
    if type(capacity) is not int or capacity <= 0:
        raise ValueError("capacity must be a positive integer, excluding bool")
    try:
        rows = list(jobs)
    except TypeError as exc:
        raise ValueError("jobs must be an iterable of (r, d, q) triples") from exc
    result = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != 3:
            raise ValueError("each job must be a tuple or list of length three")
        if any(type(value) is not int or value < 0 for value in row):
            raise ValueError("r, d and q must be nonnegative integers, excluding bool")
        result.append(tuple(row))
    return result


def _ceil_div(value: int, capacity: int) -> int:
    return (value + capacity - 1) // capacity


class _PrefixMaximum:
    """Prefix addition / prefix maximum, returning the smallest tied index."""

    def __init__(self, values: list[int]):
        self.size = len(values)
        self.values = [0] * (4 * self.size)
        self.lazy = [0] * (4 * self.size)
        self.indices = [0] * (4 * self.size)

        def build(node, left, right):
            if right - left == 1:
                self.values[node] = values[left]
                self.indices[node] = left
                return
            middle = (left + right) // 2
            build(2 * node, left, middle)
            build(2 * node + 1, middle, right)
            self._pull(node)

        build(1, 0, self.size)

    def _pull(self, node):
        left, right = 2 * node, 2 * node + 1
        # All left-child indices are smaller than right-child indices.
        chosen = left if self.values[left] >= self.values[right] else right
        self.values[node] = self.values[chosen]
        self.indices[node] = self.indices[chosen]

    def _apply(self, node, delta):
        self.values[node] += delta
        self.lazy[node] += delta

    def _push(self, node):
        if self.lazy[node]:
            self._apply(2 * node, self.lazy[node])
            self._apply(2 * node + 1, self.lazy[node])
            self.lazy[node] = 0

    def add(self, end: int, delta: int):
        def update(node, left, right):
            if left >= end:
                return
            if right <= end:
                self._apply(node, delta)
                return
            self._push(node)
            middle = (left + right) // 2
            update(2 * node, left, middle)
            update(2 * node + 1, middle, right)
            self._pull(node)

        update(1, 0, self.size)

    def maximum(self, end: int):
        def query(node, left, right):
            if left >= end:
                return None
            if right <= end:
                return self.values[node], self.indices[node]
            self._push(node)
            middle = (left + right) // 2
            first = query(2 * node, left, middle)
            second = query(2 * node + 1, middle, right)
            if first is None:
                return second
            if second is None:
                return first
            return first if first[0] >= second[0] else second

        return query(1, 0, self.size)


def resource_window_bound(
    jobs: Iterable[tuple[int, int, int]], capacity: int,
) -> dict:
    """Return a JSON-compatible exact-integer certificate for the best window.

    Repeated triples represent distinct required jobs and are counted each
    time. Ties are deterministic: descending release sweep, then the largest
    unrounded numerator, then the smallest tail threshold. The inputs are not
    modified. Invalid jobs or capacity raise ValueError.
    """
    rows = _validated_jobs(jobs, capacity)
    certificate = {
        "kind": _KIND, "capacity": capacity, "job_count": len(rows),
        "empty": not rows, "r_threshold": None, "q_threshold": None,
        "selected_count": 0, "selected_work": 0, "bound": 0,
    }
    if not rows:
        return certificate

    tails = sorted({q for _, _, q in rows})
    tree = _PrefixMaximum([capacity * q for q in tails])
    ordered = sorted(rows, reverse=True)
    index, active_tail_end, best = 0, 0, None
    while index < len(ordered):
        release = ordered[index][0]
        while index < len(ordered) and ordered[index][0] == release:
            _, service, tail = ordered[index]
            end = bisect_right(tails, tail)
            tree.add(end, service)
            active_tail_end = max(active_tail_end, end)
            index += 1
        # Higher tail thresholds have no active job. Their c*q leaf values
        # would otherwise manufacture a bound from an empty set.
        numerator, tail_index = tree.maximum(active_tail_end)
        value = release + _ceil_div(numerator, capacity)
        if best is None or value > best[0]:
            best = value, release, tails[tail_index]

    value, release, tail = best
    selected = [(r, d, q) for r, d, q in rows if r >= release and q >= tail]
    certificate.update({
        "r_threshold": release, "q_threshold": tail,
        "selected_count": len(selected),
        "selected_work": sum(d for _, d, _ in selected), "bound": value,
    })
    return certificate


def verify_resource_window(
    jobs: Iterable[tuple[int, int, int]], capacity: int, certificate: Mapping,
) -> bool:
    """Check a window witness in O(J), without running the optimizing tree.

    Capacity is supplied separately so a modified certificate cannot silently
    choose a different resource. Malformed or inconsistent certificates return
    False. Invalid job/capacity inputs raise ValueError, as in the optimizer.
    This check establishes neither the necessity of the jobs nor maximality.
    """
    rows = _validated_jobs(jobs, capacity)
    if not isinstance(certificate, Mapping) or set(certificate) != _FIELDS:
        return False
    if certificate["kind"] != _KIND or type(certificate["empty"]) is not bool:
        return False
    for field in ("capacity", "job_count", "selected_count", "selected_work", "bound"):
        if type(certificate[field]) is not int or certificate[field] < 0:
            return False
    if certificate["capacity"] != capacity or certificate["job_count"] != len(rows):
        return False
    if not rows:
        return (
            certificate["empty"] and certificate["r_threshold"] is None
            and certificate["q_threshold"] is None
            and certificate["selected_count"] == 0
            and certificate["selected_work"] == 0 and certificate["bound"] == 0
        )
    if certificate["empty"]:
        return False
    release, tail = certificate["r_threshold"], certificate["q_threshold"]
    if any(type(value) is not int or value < 0 for value in (release, tail)):
        return False
    count, work = 0, 0
    for r, d, q in rows:
        if r >= release and q >= tail:
            count += 1
            work += d
    return (
        count > 0 and certificate["selected_count"] == count
        and certificate["selected_work"] == work
        and certificate["bound"] == release + tail + _ceil_div(work, capacity)
    )
