"""Pure producer checks; no solver, E0 or native E2 is launched."""
import importlib.util
import json
from pathlib import Path
import tempfile
from unittest import TestCase, mock

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/q2_copyevent_linux_full500.py'
SPEC = importlib.util.spec_from_file_location('copyevent_linux_full500', SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class Full500Checks(TestCase):
    def test_exact_metrics_and_fallback_rejection(self):
        movement = {name: 0 for name in runner.FIELDS}
        official = {'scene': 'B', 'num_cores': 5, 'makespan': 12,
                    'cross_task_traffic': 0, 'data_movement_bytes': movement}
        native = {'status': 'ok', 'route': 'native', 'problem': 2, 'makespan': 12,
                  'cross_task_traffic': 0, 'data_movement_bytes': movement}
        self.assertEqual(runner.metrics(official, official=True, cores=5),
                         runner.metrics(native, official=False))
        with self.assertRaises(ValueError):
            runner.metrics({**native, 'route': 'e0_fallback'}, official=False)
        with self.assertRaises(ValueError):
            runner.metrics({**official, 'data_movement_bytes': {}}, official=True, cores=5)
        with self.assertRaises(ValueError):
            runner.metrics(official, official=True, cores=4)

    def test_zero_e2_requires_single_plan_and_is_labeled_e0_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            graph = root / 'data/raw/a/official/data/case_005.json'
            config = root / 'data/raw/a/official/data/config.txt'
            graph.parent.mkdir(parents=True)
            graph.write_text('{}')
            config.write_text('config')
            folder = root / 'out/005-k5'
            (folder / 'online').mkdir(parents=True)
            plan = {'node_to_subgraph': {}, 'core_schedules': [[], [], [], [], []]}
            (folder / 'plan.json').write_text(json.dumps(plan))
            ledger = {'status': 'ok', 'request_in_flight': False,
                      'calls': {'E2_api_attempted': 0, 'native_returns': 0,
                                'E0_fallback': 0, 'E0': 0},
                      'possible_E0_fallback_calls': 0,
                      'attempts': [], 'source_checked': False,
                      'solver_source_sha256': {'a.py': 'abc'},
                      'graph_sha256': runner.sha(graph), 'config_sha256': runner.sha(config),
                      'cores': 5, 'plan_sha256': runner.sha(folder / 'plan.json'),
                      'detail': {'score_evidence': 'not_requested', 'selected': 'base',
                                 'base_detail': {'score_evidence': 'not_requested',
                                                 'unique_plans': 1,
                                                 'construction_errors': []}}}
            path = folder / 'online/solver.json'
            path.write_text(json.dumps(ledger))
            process = {'status': 'ok', 'surviving_pids': []}
            with mock.patch.object(runner, 'ROOT', root):
                _, score, route = runner.inspect_solver(folder, '005', 5, process,
                                                         {'src/q2_nikolastarx/a.py': 'abc'}, {})
                self.assertIsNone(score)
                self.assertEqual(route, 'single_plan_independent_E0_only')
                ledger['detail']['base_detail']['unique_plans'] = 2
                path.write_text(json.dumps(ledger))
                with self.assertRaises(ValueError):
                    runner.inspect_solver(folder, '005', 5, process,
                                          {'src/q2_nikolastarx/a.py': 'abc'}, {})

    def test_first_failure_leaves_explicit_grid_gap(self):
        seen = []

        def fake_cell(case, cores, *_args):
            seen.append((case, cores))
            return {'case': case, 'cores': cores,
                    'status': 'accepted' if len(seen) == 1 else 'stopped',
                    'calls': {'E2_api_attempted': 0, 'native_returns': 0,
                              'E0_independent_started': 1},
                    'call_count_complete': True}

        doc = {'limits': {'workers': 1}, 'runner_source_commit': 'b' * 40,
               'baseline_provenance': {'source_commit': 'a' * 40},
               'singlecore_baseline': {'sha256': 'c' * 64}}
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(runner, 'COORDS', (('001', 1), ('001', 2), ('001', 3))), \
             mock.patch.object(runner, 'cell', fake_cell):
            summary = runner.run(doc, {'linux_receipt_sha256': 'd' * 64,
                                       'linux_binary_sha256': 'e' * 64}, {}, None,
                                 'f' * 64, 'runtime', Path(temp) / 'run')
        self.assertEqual(seen, [('001', 1), ('001', 2)])
        self.assertEqual(summary['accepted_cells'], 1)
        self.assertEqual(summary['status'], 'stopped_first_failure')


if __name__ == '__main__':
    from unittest import main
    main()
