"""Exact scalar min-max connected partition of an in-tree.

The proof concerns positive vertex weights and connected edge-cut parts only.
Official P2 COPY, contention, memory and multi-pipe timing are not this objective.
"""
from __future__ import annotations


def connected_partition(order, children, weights, parts):
    """Return optimal max scalar work and cut child->parent edges.

order is children-before-parent, its final node is the root. D[u,c] stores the
minimum open root-component weight after exactly c closed components below u;
all closed components and the open component obey threshold B. Smaller open
weight dominates because the parent only adds nonnegative weight or closes it.
"""
    parts = min(parts, len(order))
    limit = parts - 1
    inf = sum(weights.values()) + 1

    def feasible(bound, reconstruct=False):
        table, history = {}, {}
        for u in order:
            dp = [weights[u]] + [inf] * limit
            if weights[u] > bound:
                return None, None
            layers = []
            for child in children[u]:
                child_dp = table[child]
                nxt = [inf] * parts
                choices = [None] * parts
                for a, left in enumerate(dp):
                    if left == inf:
                        continue
                    for b, right in enumerate(child_dp[:parts-a]):
                        if right == inf:
                            continue
                        c = a + b
                        if left + right <= bound and left + right < nxt[c]:
                            nxt[c] = left + right
                            choices[c] = (a, b, False)
                        if c < limit and left < nxt[c+1]:
                            nxt[c+1] = left
                            choices[c+1] = (a, b, True)
                dp = nxt
                if reconstruct:
                    layers.append((child, choices))
            table[u] = dp
            if reconstruct:
                history[u] = layers
        if table[order[-1]][limit] == inf:
            return None, None
        return table, history

    lo = max(max(weights.values()), (sum(weights.values()) + parts - 1) // parts)
    hi = sum(weights.values())
    decisions = 0
    while lo < hi:
        mid = (lo + hi) // 2
        table, _ = feasible(mid)
        decisions += 1
        if table is None:
            lo = mid + 1
        else:
            hi = mid
    table, history = feasible(lo, True)
    if table is None:
        raise AssertionError("optimal threshold unexpectedly infeasible")
    cuts = set()
    stack = [(order[-1], limit)]
    while stack:
        u, wanted = stack.pop()
        for child, choices in reversed(history[u]):
            before, child_closed, cut = choices[wanted]
            stack.append((child, child_closed))
            if cut:
                cuts.add((child, u))
            wanted = before
        if wanted != 0:
            raise AssertionError("invalid DP reconstruction")
    return lo, cuts, decisions


def build_tree_plan(index, cores):
    if len(index.components) != 1 or any(len(s) > 1 for s in index.succ.values()):
        raise ValueError("tree_dp requires one connected in-tree, outdegree <= 1")
    roots = [u for u in index.order if not index.succ[u]]
    if len(roots) != 1:
        raise ValueError("tree_dp requires exactly one sink")
    children = {u: sorted(index.pred[u]) for u in index.order}
    weights = {u: index.duration(u) for u in index.order}
    capacity, cuts, probes = connected_partition(index.order, children, weights, cores)
    # Recover connected parts deterministically by walking from the sink.
    assignments = {}
    blocks = [[]]
    stack = [(roots[0], 0)]
    while stack:
        u, block = stack.pop()
        assignments[u] = block
        blocks[block].append(u)
        for child in reversed(children[u]):
            child_block = block
            if (child, u) in cuts:
                child_block = len(blocks)
                blocks.append([])
            stack.append((child, child_block))
    part_work = [sum(weights[u] for u in block) for block in blocks]
    if max(part_work) != capacity or len(blocks) != min(cores, len(index.ops)):
        raise AssertionError("partition does not meet its optimal scalar certificate")
    # Depth-first postorder completes input subtrees before retaining their
    # output. Larger compute subtrees first is a deterministic policy, not an
    # official makespan or tensor-register optimum theorem.
    subtree_work = {}
    for u in index.order:
        subtree_work[u] = weights[u] + sum(subtree_work[v] for v in children[u])
    order = []
    stack = [(roots[0], False)]
    while stack:
        u, closing = stack.pop()
        if closing:
            order.append(u)
        else:
            stack.append((u, True))
            kids = sorted(children[u], key=lambda v: (-subtree_work[v], v))
            stack.extend((v, False) for v in reversed(kids))
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules = [[] for _ in range(cores)]
    for u in order:
        schedules[assignments[u]].append(mapping[str(u)])
    plan = {"node_to_subgraph": mapping, "core_schedules": schedules}
    return plan, {"strategy": "tree_dp", "cores": cores,
                  "eligible_ops": len(index.ops), "components": 1,
                  "scalar_partition_optimum": capacity, "part_work": part_work,
                  "cut_edges": sorted(cuts), "binary_search_decisions": probes,
                  "scope": "Exact connected scalar partition only; DFS priority; official P2 execution untested"}
