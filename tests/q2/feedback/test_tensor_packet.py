"""Structural guards, COPY accounting and bounded-admission invariants."""
import json
import unittest

from src.q2.feedback.construct import ROOT, UnsupportedStructure
from src.q2.feedback.tensor_packet import TensorIndex


def fixture(shared, jobs=4, work=40):
    ops = [{'id': i+1, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': work} for i in range(jobs)]
    tensors = [{'id': 100, 'pos': 'L1', 'size': 600}] if shared else [
        {'id': 100+i, 'pos': 'L1', 'size': 600} for i in range(jobs)]
    edges = [{'source': 100 if shared else 100+i, 'target': i+1} for i in range(jobs)]
    return {'ops': ops, 'tensors': tensors, 'edges': edges}


class TensorPacketTests(unittest.TestCase):
    def test_shared_input_model_counts_replicas_per_active_core(self):
        index = TensorIndex(fixture(True))
        plan, detail = index.build_tensor_plan(4, 60, 500)
        self.assertEqual(detail['selected'], 'shared_stages')
        choices = detail['resource_choices']
        self.assertEqual([row['copy_service'] for row in choices], [10, 20, 30, 40])
        self.assertEqual([row['pipe_work'] for row in choices], [160, 80, 80, 40])
        self.assertEqual(detail['active_cores'], 4)
        self.assertEqual(len(plan['core_schedules']), 4)

    def test_ddr_dominant_model_may_keep_requested_cores_idle(self):
        index = TensorIndex(fixture(True, work=5))
        plan, detail = index.build_tensor_plan(4, 60, 500)
        self.assertEqual(detail['active_cores'], 1)
        self.assertEqual(len(plan['core_schedules']), 4)
        self.assertEqual(sum(bool(x) for x in plan['core_schedules']), 1)
        self.assertEqual(detail['online_E0_calls'], 0)

    def test_two_disjoint_input_cohorts_are_detected_without_global_common_input(self):
        g = fixture(False)
        g['tensors'] = [g['tensors'][0], g['tensors'][2]]
        for i, edge in enumerate(g['edges']):
            edge['source'] = 100 if i < 2 else 102
        index = TensorIndex(g)
        self.assertIsNone(index.shared_signature())
        plan, meta = index.build_tensor_plan(4, 60, 500)
        self.assertEqual(meta['selected'], 'shared_cohorts')
        self.assertEqual(sorted(c['jobs'] for c in meta['cohorts']), [2, 2])
        self.assertEqual(sum(map(len, plan['core_schedules'])), 4)

    def test_private_inputs_are_counted_once_each_in_packet_model(self):
        index = TensorIndex(fixture(False))
        plan, meta = index.build_tensor_plan(4, 60, 500)
        self.assertEqual(meta['selected'], 'packet_eft')
        self.assertEqual(meta['no_spill_ddr_service'], 40)
        self.assertEqual(meta['no_spill_ddr_bytes'], 2400)
        self.assertEqual(sum(map(len, plan['core_schedules'])), 4)

    def test_ordered_fork_isomorphism_can_share_stages(self):
        g = fixture(False, jobs=6)
        g['tensors'] = [g['tensors'][0], g['tensors'][1]]
        g['edges'] = [{'source': t, 'target': u} for t,u in [(100,1),(101,2),(100,4),(101,5)]]
        g['edges'] += [{'source': u, 'target': v} for u,v in [(1,3),(2,3),(4,6),(5,6)]]
        index = TensorIndex(g)
        self.assertIsNone(index.shared_signature())
        plan, meta = index.build_tensor_plan(2, 60, 500)
        self.assertEqual(meta['selected'], 'shared_cohorts')
        self.assertEqual([cohort['jobs'] for cohort in meta['cohorts']], [2])
        self.assertEqual(sum(map(len, plan['core_schedules'])), 6)

    def test_original_multiple_producer_guard_is_stronger_than_eligible_only(self):
        g = fixture(True)
        g['ops'] += [{'id': 10, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 1},
                     {'id': 11, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 1}]
        g['edges'] += [{'source': 10, 'target': 100}, {'source': 11, 'target': 100}]
        with self.assertRaises(UnsupportedStructure):
            TensorIndex(g)

    def test_contraction_and_pipeline_cover_an_unbalanced_dag(self):
        g = fixture(False, jobs=6)
        g['edges'] += [{'source': u, 'target': v, 'data_size': 8} for u,v in [(1,3),(2,3),(3,5),(4,5),(5,6)]]
        index = TensorIndex(g)
        for k in (1, 2, 5):
            plan, meta = index.build_tensor_plan(k, 60, 500)
            rank = {sg: (c, pos) for c, seq in enumerate(plan['core_schedules']) for pos, sg in enumerate(seq)}
            self.assertEqual(len(rank), len(index.ops))
            for u in index.ops:
                for v in index.succ[u]:
                    a, b = rank[plan['node_to_subgraph'][str(u)]], rank[plan['node_to_subgraph'][str(v)]]
                    if a[0] == b[0]:
                        self.assertLess(a[1], b[1])
            self.assertTrue(all(0 <= w <= 8 for w in meta['priority']['windows']))

    def test_reentry_guard_preserves_previously_frozen_resource_word(self):
        graph = json.loads((ROOT / 'data/raw/a/official/data/case_008.json').read_bytes())
        index = TensorIndex(graph)
        expected, _ = index.build(4, 'resource_word')
        actual, meta = index.build_tensor_plan(4, 60, 500)
        self.assertEqual(actual, expected)
        self.assertEqual(meta['selected'], 'guarded_resource_word')


if __name__ == '__main__':
    unittest.main()
