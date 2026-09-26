"""Exact four-coefficient response for a zero-copy serial-tail compute DAG."""
from __future__ import annotations


def analyze(ops, original_succ, schedules, tail):
    """Compress each core's local M/V DAG plus FIFO into A,B,C,D max-plus terms.

    This is exact only for positive-duration compute operations, zero inter-core
    lag, and a single serial tail as the sole cross-core interaction.
    """
    cores = len(schedules)
    if cores < 2 or not ops or any(type(op.get("cycles")) is not int or op["cycles"] <= 0 or
                                   op.get("pipe") not in ("PIPE_M", "PIPE_V") for op in ops.values()):
        raise ValueError("requires at least two cores and positive integer M/V compute ops")
    listed = [u for seq in schedules for u in seq]
    if len(listed) != len(ops) or set(listed) != set(ops):
        raise ValueError("schedules must cover every compute operation exactly once")
    owner = {u: c for c, seq in enumerate(schedules) for u in seq}
    rank = {u: i for seq in schedules for i, u in enumerate(seq)}
    if not tail or len(tail) != len(set(tail)) or any(u not in ops for u in tail):
        raise ValueError("tail must contain distinct eligible operations")
    tail_set = set(tail)
    tail_owners = [owner[u] for u in tail]
    if (tail_owners[0] != 0 or tail_owners[-1] != cores - 1 or
            any(a > b or b > a + 1 for a, b in zip(tail_owners, tail_owners[1:])) or
            set(tail_owners) != set(range(cores))):
        raise ValueError("tail must form nonempty consecutive segments on cores 0..k-1")
    cuts = [0]
    for i in range(1, len(tail)):
        if tail_owners[i] != tail_owners[i - 1]:
            cuts.append(i)
    cuts.append(len(tail))
    succ = {u: set() for u in ops}
    for u, targets in original_succ.items():
        if u not in ops:
            raise ValueError("original edge source outside compute operations")
        for v in targets:
            if v not in ops:
                raise ValueError("original edge target outside compute operations")
            succ[u].add(v)
    for u, v in zip(tail, tail[1:]):
        if v not in succ[u]:
            raise ValueError("every adjacent tail pair needs an original dependency")
    local_pred = {u: set() for u in ops}
    cross_edges = 0
    for u, targets in succ.items():
        for v in targets:
            if owner[u] == owner[v]:
                if rank[u] >= rank[v]:
                    raise ValueError("local original dependency runs backward in schedule")
                local_pred[v].add(u)
            else:
                if u not in tail_set or v not in tail_set or owner[u] >= owner[v]:
                    raise ValueError("only forward tail-to-tail cross-core dependencies are allowed")
                cross_edges += 1
    # Exactly k-1 adjacent tail edges cross a segment boundary; all others
    # are dominated by the serial tail chain under zero additional lag.
    redundant_cross = cross_edges - (cores - 1)
    coeffs, arrivals, finishes = [], [], []
    arrival = 0
    for c, seq in enumerate(schedules):
        pair = {}
        previous_pipe = {}
        tail_first, tail_last = tail[cuts[c]], tail[cuts[c + 1] - 1]
        for u in seq:
            predecessors = set(local_pred[u])
            pipe = ops[u]["pipe"]
            if pipe in previous_pipe:
                predecessors.add(previous_pipe[pipe])
            previous_pipe[pipe] = u
            duration = ops[u]["cycles"]
            a = duration + max((pair[p][0] for p in predecessors), default=0)
            incoming = ([0] if u == tail_first else []) + [pair[p][1] for p in predecessors
                                                       if pair[p][1] is not None]
            b = duration + max(incoming) if incoming else None
            pair[u] = (a, b)
        A = max(pair[u][0] for u in seq)
        finite = [pair[u][1] for u in seq if pair[u][1] is not None]
        B = max(finite) if finite else None
        C, D = pair[tail_last]
        finish = max(A, arrival + B) if B is not None else A
        next_arrival = max(C, arrival + D) if D is not None else C
        coeffs.append(dict(core=c, A=A, B=B, C=C, D=D))
        arrivals.append(arrival)
        finishes.append(finish)
        arrival = next_arrival
    return dict(cuts=cuts, coeffs=coeffs, arrival=arrivals, finish=finishes,
                bound=max(finishes), cross_core_edge_count=cross_edges,
                redundant_skip_edge_count=redundant_cross,
                limitation="Exact only for the guarded zero-lag compute DAG and per-core M/V FIFO; no COPY, spill, Cache, DDR contention, or positive transfer lag")
