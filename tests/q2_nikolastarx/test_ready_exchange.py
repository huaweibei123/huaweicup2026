"""Small synthetic r05 port checks; no real case or official evaluator."""
import itertools
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import gap_calendar, ready_exchange as r05
from src.q2_nikolastarx import ready_exchange_candidate as adapter
from src.q2_nikolastarx.gap_candidate import build_with_witness
from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan
from src.q2_nikolastarx.dag_direct import DAGIndex
from tests.q2_nikolastarx.test_gap_candidate import CONFIG, diamond


class ReadyExchangeTests(unittest.TestCase):
    def test_caller_selected_singleton_plan_and_zero_byte_dependency(self):
        graph = diamond()
        for op in graph['ops']:
            if op['pipe'].startswith('PIPE_MTE'):
                op['pipe'] = 'PIPE_M'
        graph['edges'].append({'source': 1, 'target': 5, 'data_size': 0})
        seed = {'node_to_subgraph': {str(u): u - 1 for u in range(1, 6)},
                'core_schedules': [[0, 2, 3], [1, 4]]}
        derive_multicore_plan(graph, seed)
        old_gap_seed, _, _ = build_with_witness(graph, 2, CONFIG)
        self.assertNotEqual(seed, old_gap_seed)
        with patch('src.q2_nikolastarx.gap_candidate.build_with_witness',
                   side_effect=AssertionError('old gap seed must not run')):
            with patch.object(r05, 'rebuild', wraps=r05.rebuild) as wrapped:
                plan, meta = adapter.build_from_plan(
                    graph, seed, 2, CONFIG, final_proxy_guard=False)
        self.assertEqual(meta['packetization'], 'singleton')
        self.assertEqual(meta['source'], 'caller_selected_plan')
        self.assertEqual(meta['packet_count'], len(DAGIndex(graph).ops))
        self.assertEqual(set(wrapped.call_args.args[2]),
                         {(1, 3), (2, 3), (3, 4), (3, 5), (1, 5)})
        self.assertEqual(wrapped.call_args.args[2][1, 5], 502)
        self.assertEqual(meta['returned'], 'rebuilt')
        view = derive_multicore_plan(graph, plan)
        actual = {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}
        expected = {u: meta['rebuilt_owner'][j] for j, u in enumerate(DAGIndex(graph).order)}
        self.assertEqual(actual, expected)
        self.assertEqual(mandatory_copy_work(graph, plan, CONFIG['bandwidth'])['transfer_bytes'],
                         meta['independent_bytes_returned'])
        self.assertLessEqual(meta['independent_bytes_returned'],
                             mandatory_copy_work(graph, seed, CONFIG['bandwidth'])['transfer_bytes'])
        self.assertEqual(meta['calls'], {'E0': 0, 'E1': 0, 'E2': 0})

    def test_caller_plan_requires_legal_singleton_coverage(self):
        graph = diamond()
        for op in graph['ops']:
            if op['pipe'].startswith('PIPE_MTE'):
                op['pipe'] = 'PIPE_M'
        seed = {'node_to_subgraph': {str(u): u - 1 for u in range(1, 6)},
                'core_schedules': [[0, 2, 3], [1, 4]]}
        with self.assertRaises(ValueError):
            adapter.build_from_plan(graph, seed, 3, CONFIG)
        missing = {'node_to_subgraph': dict(seed['node_to_subgraph']),
                   'core_schedules': [[0, 2, 3], [1]]}
        with self.assertRaisesRegex(Exception, 'cover every subgraph exactly once'):
            adapter.build_from_plan(graph, missing, 2, CONFIG)
        grouped = {'node_to_subgraph': dict(seed['node_to_subgraph']),
                   'core_schedules': [[0, 1, 2, 3]]}
        grouped['node_to_subgraph']['2'] = 0
        grouped['core_schedules'] = [[0, 2, 3], [4]]
        with self.assertRaises(UnsupportedStructure):
            adapter.build_from_plan(graph, grouped, 2, CONFIG)

    def test_exact_injective_net_cost_and_batch_pin_restoration(self):
        nets = [r05.Net(frozenset({0, 1, 2}), 10, 'shared'),
                r05.Net(frozenset({0, 1}), 4, 'batch-only')]
        owner = {0: 0, 1: 1, 2: 2}
        batch = [0, 1]
        matrix, outside = r05.byte_matrix(nets, owner, batch, 3)
        self.assertEqual(outside[0][2], 1)
        self.assertEqual(outside[0][0], 0)
        original = r05.net_cost(nets, owner)
        reference = sum(matrix[i][owner[j]] for i, j in enumerate(batch))
        for assignment in itertools.permutations(range(3), 2):
            moved = dict(owner)
            moved.update(zip(batch, assignment))
            delta = r05.net_cost(nets, moved) - original
            self.assertEqual(delta, sum(matrix[i][c] for i, c in enumerate(assignment)) - reference)
        # Reusing a target is outside the injective reduction and is not scored here.
        self.assertEqual(owner, {0: 0, 1: 1, 2: 2})

    def test_matching_and_rebuild_use_existing_persistent_calendar(self):
        self.assertIs(r05.empty, gap_calendar.empty)
        ops = {0: r05.Op('M', 10), 1: r05.Op('M', 10),
               2: r05.Op('V', 10), 3: r05.Op('V', 10)}
        lags = {(u, v): 2 for u in (0, 1) for v in (2, 3)}
        owner = {0: 0, 1: 1, 2: 0, 3: 1}
        nets = [r05.Net(frozenset({0, 3}), 2), r05.Net(frozenset({1, 2}), 2)]
        sequences, meta = r05.rebuild(
            ops, [[u] for u in ops], lags, nets, 2, owner, [[0, 2], [1, 3]])
        self.assertEqual(meta['pre_step2_bytes_seed'], 6)
        self.assertEqual(meta['pre_step2_bytes_rebuilt'], 2)
        self.assertEqual(meta['returned'], 'rebuilt')
        self.assertEqual(sorted(u for row in sequences for u in row), sorted(ops))

    def test_real_adapter_interfaces_on_small_synthetic_graph(self):
        graph = diamond()
        for op in graph['ops']:
            if op['pipe'].startswith('PIPE_MTE'):
                op['pipe'] = 'PIPE_M'
        plan, meta = adapter.build(graph, 2, CONFIG)
        derive_multicore_plan(graph, plan)
        self.assertIn(meta['returned'], ('seed', 'rebuilt'))
        self.assertEqual(meta['calls'], {'E0': 0, 'E1': 0, 'E2': 0})
        self.assertIn('independent_bytes_returned', meta)

    def test_proxy_guard_is_explicit_and_default_build_stays_guarded(self):
        graph = diamond()
        for op in graph['ops']:
            if op['pipe'].startswith('PIPE_MTE'):
                op['pipe'] = 'PIPE_M'
        seed, _, witness = build_with_witness(graph, 2, CONFIG)
        default_plan, default_meta = adapter.build_from_seed(graph, seed, witness, 2, CONFIG)
        raw_plan, raw_meta = adapter.build_from_seed(
            graph, seed, witness, 2, CONFIG, final_proxy_guard=False)
        self.assertTrue(default_meta['final_proxy_guard_enabled'])
        self.assertFalse(raw_meta['final_proxy_guard_enabled'])
        for plan, meta in ((default_plan, default_meta), (raw_plan, raw_meta)):
            derive_multicore_plan(graph, plan)
            self.assertEqual(mandatory_copy_work(graph, plan, CONFIG['bandwidth'])['transfer_bytes'],
                             meta['independent_bytes_returned'])
            self.assertLessEqual(meta['independent_bytes_returned'], meta['pre_step2_bytes_seed'])
        with patch.object(adapter, 'build_from_seed', wraps=adapter.build_from_seed) as wrapped:
            adapter.build(graph, 2, CONFIG)
            self.assertNotIn('final_proxy_guard', wrapped.call_args.kwargs)

    def test_unsupported_only_is_guarded(self):
        seed = {'node_to_subgraph': {}, 'core_schedules': [[], []]}
        with patch('src.q2_nikolastarx.gap_candidate.build_with_witness',
                   return_value=(seed, {}, {})):
            with patch.object(adapter, 'build_from_seed', side_effect=UnsupportedStructure('domain')):
                plan, meta = adapter.build({}, 2, CONFIG)
                self.assertIs(plan, seed)
                self.assertEqual(meta['guard_rejected'], 'domain')
            with patch.object(adapter, 'build_from_seed', side_effect=ValueError('bad witness')):
                with self.assertRaisesRegex(ValueError, 'bad witness'):
                    adapter.build({}, 2, CONFIG)


if __name__ == '__main__':
    unittest.main()
