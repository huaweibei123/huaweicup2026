"""Exact min-max scalar-work connected partition of a guarded reduction tree.

The proxy optimum is NOT a Makespan optimum or a full execution certificate.
See docs/a/q3/CAPACITY_TREE_PROOF.md for the greedy threshold proof.
"""
from .construct import UnsupportedStructure, derive_multicore_plan


def threshold_cut(order, children, weights, bound):
    """Return minimum-count cuts, minimizing remaining root weight on ties.

    ``order`` must place every child before its parent; weights are nonnegative.
    None denotes an indivisible vertex heavier than the threshold.
    """
    residual = {}
    cuts = []
    for u in order:
        if weights[u] > bound:
            return None
        total = weights[u] + sum(residual[v] for v in children[u])
        for v in sorted(children[u], key=lambda v: (-residual[v], v)):
            if total <= bound:
                break
            total -= residual[v]
            cuts.append((v, u))
        residual[u] = total
    return cuts


def construct(index, cores):
    if type(cores) is not int or cores < 1:
        raise ValueError("cores must be a positive integer")
    if len(index.components) != 1 or any(len(index.succ[u]) > 1 for u in index.ops):
        raise UnsupportedStructure("requires one weak component with out-degree <= 1")
    if not any(len(index.pred[u]) > 1 for u in index.ops):
        raise UnsupportedStructure("requires a join, not a serial chain")
    weights = {u: index.duration(u) for u in index.ops}
    total = sum(weights.values())
    lower = max(max(weights.values()), (total + cores - 1) // cores)
    upper = total
    checks = 0
    while lower < upper:
        middle = (lower + upper) // 2
        cuts = threshold_cut(index.order, index.pred, weights, middle)
        checks += 1
        if cuts is not None and len(cuts) + 1 <= cores:
            upper = middle
        else:
            lower = middle + 1
    cuts = threshold_cut(index.order, index.pred, weights, lower)
    checks += 1
    if cuts is None or len(cuts) + 1 > cores:
        raise AssertionError("threshold feasibility certificate failed")
    blocks = blocks_from_cuts(index, cuts)
    owner = {u: c for c, block in enumerate(blocks) for u in block}
    plan = plan_from_owner(index, owner, cores)
    block_work = [sum(weights[u] for u in block) for block in blocks]
    if max(block_work) != lower:
        raise AssertionError("minimal feasible threshold does not match partition")
    return plan, {"strategy": "capacity_reduction_tree", "cuts": cuts,
                  "block_work_cycles": block_work, "block_operations": list(map(len, blocks)),
                  "proxy_optimum_cycles": lower, "proxy": "sum of original compute cycles per connected block",
                  "threshold_checks": checks, "piece_count": len(blocks),
                  "order": "original-op-id depth-first postorder"}


def blocks_from_cuts(index, cuts):
    cut_set = set(cuts)
    sinks = sorted(u for u in index.ops if not index.succ[u])
    block_roots = sinks + [u for u, _ in cuts]
    blocks = []
    for root in block_roots:
        block = []
        stack = [root]
        while stack:
            u = stack.pop()
            block.append(u)
            stack.extend(v for v in index.pred[u] if (v, u) not in cut_set)
        blocks.append(block)
    blocks.sort(key=min)
    if len({u for block in blocks for u in block}) != len(index.ops) or sum(map(len, blocks)) != len(index.ops):
        raise AssertionError("partition does not cover every operation once")
    return blocks


def plan_from_owner(index, owner, cores):
    # Same global DFS postorder as the legacy construction; isolate partition.
    sinks = sorted(u for u in index.ops if not index.succ[u])
    ordered = []
    stack = [(u, False) for u in reversed(sinks)]
    while stack:
        u, expanded = stack.pop()
        if expanded:
            ordered.append(u)
        else:
            stack.append((u, True))
            stack.extend((v, False) for v in sorted(index.pred[u], reverse=True))
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules = [[] for _ in range(cores)]
    for u in ordered:
        schedules[owner[u]].append(mapping[str(u)])
    plan = {"node_to_subgraph": mapping, "core_schedules": schedules}
    derive_multicore_plan(index.graph, plan)
    return plan
