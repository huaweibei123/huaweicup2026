"""Minimax interval cuts from a supplied zero-lag max-plus response table."""
from __future__ import annotations


def _prepare(length, cores, coefficients):
    if (type(length) is not int or type(cores) is not int or
            length < 1 or cores < 1 or cores > length):
        raise ValueError("require integer 1 <= cores <= length")
    if not isinstance(coefficients, dict):
        raise ValueError("coefficients must be a dictionary")
    adjacency = [[[] for _ in range(length + 1)] for _ in range(cores)]
    largest = 0
    for key, value in coefficients.items():
        if (not isinstance(key, tuple) or len(key) != 3 or
                any(type(x) is not int for x in key)):
            raise ValueError("interval key must be (integer stage,left,right)")
        stage, left, right = key
        if not 0 <= stage < cores or not 0 <= left < right <= length:
            raise ValueError("interval key outside nonempty stage/domain range")
        if not isinstance(value, dict) or set(value) != {"A", "B", "C", "D"}:
            raise ValueError("response must contain exactly A,B,C,D")
        terms = tuple(value[name] for name in ("A", "B", "C", "D"))
        if any(type(x) is not int or x < 0 for x in terms):
            raise ValueError("response coefficients must be nonnegative integers")
        adjacency[stage][left].append((right, terms))
        largest = max(largest, *terms)
    return adjacency, largest


def _decide(length, cores, adjacency, threshold):
    # At (stage,end), only the smallest arrival R can help any suffix:
    # max(A,R+B) and max(C,R+D) are both monotone in R.
    best = [[None] * (length + 1) for _ in range(cores + 1)]
    parent = [[None] * (length + 1) for _ in range(cores + 1)]
    best[0][0] = 0
    transitions = 0
    for stage in range(cores):
        for left in range(stage, length - (cores - stage) + 1):
            arrival = best[stage][left]
            if arrival is None:
                continue
            for right, (A, B, C, D) in adjacency[stage][left]:
                if right > length - (cores - stage - 1):
                    continue
                transitions += 1
                finish = max(A, arrival + B)
                if finish > threshold:
                    continue
                tail_end = max(C, arrival + D)
                old = best[stage + 1][right]
                if old is None or tail_end < old:
                    best[stage + 1][right] = tail_end
                    parent[stage + 1][right] = (left, arrival, finish, tail_end)
    if best[cores][length] is None:
        return None, transitions
    cuts, arrivals, finishes, tail_ends = [length], [], [], []
    right = length
    for stage in range(cores, 0, -1):
        left, arrival, finish, tail_end = parent[stage][right]
        cuts.append(left)
        arrivals.append(arrival)
        finishes.append(finish)
        tail_ends.append(tail_end)
        right = left
    cuts.reverse()
    arrivals.reverse()
    finishes.reverse()
    tail_ends.reverse()
    return dict(cuts=cuts, arrival=arrivals, finish=finishes,
                tail_end=tail_ends, makespan=max(finishes)), transitions


def decide(length, cores, coefficients, threshold):
    """Return a threshold-feasible minimal-arrival route, or None, plus work count."""
    if type(threshold) is not int or threshold < 0:
        raise ValueError("threshold must be a nonnegative integer")
    adjacency, _ = _prepare(length, cores, coefficients)
    return _decide(length, cores, adjacency, threshold)


def optimize(length, cores, coefficients):
    """Find the exact minimax cuts for the fixed supplied coefficient table."""
    adjacency, largest = _prepare(length, cores, coefficients)
    upper = cores * largest  # R and E grow by at most largest once per stage.
    initial, transitions = _decide(length, cores, adjacency, upper)
    calls = 1
    if initial is None:
        raise ValueError("no connected nonempty k-segment path in coefficient table")
    low, high = 0, upper
    while low < high:
        mid = (low + high) // 2
        route, count = _decide(length, cores, adjacency, mid)
        transitions += count
        calls += 1
        if route is None:
            low = mid + 1
        else:
            high = mid
    route, count = _decide(length, cores, adjacency, low)
    transitions += count
    calls += 1
    if route is None or route["makespan"] != low:
        raise AssertionError("threshold restoration disagrees with minimax optimum")
    route.update(optimum=low, transition_count=transitions,
                 feasibility_calls=calls, coefficient_count=len(coefficients),
                 complexity="O((|table|+kL) (1+log(1+k*max_coefficient))) time; O(|table|+kL) memory; coefficient derivation excluded",
                 scope="Fixed nonnegative integer response table only; coefficient derivation and policy costs excluded; no official E0 claim or byte tie-break")
    return route
