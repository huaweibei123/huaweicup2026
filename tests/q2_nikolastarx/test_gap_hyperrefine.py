"""Synthetic regional placement checks; no official evaluator or real cases."""
import unittest

from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan
from src.q2_nikolastarx.gap_hyperrefine import refine
from src.q2_nikolastarx.hypergraph_cost import HypergraphCost
from tests.q2_nikolastarx.test_gap_candidate import CONFIG, diamond


def singleton(rows):
    nodes = [u for row in rows for u in row]
    return {'node_to_subgraph': {str(u): u for u in nodes}, 'core_schedules': rows}


def owners(plan):
    return {int(u): c for c, row in enumerate(plan['core_schedules'])
            for u, sg in plan['node_to_subgraph'].items() if sg in row}


def swap_graph():
    ops = [{'id': u, 'op': 'COMPUTE', 'pipe': p, 'cycles': 10}
           for u, p in ((1, 'PIPE_M'), (2, 'PIPE_M'), (3, 'PIPE_V'),
                        (4, 'PIPE_V'), (5, 'PIPE_MTE2'))]
    edges = [{'source': u, 'target': v, 'data_size': s} for u, v, s in
             ((1, 3, 100), (2, 4, 100), (1, 5, 0),
              (2, 5, 0), (5, 3, 0), (5, 4, 0))]
    return {'ops': ops, 'tensors': [], 'edges': edges}


class GapHyperrefineTests(unittest.TestCase):
    def check_result(self, graph, before, after, detail):
        derive_multicore_plan(graph, after)
        model = HypergraphCost(graph, owners(before))
        self.assertEqual(detail['before_original_copy_bytes'],
                         model.state(owners(before)).total_bytes)
        self.assertEqual(detail['after_original_copy_bytes'],
                         model.state(owners(after)).total_bytes)
        self.assertLessEqual(detail['after_original_copy_bytes'],
                             detail['before_original_copy_bytes'])
        for c, row in detail['after_pipe_loads'].items():
            for pipe, amount in row.items():
                self.assertLessEqual(amount, detail['pipe_caps'][c][pipe])
        self.assertLessEqual(detail['flows'], detail['regions'] * 17)

    def test_fork_join_refine_and_no_change_identity(self):
        graph = diamond()
        before = singleton([[1, 3, 4], [2, 5]])
        after, detail = refine(graph, before, CONFIG)
        self.check_result(graph, before, after, detail)
        self.assertLess(detail['after_original_copy_bytes'], detail['before_original_copy_bytes'])
        same, again = refine(graph, after, CONFIG)
        self.assertIs(same, after)
        self.assertEqual(again['accepted_regions'], 0)

    def test_simultaneous_opposite_moves_and_finite_flow(self):
        graph = swap_graph()
        before = singleton([[1, 5, 4], [2, 3]])
        after, detail = refine(graph, before, CONFIG, region_width=16)
        self.check_result(graph, before, after, detail)
        old, new = owners(before), owners(after)
        self.assertTrue(any(old[u] == 0 and new[u] == 1 for u in old))
        self.assertTrue(any(old[u] == 1 and new[u] == 0 for u in old))
        self.assertEqual(detail['after_original_copy_bytes'], 0)
        self.assertGreater(detail['accepted_regions'], 0)

    def test_no_possible_connection_gain_skips_flow(self):
        graph = diamond()
        before = singleton([[1, 2, 3, 4, 5], []])
        after, detail = refine(graph, before, CONFIG)
        self.assertIs(after, before)
        self.assertEqual(detail['flows'], 0)
        self.assertGreater(detail['skipped_by_connection_floor'], 0)

    def test_multiple_regions_keep_outside_work_separate(self):
        # Twenty noncontractible chains exceed the sixteen-unit flow region.
        graph = {'ops': [], 'tensors': [], 'edges': []}
        rows = [[], []]
        for offset in (0, 10, 20, 30):
            part = swap_graph()
            graph['ops'].extend({**op, 'id': op['id'] + offset}
                                for op in part['ops'])
            graph['edges'].extend({**edge,
                                   'source': edge['source'] + offset,
                                   'target': edge['target'] + offset}
                                  for edge in part['edges'])
            rows[0].extend(u + offset for u in (1, 5, 4))
            rows[1].extend(u + offset for u in (2, 3))
        before = singleton(rows)
        after, detail = refine(graph, before, CONFIG, region_width=16)
        self.check_result(graph, before, after, detail)
        self.assertEqual(detail['regions'], 2)
        self.assertGreater(detail['flows'], 0)
        self.assertLess(detail['after_original_copy_bytes'],
                        detail['before_original_copy_bytes'])

    def test_rejects_split_chain_and_non_singleton(self):
        graph = diamond()
        before = singleton([[1, 3, 4], [2, 5]])
        bad = {'node_to_subgraph': dict(before['node_to_subgraph']),
               'core_schedules': [list(row) for row in before['core_schedules']]}
        bad['node_to_subgraph']['2'] = 1
        bad['core_schedules'][1].remove(2)
        with self.assertRaises(UnsupportedStructure):
            refine(graph, bad, CONFIG)
        split_graph = diamond()
        split_graph['ops'].append({'id': 6, 'op': 'COMPUTE',
                                   'pipe': 'PIPE_M', 'cycles': 1})
        split_graph['edges'] = [e for e in split_graph['edges']
                                if (e['source'], e['target']) != (3, 4)]
        split_graph['edges'] += [{'source': 3, 'target': 6, 'data_size': 8},
                                 {'source': 6, 'target': 4, 'data_size': 8}]
        with self.assertRaisesRegex(UnsupportedStructure, 'chain'):
            refine(split_graph, singleton([[1, 3, 6], [2, 4, 5]]), CONFIG)
        with self.assertRaises(ValueError):
            refine(graph, before, CONFIG, region_width=17)


if __name__ == '__main__':
    unittest.main()
