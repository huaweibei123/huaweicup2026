"""Small, self-contained coverage receipts; no solver or E0 calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.q2.feedback import coverage


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')
    return path


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(coverage, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def batch(self, name, *, variant='gap_packet', args=(), source='hash', attempts=()):
        path = self.root / name
        write(path / 'spec.json', {'solver_commit': 'fixed',
                                   'methods': [{'variant': variant, 'args': list(args)}],
                                   'source_paths': ['solver.py']})
        write(path / 'ledger.json', {
            'state': 'completed', 'started_at': 'start', 'finished_at': 'finish',
            'batch_wall_seconds': 1, 'preparation': {'wall_seconds': 0},
            'charged_calls': {'solver': len(attempts), 'E0': len(attempts), 'E1': 0, 'E2': 0},
            'source_hashes': {'solver.py': source}, 'attempts': list(attempts)})
        return path

    def success(self, name, case='001', cores=1, variant='gap_packet', args=(), source='hash'):
        identity = {'graph_sha256': 'graph', 'config_sha256': 'config',
                    'official_sha256': 'official'}
        baseline = self.root / 'results/benchmark-board/official-singlecore-20260924' / case / 'run.json'
        write(baseline, {'graph_sha256': 'graph', 'config_sha256': 'config',
                         'official_code_hash': 'official', 'makespan_cycles': 200})
        result = write(self.root / name / 'result.json', {
            'scene': 'B', 'num_cores': cores, 'makespan': 100,
            'data_movement_bytes': {'added_copy_bytes': 4, 'spill_added_copy_bytes': 0}})
        run_path = write(self.root / name / 'run.json', {
            'status': 'ok', 'case_id': case, 'cores': cores, 'solver_commit': 'fixed',
            'method': {'variant': variant, 'args': list(args)},
            'source_hashes': {'solver.py': source}, 'calls': {'E0': 1},
            'stages': {'E0': {'status': 'ok', 'returncode': 0, 'wall_seconds': 2},
                       'solver': {'wall_seconds': 1}},
            'identity': identity, 'artifacts': {'result': coverage.reference(result)},
            'metrics': {'makespan_cycles': 100}})
        return run_path.relative_to(self.root).as_posix()

    def test_explicit_variant_and_incomplete_mean(self):
        attempt = self.success('a')
        batch = self.batch('a', attempts=(attempt,))
        report = coverage.summarize([batch], 'fixed', 'gap_packet')
        self.assertEqual(report['algorithm'], 'gap_packet')
        self.assertEqual(report['args'], [])
        self.assertEqual(report['cores']['1']['successful_cases'], 1)
        self.assertIsNone(report['cores']['1']['full100_arithmetic_mean'])
        self.assertEqual(report['cores']['1']['observed_subset_mean'], 2)
        with self.assertRaisesRegex(ValueError, 'variant'):
            coverage.summarize([batch], 'fixed')

    def test_default_variant_remains_tensor_packet(self):
        batch = self.batch('a', variant='tensor_packet')
        report = coverage.summarize([batch], 'fixed')
        self.assertEqual(report['algorithm'], 'tensor_packet')
        self.assertEqual(report['args'], [])
        self.assertIsNone(report['cores']['1']['full100_arithmetic_mean'])

    def test_cross_batch_variant_args_and_source_must_match(self):
        first = self.batch('a')
        for other, message in [(self.batch('variant', variant='tensor_packet'), 'variant'),
                               (self.batch('args', args=('--window', '2')), 'args'),
                               (self.batch('source', source='other'), 'source bytes')]:
            with self.subTest(other=other.name), self.assertRaisesRegex(ValueError, message):
                coverage.summarize([first, other], 'fixed', 'gap_packet')

    def test_duplicate_successful_cell_rejected(self):
        one = self.success('a')
        two = self.success('b')
        first = self.batch('a', attempts=(one,))
        second = self.batch('b', attempts=(two,))
        with self.assertRaisesRegex(ValueError, 'duplicate successful cell'):
            coverage.summarize([first, second], 'fixed', 'gap_packet')


if __name__ == '__main__':
    unittest.main()
