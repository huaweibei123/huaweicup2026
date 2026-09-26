"""Exact maximization of a release/tail pipe-work lower-bound family.

Jobs are triples (guaranteed release, guaranteed remaining tail, pipe work).
For any r,q, jobs with release>=r and tail>=q must run within [r,T-q].
Thus T >= r + q + ceil(sum(work)/cores). This is a relaxation, not a schedule.
"""
from __future__ import annotations


def pipe_bound(jobs, cores):
    """O(n log n), integer-only; return the strongest threshold certificate.

    Sweep releases downward. On sorted tail thresholds, adding work w at tail q
    adds w to every threshold <=q. A lazy prefix-add/range-max tree maintains
    cores*threshold + accumulated eligible work. Query only nonempty subsets.
    """
    if type(cores) is not int or cores < 1:
        raise ValueError('positive integer core count required')
    jobs = tuple(tuple(job) for job in jobs)
    if any(len(job) != 3 or any(type(x) is not int for x in job)
           or job[0] < 0 or job[1] < 0 or job[2] <= 0 for job in jobs):
        raise ValueError('integer nonnegative release/tail and positive work required')
    if not jobs:
        return {'lower_bound_cycles': 0, 'release': None, 'tail': None, 'work': 0, 'jobs': 0}
    tails = sorted({q for _, q, _ in jobs})
    position = {q: i for i, q in enumerate(tails)}
    size = 1
    while size < len(tails):
        size *= 2
    values = [-1] * (2 * size)
    indices = [0] * (2 * size)
    lazy = [0] * (2 * size)
    for i in range(size):
        indices[size+i] = i
        if i < len(tails):
            values[size+i] = cores * tails[i]

    def pull(node):
        a, b = 2 * node, 2 * node + 1
        chosen = a if (values[a], -indices[a]) >= (values[b], -indices[b]) else b
        values[node], indices[node] = values[chosen], indices[chosen]

    for node in reversed(range(1, size)):
        pull(node)

    def push(node):
        if lazy[node]:
            for child in (2*node, 2*node+1):
                values[child] += lazy[node]
                lazy[child] += lazy[node]
            lazy[node] = 0

    def add_prefix(node, left, right, stop, amount):
        if right <= stop:
            values[node] += amount
            lazy[node] += amount
            return
        push(node)
        mid = (left + right) // 2
        add_prefix(2*node, left, mid, stop, amount)
        if stop > mid:
            add_prefix(2*node+1, mid+1, right, stop, amount)
        pull(node)

    def max_prefix(node, left, right, stop):
        if right <= stop:
            return values[node], -indices[node]
        push(node)
        mid = (left + right) // 2
        result = max_prefix(2*node, left, mid, stop)
        if stop > mid:
            result = max(result, max_prefix(2*node+1, mid+1, right, stop))
        return result

    ordered = sorted(jobs, reverse=True)
    maximum_tail_index = -1
    best, certificate = -1, None
    at = 0
    while at < len(ordered):
        release = ordered[at][0]
        while at < len(ordered) and ordered[at][0] == release:
            _, tail, work = ordered[at]
            i = position[tail]
            add_prefix(1, 0, size-1, i, work)
            maximum_tail_index = max(maximum_tail_index, i)
            at += 1
        value, neg_index = max_prefix(1, 0, size-1, maximum_tail_index)
        numerator = cores * release + value
        if numerator > best:
            best, certificate = numerator, (release, tails[-neg_index])
    release, tail = certificate
    subset = [w for r, q, w in jobs if r >= release and q >= tail]
    total = sum(subset)
    bound = release + tail + (total + cores - 1) // cores
    if bound != (best + cores - 1) // cores:
        raise AssertionError('segment tree certificate differs from direct subset sum')
    return {'lower_bound_cycles': bound, 'release': release, 'tail': tail,
            'work': total, 'jobs': len(subset)}
