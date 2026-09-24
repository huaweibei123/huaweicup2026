"""Finite scalar tree-partition oracle checks; never import or call E0.

Usage: python -m src.q3.review.capacity_threshold_check --output NEW_JSON
This small check supplements the proof, and is not a production partitioner.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import random
import time


def threshold_greedy(parents, weights, bound):
    """Return (cut count, root residual); parents must have larger indices."""
    if max(weights) > bound:
        return None
    children = [[] for _ in parents]
    for u, parent in enumerate(parents):
        if parent >= 0:
            children[parent].append(u)
    residual = [0] * len(parents)
    cuts = 0
    for u in range(len(parents)):
        residual[u] = weights[u] + sum(residual[v] for v in children[u])
        for v in sorted(children[u], key=lambda v: (-residual[v], v)):
            if residual[u] <= bound:
                break
            residual[u] -= residual[v]
            cuts += 1
    return cuts, residual[-1]


def exhaustive_partitions(parents, weights):
    """Tiny independent oracle: enumerate all subsets of the tree edges."""
    n = len(parents)
    outcomes = []
    for mask in range(1 << (n - 1)):
        representatives = list(range(n))

        def find(v):
            while representatives[v] != v:
                v = representatives[v]
            return v

        for u in range(n - 1):
            if not (mask >> u) & 1:
                representatives[find(u)] = find(parents[u])
        loads = {}
        for u in range(n):
            root = find(u)
            loads[root] = loads.get(root, 0) + weights[u]
        outcomes.append((max(loads.values()), mask.bit_count(), loads[find(n - 1)]))
    return outcomes


def check_tree(parents, weights):
    outcomes = exhaustive_partitions(parents, weights)
    checks = 0
    for bound in range(sum(weights) + 1):
        feasible = [(cuts, residual) for maximum, cuts, residual in outcomes
                    if maximum <= bound]
        exact = min(feasible) if feasible else None
        actual = threshold_greedy(parents, weights, bound)
        if actual != exact:
            raise AssertionError({"parents": parents, "weights": weights,
                                  "bound": bound, "greedy": actual, "oracle": exact})
        checks += 1
    for k in range(1, min(5, len(parents)) + 1):
        low = max(max(weights), (sum(weights) + k - 1) // k)
        high = sum(weights)
        while low < high:
            middle = (low + high) // 2
            result = threshold_greedy(parents, weights, middle)
            if result is not None and result[0] + 1 <= k:
                high = middle
            else:
                low = middle + 1
        exact = min(maximum for maximum, cuts, _ in outcomes if cuts + 1 <= k)
        if low != exact:
            raise AssertionError({"parents": parents, "weights": weights,
                                  "cores": k, "binary_search": low, "oracle": exact})
    return checks, min(5, len(parents))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; use a new path")
    started = time.perf_counter()
    threshold_checks = minmax_checks = exhaustive_trees = random_trees = 0
    for n in range(1, 6):
        for pp in itertools.product(*(range(i + 1, n) for i in range(n - 1))):
            parents = (*pp, -1)
            for weights in itertools.product(range(3), repeat=n):
                thresholds, minmax = check_tree(parents, weights)
                threshold_checks += thresholds
                minmax_checks += minmax
                exhaustive_trees += 1
    rng = random.Random(73636)
    for _ in range(2500):
        n = rng.randrange(6, 12)
        parents = tuple(rng.randrange(i + 1, n) for i in range(n - 1)) + (-1,)
        weights = tuple(rng.randrange(0, 8) for _ in range(n))
        thresholds, minmax = check_tree(parents, weights)
        threshold_checks += thresholds
        minmax_checks += minmax
        random_trees += 1
    report = {
        "status": "passed",
        "scope": "finite scalar nonnegative tree-partition checks, not E0 or formal proof",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "exhaustive_n_max": 5,
        "exhaustive_parent_order": "parent index strictly greater than child index",
        "exhaustive_weights": [0, 1, 2],
        "exhaustive_weighted_trees": exhaustive_trees,
        "random_trees": random_trees,
        "random_n_range_inclusive": [6, 11],
        "random_weights_range_inclusive": [0, 7],
        "random_seed": 73636,
        "threshold_pair_checks": threshold_checks,
        "integer_minmax_checks": minmax_checks,
        "verified_pair": ["minimum edge cuts", "minimum root residual among minimum cuts"],
        "failures": 0,
        "official_e0_calls": 0,
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
