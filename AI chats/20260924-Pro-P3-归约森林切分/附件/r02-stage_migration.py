"""Two deterministic five-core singleton constructors for a guarded stage family.

Copy this file to src/q3/stage_migration.py in the repository. No evaluator calls.
Use construct(index, 5, 'single_cut') for the lower-traffic candidate.
Use construct(index, 5, 'two_cut_optimal') for the compute+500-optimal certificate.
The optimality assertion concerns the COMPUTATION MODEL ONLY, not official P3.
"""
from __future__ import annotations

# Original ADD nodes are looked up by descendant sets, never recreated.
ADD_SETS = [frozenset((2*j, 2*j+1)) for j in range(6)] + [
    frozenset(range(0, 4)), frozenset(range(4, 8)),
    frozenset(range(8, 12)), frozenset(range(0, 8)),
    frozenset(range(0, 12)),
]
ADD_WORD = (0, 1, 2, 3, 6, 7, 9, 5, 4, 8, 10)


def _build(index, rec: dict, variant: str) -> tuple[dict, dict]:
    """Internal builder; caller must run the existing recognize(index) guard."""
    if variant not in {'single_cut', 'two_cut_optimal'}:
        raise ValueError('unknown variant')
    lanes = rec['lane_ids']
    if len(lanes) != 12:
        raise ValueError('requires exactly 12 immutable-input lanes')
    slot = {lane:j for j,lane in enumerate(lanes)}
    schedules: list[list[int]] = [[] for _ in range(5)]
    migration_edges = []
    collector_sequence = []
    for number, stage in enumerate(rec['stages']):
        chains = [list(stage['chains'][lane]) for lane in lanes]
        if any(len(ch) != 4 or any(index.duration(u) != 524 for u in ch) for ch in chains):
            raise ValueError('requires four indivisible 524-cycle ops per lane')
        by_set = {}
        for u in stage['join_order']:
            key = frozenset(slot[x] for x in stage['descendants'][u])
            if key in by_set or index.duration(u) != 13:
                raise ValueError('original ADD shape/duration mismatch')
            by_set[key] = u
        if set(by_set) != set(ADD_SETS):
            raise ValueError('original tree does not match the verified 8+4 shape and lane order')
        joins = [by_set[key] for key in ADD_SETS]
        if joins[-1] != stage['root']:
            raise ValueError('root mismatch')
        L = chains
        seq = [[] for _ in range(5)]
        if variant == 'single_cut':
            collector = 2
            seq[0] = L[2][:2] + L[0] + L[1]
            seq[1] = L[3] + L[4] + L[2][2:]
            seq[2] = L[5] + L[6] + L[7]
            seq[3] = L[8] + L[9]
            seq[4] = L[10] + L[11]
            owner = {u:c for c,word in enumerate(seq) for u in word}
            leaf_core = {lane:owner[stage['chains'][lane][-1]] for lane in lanes}
            pure, mixed = [], []
            for u in stage['join_order']:
                cs = {leaf_core[x] for x in stage['descendants'][u]}
                owner[u] = next(iter(cs)) if len(cs) == 1 else collector
                (pure if len(cs) == 1 else mixed).append(u)
            for u in pure + mixed:
                seq[owner[u]].append(u)
        else:
            # First stage has no root-release delay; subsequently a is the previous root.
            a = number % 2
            b = 1 - a
            collector = b
            seq[a] = L[2][:2] + L[0] + L[10]
            seq[b] = L[3] + L[4] + L[2][2:]
            seq[2] = L[9][:2] + L[5] + L[8]
            seq[3] = L[1] + L[11] + L[9][2:]
            seq[4] = L[6] + L[7]
            if number == 0:
                # Original ADD(10,11) runs on core a to meet the first-stage bound.
                # This changes ownership only; both original incoming edges remain.
                seq[a].append(joins[5])
                seq[b].extend(joins[j] for j in ADD_WORD if j != 5)
            else:
                seq[b].extend(joins[j] for j in ADD_WORD)
        owner = {u:c for c,word in enumerate(seq) for u in word}
        nodes = set(stage['join_order']) | {u for ch in chains for u in ch}
        if set(owner) != nodes or sum(map(len,seq)) != len(nodes):
            raise AssertionError('stage coverage/duplicate error')
        for j,ch in enumerate(chains):
            for u,v in zip(ch,ch[1:]):
                if owner[u] != owner[v]:
                    migration_edges.append({'stage':number+1,'lane_slot':j,'source_op':u,
                        'target_op':v,'source_core':owner[u],'target_core':owner[v]})
        collector_sequence.append(collector)
        for c in range(5):
            schedules[c].extend(seq[c])
    mapping = {str(u):j for j,u in enumerate(index.order)}
    plan = {'node_to_subgraph':mapping,
            'core_schedules':[[mapping[str(u)] for u in word] for word in schedules]}
    n = len(rec['stages'])
    if n < 1:
        raise ValueError('empty stage sequence')
    return plan, {
        'strategy':'stage_migration_' + variant,
        'stage_count':n,
        'large_vector_migration_edges':migration_edges,
        'large_vector_migrations':len(migration_edges),
        'collector_sequence':collector_sequence,
        'compute_plus_500_expected':6379*n if variant == 'single_cut' else 6279*n-500,
        'compute_model_global_lower_bound':6279*n-500,
        'official_e0_calls':0,
        'official_execution_feasibility_proved':False,
        'memory_cache_bandwidth_not_simulated':True,
    }


def construct(index, cores: int, variant: str = 'single_cut') -> tuple[dict, dict]:
    from .construct import UnsupportedStructure, derive_multicore_plan
    from .stage_fork_join import recognize
    if type(cores) is not int or cores != 5:
        raise UnsupportedStructure('these two constructions are five-core only')
    rec = recognize(index)
    sig = rec['signature']
    if sig[0] != 4 or tuple(sig[1]) != (524,)*4 or sig[-2:] != (32768,2):
        raise UnsupportedStructure('requires the proved 4x524, 32768-to-2 signature')
    try:
        plan, meta = _build(index,rec,variant)
    except ValueError as exc:
        raise UnsupportedStructure(str(exc)) from exc
    derive_multicore_plan(index.graph,plan)  # official static validation only
    return plan,meta
