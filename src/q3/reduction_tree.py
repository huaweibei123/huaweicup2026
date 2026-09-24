"""A balanced edge-cut construction for a COPY-contracted reduction tree.

This guard is about compute precedence, not official execution feasibility.
The caller must obtain a full official result before accepting the proposal.
"""
from .construct import UnsupportedStructure, derive_multicore_plan


def construct(index, cores):
    if type(cores) is not int or cores < 1:
        raise ValueError("cores must be a positive integer")
    if len(index.components) != 1 or any(len(index.succ[u]) > 1 for u in index.ops):
        raise UnsupportedStructure("requires one weak component with out-degree <= 1")
    if not any(len(index.pred[u]) > 1 for u in index.ops):
        raise UnsupportedStructure("requires a join, not a serial chain")

    # Repeatedly bisect the heaviest current tree block at its best-balanced edge.
    # Every block remains connected; detached subtrees cannot have an external
    # input from another detached subtree in an out-degree-one original tree.
    blocks = [set(index.ops)]
    cuts = []
    while len(blocks) < min(cores, len(index.ops)):
        candidates = [b for b in blocks if len(b) > 1]
        if not candidates:
            break
        block = min(candidates, key=lambda b: (-sum(index.duration(u) for u in b), min(b)))
        weights = {}
        for u in index.order:
            if u in block:
                weights[u] = index.duration(u) + sum(weights[p] for p in index.pred[u]
                                                     if p in block)
        total = sum(index.duration(u) for u in block)
        edges = [(u, next(iter(index.succ[u]))) for u in block
                 if index.succ[u] and next(iter(index.succ[u])) in block]
        u, v = min(edges, key=lambda e: (max(weights[e[0]], total - weights[e[0]]),
                                        abs(total - 2 * weights[e[0]]), e))
        detached = set()
        stack = [u]
        while stack:
            x = stack.pop()
            detached.add(x)
            stack.extend(p for p in index.pred[x] if p in block)
        blocks.remove(block)
        blocks.extend([detached, block - detached])
        cuts.append([u, v])

    # Deterministic depth-first postorder releases branch outputs at their join.
    # This is a single global linear extension. Each core receives a subsequence,
    # so original precedence plus the induced compute-order edges is acyclic.
    roots = sorted(u for u in index.ops if not index.succ[u])
    ordered = []
    stack = [(u, False) for u in reversed(roots)]
    while stack:
        u, expanded = stack.pop()
        if expanded:
            ordered.append(u)
        else:
            stack.append((u, True))
            stack.extend((p, False) for p in sorted(index.pred[u], reverse=True))
    if len(ordered) != len(index.ops) or len(set(ordered)) != len(ordered):
        raise AssertionError("guarded tree traversal did not cover each operation once")

    blocks.sort(key=min)
    owner = {u: c for c, b in enumerate(blocks) for u in b}
    mapping = {str(u): i for i, u in enumerate(index.order)}
    schedules = [[] for _ in range(cores)]
    for u in ordered:
        schedules[owner[u]].append(mapping[str(u)])
    plan = {"node_to_subgraph": mapping, "core_schedules": schedules}
    derive_multicore_plan(index.graph, plan)
    return plan, {"strategy": "balanced_reduction_tree", "cuts": cuts,
                  "block_work_cycles": [sum(index.duration(u) for u in b) for b in blocks],
                  "block_operations": [len(b) for b in blocks],
                  "order": "original-op-id depth-first postorder"}
