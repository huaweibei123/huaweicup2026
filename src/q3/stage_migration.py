"""Guarded five-core stage templates with one or two vector migrations.

Adapted after source review from the Pro r02 proposal archived at
AI chats/20260924-Pro-P3-归约森林切分/附件/r02-stage_migration.py.
The constructor moves whole original operations and preserves all tensor/tree
edges. It does not execute the archived code or run an official evaluator.

The returned bound includes original compute work, per-core V FIFO and a
500-cycle cross-core dependency lag. COPY service, allocation, bandwidth and
Cache are omitted. Acyclic compute words do not prove official feasibility.
"""
from __future__ import annotations

from .construct import UnsupportedStructure
from .pipe_bound import analyze
from .stage_fork_join import recognize


_MODES = {"single_cut", "two_cut"}
_SIGNATURE = (4, (524, 524, 524, 524), ("RELU", "RELU", "REDUCE"), 32768, 2)
# Identify original ADD nodes by immutable-input lane slots, never op IDs.
_ADD_SETS = tuple(frozenset((2 * j, 2 * j + 1)) for j in range(6)) + (
    frozenset(range(4)), frozenset(range(4, 8)), frozenset(range(8, 12)),
    frozenset(range(8)), frozenset(range(12)),
)
_TWO_CUT_ADD_WORD = (0, 1, 2, 3, 6, 7, 9, 5, 4, 8, 10)


def _guard(index):
    rec = recognize(index)
    if len(rec["lane_ids"]) != 12:
        raise UnsupportedStructure("stage migration requires exactly 12 immutable-input lanes")
    if rec["signature"] != _SIGNATURE:
        raise UnsupportedStructure("requires the exact 4x524 RELU/RELU/REDUCE, 32768-to-2 signature")
    if not rec["stages"]:
        raise UnsupportedStructure("requires a nonempty stage sequence")
    # Index already validates integer cycles and sizes. Keep raw work checks
    # here too: template applicability must not depend on duration() clamping.
    for op in index.graph["ops"]:
        if op["op"] in {"COPY_IN", "COPY_OUT"}:
            pipe = "PIPE_MTE2" if op["op"] == "COPY_IN" else "PIPE_MTE3"
            if op["pipe"] != pipe or type(op["cycles"]) is not int or op["cycles"] != 0:
                raise UnsupportedStructure("requires original zero-cycle COPY_IN/MTE2 and COPY_OUT/MTE3")
    slots = {lane: j for j, lane in enumerate(rec["lane_ids"])}
    stage_joins = []
    for number, stage in enumerate(rec["stages"]):
        expected_kinds = ("RELU" if number == 0 else "ADD", "RELU", "RELU", "REDUCE")
        for chain in stage["chains"].values():
            if (len(chain) != 4 or tuple(index.ops[u]["op"] for u in chain) != expected_kinds
                    or any(type(index.ops[u]["cycles"]) is not int
                           or index.ops[u]["cycles"] != 524 for u in chain)):
                raise UnsupportedStructure("requires four original 524-cycle V operations per lane")
        by_set = {}
        for u in stage["join_order"]:
            op = index.ops[u]
            key = frozenset(slots[lane] for lane in stage["descendants"][u])
            if (key in by_set or op["op"] != "ADD"
                    or type(op["cycles"]) is not int or op["cycles"] != 13):
                raise UnsupportedStructure("original scalar ADD shape/duration mismatch: requires 13 cycles")
            by_set[key] = u
        if set(by_set) != set(_ADD_SETS):
            raise UnsupportedStructure("requires the original 8+4 tree in sorted immutable-lane order")
        joins = [by_set[key] for key in _ADD_SETS]
        if joins[-1] != stage["root"]:
            raise UnsupportedStructure("original stage root does not match its full leaf set")
        stage_joins.append(joins)
    return rec, stage_joins


