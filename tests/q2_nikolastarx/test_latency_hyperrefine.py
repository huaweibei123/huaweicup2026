"""Tiny exhaustive proxy checks; no real graph or evaluator."""
import itertools
import unittest

from src.q2_nikolastarx.binary_hypercut import Hyperedge, binary_hypercut, connectivity_cost
from src.q2_nikolastarx.hypergraph_cost import HypergraphCost, UnsupportedHypergraph
from src.q2_nikolastarx.latency_hyperrefine import build
from tests.q2_nikolastarx.test_gap_hyperrefine import singleton, swap_graph


def graph():
    return {
        'ops': [{'id': u, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 1}
                for u in (1, 2, 3)],
        'tensors': [{'id': 10, 'size': 5}, {'id': 11, 'size': 7},
                    {'id': 12, 'size': 0}],
        'edges': [
            {'source': 1, 'target': 10},
            {'source': 10, 'target': 2}, {'source': 10, 'target': 3},
            {'source': 11, 'target': 2}, {'source': 11, 'target': 3},
            {'source': 1, 'target': 12}, {'source': 12, 'target': 2},
            {'source': 1, 'target': 3, 'data_size': 0},
            {'source': 1, 'target': 3, 'data_size': 0},
        ],
    }


class LatencyHyperrefineTests(unittest.TestCase):
    def test_all_assignments_delta_and_binary_cut(self):
        g = graph()
        model = HypergraphCost(g, (1, 2, 3), proxy_bandwidth=4, cross_core_delay=500)
        self.assertCountEqual([e.weight for e in model.edges],
                              [504, 2, 500, 500, 500])
        byte_model = HypergraphCost(g, (1, 2, 3))
        self.assertCountEqual([e.weight for e in byte_model.edges], [10, 7])
        rows = [Hyperedge(e.pins, frozenset(), e.weight) for e in model.edges]
        scores = []
        for bits in itertools.product((0, 1), repeat=3):
            labels = dict(zip((1, 2, 3), bits))
            # Tensor fanout is one connectivity net; duplicate direct edges remain separate.
            expected = (504 * (len({bits[0], bits[1], bits[2]}) - 1)
                        + 2 * (len({bits[1], bits[2]}) - 1)
                        + 500 * (len({bits[0], bits[1]}) - 1)
                        + 1000 * (len({bits[0], bits[2]}) - 1))
            state = model.state(labels)
            self.assertEqual(state.total_bytes, expected)
            self.assertEqual(connectivity_cost(labels, rows), expected)
            for u in (1, 2, 3):
                target = 1 - labels[u]
                changed = dict(labels)
                changed[u] = target
                self.assertEqual(state.delta([u], labels[u], target),
                                 model.state(changed).total_bytes - expected)
            scores.append(expected)
        cut = binary_hypercut((1, 2, 3), rows, 0, 1, anchors={1: 0, 2: 1})
        self.assertEqual(cut.cost, min(scores[i] for i, bits in enumerate(
            itertools.product((0, 1), repeat=3)) if bits[0] == 0 and bits[1] == 1))

    def test_invalid_direct_size_and_default_byte_detail(self):
        g = graph()
        g['edges'].append({'source': 1, 'target': 2, 'data_size': -1})
        with self.assertRaises(UnsupportedHypergraph):
            HypergraphCost(g, (1, 2, 3), proxy_bandwidth=4, cross_core_delay=500)
        self.assertEqual(HypergraphCost(g, (1, 2, 3)).state({1: 0, 2: 1, 3: 1}).total_bytes,
                         10 + 7)

    def test_candidate_retimes_and_labels_proxy(self):
        g = swap_graph()
        before = singleton([[1, 5, 4], [2, 3]])
        out, detail = build(g, before,
                            {'bandwidth': 60, 'cross_core_copy_delay_cycles': 500})
        self.assertLess(detail['placement']['after_isolated_transfer_proxy_cycles'],
                        detail['placement']['before_isolated_transfer_proxy_cycles'])
        self.assertNotIn('after_original_copy_bytes', detail['placement'])
        self.assertIsNotNone(detail['retime'])
        self.assertEqual(set(out), {'node_to_subgraph', 'core_schedules'})
        self.assertIn('official quality unknown', detail['scope'])


if __name__ == '__main__':
    unittest.main()
