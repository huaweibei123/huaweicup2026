"""Controller fault tests with fabricated process outputs; never run an evaluator."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from src.q2_nikolastarx.solve import solve


class IncumbentTests(unittest.TestCase):
    def run_mock(self, outcomes, bounds=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph = root / 'graph.json'
            graph.write_text('{}')
            output = root / 'final.json'
            remaining = iter(outcomes)

            class FakeProcess:
                def __init__(self, command, **unused):
                    self.outcome = next(remaining)
                    self.pid = 123456789
                    self.returncode = 0
                    self.waits = 0
                    if type(self.outcome) in (int, float):
                        Path(command[command.index('-o') + 1]).write_text(json.dumps(
                            {'makespan': self.outcome, 'data_movement_bytes': {}}))

                def wait(self, timeout=None):
                    self.waits += 1
                    if self.outcome == 'timeout' and self.waits == 1:
                        raise subprocess.TimeoutExpired('fabricated', timeout)
                    self.returncode = 1 if isinstance(self.outcome, str) else 0
                    return self.returncode

            def proposal(graph, cores, name):
                return {'node_to_subgraph': {name: 0}, 'core_schedules': [[0]]}, {}

            with patch('src.q2_nikolastarx.solve.construct', proposal), \
                 patch('src.q2_nikolastarx.solve.subprocess.Popen', FakeProcess), \
                 patch('src.q2_nikolastarx.solve.assigned_pipe_lower_bound',
                       side_effect=bounds), \
                 patch('src.q2_nikolastarx.solve.os.killpg'):
                receipt = solve(graph, root/'unused.conf', 1, output, root/'evidence',
                                prune_bounds=bounds is not None)
            return receipt, json.loads(output.read_text()) if output.exists() else None

    def test_regression_error_and_timeout_keep_confirmed_seed(self):
        result, plan = self.run_mock([100, 130, 'error', 'timeout'])
        self.assertEqual(result['selected'], 'contiguous')
        self.assertEqual(result['calls']['E0'], 4)
        self.assertEqual(list(plan['node_to_subgraph']), ['contiguous'])
        self.assertEqual([r['status'] for r in result['attempts']],
                         ['ok', 'ok', 'official_error', 'timeout'])

    def test_strict_improvement_and_tie(self):
        result, plan = self.run_mock([100, 80, 80, 90])
        self.assertEqual(result['selected'], 'chain_critical')
        self.assertEqual(result['makespan_cycles'], 80)
        self.assertEqual(list(plan['node_to_subgraph']), ['chain_critical'])

    def test_no_success_publishes_no_plan(self):
        result, plan = self.run_mock(['error', 'timeout', 'error', 'error'])
        self.assertEqual(result['status'], 'failed')
        self.assertIsNone(plan)

    def test_failed_seed_does_not_poison_later_success(self):
        result, plan = self.run_mock(['error', 110, 100, 120])
        self.assertEqual(result['selected'], 'affine_eighth')
        self.assertEqual(list(plan['node_to_subgraph']), ['affine_eighth'])

    def test_equal_bound_skips_call_but_preserves_later_improvement(self):
        result, plan = self.run_mock([12, 10, 9], [5, 10, 10, 9])
        self.assertEqual(result['calls']['E0'], 3)
        self.assertEqual(result['selected'], 'guarded_reentry')
        skipped = result['attempts'][2]
        self.assertEqual(skipped['status'], 'bound_pruned')
        self.assertEqual(skipped['incumbent_makespan_cycles'], 10)
        self.assertIn('plan_sha256', skipped)

    def test_no_confirmed_incumbent_or_no_certificate_cannot_prune(self):
        result, plan = self.run_mock(['error', 110, 100, 120], [999, 100, None, None])
        self.assertEqual(result['calls']['E0'], 4)
        self.assertEqual(result['selected'], 'affine_eighth')


if __name__ == '__main__':
    unittest.main()
