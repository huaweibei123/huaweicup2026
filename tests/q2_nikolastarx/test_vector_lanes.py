"""Synthetic template/negative cases and contiguous-partition oracle; no E0."""
import copy
from itertools import combinations
import random
import unittest

from src.q2_nikolastarx.direct import Index, UnsupportedStructure, derive_multicore_plan
from src.q2_nikolastarx.vector_lanes import build, recognize, _partition


CONFIG = {'capacity': {'L1': 524288, 'UB': 131072}, 'bandwidth': 60}


def template(lanes=5, stages=3, length=3, sizes=None, scalar=3, wrapped=True):
    sizes = sizes or [1024 + 128 * i for i in range(lanes)]
    graph = {'ops': [], 'tensors': [], 'edges': []}
    op_id, tensor_id = 0, 100000

    def tensor(size, pos):
        nonlocal tensor_id
        tensor_id += 1
        graph['tensors'].append({'id': tensor_id, 'size': size, 'pos': pos})
        return tensor_id

    def operation(inputs, output, cycles, kind='WORK', pipe='PIPE_V'):
        nonlocal op_id
        op_id += 1
        graph['ops'].append({'id': op_id, 'cycles': cycles, 'op': kind, 'pipe': pipe})
        graph['edges'].extend({'source': t, 'target': op_id} for t in inputs)
        graph['edges'].append({'source': op_id, 'target': output})
        return op_id

    anchors = []
    for size in sizes:
        anchor = tensor(size, 'L1')
        anchors.append(anchor)
        if wrapped:
            source = tensor(size, 'DDR')
            operation([source], anchor, 0, 'COPY_IN', 'PIPE_MTE2')
    previous = None
    for stage in range(stages):
        leaves = []
        for lane, (anchor, size) in enumerate(zip(anchors, sizes)):
            inputs = [anchor] + ([] if previous is None else [previous])
            for depth in range(length):
                output = tensor(size if depth < length-1 else scalar, 'UB')
                operation(inputs, output, 10 + lane + depth + stage)
                inputs = [output]
            leaves.append(output)
        while len(leaves) > 1:
            next_leaves = []
            for i in range(0, len(leaves)-1, 2):
                output = tensor(scalar, 'UB')
                operation(leaves[i:i+2], output, 2)
                next_leaves.append(output)
            if len(leaves) % 2:
                next_leaves.append(leaves[-1])
            leaves = next_leaves
        previous = leaves[0]
    if wrapped:
        output = tensor(scalar, 'DDR')
        operation([previous], output, 0, 'COPY_OUT', 'PIPE_MTE3')
    return graph


def owners(graph, plan):
    view = derive_multicore_plan(graph, plan)
    return {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}


