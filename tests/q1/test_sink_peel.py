"""Structural adversarial witnesses only: zero E0/E1/E2 calls."""
import copy
import itertools
import unittest
from src.q1.bounded_tasks import construct as bounded
from src.q1.component_pack import construct as component
from src.q1.sink_peel import construct, peel_packets, PeelBudgetExceeded
from tests.q1.test_component_pack import graph


def adjacency(n, edges):
    p, s = {i: set() for i in range(n)}, {i: set() for i in range(n)}
    for u, v in edges:
        s[u].add(v); p[v].add(u)
    return p, s


class SinkPeelTests(unittest.TestCase):
    def test_coarse_forked_regions_stay_intact(self):
        # Shared prefix 1 -> two regions which each contain a diamond and sink.
        links = [(1, 2), (2, 3), (2, 4), (3, 5), (4, 5),
                 (1, 6), (6, 7), (6, 8), (7, 9), (8, 9)]
        g = graph([(u, 'V', 0 if u == 1 else 100) for u in range(1, 10)], links)
        original = copy.deepcopy(g)
        plan, d = construct(g, 2)
        self.assertEqual(d['selected'], 'sink-peel')
        self.assertEqual(d['wave_count'], 2)
        self.assertEqual(d['tasks'], 3)
        self.assertEqual(d['waves'][0]['pipe_work_by_core'][0], {'PIPE_V': 1})
        for region in [(2, 3, 4, 5), (6, 7, 8, 9)]:
            self.assertEqual(len({plan['node_to_subgraph'][u] for u in region}), 1)
        self.assertNotEqual(plan['node_to_subgraph'][2], plan['node_to_subgraph'][6])
        self.assertEqual(g, original)
        self.assertEqual(construct(g, 2), (plan, d))

    def test_repeated_shared_layers_are_not_merged_across_gates(self):
        links = [(0, 1), (0, 2), (1, 3), (2, 3), (1, 4), (2, 4)]
        p, s = adjacency(5, links)
        waves = peel_packets(range(5), p, s)
        self.assertEqual(waves, [[[0]], [[1], [2]], [[3], [4]]])

    def test_copy_bridge_remains_a_precedence_edge(self):
        g = graph([(1, 'V', 10), (2, 'M', 1), (3, 'V', 10), (4, 'V', 10)],
                  [(1, 2), (2, 3), (1, 4)])
        g['ops'][1]['op'] = 'COPY_IN'
        plan, d = construct(g, 2)
        self.assertEqual(d['wave_count'], 2)
        self.assertNotIn(2, plan['node_to_subgraph'])
        self.assertNotEqual(plan['node_to_subgraph'][1], plan['node_to_subgraph'][3])

    def test_budgets_and_single_sink_fall_back_without_partial_plan(self):
        g = graph([(i, 'V', 10) for i in range(1, 4)], [(1, 2), (1, 3)])
        for kwargs in ({'max_rounds': 1}, {'max_sinks': 1}):
            plan, d = construct(g, 2, **kwargs)
            self.assertEqual(d['selected'], 'bounded04')
            self.assertEqual(plan, component(g, 2)[0])
        single = graph([(i, 'V', 10) for i in range(1, 5)],
                       [(1, 2), (1, 3), (2, 4), (3, 4)])
        self.assertEqual(construct(single, 2)[0], component(single, 2)[0])
        for bad in (0, True):
            with self.assertRaises(ValueError):
                construct(g, 2, max_rounds=bad)
        p, s = adjacency(2, [(0, 1), (1, 0)])
        with self.assertRaises(ValueError):
            peel_packets(range(2), p, s)

    def test_existing_in_tree_plan_is_retained(self):
        g = graph([(u, 'V', 100) for u in range(1, 6)],
                  [(1, 5), (2, 5), (3, 5), (4, 5)])
        plan, d = construct(g, 4)
        self.assertEqual(plan, bounded(g, 4)[0])
        self.assertEqual(d['selected'], 'bounded04')

    def test_all_five_vertex_ordered_dags_have_monotone_cross_packet_edges(self):
        # Exhaustive structural proof witness, not candidate/evaluator search.
        possible = list(itertools.combinations(range(5), 2))
        for bits in range(1 << len(possible)):
            edges = [e for i, e in enumerate(possible) if bits & (1 << i)]
            p, s = adjacency(5, edges)
            waves = peel_packets(range(5), p, s)
            where = {u: (i, j) for i, wave in enumerate(waves)
                     for j, packet in enumerate(wave) for u in packet}
            self.assertEqual(set(where), set(range(5)))
            for u, v in edges:
                self.assertTrue(where[u] == where[v] or where[u][0] < where[v][0])


if __name__ == '__main__':
    unittest.main()
