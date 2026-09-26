"""Independent small synthetic audit; never loads official graphs or runs E0."""
import random
import unittest

from src.q2.feedback.gap_packet import build, chain_dag
from src.q2.feedback.tensor_packet import TensorIndex
from tests.q2.feedback.test_capacity_window import chains
from tests.q2.feedback.test_gap_packet import diamond


class PhysicalGuardAudit(unittest.TestCase):
    def test_redundant_copy_path_preserves_relation_but_not_transfer_model(self):
        """A duplicate COPY path changes service demand, not the dependency pair."""
        graph = diamond()
        graph['ops'].append({'id': 90, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 1})
        graph['tensors'] = [
            {'id': 100, 'pos': 'L1', 'size': 8},
            {'id': 101, 'pos': 'DDR', 'size': 8},
        ]
        graph['edges'] += [
            {'source': u, 'target': v} for u, v in
            ((1, 100), (100, 90), (90, 101), (101, 3))
        ]
        index = TensorIndex(graph)
        self.assertEqual(index.pred[3], {1, 2})
        # The original direct edge 1→3 is still present. The contracted COPY
        # path adds no new predecessor relation, but the static delay model
        # does not account for the extra COPY service.
        self.assertIsNotNone(chain_dag(index, 60, 500))
        for cores in (1, 2, 5):
            plan, meta = build(index, cores, 60, 500,
                               {'L1': 524288, 'UB': 131072})
            self.assertEqual(meta['selected'], 'join_gap_packet')
            self.assertEqual(sorted(node for seq in plan['core_schedules']
                                    for node in seq), list(range(5)))

    def test_copy_only_path_is_rejected(self):
        graph = diamond()
        graph['edges'] = [e for e in graph['edges']
                          if (e['source'], e['target']) != (1, 3)]
        graph['ops'].append({'id': 90, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 1})
        graph['tensors'] = [{'id': 100, 'pos': 'L1', 'size': 8},
                            {'id': 101, 'pos': 'DDR', 'size': 8}]
        graph['edges'] += [{'source': u, 'target': v} for u, v in
                           ((1, 100), (100, 90), (90, 101), (101, 3))]
        self.assertIsNone(chain_dag(TensorIndex(graph), 60, 500))


class PlacementAudit(unittest.TestCase):
    def test_integrated_future_gap_insertion_retains_valid_priority(self):
        rng = random.Random(0)
        ops = [{'id': u, 'op': 'COMPUTE',
                'pipe': rng.choice(('PIPE_M', 'PIPE_V')),
                'cycles': rng.randrange(2, 30)} for u in range(1, 11)]
        edges = {(1, 3), (2, 3), (3, 4), (3, 5)}
        for u in range(1, 11):
            for v in range(u + 1, 11):
                if rng.random() < 0.12:
                    edges.add((u, v))
        graph = {'ops': ops, 'tensors': [],
                 'edges': [{'source': u, 'target': v, 'data_size': 8}
                           for u, v in sorted(edges)]}
        index = TensorIndex(graph)
        plan, meta = build(index, 2, 60, 0,
                           {'L1': 524288, 'UB': 131072})
        self.assertEqual(meta['selected'], 'join_gap_packet')
        self.assertGreater(meta['operations_inserted_before_tail'], 0)
        self.assertEqual(meta['paired_joins'], 2)
        inverse = {subgraph: int(node) for node, subgraph in
                   plan['node_to_subgraph'].items()}
        schedules = [[inverse[subgraph] for subgraph in schedule]
                     for schedule in plan['core_schedules']]
        self.assertEqual(sorted(u for seq in schedules for u in seq),
                         sorted(index.ops))
        for schedule in schedules:
            positions = {u: i for i, u in enumerate(schedule)}
            for u in schedule:
                for v in index.succ[u]:
                    if v in positions:
                        self.assertLess(positions[u], positions[v])

    def test_join_pair_and_exported_priority_cover_direct_dag(self):
        graph = diamond()
        index = TensorIndex(graph)
        for cores in (1, 2, 5):
            with self.subTest(cores=cores):
                plan, meta = build(index, cores, 60, 500,
                                   {'L1': 524288, 'UB': 131072})
                self.assertEqual(meta['selected'], 'join_gap_packet')
                self.assertEqual(meta['paired_joins'], 1)
                self.assertLessEqual(meta['arithmetic_placement_choices'],
                                     cores * (meta['chains'] - 1) + cores * cores)
                inverse = {subgraph: int(node) for node, subgraph in
                           plan['node_to_subgraph'].items()}
                sequence = [[inverse[subgraph] for subgraph in schedule]
                            for schedule in plan['core_schedules']]
                flat = [node for schedule in sequence for node in schedule]
                self.assertEqual(sorted(flat), sorted(index.ops))
                for schedule in sequence:
                    position = {node: i for i, node in enumerate(schedule)}
                    for u in schedule:
                        for v in index.succ[u]:
                            if v in position:
                                self.assertLess(position[u], position[v])

    def test_capacity_fallback_label_does_not_certify_all_cores(self):
        index = TensorIndex(chains())
        _, meta = build(index, 1, 60, 500, {'L1': 0, 'UB': 0})
        self.assertEqual(meta['selected'], 'gap_guard_capacity_fallback')
        self.assertEqual(meta['fallback']['selected'], 'capacity_window')
        self.assertEqual(meta['fallback']['core_details'][0]['window'], 0)
        self.assertFalse(meta['fallback']['core_details'][0]['changed'])


if __name__ == '__main__':
    unittest.main()
