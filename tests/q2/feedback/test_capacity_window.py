"""Small interval-capacity and topology fixtures, no official evaluation."""
import unittest

from src.q2.feedback.capacity_window import build, footprint, memory_window
from src.q2.feedback.tensor_packet import TensorIndex


def chains(jobs=6, shared_size=64):
    ops, tensors = [], [{'id': 1000, 'pos': 'L1', 'size': shared_size}]
    edges = []
    for j in range(jobs):
        a, b, t, out = 2*j+1, 2*j+2, 2000+2*j, 2001+2*j
        ops.extend([{'id': a, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 10},
                    {'id': b, 'op': 'COMPUTE', 'pipe': 'PIPE_V', 'cycles': 10}])
        tensors.extend([{'id': t, 'pos': 'UB', 'size': 32},
                        {'id': out, 'pos': 'UB', 'size': 32}])
        edges.extend({'source': u, 'target': v}
                     for u, v in [(1000, a), (a, t), (t, b), (b, out)])
    return {'ops': ops, 'tensors': tensors, 'edges': edges}


class CapacityWindowTests(unittest.TestCase):
    def test_small_shared_cohort_does_not_mask_a_heavy_fork_join(self):
        ops = [{'id': u, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 100}
               for u in range(1, 7)]
        ops += [{'id': u, 'op': 'COMPUTE', 'pipe': 'PIPE_V', 'cycles': 10}
                for u in (7, 8, 9)]
        g = {'ops': ops, 'tensors': [{'id': 1000, 'pos': 'L1', 'size': 10}],
             'edges': [{'source': u, 'target': 7} for u in range(1, 7)]
                      + [{'source': 1000, 'target': u} for u in (8, 9)]}
        index = TensorIndex(g)
        _, old = index.build_tensor_plan(4, 60, 500)
        self.assertEqual(old['selected'], 'shared_cohorts')
        plan, meta = build(index, 4, 60, 500, {'L1': 512, 'UB': 128})
        self.assertEqual(meta['selected'], 'heavy_component_packet_override')
        self.assertEqual(meta['heavy_components'], 1)
        self.assertEqual(sum(map(len, plan['core_schedules'])), 9)
        expected, _ = index.packet_eft(4, 60, 500)
        mapping = plan['node_to_subgraph']
        self.assertEqual(plan['core_schedules'], [[mapping[str(u)] for u in seq] for seq in expected])

    def test_consumed_and_produced_buffers_coexist_at_a_bucket(self):
        index = TensorIndex(chains(1))
        self.assertEqual(footprint(index, [1, 2]), {'L1': 64, 'UB': 64})
        self.assertEqual(footprint(index, [1, 2], [1000]), {'L1': 0, 'UB': 64})

    def test_whole_cohort_overflows_but_bounded_admission_fits(self):
        index = TensorIndex(chains())
        old, _ = index.build_tensor_plan(1, 60, 500)
        inverse = {sg: int(u) for u, sg in old['node_to_subgraph'].items()}
        previous = [inverse[sg] for sg in old['core_schedules'][0]]
        self.assertGreater(footprint(index, previous)['UB'], 128)
        plan, meta = build(index, 1, 60, 500, {'L1': 128, 'UB': 128})
        detail = meta['core_details'][0]
        self.assertEqual(detail['window'], 2)
        self.assertTrue(detail['changed'])
        self.assertLessEqual(detail['bucket_footprint_bytes']['UB'], 128)
        self.assertEqual(plan['node_to_subgraph'], old['node_to_subgraph'])
        sequence = [inverse[sg] for sg in plan['core_schedules'][0]]
        self.assertEqual(set(sequence), set(index.ops))
        rank = {u: i for i, u in enumerate(sequence)}
        for u in index.ops:
            for v in index.succ[u]:
                self.assertLess(rank[u], rank[v])
        active = set()
        maximum = 0
        for u in sequence:
            j = index.owner[u]
            active.add(j)
            maximum = max(maximum, len(active))
            if u == index.components[j][-1]:
                active.remove(j)
        self.assertLessEqual(maximum, 2)

    def test_failed_reservation_keeps_original_plan(self):
        index = TensorIndex(chains(shared_size=256))
        expected, _ = index.build_tensor_plan(2, 60, 500)
        actual, meta = build(index, 2, 60, 500, {'L1': 128, 'UB': 128})
        self.assertEqual(actual, expected)
        self.assertTrue(all(not d['changed'] for d in meta['core_details']))

    def test_ddr_input_is_reserved_in_local_ub(self):
        g = chains()
        g['tensors'][0]['pos'] = 'DDR'
        index = TensorIndex(g)
        width, detail = memory_window(index, list(range(6)), {'L1': 128, 'UB': 192})
        self.assertEqual(detail['shared_reservation_bytes'], {'L1': 0, 'UB': 64})
        self.assertEqual(width, 2)

    def test_capacity_validation(self):
        index = TensorIndex(chains())
        for capacity in ({'L1': 128}, {'L1': -1, 'UB': 128}, {'L1': True, 'UB': 128}):
            with self.subTest(capacity=capacity), self.assertRaises(ValueError):
                build(index, 1, 60, 500, capacity)


if __name__ == '__main__':
    unittest.main()