def construct(index, cores: int, mode: str = "single_cut", *,
              cross_core_delay_cycles: int = 500) -> tuple[dict, dict]:
    """Return a two-field singleton plan and static diagnostics, without scoring.

    Both modes have a narrow, identical input guard; unsupported graphs raise
    UnsupportedStructure instead of falling back to another construction.
    ``single_cut`` migrates lane 2 after op 2 with fixed collector 2.
    ``two_cut`` also migrates lane 9 and alternates collectors 1, 0, 1, 0.
    The caller must check the actual frozen configuration has delay 500.
    """
    if type(cores) is not int or cores != 5:
        raise UnsupportedStructure("stage migration is five-core only")
    if mode not in _MODES:
        raise ValueError("mode must be single_cut or two_cut")
    if type(cross_core_delay_cycles) is not int or cross_core_delay_cycles != 500:
        raise UnsupportedStructure("stage migration template requires a 500-cycle cross-core delay")
    rec, stage_joins = _guard(index)
    lanes = rec["lane_ids"]
    words = [[] for _ in range(cores)]
    migration_edges, collectors, stage_diagnostics = [], [], []
    for number, (stage, joins) in enumerate(zip(rec["stages"], stage_joins)):
        chains = [stage["chains"][lane] for lane in lanes]
        seq = [[] for _ in range(cores)]
        if mode == "single_cut":
            collector = 2
            seq[0] = chains[2][:2] + chains[0] + chains[1]
            seq[1] = chains[3] + chains[4] + chains[2][2:]
            seq[2] = chains[5] + chains[6] + chains[7]
            seq[3] = chains[8] + chains[9]
            seq[4] = chains[10] + chains[11]
            owner = {u: core for core, word in enumerate(seq) for u in word}
            # Reduction ownership follows each chain's LAST operation, which
            # differs from its head on the migrated lane. Canonical leaf sets
            # make this word independent of topological op-ID tie breaking.
            leaf_core = {lane: owner[stage["chains"][lane][-1]] for lane in lanes}
            pure, mixed = [], []
            for u in joins:
                owners = {leaf_core[lane] for lane in stage["descendants"][u]}
                owner[u] = next(iter(owners)) if len(owners) == 1 else collector
                (pure if len(owners) == 1 else mixed).append(u)
            for u in pure + mixed:
                seq[owner[u]].append(u)
        else:
            # Stage zero has no incoming root. Later a is the previous root's
            # owner, and b becomes the new root's owner.
            a, b = number % 2, 1 - number % 2
            collector = b
            seq[a] = chains[2][:2] + chains[0] + chains[10]
            seq[b] = chains[3] + chains[4] + chains[2][2:]
            seq[2] = chains[9][:2] + chains[5] + chains[8]
            seq[3] = chains[1] + chains[11] + chains[9][2:]
            seq[4] = chains[6] + chains[7]
            if number == 0:
                # The first-stage boundary uses this ORIGINAL ADD on a. Do
                # not apply the later-stage scalar word to this boundary.
                seq[a].append(joins[5])
                seq[b].extend(joins[j] for j in _TWO_CUT_ADD_WORD if j != 5)
            else:
                seq[b].extend(joins[j] for j in _TWO_CUT_ADD_WORD)
        owner = {u: core for core, word in enumerate(seq) for u in word}
        expected = set(stage["join_order"]) | {u for chain in chains for u in chain}
        if set(owner) != expected or sum(map(len, seq)) != len(expected):
            raise AssertionError("stage template lost or duplicated original operations")
        for lane, chain in enumerate(chains):
            for u, v in zip(chain, chain[1:]):
                if owner[u] != owner[v]:
                    migration_edges.append({"stage": number + 1, "lane_slot": lane,
                                            "source_op": u, "target_op": v,
                                            "source_core": owner[u], "target_core": owner[v],
                                            "original_tensor_bytes": 32768})
        collectors.append(collector)
        stage_diagnostics.append({
            "stage": number + 1, "root": stage["root"], "collector_core": collector,
            "work_by_core": [sum(index.ops[u]["cycles"] for u in word) for word in seq],
            "head_cores": [owner[chain[0]] for chain in chains],
            "leaf_cores": [owner[chain[-1]] for chain in chains],
        })
        for core, word in enumerate(seq):
            words[core].extend(word)
    mapping = {str(u): j for j, u in enumerate(index.order)}
    plan = {"node_to_subgraph": mapping,
            "core_schedules": [[mapping[str(u)] for u in word] for word in words]}
    # This includes official STATIC plan validation and rejects an augmented
    # original-dependency/FIFO cycle. All compute uses V, so pipe FIFO here is
    # the entire submitted per-core word. This never executes Step2/Step3/E0.
    bound = analyze(index.graph, plan, cross_core_delay_cycles)
    n = len(rec["stages"])
    template_cycles = 6379 * n if mode == "single_cut" else 6279 * n - 500
    actual_bound = bound["with_cross_core_delay"]["lower_bound_cycles"]
    if actual_bound != template_cycles:
        raise AssertionError("guarded template differs from its augmented-DAG timing certificate")
    return plan, {
        "strategy": "stage_migration_" + mode, "mode": mode,
        "provenance": "AI chats/20260924-Pro-P3-归约森林切分/附件/r02-stage_migration.py",
        "lane_count": 12, "stage_count": n, "chain_signature": rec["signature"],
        "collector_sequence": collectors, "stage_diagnostics": stage_diagnostics,
        "large_vector_migration_edges": migration_edges,
        "large_vector_migrations": len(migration_edges),
        "compute_plus_500_bound": actual_bound,
        "zero_delay_bound": bound["zero_delay"]["lower_bound_cycles"],
        "compute_model_template_cycles": template_cycles,
        "cross_core_delay_cycles": cross_core_delay_cycles,
        "cross_core_compute_edges": bound["cross_core_dependency_edges"],
        "total_work_by_core": [row["PIPE_V"] for row in bound["per_core_pipe_work"]],
        "original_dependency_and_core_word_acyclic": True,
        "official_e0_calls": 0, "official_execution_feasibility_proved": False,
        "memory_cache_bandwidth_not_simulated": True,
        "model_scope": "original compute + core V FIFO + 500-cycle cross-core dependency lag; not an official score prediction",
        "global_official_optimality_claimed": False,
    }
