"""Synthetic C01 packet exchange tests; no official prepare/evaluation."""
import copy
import unittest

from src.q2_nikolastarx.critical_packet_exchange import construct, propose
from src.q2_nikolastarx.direct import derive_multicore_plan


def scene():
    graph = {'ops': [
        {'id': 1, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 2},
        {'id': 2, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 2},
        {'id': 3, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 2}],
        'tensors': [{'id': 10, 'size': 4, 'pos': 'UB'},
                    {'id': 20, 'size': 4, 'pos': 'UB'}],
        'edges': [{'source': 1, 'target': 10}, {'source': 10, 'target': 2},
                  {'source': 2, 'target': 3, 'data_size': 0},
                  {'source': 3, 'target': 20}]}
    plan = {'node_to_subgraph': {'1': 0, '2': 1, '3': 2},
            'core_schedules': [[0], [1, 2]]}
    config = {'capacity': {'L1': 100, 'UB': 100}, 'bandwidth': 60}
    link = {'tensor_id': 10, 'source_core': 0, 'target_core': 1,
            'exposed_delay': 500}
    return graph, plan, config, link


class CriticalPacketTests(unittest.TestCase):
    def test_critical_cone_crosses_third_core_and_accounts_load(self):
        graph, plan, config, link = scene()
        graph['ops'] += [{'id': 4, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 2},
                         {'id': 5, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 4},
                         {'id': 6, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 4},
                         {'id': 7, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 3}]
        graph['edges'].append({'source': 3, 'target': 4, 'data_size': 0})
        graph['edges'].append({'source': 4, 'target': 7, 'data_size': 0})
        plan['node_to_subgraph'].update({'4': 3, '5': 4, '6': 5, '7': 6})
        plan['core_schedules'][0].append(6)
        plan['core_schedules'].append([4, 3, 5])
        original = copy.deepcopy((graph, plan, config))
        same, _ = propose(graph, plan, config, [link], {3, 4, 7},
                          incumbent_makespan=99)
        cone, meta = propose(graph, plan, config, [link], {3, 4, 7},
                             incumbent_makespan=99, closure_scope='critical_cone')
        self.assertTrue(same)
        self.assertTrue(cone, meta)
        detail = cone[0]['detail']
        self.assertEqual(same[0]['detail']['packet'], [2, 3])
        self.assertEqual(detail['packet'], [2, 3, 4, 7])
        self.assertEqual(detail['packet_old_core_counts'], {0: 1, 1: 2, 2: 1})
        self.assertEqual(detail['effective_moved_count'], 3)
        self.assertEqual(detail['pipe_load_peaks_before']['PIPE_M'], 10)
        self.assertEqual(detail['pipe_load_peaks_after']['PIPE_M'], 8)
        self.assertEqual(cone[0]['plan']['core_schedules'][2], [4, 5])
        derive_multicore_plan(graph, cone[0]['plan'])
        self.assertEqual((graph, plan, config), original)

    def test_unknown_closure_scope_is_unsupported(self):
        graph, plan, config, link = scene()
        candidates, meta = propose(graph, plan, config, [link], {3},
                                   incumbent_makespan=99, closure_scope='unknown')
        self.assertEqual(candidates, [])
        self.assertEqual(meta['status'], 'unsupported')

    def test_shifted_merge_places_packet_between_retained_ops(self):
        graph, plan, config, link = scene()
        graph['ops'] += [{'id': 4, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 2},
                         {'id': 5, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 2}]
        plan['node_to_subgraph'].update({'4': 3, '5': 4})
        plan['core_schedules'][0] += [3, 4]
        link['exposed_delay'] = 10
        starts = {1: 0, 4: 1, 2: 12, 5: 3, 3: 14}
        original = copy.deepcopy((graph, plan, config, link, starts))
        extreme, _ = propose(graph, plan, config, [link], {3}, incumbent_makespan=99)
        shifted, meta = propose(graph, plan, config, [link], {3},
                                incumbent_makespan=99, merge_policy='shifted',
                                original_start_times=starts)
        self.assertEqual(len(shifted), 1, meta)
        output = shifted[0]['plan']
        self.assertEqual(output['core_schedules'][0], [0, 3, 1, 4, 2])
        self.assertNotIn(output, [item['plan'] for item in extreme])
        self.assertEqual(meta['candidates_checked'], 1)
        self.assertEqual(meta['candidate_summaries'][0]['merge'], 'shifted')
        self.assertEqual(derive_multicore_plan(graph, output)['mapping'],
                         derive_multicore_plan(graph, plan)['mapping'])
        self.assertEqual((graph, plan, config, link, starts), original)

    def test_shifted_rejects_missing_or_malformed_starts(self):
        graph, plan, config, link = scene()
        for starts in (None, {1: 0, 2: 1}, {1: 0, 2: 1, 3: True},
                       {1: 0, 2: -1, 3: 2}, {1: 0, 2: 1.0, 3: 2},
                       {1: 0, 2: 1, 3: 2, 4: 3}):
            with self.subTest(starts=starts):
                candidates, meta = propose(graph, plan, config, [link], {3},
                                           incumbent_makespan=99, merge_policy='shifted',
                                           original_start_times=starts)
                self.assertEqual(candidates, [])
                self.assertEqual(meta['status'], 'unsupported')

    def test_propose_deduplicates_identical_full_plans(self):
        graph, plan, config, link = scene()
        original = copy.deepcopy((graph, plan, config, link))
        candidates, meta = propose(graph, plan, config, [link, link], {3},
                                   incumbent_makespan=99)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(meta['unique_count'], 1)
        self.assertGreaterEqual(meta['duplicates'], 1)
        self.assertEqual(len(candidates[0]['detail']['origins']),
                         meta['validated_candidates'])
        self.assertEqual((graph, plan, config, link), original)

    def test_construct_keeps_static_choice_over_proposals(self):
        graph, plan, config, link = scene()
        graph['ops'].append({'id': 4, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 2})
        plan['node_to_subgraph']['4'] = 3
        plan['core_schedules'][0].append(3)
        candidates, meta = propose(graph, plan, config, [link], {3},
                                   incumbent_makespan=99)
        self.assertEqual(len(candidates), 2, meta)
        chosen = min(candidates, key=lambda item: tuple(item['detail']['static_rank_key']))
        out, selected = construct(graph, plan, config, [link], {3},
                                  incumbent_makespan=99)
        self.assertEqual(out, chosen['plan'])
        self.assertEqual(selected['selected']['static_rank_key'],
                         chosen['detail']['static_rank_key'])

    def test_downstream_critical_closure_reaches_sink(self):
        graph, plan, config, link = scene()
        original = copy.deepcopy((graph, plan, config, link))
        out, meta = construct(graph, plan, config, [link], {3}, incumbent_makespan=99)
        self.assertIsNotNone(out, meta)
        self.assertEqual(meta['selected']['packet'], [2, 3])
        self.assertEqual(meta['selected']['packet_size'], 2)
        self.assertEqual(meta['selected']['receiver_count'], 1)
        self.assertEqual(meta['selected']['critical_downstream_added'], 1)
        self.assertLessEqual(meta['candidates_checked'], 2)
        view = derive_multicore_plan(graph, out)
        self.assertEqual([view['core_by_subgraph'][view['mapping'][u]] for u in (1, 2, 3)],
                         [0, 0, 0])
        self.assertEqual((graph, plan, config, link), original)

    def test_topological_merge_interleaves_packet(self):
        graph, plan, config, link = scene()
        # Both 2 and 3 consume the tensor. Old constraints require
        # 1 -> 2 -> 4 -> 3, so X=[2,3] cannot be one contiguous block.
        graph['edges'].remove({'source': 2, 'target': 3, 'data_size': 0})
        graph['edges'] += [{'source': 10, 'target': 3},
                           {'source': 2, 'target': 4, 'data_size': 0},
                           {'source': 4, 'target': 3, 'data_size': 0}]
        graph['ops'].append({'id': 4, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 2})
        plan['node_to_subgraph']['4'] = 3
        plan['core_schedules'][0].append(3)
        out, meta = construct(graph, plan, config, [link], set(), incumbent_makespan=99)
        self.assertIsNotNone(out, meta)
        self.assertEqual(out['core_schedules'][0], [0, 1, 3, 2])
        self.assertEqual(out['core_schedules'][1], [])

    def test_allow_load_growth_but_reject_impossible_strict_gain(self):
        graph, plan, config, link = scene()
        graph['ops'].append({'id': 5, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 4})
        plan['node_to_subgraph']['5'] = 3
        plan['core_schedules'][0].append(3)
        out, meta = construct(graph, plan, config, [link], {3}, incumbent_makespan=99)
        self.assertIsNotNone(out, meta)
        self.assertGreater(meta['selected']['pipe_load_peaks_after']['PIPE_V'],
                           meta['selected']['pipe_load_peaks_before']['PIPE_V'])
        out, meta = construct(graph, plan, config, [link], {3}, incumbent_makespan=6)
        self.assertIsNone(out)
        self.assertIn('load_lower_bound_no_strict_gain', meta['rejections'])

    def test_alias_and_capacity_abstain(self):
        graph, plan, config, link = scene()
        graph['tensors'][0]['logical_tid'] = 10
        self.assertEqual(construct(graph, plan, config, [link], {3}, incumbent_makespan=99)[1]['status'], 'unsupported')
        del graph['tensors'][0]['logical_tid']
        config['capacity']['UB'] = 1
        self.assertEqual(construct(graph, plan, config, [link], {3}, incumbent_makespan=99)[1]['status'], 'unsupported')


if __name__ == '__main__':
    unittest.main()