class VectorLaneTests(unittest.TestCase):
    def test_general_template_fixed_ownership_and_closed_chain(self):
        graph = template(lanes=5, stages=3, length=3)
        plan, detail = build(graph, 3, CONFIG)
        model = recognize(Index(graph))
        own = owners(graph, plan)
        self.assertEqual((detail['lanes'], detail['stages']), (5, 3))
        self.assertFalse(detail['zero_spill_claim'])
        self.assertFalse(detail['official_score_available'])
        mapping = {int(k): v for k, v in plan['node_to_subgraph'].items()}
        for anchor in model['anchors']:
            all_heads = [stage['heads'][anchor] for stage in model['stages']]
            expected_core = own[all_heads[0]]
            for h in all_heads:
                chain = model['heads'][h]
                self.assertEqual({own[u] for u in chain}, {expected_core})
                seq = plan['core_schedules'][expected_core]
                positions = [seq.index(mapping[u]) for u in chain]
                self.assertEqual(positions, list(range(positions[0], positions[0]+len(chain))))
        self.assertEqual(set(plan), {'node_to_subgraph', 'core_schedules'})

    def test_more_cores_than_lanes_and_one_stage_no_copy_wrapper(self):
        graph = template(lanes=3, stages=1, length=2, scalar=7, wrapped=False)
        plan, detail = build(graph, 5, CONFIG)
        self.assertEqual(len(plan['core_schedules']), 5)
        self.assertEqual(sum(bool(x) for x in plan['core_schedules']), 3)
        self.assertEqual(detail['stages'], 1)
        self.assertEqual(detail['scalar_bytes'], 7)

    def test_record_shuffle_deterministic_and_does_not_mutate_input(self):
        graph = template()
        original = copy.deepcopy(graph)
        shuffled = copy.deepcopy(graph)
        for records in shuffled.values():
            records.reverse()
        self.assertEqual(build(graph, 4, CONFIG), build(shuffled, 4, CONFIG))
        self.assertEqual(graph, original)

    def test_compute_edges_plus_core_fifo_are_acyclic(self):
        graph = template(lanes=7, stages=4, length=2)
        plan, _ = build(graph, 4, CONFIG)
        index = Index(graph)
        succ = {u: set(vs) for u, vs in index.succ.items()}
        reverse = {sg: int(u) for u, sg in plan['node_to_subgraph'].items()}
        for seq in plan['core_schedules']:
            for a, b in zip(seq, seq[1:]):
                succ[reverse[a]].add(reverse[b])
        degree = dict.fromkeys(succ, 0)
        for vs in succ.values():
            for v in vs:
                degree[v] += 1
        ready = [u for u in degree if degree[u] == 0]
        seen = []
        while ready:
            u = ready.pop()
            seen.append(u)
            for v in succ[u]:
                degree[v] -= 1
                if degree[v] == 0:
                    ready.append(v)
        self.assertEqual(set(seen), set(index.ops))

    def test_raw_capacity_certificate_does_not_promise_no_spill(self):
        graph = template(lanes=2, stages=2, length=4)
        _, detail = build(graph, 1, {'capacity': {'L1': 1, 'UB': 1}})
        row = detail['per_core'][0]
        self.assertFalse(row['raw_envelope_within_capacity'])
        self.assertLessEqual(row['raw_priority_peak_bytes']['UB'], row['raw_envelope_bytes']['UB'])
        self.assertFalse(detail['zero_spill_claim'])

    def test_partition_matches_small_exhaustive_contiguous_oracle(self):
        rng = random.Random(9)
        for n in range(2, 8):
            values = [rng.randrange(1, 20) for _ in range(n)]
            for k in range(1, n+1):
                result, bound = _partition(list(range(n)), dict(enumerate(values)), k)
                expected = min(max(sum(values[a:b]) for a, b in zip((0,)+cuts, cuts+(n,)))
                               for cuts in combinations(range(1, n), k-1))
                loads = [sum(values[t] for t in result if result[t] == c) for c in range(k)]
                self.assertEqual(max(loads), expected)
                self.assertEqual(bound, expected)
                self.assertEqual(sorted(set(result.values())), list(range(k)))

    def test_refuses_large_tensor_branch_or_hidden_dependency(self):
        graph = template(lanes=3, stages=2)
        model = recognize(Index(graph))
        first = model['stages'][0]['heads']
        h1, h2 = [first[a] for a in model['anchors'][:2]]
        first_output = next(iter(model['outgoing'][h1]))
        branched = copy.deepcopy(graph)
        branched['edges'].append({'source': first_output, 'target': model['heads'][h2][1]})
        with self.assertRaises(UnsupportedStructure):
            build(branched, 2, CONFIG)
        direct = copy.deepcopy(graph)
        direct['edges'].append({'source': h1, 'target': model['heads'][h2][-1]})
        with self.assertRaises(UnsupportedStructure):
            build(direct, 2, CONFIG)

    def test_refuses_missing_lane_in_stage_and_scalar_tree_fanout(self):
        graph = template(lanes=3, stages=2)
        model = recognize(Index(graph))
        head = model['stages'][1]['heads'][model['anchors'][0]]
        root = model['stages'][0]['root']
        graph['edges'].remove({'source': root, 'target': head})
        with self.assertRaises(UnsupportedStructure):
            build(graph, 2, CONFIG)
        graph = template(lanes=4, stages=2)
        model = recognize(Index(graph))
        leaves = sorted(model['stages'][0]['leaves'])
        consumer = next(iter(model['ec'][leaves[-1]]))
        graph['edges'].append({'source': leaves[0], 'target': consumer})
        with self.assertRaises(UnsupportedStructure):
            build(graph, 2, CONFIG)

    def test_refuses_wrong_pipe_or_anchor_pool_and_bad_core_count(self):
        for mutation in ('pipe', 'anchor'):
            graph = template()
            model = recognize(Index(graph))
            if mutation == 'pipe':
                u = min(model['index'].ops)
                next(o for o in graph['ops'] if o['id'] == u)['pipe'] = 'PIPE_M'
            else:
                t = model['anchors'][0]
                next(tensor for tensor in graph['tensors'] if tensor['id'] == t)['pos'] = 'UB'
            with self.assertRaises(UnsupportedStructure):
                build(graph, 2, CONFIG)
        for k in (True, 0, -1):
            with self.assertRaises(ValueError):
                build(template(), k, CONFIG)


if __name__ == '__main__':
    unittest.main()
