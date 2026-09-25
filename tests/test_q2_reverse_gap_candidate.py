"""Synthetic graph checks only; no official graph or evaluator."""
import copy
import unittest

from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan, topo
from src.q2_nikolastarx.gap_candidate import build as forward_build
from src.q2_nikolastarx.reverse_gap_candidate import build
from tests.q2_nikolastarx.test_gap_candidate import CONFIG, diamond


def check_original_order(graph, plan):
    index = DAGIndex(graph)
    reverse_mapping = {subgraph: int(u) for u, subgraph in plan['node_to_subgraph'].items()}
    combined = {u: set(index.succ[u]) for u in index.ops}
    for row in plan['core_schedules']:
        nodes = [reverse_mapping[sg] for sg in row]
        for u, v in zip(nodes, nodes[1:]):
            combined[u].add(v)
    assert len(topo(index.ops, combined)) == len(index.ops)
    derive_multicore_plan(graph, plan)


class ReverseGapCandidateTests(unittest.TestCase):
    def test_asymmetric_fork_join_is_legal_and_differs_from_forward(self):
        graph = diamond()  # Unequal source durations and different sink pipes.
        for cores in (1, 2, 5):
            plan, meta = build(graph, cores, CONFIG)
            check_original_order(graph, plan)
            self.assertEqual(len(plan['core_schedules']), cores)
            self.assertEqual(meta['online_E0_calls'], 0)
            self.assertLessEqual(meta['arithmetic_placement_choices'], meta['choice_bound'])
            self.assertNotEqual(plan, forward_build(graph, cores, CONFIG)[0])

    def test_single_producer_fanout_remains_original_direction(self):
        graph = diamond()
        graph['tensors'] = [{'id': 100, 'pos': 'UB', 'size': 8}]
        graph['edges'] = [edge for edge in graph['edges']
                          if (edge['source'], edge['target']) not in ((3, 4), (3, 5))]
        graph['edges'] += [{'source': 3, 'target': 100},
                           {'source': 100, 'target': 4},
                           {'source': 100, 'target': 5}]
        plan, _ = build(graph, 3, CONFIG)
        check_original_order(graph, plan)
        self.assertEqual(set(plan['node_to_subgraph']), {'1', '2', '3', '4', '5'})

    def test_deterministic_and_input_unchanged(self):
        graph = diamond()
        original = copy.deepcopy(graph)
        shuffled = copy.deepcopy(graph)
        for values in shuffled.values():
            values.reverse()
        self.assertEqual(build(graph, 3, CONFIG), build(shuffled, 3, CONFIG))
        self.assertEqual(graph, original)

    def test_physical_guard_is_preserved(self):
        graph = diamond()
        graph['tensors'] = [{'id': 100, 'pos': 'UB', 'size': 8}]
        graph['edges'] += [{'source': 1, 'target': 100}, {'source': 2, 'target': 100}]
        with self.assertRaises(UnsupportedStructure):
            build(graph, 2, CONFIG)


if __name__ == '__main__':
    unittest.main()
