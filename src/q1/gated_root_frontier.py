"""Strict generic fork/chain/binary-reduction candidate for P1.

The gate is a structural proxy, not an E0 prediction or optimality certificate.
Unsupported graphs return ``(None, reason)`` without a fallback search.
"""
from __future__ import annotations

from src.q1.fork_frontier import stage_units, topo
from src.q1.component_pack import _build_op_adjacency, _contract_excluded_copy_nodes
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


def root_count(width: int, cores: int, h: int, gate: int, same: int, cross: int):
    """Minimize the stated two-branch proxy with O(log width) evaluations.

    On a tie choose the larger q. Since q*h grows strictly and the remote
    ceiling term never grows, crossing and its predecessor suffice, including
    a flat remote-side plateau.
    """
    if not (all(type(x) is int for x in (width, cores, h, gate, same, cross)) and
            width >= cores >= 2 and h > 0 and gate > 0 and
            0 <= same <= cross):
        raise ValueError("invalid width, cores, compute, gate, or waits")
    upper = width - cores + 1
    def terms(q):
        return q * h + gate * same, ((width - q + cores - 2) // (cores - 1)) * h + gate * cross
    lo, hi = 1, upper + 1
    while lo < hi:
        mid = (lo + hi) // 2
        a, b = terms(mid)
        if a >= b:
            hi = mid
        else:
            lo = mid + 1
    choices = {1, upper}
    if lo <= upper:
        choices.add(lo)
    if lo > 1:
        choices.add(lo - 1)
    return min(choices, key=lambda q: (max(terms(q)), -q))


def choose_counts(width, cores, h, gate, same, cross):
    """Choose active cores and balanced nonroot counts by the relaxed proxy."""
    if not (type(width) is int and type(cores) is int and
            width >= 2 and 2 <= cores <= 5):
        raise ValueError("invalid width or core budget")
    def allocation(active):
        if active == 1:
            return (width*h + gate*same, active, -width, width)
        chosen = root_count(width, active, h, gate, same, cross)
        proxy = max(chosen*h + gate*same,
                    ((width-chosen+active-2)//(active-1))*h + gate*cross)
        return (proxy, active, -chosen, chosen)
    proxy, active, _, q = min(allocation(a) for a in range(1, min(cores, width)+1))
    if active == 1:
        counts = [width]
    else:
        remaining, bins = width - q, active - 1
        counts = [q] + [remaining // bins + (k < remaining % bins) for k in range(bins)]
    return counts + [0] * (cores - active), active, q, proxy


def guarded_stages(graph, cores):
    if type(cores) is not int or not 2 <= cores <= 5:
        raise ValueError("cores must be an integer in 2..5")
    noncopy_work = sum(max(1, o["cycles"]) for o in graph["ops"]
                       if o["op"] not in {"COPY_IN", "COPY_OUT"})
    if noncopy_work == 0:
        return None, "no compute operations"
    try:
        # A global work upper bound makes every stage threshold exactly one.
        # Even a very costly reduction must therefore peel to source chains.
        ops, units, _, _, stages = stage_units(graph, cores, grain=noncopy_work)
        full_pred, full_succ = _build_op_adjacency(graph)
    except (ValueError, AssertionError) as exc:
        return None, f"unsupported stage structure: {exc}"
    pred = {u: full_pred[u] & ops.keys() for u in ops}
    succ = {u: full_succ[u] & ops.keys() for u in ops}
    c_pred, c_succ = _contract_excluded_copy_nodes(sorted(ops), full_succ)
    if pred != c_pred or succ != c_succ:
        return None, "COPY-contracted and retained compute dependencies differ"
    previous, rounds = None, []
    for stage, entry in stages.items():
        frontier, tail_id = entry["frontier"], entry["tail"]
        if len(frontier) < 2 or tail_id is None:
            return None, "need at least two intact chains and one reduction tail"
        chains = []
        for g in sorted(frontier):
            members = set(units[g]["nodes"])
            chain = topo(members, {u: succ[u] & members for u in members})
            chains.append(chain)
        tail = set(units[tail_id]["nodes"])
        width = len(chains)
        if len(tail) != width - 1 or not all(chains):
            return None, "tail must have W-1 reductions and chains must be nonempty"
        heavy = {u for chain in chains for u in chain}
        if len(heavy) != sum(map(len, chains)) or heavy & tail:
            return None, "chain/tail overlap"
        if any(ops[u]["pipe"] != "PIPE_V" for u in heavy | tail):
            return None, "all compute operations must use PIPE_V"
        costs = [sum(max(1, ops[u]["cycles"]) for u in chain) for chain in chains]
        if len(set(costs)) != 1:
            return None, "unequal chain compute within round"
        starts = {chain[0] for chain in chains}
        for chain in chains:
            for index, u in enumerate(chain):
                expected = {chain[index - 1]} if index else ({previous} if previous is not None else set())
                if pred[u] != expected:
                    return None, "unexpected chain predecessor"
                if index < len(chain) - 1 and succ[u] != {chain[index + 1]}:
                    return None, "chain branches before last operation"
            if len(succ[chain[-1]]) != 1 or not succ[chain[-1]] <= tail:
                return None, "chain leaf does not enter exactly one reduction"
        roots = [u for u in tail if not succ[u] & tail]
        if len(roots) != 1:
            return None, "reduction must have one root"
        root = roots[0]
        for u in tail:
            if len(pred[u]) != 2 or not pred[u] <= heavy | tail:
                return None, "reduction must be binary over chains"
            if u != root and (len(succ[u]) != 1 or not succ[u] <= tail):
                return None, "reduction branch leaves its tail"
        if previous is not None and succ[previous] != starts:
            return None, "previous root must fork to all next chains only"
        rounds.append({"stage": stage, "chains": chains, "tail": sorted(tail),
                       "root": root, "width": width, "h": costs[0],
                       "tail_cycles": sum(max(1, ops[u]["cycles"]) for u in tail)})
        previous = root
    if not rounds or succ[previous]:
        return None, "missing rounds or final root is not terminal"
    return rounds, "guard passed"


def construct(graph, cores, waits=None, *, fuse_reductions=False):
    if type(cores) is not int or not 2 <= cores <= 5:
        raise ValueError("cores must be an integer in 2..5")
    waits = {"task_same_core_wait_cycles": 100,
             "task_cross_core_wait_cycles": 1000} if waits is None else waits
    same, cross = waits["task_same_core_wait_cycles"], waits["task_cross_core_wait_cycles"]
    if type(same) is not int or type(cross) is not int or not 0 <= same <= cross:
        raise ValueError("waits must be integers with 0 <= same <= cross")
    rounds, reason = guarded_stages(graph, cores)
    if rounds is None:
        return None, {"selected": "unsupported", "reason": reason}
    mapping, schedules, tasks, records = {}, [[] for _ in range(cores)], [], []
    _, full_succ = _build_op_adjacency(graph)
    compute = {o["id"] for o in graph["ops"] if o["op"] not in {"COPY_IN", "COPY_OUT"}}
    pred = {u: set() for u in compute}
    for u in compute:
        for v in full_succ[u] & compute:
            pred[v].add(u)
    total_fused = total_tails = 0
    def add(core, nodes, stage, phase, count):
        task = len(tasks)
        for u in nodes:
            if u in mapping:
                raise AssertionError("duplicate compute assignment")
            mapping[u] = task
        schedules[core].append(task)
        tasks.append({"id": task, "core": core, "stage": stage, "phase": phase,
                      "ops": len(nodes), "intact_chains": count})
    for index, entry in enumerate(rounds):
        width, h = entry["width"], entry["h"]
        gate = 1 if index == 0 else 2
        counts, active, q, proxy = choose_counts(width, cores, h, gate, same, cross)
        offset = 0
        branch_task_ids = set()
        for core, count in enumerate(counts):
            if count == 0:
                continue
            chosen = entry["chains"][offset:offset + count]
            add(core, [u for chain in chosen for u in chain], entry["stage"], 0, count)
            branch_task_ids.add(tasks[-1]["id"])
            offset += count
        if offset != width:
            raise AssertionError("incomplete chain packing")
        fused, residual = [], []
        tail_members = set(entry["tail"])
        tail_order = topo(tail_members,
                          {u: full_succ[u] & tail_members for u in tail_members})
        for u in tail_order:
            parents = pred[u]
            target = {mapping[p] for p in parents if p in mapping}
            if (fuse_reductions and len(parents) == 2 and len(target) == 1 and
                    all(p in mapping for p in parents) and
                    next(iter(target)) in branch_task_ids):
                task = next(iter(target))
                mapping[u] = task
                tasks[task]["ops"] += 1
                fused.append(u)
            else:
                residual.append(u)
        if residual:
            add(0, residual, entry["stage"], 1, 0)
            total_tails += 1
        total_fused += len(fused)
        records.append({"stage": entry["stage"], "width": width, "h": h,
                        "tail_cycles": entry["tail_cycles"], "q": q,
                        "counts": counts, "active_cores": active,
                        "gate_multiplier": gate, "proxy": proxy,
                        "fused_reduction_ops": fused,
                        "residual_tail_ops": len(residual),
                        "emitted_tail_count": int(bool(residual))})
    plan = {"node_to_subgraph": {u: mapping[u] for u in sorted(mapping)},
            "core_schedules": schedules}
    view = derive_multicore_plan(graph, plan)
    validate_task_order(view)
    rank = {t["id"]: (t["stage"], t["phase"]) for t in tasks}
    edges = list(view["dependency_pairs"]) + [
        (a, b) for seq in schedules for a, b in zip(seq, seq[1:])]
    if any(rank[a] >= rank[b] for a, b in edges):
        raise AssertionError("joint Task edge does not advance stage/phase")
    return plan, {"algorithm_id": "q1-gated-root-frontier",
                  "variant": ("root-wait-balanced-chains-fused-v1" if fuse_reductions
                              else "root-wait-balanced-chains-v1"),
                  "selected": "gated-root-frontier", "reason": reason,
                  "rounds": records, "task_count": len(tasks), "tasks": tasks,
                  "fused_reduction_ops": total_fused,
                  "emitted_tail_count": total_tails,
                  "tail_core": 0,
                  "scope": "Counts use unfused structural proxy, not E0 prediction or certificate; "
                           "fusion may change DDR, FIFO, or memory, with no quality dominance claim."}
