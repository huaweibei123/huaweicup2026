"""Independent stdlib readback of submitted plans and weighted FIFO bounds.

No constructor/official imports and no scoring calls.
"""
from collections import Counter, defaultdict
import gzip
import hashlib
import heapq
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def read(path):
    if path.suffix == '.gz':
        with gzip.open(path, 'rt') as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def unpack(plan):
    inverse = {sg: int(u) for u, sg in plan['node_to_subgraph'].items()}
    assert len(inverse) == len(plan['node_to_subgraph'])
    seqs = [[inverse[sg] for sg in seq] for seq in plan['core_schedules']]
    owner = {u: c for c, seq in enumerate(seqs) for u in seq}
    assert len(owner) == sum(map(len, seqs)) == len(inverse)
    return owner, seqs


def main():
    graph = read(ROOT/'data/raw/a/official/data/case_016.json')
    ops = {x['id']: x for x in graph['ops'] if x['op'] not in ('COPY_IN', 'COPY_OUT')}
    tensors = {x['id']: x for x in graph['tensors']}
    producers, consumers, incident = defaultdict(set), defaultdict(set), defaultdict(set)
    for e in graph['edges']:
        a, b = e['source'], e['target']
        if a in ops:
            assert b in tensors
            producers[b].add(a)
            incident[a].add(b)
        elif b in ops:
            assert a in tensors
            consumers[a].add(b)
            incident[b].add(a)
    assert all(len(ps) <= 1 for ps in producers.values())
    settings, section = {}, None
    for line in (ROOT/'data/raw/a/official/data/config.txt').read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('['):
            section = line[1:-1]
        else:
            key, value = line.split()
            settings[section, key] = int(value)
    bandwidth = settings['bandwidth', 'bandwidth']
    delay = settings['multicore_scene_b', 'cross_core_copy_delay_cycles']
    receipt = read(OUT/'receipt.json')
    for name, expected in receipt['source_inputs'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected
    rows = []
    for k in (2, 4, 5):
        folder = OUT/f'016-k{k}'
        plan, ledger = read(folder/'plan.json'), read(folder/'solver.json')
        detail = ledger['attempts'][0]['detail']
        owner, seqs = unpack(plan)
        old_owner, _ = unpack(read(ROOT/f'results/a/q2-nikolastarx/vector-pilot-20260924/run/016-k{k}/plan.json'))
        assert set(owner) == set(ops) and len(seqs) == k
        scalar = detail['scalar_bytes']
        vector_ops = {u for u in ops if any(tensors[t]['size'] > scalar for t in incident[u])}
        assert all(owner[u] == old_owner[u] for u in vector_ops)
        arcs = {u: {} for u in ops}
        crosses = set()
        for t, ps in producers.items():
            for p in ps:
                for c in consumers[t]:
                    cross = owner[p] != owner[c]
                    if cross:
                        assert tensors[t]['size'] == scalar
                        crosses.add((t, owner[p], owner[c]))
                    lag = delay + 2*max(1, (tensors[t]['size']+bandwidth-1)//bandwidth) if cross else 0
                    arcs[p][c] = lag
        for seq in seqs:
            for a, b in zip(seq, seq[1:]):
                arcs[a].setdefault(b, 0)
        degree = Counter(v for vs in arcs.values() for v in vs)
        ready = [u for u in ops if not degree[u]]
        heapq.heapify(ready)
        start, seen = dict.fromkeys(ops, 0), []
        while ready:
            u = heapq.heappop(ready)
            seen.append(u)
            for v, lag in arcs[u].items():
                start[v] = max(start[v], start[u]+max(1, ops[u]['cycles'])+lag)
                degree[v] -= 1
                if not degree[v]:
                    heapq.heappush(ready, v)
        assert len(seen) == len(ops)
        bound = max(start[u]+max(1, ops[u]['cycles']) for u in ops)
        assert bound == detail['fixed_plan_bound']['makespan_lower_bound_cycles']
        references = {name: read(ROOT/f'results/a/q2-nikolastarx/{name}-pilot-20260924/run/016-k{k}/final/result.json.gz')['makespan']
                      for name in ('direct', 'vector')}
        rows.append({'cores': k, 'independent_fixed_plan_bound_cycles': bound,
            'bound_matches_constructor_ledger': True, 'vector_op_count_with_unchanged_core': len(vector_ops),
            'only_scalar_tensors_cross_cores': True, 'raw_cross_core_pairs': len(crosses),
            'raw_cross_copy_bytes_without_spill': 2*scalar*len(crosses),
            'existing_official_reference_makespans': references,
            'bound_minus_direct_official': bound-references['direct'],
            'bound_minus_vector_official': bound-references['vector'],
            'listed_proxy_period_histogram': sorted(Counter(s['listed_root_period'] for s in detail['stage_detail'][1:]).items()),
            'max_broadcast_plus_reduction_crossings_histogram': sorted(Counter(s['max_broadcast_plus_reduction_crossings_on_data_path'] for s in detail['stage_detail']).items()),
            'root_core_histogram': sorted(Counter(s['root_core'] for s in detail['stage_detail']).items()),
            'peak_raw_UB_bytes': max(c['raw_priority_peak_bytes']['UB'] for c in detail['per_core']),
            'new_official_score_available': False})
    (OUT/'readback.json').write_text(json.dumps(rows, indent=2)+'\n')
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
