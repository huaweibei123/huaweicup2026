"""Small synthetic C01 constructor tests; no builder, solver, or evaluator."""
import copy
import unittest

from src.q2_nikolastarx.receiver_closure_exchange import construct
from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
from src.q2_nikolastarx.direct import derive_multicore_plan


def fixture(compensation=False):
    ops = [{'id': 1, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 2},
           {'id': 2, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 2},
           {'id': 3, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 2}]
    first = [0]
    if compensation:
        ops.append({'id': 5, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 4})
        first.append(3)
    graph = {'ops': ops, 'tensors': [{'id': 10, 'size': 4, 'pos': 'UB'}],
             'edges': [{'source': 1, 'target': 10}, {'source': 10, 'target': 2},
                       {'source': 10, 'target': 3}]}
    plan = {'node_to_subgraph': {'1': 0, '2': 1, '3': 2, **({'5': 3} if compensation else {})},
            'core_schedules': [first, [1, 2]]}
    config = {'capacity': {'L1': 100, 'UB': 100}, 'bandwidth': 60}
    link = {'tensor_id': 10, 'source_core': 0, 'target_core': 1, 'exposed_delay': 500}
    return graph, plan, config, link


class RCXTests(unittest.TestCase):
    def test_full_receiver_closure_and_byte_drop(self):
        graph, plan, config, link = fixture()
        original = copy.deepcopy((graph, plan, config, link))
        out, meta = construct(graph, plan, config, [link])
        self.assertEqual(meta['status'], 'candidate')
        self.assertEqual(meta['selected']['moved_x'], [2, 3])
        self.assertEqual(meta['selected']['compensation_y'], [])
        self.assertLessEqual(meta['candidates_checked'], 4)
        view = derive_multicore_plan(graph, out)
        owners = {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}
        self.assertEqual([owners[1], owners[2], owners[3]], [0, 0, 0])
        self.assertGreater(mandatory_copy_work(graph, plan, 60)['transfer_bytes'],
                           mandatory_copy_work(graph, out, 60)['transfer_bytes'])
        self.assertEqual((graph, plan, config, link), original)

    def test_shortest_stable_compensation_prefix(self):
        graph, plan, config, link = fixture(True)
        out, meta = construct(graph, plan, config, [link])
        self.assertIsNotNone(out, meta)
        self.assertEqual(meta['selected']['compensation_y'], [5])
        self.assertEqual(meta['selected']['moved_x'], [2, 3])
        view = derive_multicore_plan(graph, out)
        self.assertEqual(view['core_by_subgraph'][view['mapping'][5]], 1)

    def test_x_waits_for_later_target_core_predecessor(self):
        graph, plan, config, link = fixture()
        graph['ops'].append({'id': 6, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 2})
        graph['edges'].append({'source': 6, 'target': 2, 'data_size': 0})
        plan['node_to_subgraph']['6'] = 3
        plan['core_schedules'][0].append(3)
        out, meta = construct(graph, plan, config, [link])
        self.assertIsNotNone(out, meta)
        first = out['core_schedules'][0]
        self.assertLess(first.index(3), first.index(1))
        self.assertEqual(meta['selected']['moved_x'], [2, 3])

    def test_y_waits_for_target_core_predecessor(self):
        graph, plan, config, link = fixture(True)
        graph['ops'].append({'id': 7, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 1})
        graph['edges'].append({'source': 7, 'target': 5, 'data_size': 0})
        plan['node_to_subgraph']['7'] = 4
        plan['core_schedules'][1].insert(0, 4)
        out, meta = construct(graph, plan, config, [link])
        self.assertIsNotNone(out, meta)
        second = out['core_schedules'][1]
        self.assertLess(second.index(4), second.index(3))
        self.assertEqual(meta['selected']['compensation_y'], [5])

    def test_no_witness_no_candidate(self):
        graph, plan, config, _ = fixture()
        out, meta = construct(graph, plan, config, [])
        self.assertIsNone(out)
        self.assertEqual(meta['seeds_seen'], 0)

    def test_wrong_source_and_missing_delay_rejected(self):
        graph, plan, config, link = fixture()
        for bad in ({**link, 'source_core': 1}, {**link, 'exposed_delay': 0},
                    {k: v for k, v in link.items() if k != 'exposed_delay'}):
            out, _ = construct(graph, plan, config, [bad])
            self.assertIsNone(out)

    def test_alias_and_baseline_capacity_guard(self):
        graph, plan, config, link = fixture()
        graph['tensors'][0]['logical_tid'] = 10
        self.assertEqual(construct(graph, plan, config, [link])[1]['status'], 'unsupported')
        del graph['tensors'][0]['logical_tid']
        config['capacity']['UB'] = 3
        self.assertEqual(construct(graph, plan, config, [link])[1]['status'], 'unsupported')

    def test_packet_limit(self):
        graph, plan, config, link = fixture()
        out, meta = construct(graph, plan, config, [link], max_packet_ops=1)
        self.assertIsNone(out)
        self.assertIn('empty_or_oversize_closure', meta['rejections'])


if __name__ == '__main__':
    unittest.main()
