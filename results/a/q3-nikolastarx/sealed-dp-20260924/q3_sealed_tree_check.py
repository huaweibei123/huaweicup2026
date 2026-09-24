"""Independent static checks for the local Index adapter, never E0."""
import hashlib
import json
import random
import time
from pathlib import Path

from src.q3.construct import Index, UnsupportedStructure, topo
from src.q3.pipe_bound import analyze
from q3_sealed_tree_prototype import construct, _guard, _signatures


def graph(children, weights=None, pipes=None):
    weights = weights or dict.fromkeys(children, 1)
    pipes = pipes or dict.fromkeys(children, 'PIPE_M')
    return {'ops': [{'id': u, 'op': 'COMPUTE', 'pipe': pipes[u], 'cycles': weights[u]}
                    for u in children], 'tensors': [],
            'edges': [{'source': u, 'target': v} for v, ch in children.items() for u in ch]}


def perfect(height, weight=1):
    children = {}
    def add(h):
        ch = () if h == 0 else (add(h - 1), add(h - 1))
        u = len(children)
        children[u] = ch
        return u
    add(height)
    return graph(children, dict.fromkeys(children, weight))


def owner(plan):
    c = {sg: j for j, seq in enumerate(plan['core_schedules']) for sg in seq}
    return {int(u): c[sg] for u, sg in plan['node_to_subgraph'].items()}


def check(g, k, delay, expected=None):
    before = json.dumps(g, sort_keys=True)
    index = Index(g)
    p, m = construct(index, k, delay)
    assert (p, m) == construct(index, k, delay)
    assert set(p) == {'node_to_subgraph', 'core_schedules'}
    assert set(owner(p)) == set(index.ops)
    assert json.dumps(g, sort_keys=True) == before
    independent = analyze(g, p, delay)
    l = independent['with_cross_core_delay']['lower_bound_cycles']
    assert l == m['abstract_fifo_cycles'] <= m['abstract_witness_upper_cycles']
    assert independent['zero_delay']['lower_bound_cycles'] == m['zero_delay_fifo_cycles']
    assert owner(p)[m['root']] == 0
    assert all(a >= b for a, b in zip(m['root_witness_by_budget'], m['root_witness_by_budget'][1:]))
    # The entire per-core word also has a common topological extension.
    successors = {u: set(index.succ[u]) for u in index.ops}
    inverse = {sg: int(u) for u, sg in p['node_to_subgraph'].items()}
    for word in p['core_schedules']:
        for a, b in zip(word, word[1:]):
            successors[inverse[a]].add(inverse[b])
    topo(successors, successors)
    if expected is not None:
        assert (l, m['abstract_witness_upper_cycles']) == (expected, expected)
    return p, m


def check_signature(g, rng):
    index = Index(g)
    root, ch, w = _guard(index)
    pipes, matrices, rows, local = _signatures(index, ch, w)
    checked = 0
    for v in index.order:
        word, stack = [], [(v, False)]
        while stack:
            x, done = stack.pop()
            if done:
                word.append(x)
            else:
                stack.append((x, True))
                stack.extend((a, False) for a in reversed(ch[x]))
        for values in ([0] * len(pipes), [rng.randrange(0, 150) for _ in pipes]):
            state = [0] + values
            projected = [max(a + state[j] for j, a in enumerate(row) if a is not None)
                         for row in matrices[v]]
            f = max(a + state[j] for j, a in enumerate(rows[v]) if a is not None)
            available, ends = dict(zip(pipes, values)), {}
            for u in word:
                p = index.ops[u]['pipe']
                ends[u] = max(available[p], max((ends[a] for a in ch[u]), default=0)) + w[u]
                available[p] = ends[u]
            assert projected == [0] + [available[p] for p in pipes]
            assert f == ends[v]
            if not any(values): assert f == local[v]
            checked += 1
    return checked


