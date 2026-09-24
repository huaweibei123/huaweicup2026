"""Fake receipts/results only. These tests never execute a solver or evaluator."""
from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from src.benchmark_board.protocol import validate_feed
from src.q2_nikolastarx import evaluate_matrix as matrix


def protocol(mode='direct'):
    return {'schema_version': 1, 'run_id': 'test-matrix-not-a-score', 'session': 'test/s-fake',
            'task_url': 'https://github.com/huaweibei123/huaweicup2026/issues/33',
            'cases': ['002', '016'], 'cores': [2, 4, 5], 'methods': ['structural_router'],
            'solver_mode': mode, 'solver_module': 'src.q2_nikolastarx.direct_solve',
            'source_files': ['src/q2_nikolastarx/direct_solve.py'],
            'algorithm_id': 'fake-for-unit-test', 'algorithm_name': 'Synthetic test only',
            'variant': 'not-executed', 'method_description': 'Synthetic test only; no official scores',
            'output_prefix': 'results/a/q2-nikolastarx/unit-test',
            'config_sha256': 'b' * 64, 'official_sha256': 'c' * 64,
            'max_E0': 12, 'max_internal_per_cell': 0 if mode == 'direct' else 1,
            'evaluation_timeout_seconds': 1, 'solver_wall_seconds': 2, 'batch_wall_seconds': 10,
            'rss_observation_stop_bytes': 1024**3, 'workers': 1, 'retries': 0, 'max_E1': 0, 'max_E2': 0}


class MatrixTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.patcher = patch.object(matrix, 'ROOT', self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.addCleanup(self.temporary.cleanup)
        self.argv = []

    def fake_monitor(self, mode='direct', mismatch=False, timeout=False):
        def run(argv, folder, deadline, rss_limit):
            self.argv.append(argv)
            folder.mkdir(parents=True, exist_ok=True)
            receipt = {'pid': 12345, 'status': 'timeout' if timeout else 'ok',
                       'exit_code': -9 if timeout else 0, 'wall_seconds': .01,
                       'observed_peak_rss_bytes': 1000, 'argv': argv}
            matrix.save(folder / 'process.json', receipt)
            if timeout:
                return receipt
            def destination(flag):
                return self.root / argv[argv.index(flag) + 1]
            result = {'scene': 'B', 'num_cores': 2, 'makespan': 10,
                      'data_movement_bytes': {'scheduled_copy_bytes': 100, 'added_copy_bytes': 0, 'spill_added_copy_bytes': 0}}
            if '-m' in argv:
                plan = {'node_to_subgraph': {'1': 0}, 'core_schedules': [[0], []]}
                matrix.save(destination('--output'), plan)
                evidence = destination('--evidence')
                ledger = {'status': 'ok', 'selected': 'synthetic-direct-route',
                          'plan_sha256': matrix.sha(destination('--output').read_bytes()),
                          'calls': {'E0': int(mode == 'portfolio'), 'E1': 0, 'E2': 0},
                          'attempts': [{'name': 'structural_router', 'status': 'constructed'}]}
                if mode == 'portfolio':
                    ledger['selected_result'] = 'structural_router/result.json'
                    ledger['makespan_cycles'] = 10
                    ledger['attempts'][0]['status'] = 'ok'
                    matrix.save(evidence / ledger['selected_result'], result)
                matrix.save(evidence / 'solver.json', ledger)
            else:
                result['makespan'] += int(mismatch)
                matrix.save(destination('-o'), result)
            return receipt
        return run

    def execute(self, p, **kwargs):
        return matrix.execute_cell(p, '002', 2, self.root / 'results/a/q2-nikolastarx/unit-test/002-k2',
                                   time.perf_counter() + 10, self.fake_monitor(p['solver_mode'], **kwargs))

    def test_fixed_cartesian_product_and_direct_budget(self):
        p = protocol()
        self.assertEqual(matrix.validate_protocol(p), [('002', 2), ('002', 4), ('002', 5), ('016', 2), ('016', 4), ('016', 5)])
        p['max_internal_per_cell'] = 1
        with self.assertRaisesRegex(ValueError, 'zero online'):
            matrix.validate_protocol(p)

    def test_invalid_enums_and_override_cannot_launch(self):
        for field, value in [('cases', ['002', '002']), ('cores', [True]), ('methods', []),
                             ('extra_solver_argv', ['--output=elsewhere']), ('source_files', ['../outside.py'])]:
            p = protocol(); p[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                matrix.validate_protocol(p)
        self.assertEqual(self.argv, [])

    def test_dispatch_is_persisted_and_cannot_be_retried(self):
        path = self.root / 'journal.json'
        journal = matrix.Journal(path, {'source_commit': 'a' * 40}, [('002', 2), ('016', 2)], 1)
        self.assertTrue(journal.reserve('002-k2', 1))
        # Crash before any finish: the persisted reservation is never pending again.
        status = matrix.recovery_status(path)
        self.assertEqual(status['pending'], ['016-k2'])
        self.assertEqual(status['dispatched_never_retry'], ['002-k2'])
        with self.assertRaises(ValueError): journal.reserve('002-k2', 1)
        self.assertFalse(journal.reserve('016-k2', 1))
        with self.assertRaises(FileExistsError): matrix.Journal(path, {}, [], 99)

    def test_direct_has_no_online_result_or_score(self):
        row = self.execute(protocol())
        self.assertEqual(row['status'], 'ok')
        self.assertEqual(row['calls'], {'solver': 1, 'E0': 1, 'E1': 0, 'E2': 0})
        self.assertNotIn('selected_result', row['online'])
        self.assertNotIn('makespan_cycles', row['online'])
        self.assertIsNone(row['full_online_result_equal'])
        self.assertNotIn('--evaluation-timeout', self.argv[0])
        self.assertEqual(len(self.argv), 2)

    def test_portfolio_full_result_mismatch_is_failure(self):
        row = self.execute(protocol('portfolio'), mismatch=True)
        self.assertEqual(row['status'], 'failed')
        self.assertIn('Full online/final result mismatch', row['error'])
        self.assertEqual(row['calls']['E0'], 2)
        self.assertIn('--evaluation-timeout', self.argv[0])

    def test_timeout_preserves_unknown_calls_and_never_runs_final(self):
        row = self.execute(protocol(), timeout=True)
        self.assertEqual(row['status'], 'timeout')
        self.assertIsNone(row['calls']['E0'])
        self.assertEqual(len(self.argv), 1)
        self.assertEqual(row['calls']['solver'], 1)

    def test_literal_method_violation_stops_before_final(self):
        p = protocol(); p['methods'] = ['another_method']
        row = self.execute(p)
        self.assertEqual(row['status'], 'failed')
        self.assertIn('method enum', row['error'])
        self.assertEqual(len(self.argv), 1)

    def test_launch_error_does_not_fabricate_a_started_solver(self):
        def fail(argv, folder, deadline, rss_limit):
            matrix.save(folder / 'process.json', {'status': 'runner_error', 'wall_seconds': .01})
            raise FileNotFoundError('synthetic missing executable')
        row = matrix.execute_cell(protocol(), '002', 2, self.root / 'missing-process', time.perf_counter()+1, fail)
        self.assertEqual(row['status'], 'failed')
        self.assertEqual(row['calls']['solver'], 0)
        self.assertEqual(row['calls']['E0'], 0)

    def test_observer_error_preserves_unknown_after_child_started(self):
        def fail(argv, folder, deadline, rss_limit):
            matrix.save(folder / 'process.json', {'pid': 12345, 'status': 'runner_error', 'wall_seconds': .01})
            raise RuntimeError('synthetic observer failure')
        row = matrix.execute_cell(protocol(), '002', 2, self.root / 'observed-process', time.perf_counter()+1, fail)
        self.assertEqual(row['calls']['solver'], 1)
        self.assertIsNone(row['calls']['E0'])
        self.assertEqual(matrix.stop_dispatch_reason(row), 'unknown_dispatch_or_call_count')

    def test_known_final_failure_may_continue_but_survivor_must_stop(self):
        row = {'calls': {'solver': 1, 'E0': 1}, 'final': {'status': 'timeout', 'surviving_pids': []}}
        self.assertIsNone(matrix.stop_dispatch_reason(row))
        row['final']['surviving_pids'] = [12345]
        self.assertEqual(matrix.stop_dispatch_reason(row), 'final_owned_processes_still_live')

    def test_direct_and_failure_feed_shapes_are_valid(self):
        for mode, timeout in [('direct', False), ('direct', True), ('portfolio', False)]:
            with self.subTest(mode=mode, timeout=timeout):
                p = protocol(mode); p['output_prefix'] += f'-{mode}-{timeout}'
                folder = self.root / p['output_prefix'] / '002-k2'
                row = matrix.execute_cell(p, '002', 2, folder, time.perf_counter()+10,
                                          self.fake_monitor(mode=mode, timeout=timeout))
                matrix.archive_cell(folder, self.root / 'raw' / str(timeout))
                matrix.write_manifest(folder)
                context = {'source_commit': 'd' * 40, 'runner_commit': 'e' * 40, 'argv': ['python', 'fake-only'],
                           'hashes': {'inputs': {'data/case_002.json': 'a' * 64}},
                           'environment': {'os': 'synthetic', 'cpu': 'synthetic', 'gpu': 'none', 'ram_bytes': 1024**3,
                            'python': 'synthetic', 'dependencies': 'none; no runtime executed', 'threads': 1, 'workers': 1}}
                record = matrix.board_record(p, row, folder, context)
                self.assertTrue(validate_feed({'schema_version':1,'submission_version':1,'records':[record]}, submission=True))
                self.assertEqual(record['metrics']['solver_wall_seconds'], .01)
                # The timing boolean refers to the separately reported FINAL E0.
                self.assertFalse(record['timing']['solver_includes_evaluation'])
                self.assertEqual(record['parameters']['online_evaluation_in_solver_wall'], mode == 'portfolio')
                scope = record['provenance']['measurement']['evaluation_scope']
                self.assertIn('Online E0 is included' if mode == 'portfolio' else 'Zero online E0', scope)

    def test_driver_continues_after_failed_final_without_repeating_cell(self):
        p = protocol(); p.update(cases=['002', '016'], cores=[2], max_E0=2)
        protocol_path = self.root / 'protocol.json'; matrix.save(protocol_path, p)
        real_execute = matrix.execute_cell
        normal = self.fake_monitor(); timed_out = self.fake_monitor(timeout=True)
        def monitor(argv, folder, deadline, rss_limit):
            if '-m' not in argv and 'data/raw/a/official/data/case_002.json' in argv:
                return timed_out(argv, folder, deadline, rss_limit)
            return normal(argv, folder, deadline, rss_limit)
        def execute(*args, **kwargs):
            return real_execute(*args, **kwargs, monitor=monitor)
        hashes = {'inputs': {'data/case_002.json': 'a'*64, 'data/case_016.json': 'b'*64}}
        env = {'os':'synthetic','cpu':'synthetic','gpu':'none','ram_bytes':1024**3,'python':'synthetic',
               'dependencies':'synthetic','threads':1,'workers':1}
        argv = ['matrix', 'run', '--protocol', str(protocol_path), '--source-commit', 'd'*40, '--runner-commit', 'e'*40]
        fake_check = subprocess.CompletedProcess(['not-executed'], 0, '{"valid":true}', '')
        with patch.object(sys, 'argv', argv), patch.object(matrix, 'frozen_inputs', return_value=hashes), \
             patch.object(matrix.common, 'environment', return_value=env), patch.object(matrix, 'execute_cell', side_effect=execute), \
             patch.object(matrix.subprocess, 'run', return_value=fake_check), \
             patch.object(matrix.tempfile, 'mkdtemp', return_value=str(self.root/'raw-backup')), redirect_stdout(io.StringIO()):
            matrix.main()
        output = self.root / p['output_prefix']; journal = matrix.read(output / 'journal.json')
        self.assertEqual(journal['cells']['002-k2']['state'], 'timeout')
        self.assertEqual(journal['cells']['002-k2']['calls']['E0'], 1)
        self.assertEqual(journal['cells']['016-k2']['state'], 'ok')
        self.assertEqual(journal['cells']['016-k2']['calls']['E0'], 1)
        self.assertEqual(len(self.argv), 4)  # One solver and one fake final for each cell.
        for key in ('002-k2', '016-k2'):
            feed = matrix.read(output / f'board-feed-{key}.json')
            self.assertTrue(validate_feed(feed, submission=True))


if __name__ == '__main__':
    unittest.main()
