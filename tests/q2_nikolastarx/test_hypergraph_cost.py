"""Synthetic exact-byte checks; no official scoring or scheduling."""
import itertools
import unittest

from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
from src.q2_nikolastarx.hypergraph_cost import HypergraphCost, UnsupportedHypergraph


def graph():
    ops = [{'id': u, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 1} for u in (1, 2, 3)]
    ops.append({'id': 4, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 1})
    tensors = [{'id': t, 'size': s, 'pos': 'UB'} for t, s in ((10, 7), (11, 13), (12, 5))]
    edges = [{'source': a, 'target': b} for a, b in
             ((10, 1), (10, 2), (1, 11), (11, 2), (11, 3), (11, 4), (3, 12))]
    edges.append({'source': 1, 'target': 3, 'data_size': 4})
    return {'ops': ops, 'tensors': tensors, 'edges': edges}


def plan(assignment):
    return {'node_to_subgraph': {str(u): u for u in (1, 2, 3)},
            'core_schedules': [[u for u in (1, 2, 3) if assignment[u] == core]
                               for core in range(3)]}


def brute(graph_json, assignment):
    op_by_id = {o['id']: o for o in graph_json['ops']}
    total = 0
    for t in graph_json['tensors']:
        tid, size = t['id'], t['size']
        producers = {e['source'] for e in graph_json['edges'] if e['target'] == tid
                     and e['source'] in assignment}
        consumers = {e['target'] for e in graph_json['edges'] if e['source'] == tid
                     and e['target'] in assignment}
        pc = {assignment[u] for u in producers}
        cc = {assignment[u] for u in consumers}
        if cc and not pc:
            total += size * len(cc)
        original_out = any(e['source'] == tid and e['target'] in op_by_id and
                           op_by_id[e['target']]['op'] == 'COPY_OUT'
                           for e in graph_json['edges'])
        if pc and (original_out or not cc):
            total += size * len(pc)
        total += 2 * size * sum(a != b for a in pc for b in cc)
    for e in graph_json['edges']:
        a, b = e['source'], e['target']
        if a in assignment and b in assignment and assignment[a] != assignment[b]:
            total += 2 * max(0, int(e.get('data_size', 0)))
    return total


class HypergraphCostTests(unittest.TestCase):
    def test_all_small_placements_match_independent_sets_and_static_counter(self):
        source = graph()
        model = HypergraphCost(source, {1, 2, 3})
        for cores in itertools.product(range(3), repeat=3):
            assignment = dict(zip((1, 2, 3), cores))
            state = model.state(assignment)
            self.assertEqual(state.total_bytes, brute(source, assignment))
            self.assertEqual(state.total_bytes,
                             mandatory_copy_work(source, plan(assignment), 60)['transfer_bytes'])

    def test_multi_pin_group_delta_and_apply(self):
        source = graph()
        model = HypergraphCost(source, (1, 2, 3))
        for assignment in ({1: 0, 2: 0, 3: 1}, {1: 0, 2: 0, 3: 0}):
            state = model.state(assignment)
            for group in ((1,), (2,), (1, 2)):
                trial = model.state(assignment)
                changed = dict(assignment)
                changed.update({u: 1 for u in group})
                expected = brute(source, changed) - brute(source, assignment)
                self.assertEqual(trial.delta(group, 0, 1), expected)
                self.assertEqual(trial.apply(group, 0, 1), expected)
                self.assertEqual(trial.total_bytes, brute(source, changed))
                self.assertEqual(trial.assignment, changed)
            self.assertEqual(state.assignment, assignment)
        # The internal tensor has two original pins in the moving chain.
        internal = {'ops': source['ops'], 'tensors': [source['tensors'][1]],
                    'edges': [e for e in source['edges'] if (e['source'], e['target']) in
                              {(1, 11), (11, 2), (11, 3)}]}
        state = HypergraphCost(internal, (1, 2, 3)).state({1: 0, 2: 0, 3: 1})
        self.assertEqual(state.delta((1, 2), 0, 1), -26)

    def test_guards_and_zero_direct_bytes(self):
        source = graph()
        source['edges'].append({'source': 1, 'target': 3, 'data_size': 4})
        source['edges'].append({'source': 11, 'target': 3})
        model = HypergraphCost(source, (1, 2, 3))
        self.assertTrue(any(edge.weight == 8 for edge in model.edges))
        self.assertEqual(sum(edge.weight == 8 for edge in model.edges), 2)
        assignment = {1: 0, 2: 0, 3: 1}
        self.assertEqual(model.state(assignment).total_bytes, brute(source, assignment))
        source['edges'].append({'source': 2, 'target': 3, 'data_size': 0})
        self.assertEqual(HypergraphCost(source, (1, 2, 3)).state(assignment).total_bytes,
                         brute(source, assignment))
        source['tensors'][0]['logical_tid'] = 10
        with self.assertRaises(UnsupportedHypergraph):
            HypergraphCost(source, (1, 2, 3))
        del source['tensors'][0]['logical_tid']
        source['tensors'][0]['size'] = -1
        with self.assertRaises(UnsupportedHypergraph):
            HypergraphCost(source, (1, 2, 3))
        source['tensors'][0]['size'] = 7
        source['edges'].append({'source': 4, 'target': 11})
        with self.assertRaises(UnsupportedHypergraph):
            HypergraphCost(source, (1, 2, 3))


if __name__ == '__main__':
    unittest.main()