started = time.perf_counter()
records = []
for name, g, k, d, e in [
    ('two_unit_leaves_delay500', perfect(1), 2, 500, 3),
    ('perfect15_k4_delta0', perfect(3), 4, 0, 5),
    ('perfect15_k4_weight1000_delta500', perfect(3, 1000), 4, 500, 6000),
    ('raw_zero_singleton', graph({0: ()}, {0: 0}), 5, 500, 1),
    ('first_child_root_row', graph({0: (), 1: (), 2: (0, 1)}, {0: 100, 1: 1, 2: 1},
                                   {0: 'PIPE_V', 1: 'PIPE_M', 2: 'PIPE_M'}), 1, 500, 101),
    ('PAR_B_return_core', graph({0: (), 1: (), 2: (0, 1)}, {0: 1, 1: 100, 2: 1}), 2, 50, 101),
    ('PAR_B_under_unary', graph({0: (), 1: (), 2: (0, 1), 3: (2,)},
                               {0: 1, 1: 100, 2: 1, 3: 1}), 2, 50, 102),
]:
    p, m = check(g, k, d, e)
    if name == 'PAR_B_return_core': assert owner(p)[1] == owner(p)[2] == 0 and owner(p)[0] == 1
    records.append({'name': name, 'L': m['abstract_fifo_cycles'], 'H': m['abstract_witness_upper_cycles']})

ch = {0: (), 1: (), 2: (0, 1), 3: (), 4: (), 5: (3, 4), 6: (2, 5),
      7: (), 8: (), 9: (7, 8), 10: (6, 9)}
g = graph(ch)
p, m = check(g, 2, 0, 7)
alt = {'node_to_subgraph': {str(u): u for u in ch},
       'core_schedules': [[0, 3, 2, 5, 6, 10], [1, 4, 7, 8, 9]]}
assert analyze(g, alt, 0)['zero_delay']['lower_bound_cycles'] == 6
records.append({'name': 'eleven_node_restricted_family_not_global_optimum', 'L': 7, 'H': 7,
                'explicit_alternative': 6})

rejects = []
for name, g in [
    ('fork', graph({0: (), 1: (0,), 2: (0,), 3: (1, 2)})),
    ('high_indegree', graph({0: (), 1: (), 2: (), 3: (0, 1, 2)})),
    ('forest', graph({0: (), 1: ()})),
]:
    try: construct(Index(g), 2, 500)
    except UnsupportedStructure as e: rejects.append({'name': name, 'reason': str(e)})
    else: raise AssertionError(name + ' accepted')
# Original COPY bridge is a path in Index but not a supported P3 direct/tensor edge.
g = graph({0: (), 1: ()})
g['ops'].append({'id': 10, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 1})
g['edges'] = [{'source': 0, 'target': 10}, {'source': 10, 'target': 1}]
try: construct(Index(g), 2, 500)
except UnsupportedStructure as e: rejects.append({'name': 'COPY_bridge', 'reason': str(e)})
else: raise AssertionError('COPY bridge accepted')

rng = random.Random(240924073)
random_plans = signature_states = 0
for n in (1, 2, 3, 7, 11, 23, 37):
    for repetition in range(6):
        children = {0: []}
        available = [0]
        for u in range(1, n):
            parent = rng.choice(available)
            children[parent].append(u)
            if len(children[parent]) == 2: available.remove(parent)
            children[u] = []
            available.append(u)
        g = graph(children, {u: rng.randrange(0, 100) for u in children},
                  {u: rng.choice(('PIPE_M', 'PIPE_V')) for u in children})
        signature_states += check_signature(g, rng)
        for k in (1, 2, 3, 5):
            for d in (0, 7, 500):
                check(g, k, d)
                random_plans += 1

result = {'schema': 'q3-sealed-tree-static-check-v1', 'official_evaluations': 0,
          'prototype_sha256': hashlib.sha256(Path(__file__).resolve().with_name('q3_sealed_tree_prototype.py').read_bytes()).hexdigest(),
          'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'seed': 240924073, 'fixed_checks': records, 'rejected_structures': rejects,
          'random_tree_count': 42, 'random_plan_checks': random_plans,
          'signature_state_checks': signature_states, 'elapsed_seconds': time.perf_counter() - started,
          'all_passed': True}
Path(__file__).resolve().with_name('q3-sealed-tree-static-check.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
