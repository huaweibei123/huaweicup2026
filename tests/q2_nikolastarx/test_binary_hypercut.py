"""Synthetic exact-cut checks; enumeration is a test oracle only."""
import itertools
import random
import unittest

from src.q2_nikolastarx.binary_hypercut import (
    Hyperedge, binary_hypercut, connectivity_cost, load_guarded_cut,
)


def exhaustive(units, edges, anchors=None):
    anchors = anchors or {}
    candidates = []
    for values in itertools.product((0, 1), repeat=len(units)):
        labels = dict(zip(units, values))
        if all(labels[u] == core for u, core in anchors.items()):
            candidates.append(connectivity_cost(labels, edges))
    return min(candidates)


class BinaryHypercutTests(unittest.TestCase):
    def test_random_small_graphs_match_exhaustive_oracle(self):
        rng = random.Random(20260925)
        for _ in range(180):
            units = list(range(rng.randrange(1, 6)))
            edges = []
            for _ in range(rng.randrange(0, 8)):
                pins = frozenset(u for u in units if rng.randrange(2))
                fixed = frozenset(c for c in (0, 1, 2, 3) if rng.randrange(5) == 0)
                if not pins and not fixed:
                    fixed = frozenset({2})
                edges.append(Hyperedge(pins, fixed, rng.randrange(6)))
            anchors = {u: rng.randrange(2) for u in units if rng.randrange(4) == 0}
            result = binary_hypercut(units, edges, 0, 1, anchors)
            self.assertEqual(result.cost, exhaustive(units, edges, anchors))
            self.assertEqual(result.cost, result.flow + result.offset)
            self.assertEqual(result.cost, connectivity_cost(result.labels, edges))
            self.assertTrue(all(result.labels[u] == c for u, c in anchors.items()))

    def test_fixed_third_core_and_all_pins_migrate(self):
        edges = [Hyperedge(frozenset({0, 1, 2}), frozenset({2}), 7),
                 Hyperedge(frozenset({0, 1, 2}), frozenset(), 4)]
        result = binary_hypercut([0, 1, 2], edges, 0, 1, {0: 1})
        self.assertEqual(result.labels, {0: 1, 1: 1, 2: 1})
        self.assertEqual(result.cost, 7)
        self.assertEqual(result.cost, exhaustive([0, 1, 2], edges, {0: 1}))

    def test_zero_weight_constant_and_empty_edge(self):
        edges = [Hyperedge(frozenset(), frozenset({2, 3}), 11),
                 Hyperedge(frozenset({0, 1}), frozenset(), 0)]
        result = binary_hypercut([0, 1], edges, 0, 1)
        self.assertEqual(result.cost, 11)
        self.assertEqual(result.flow, 0)
        with self.assertRaisesRegex(ValueError, 'empty hyperedge'):
            binary_hypercut([0], [Hyperedge(frozenset(), frozenset(), 1)], 0, 1)

    def test_load_guard_multi_pipe_dynamic_anchors(self):
        units = [0, 1, 2, 3]
        # Edge preferences move both a-units to b; b cannot take both in M.
        edges = [Hyperedge(frozenset({u}), frozenset({1}), 10) for u in (0, 1)]
        initial = {0: 0, 1: 0, 2: 1, 3: 1}
        work = {0: {'M': 7, 'V': 1}, 1: {'M': 5, 'V': 4},
                2: {'M': 1, 'V': 1}, 3: {'M': 1, 'V': 1}}
        outside = {0: {'M': 1, 'V': 0}, 1: {'M': 1, 'V': 2}}
        caps = {0: {'M': 13, 'V': 5}, 1: {'M': 8, 'V': 8}}
        result = load_guarded_cut(units, edges, 0, 1, initial, work, outside, caps)
        self.assertGreaterEqual(result.flow_calls, 2)
        self.assertLessEqual(result.flow_calls, len(units) + 1)
        self.assertTrue(result.anchored)
        self.assertLessEqual(result.cost, connectivity_cost(initial, edges))
        self.assertEqual(result.cost, connectivity_cost(result.labels, edges))
        self.assertTrue(all(result.loads[c][p] <= caps[c][p]
                            for c in (0, 1) for p in caps[c]))
        self.assertTrue(all(result.labels[u] == initial[u] for u in result.anchored))

    def test_initial_infeasible_rejected(self):
        with self.assertRaisesRegex(ValueError, 'initial assignment'):
            load_guarded_cut([0], [], 0, 1, {0: 0}, {0: {'M': 3}},
                             {0: {}, 1: {}}, {0: {'M': 2}, 1: {'M': 2}})

    def test_random_feasible_load_guards_preserve_baseline_bound(self):
        rng = random.Random(91)
        for _ in range(90):
            units = list(range(rng.randrange(1, 6)))
            initial = {u: rng.randrange(2) for u in units}
            work = {u: {p: rng.randrange(5) for p in ('M', 'V')} for u in units}
            outside = {c: {p: rng.randrange(3) for p in ('M', 'V')} for c in (0, 1)}
            caps = {c: {p: outside[c][p] + sum(work[u][p] for u in units
                                                  if initial[u] == c) + rng.randrange(3)
                        for p in ('M', 'V')} for c in (0, 1)}
            edges = []
            for _ in range(rng.randrange(1, 7)):
                pins = frozenset(u for u in units if rng.randrange(2))
                if pins:
                    edges.append(Hyperedge(pins, frozenset({rng.randrange(3)}),
                                           rng.randrange(6)))
            result = load_guarded_cut(units, edges, 0, 1, initial, work, outside, caps)
            self.assertLessEqual(result.flow_calls, len(units) + 1)
            self.assertLessEqual(result.cost, connectivity_cost(initial, edges))
            self.assertTrue(all(result.loads[c][p] <= caps[c][p]
                                for c in (0, 1) for p in ('M', 'V')))


if __name__ == '__main__':
    unittest.main()
