"""Release-aware list construction on connected reduction-forest fragments.

This is a compute/pipe timing proxy, not an official scheduler or a memory
certificate. Fragment size stays identical to fragment_tree for the ablation.
"""
import heapq

from .construct import UnsupportedStructure, derive_multicore_plan, topo
from .capacity_tree import threshold_cut, blocks_from_cuts


def construct(index, cores, *, place=False, cross_delay=500):
    if type(cores) is not int or cores < 1:
        raise ValueError("cores must be a positive integer")
    if type(cross_delay) is not int or cross_delay < 0:
        raise ValueError("cross_delay must be a nonnegative integer")
    if (not index.ops or any(len(index.succ[u]) > 1 for u in index.ops)
            or not any(len(index.pred[u]) > 1 for u in index.ops)):
        raise UnsupportedStructure("requires a reduction forest containing a join")
    weights = {u: index.duration(u) for u in index.ops}
    total = sum(weights.values())
    bound = max(max(weights.values()), (total + 4 * cores - 1) // (4 * cores))
    cuts = threshold_cut(index.order, index.pred, weights, bound)
    blocks = blocks_from_cuts(index, cuts)
    block_of = {u: j for j, block in enumerate(blocks) for u in block}
    block_work = [sum(weights[u] for u in block) for block in blocks]
    successors = {j: set() for j in range(len(blocks))}
    predecessors = {j: set() for j in range(len(blocks))}
    for u in index.order:
        for v in index.succ[u]:
            a, b = block_of[u], block_of[v]
            if a != b:
                successors[a].add(b)
                predecessors[b].add(a)
    border_order = topo(successors, successors)
    rank = {}
    for j in reversed(border_order):
        rank[j] = block_work[j] + max((rank[b] for b in successors[j]), default=0)

    # Preserve the exact old LPT ownership in the order-only ablation.
    loads = [0] * cores
    fixed_owner = {}
    for j in sorted(successors, key=lambda j: (-block_work[j], min(blocks[j]))):
        c = min(range(cores), key=lambda c: (loads[c], c))
        loads[c] += block_work[j]
        fixed_owner[j] = c

    # A connected forest block has one sink; postorder stays inside the block.
    words = {}
    for j, block in enumerate(blocks):
        block = set(block)
        roots = sorted(u for u in block if not (index.succ[u] & block))
        stack = [(u, False) for u in reversed(roots)]
        word = []
        while stack:
            u, expanded = stack.pop()
            if expanded:
                word.append(u)
            else:
                stack.append((u, True))
                stack.extend((p, False) for p in sorted(index.pred[u] & block, reverse=True))
        words[j] = word

    pipe_free = [{} for _ in range(cores)]
    finish, owner = {}, {}
    external = {j: [(p, u) for u in words[j] for p in index.pred[u]
                    if block_of[p] != j] for j in successors}

    def queue_key(j):
        # An ordering coordinate, not a claim that every input is needed at
        # fragment entry. Exact per-operation releases are used in each trial.
        incoming = min(max((finish[p] + (cross_delay if owner[p] != c else 0)
                            for p, _ in external[j]), default=0)
                       for c in (range(cores) if place else [fixed_owner[j]]))
        return incoming, -rank[j], min(blocks[j]), j

    degree = {j: len(predecessors[j]) for j in successors}
    ready = [queue_key(j) for j in successors if not degree[j]]
    heapq.heapify(ready)
    schedules = [[] for _ in range(cores)]
    choices = []
    while ready:
        _, _, _, j = heapq.heappop(ready)
        trials = []
        for c in (range(cores) if place else [fixed_owner[j]]):
            free = dict(pipe_free[c])
            local = {}
            remote_edges = 0
            for u in words[j]:
                release = 0
                for p in index.pred[u]:
                    if block_of[p] == j:
                        at = local[p]
                    else:
                        remote = owner[p] != c
                        remote_edges += int(remote)
                        at = finish[p] + (cross_delay if remote else 0)
                    release = max(release, at)
                pipe = index.ops[u]["pipe"]
                local[u] = max(release, free.get(pipe, 0)) + weights[u]
                free[pipe] = local[u]
            trials.append((max(local.values()), remote_edges, c, local, free))
        end, remote_count, c, local, free = min(trials, key=lambda t: t[:3])
        pipe_free[c] = free
        finish.update(local)
        owner.update((u, c) for u in blocks[j])
        schedules[c].extend(words[j])
        choices.append({"fragment": j, "core": c, "proxy_finish": end,
                        "remote_inputs": remote_count})
        for b in sorted(successors[j]):
            degree[b] -= 1
            if degree[b] == 0:
                heapq.heappush(ready, queue_key(b))
    if len(finish) != len(index.ops):
        raise AssertionError("fragment quotient is cyclic or incomplete")
    mapping = {str(u): i for i, u in enumerate(index.order)}
    plan = {"node_to_subgraph": mapping,
            "core_schedules": [[mapping[str(u)] for u in seq] for seq in schedules]}
    derive_multicore_plan(index.graph, plan)
    core_work = [sum(weights[u] for u in owner if owner[u] == c) for c in range(cores)]
    return plan, {"strategy": "release_place_forest" if place else "release_order_forest",
                  "fragment_threshold_cycles": bound, "fragment_count": len(blocks),
                  "fragment_work_cycles": block_work, "cuts": cuts,
                  "core_work_cycles": core_work, "fragment_dispatch": choices,
                  "proxy_makespan_cycles": max(finish.values()),
                  "cross_delay_proxy": cross_delay,
                  "cross_core_compute_edges": [[u, v] for u in index.order
                      for v in sorted(index.succ[u]) if owner[u] != owner[v]],
                  "order": "minimum incoming release then quotient bottom-level ready list; within-fragment DFS postorder",
                  "placement": "minimum proxy completion" if place else "unchanged LPT",
                  "limitations": "No COPY/Cache/bandwidth/capacity model; no official performance or zero-spill guarantee."}
