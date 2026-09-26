"""Synthetic lifecycle counterexamples; no official graph or evaluator."""
import unittest

from src.q2.feedback.capacity_window import build as capacity_build, footprint
from src.q2.feedback.lifecycle_window import build
from src.q2.feedback.tensor_packet import TensorIndex


def groups(signatures, copies=2, size=40):
    ops, tensors, edges = [], [], []
    for t in sorted(set().union(*signatures)):
        tensors.append({'id': 1000 + t, 'pos': 'L1', 'size': size})
    for group, signature in enumerate(signatures):
        for replica in range(copies):
            a = 1 + 10 * group + 2 * replica
            b = a + 1
            ops += [{'id': a, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 10},
                    {'id': b, 'op': 'COMPUTE', 'pipe': 'PIPE_V', 'cycles': 10}]
            edges.append({'source': a, 'target': b})
            edges.extend({'source': 1000 + t, 'target': a} for t in signature)
    return {'ops': ops, 'tensors': tensors, 'edges': edges}


class LifecycleWindowTests(unittest.TestCase):
    def test_separated_shared_input_groups_get_full_certificate(self):
        graph = groups([(1,), (2,)], copies=3)
        index = TensorIndex(graph)
        cap = {'L1': 60, 'UB': 0}
        baseline, old = capacity_build(index, 1, 60, 500, cap)
        self.assertEqual(old['selected'], 'capacity_window')
        self.assertEqual(old['core_details'][0]['window'], 0)
        plan, meta = build(index, 1, 60, 500, cap)
        detail = meta['core_details'][0]
        self.assertEqual(detail['group_count'], 2)
        self.assertTrue(all(1 <= width <= 8 for width in detail['group_widths']))
        self.assertEqual(detail['full_bucket_footprint_bytes'], {'L1': 40, 'UB': 0})
        self.assertEqual(detail['reason'], 'certified full sequence')
        self.assertTrue(detail['changed'])
        self.assertEqual(plan['node_to_subgraph'], baseline['node_to_subgraph'])
        inverse = {sg: int(u) for u, sg in plan['node_to_subgraph'].items()}
        seq = [inverse[sg] for sg in plan['core_schedules'][0]]
        self.assertEqual(footprint(index, seq), detail['full_bucket_footprint_bytes'])
        self.assertEqual(set(seq), set(index.ops))
        rank = {u: pos for pos, u in enumerate(seq)}
        self.assertTrue(all(rank[u] < rank[v] for u in index.ops for v in index.succ[u]))
        self.assertEqual(set(plan), {'node_to_subgraph', 'core_schedules'})
        self.assertEqual(build(index, 1, 60, 500, cap), (plan, meta))

    def test_pairwise_overlap_defeats_local_group_certificates(self):
        index = TensorIndex(groups([(1, 2), (2, 3), (1, 3)]))
        cap = {'L1': 100, 'UB': 0}
        baseline, old = capacity_build(index, 1, 60, 500, cap)
        self.assertEqual(old['core_details'][0]['window'], 0)
        plan, meta = build(index, 1, 60, 500, cap)
        detail = meta['core_details'][0]
        self.assertEqual(detail['group_count'], 3)
        self.assertTrue(all(width >= 1 for width in detail['group_widths']))
        self.assertEqual(detail['full_bucket_footprint_bytes']['L1'], 120)
        self.assertEqual(detail['reason'], 'full sequence exceeds capacity')
        self.assertEqual(plan, baseline)

    def test_unadmittable_group_keeps_whole_core(self):
        graph = groups([(1,), (2,)])
        for op in graph['ops']:
            if op['id'] % 2:
                tid = 2000 + op['id']
                graph['tensors'].append({'id': tid, 'pos': 'L1', 'size': 30})
                graph['edges'].append({'source': tid, 'target': op['id']})
        index = TensorIndex(graph)
        cap = {'L1': 60, 'UB': 0}
        baseline, _ = capacity_build(index, 1, 60, 500, cap)
        plan, meta = build(index, 1, 60, 500, cap)
        self.assertEqual(plan, baseline)
        self.assertEqual(meta['core_details'][0]['reason'], 'a group cannot admit one job')
        self.assertNotIn('full_bucket_footprint_bytes', meta['core_details'][0])

    def test_alias_and_unselected_route_keep_exact_base_plan(self):
        graph = groups([(1,), (2,)])
        graph['tensors'][0]['logical_tid'] = 1001
        index = TensorIndex(graph)
        cap = {'L1': 80, 'UB': 0}
        expected, _ = capacity_build(index, 1, 60, 500, cap)
        actual, meta = build(index, 1, 60, 500, cap)
        self.assertEqual(actual, expected)
        self.assertEqual(meta['selected'], 'lifecycle_window_guard_unchanged')

        # Distinct jobs without a repeated input take the packet route.
        index = TensorIndex(groups([(1,), (2,)], copies=1))
        expected, _ = capacity_build(index, 1, 60, 500, cap)
        actual, meta = build(index, 1, 60, 500, cap)
        self.assertEqual(actual, expected)
        self.assertEqual(meta['selected'], 'lifecycle_window_guard_unchanged')


if __name__ == '__main__':
    unittest.main()
