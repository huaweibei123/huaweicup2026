"""Bounded-weight reduction-forest fragments, packed into possibly disconnected cores.

Fixed B=max(largest node, ceil(W/(4k))) provides a list-scheduling work bound.
It does not bound fragment count by 4k or guarantee official Makespan improvement.
"""
from .construct import UnsupportedStructure
from .capacity_tree import threshold_cut, blocks_from_cuts, plan_from_owner


def construct(index, cores):
    if type(cores) is not int or cores < 1:
        raise ValueError("cores must be a positive integer")
    if not index.ops or any(len(index.succ[u]) > 1 for u in index.ops):
        raise UnsupportedStructure("requires a nonempty out-degree <= 1 reduction forest")
    if not any(len(index.pred[u]) > 1 for u in index.ops):
        raise UnsupportedStructure("requires a join, not serial independent jobs")
    weights = {u: index.duration(u) for u in index.ops}
    total = sum(weights.values())
    bound = max(max(weights.values()), (total + 4 * cores - 1) // (4 * cores))
    cuts = threshold_cut(index.order, index.pred, weights, bound)
    if cuts is None:
        raise AssertionError("a node exceeds its declared bound")
    blocks = blocks_from_cuts(index, cuts)
    work = [sum(weights[u] for u in block) for block in blocks]
    if max(work) > bound:
        raise AssertionError("fragment weight exceeds threshold")
    load = [0] * cores
    owner = {}
    fragments_by_core = [[] for _ in range(cores)]
    for j in sorted(range(len(blocks)), key=lambda j: (-work[j], min(blocks[j]))):
        core = min(range(cores), key=lambda c: (load[c], c))
        load[core] += work[j]
        fragments_by_core[core].append(j)
        owner.update((u, core) for u in blocks[j])
    load_bound = (total + (cores - 1) * bound) // cores
    if max(load) > load_bound:
        raise AssertionError("list-scheduling work bound violated")
    plan = plan_from_owner(index, owner, cores)
    crossed = [[u, v] for u in index.order for v in sorted(index.succ[u])
               if owner[u] != owner[v]]
    return plan, {"strategy": "fragment_reduction_forest", "fragment_threshold_cycles": bound,
                  "fragment_work_cycles": work, "fragment_count": len(blocks),
                  "fragments_by_core": fragments_by_core, "core_work_cycles": load,
                  "compute_load_upper_bound_cycles": load_bound, "cuts": cuts,
                  "cross_core_compute_edges": crossed, "weak_components": len(index.components),
                  "granularity_rule": "max(max_node_cycles, ceil(total_compute_cycles / (4 * cores)))",
                  "order": "original-op-id depth-first postorder"}
