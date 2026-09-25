"""Manifest routing and source ownership checks; no evaluator subprocesses."""
import json
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from src.q2_nikolastarx import hypergap_full500 as runner


class CopyEventFull500Tests(TestCase):
    def test_exact_route_budgets(self):
        old = runner.route_limits('hypergap_full500_v1')
        new = runner.route_limits('copyevent_full500_v1')
        self.assertEqual((old['E2_api'], old['E0_fallback_reserved']), (1500, 1500))
        self.assertEqual((new['E2_api'], new['E0_fallback_reserved']), (2000, 2000))
        for key in old.keys() - {'E2_api', 'E0_fallback_reserved'}:
            self.assertEqual(old[key], new[key])
        with self.assertRaises(ValueError):
            runner.route_limits('arbitrary_algorithm')

    def test_runner_file_owned_by_runner_commit_even_if_present_in_solver_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / 'src/q2_nikolastarx'
            package.mkdir(parents=True)
            own = 'src/q2_nikolastarx/hypergap_full500.py'
            other = ['src/q2_nikolastarx/a.py',
                     'src/q2_nikolastarx/evaluate_feedback.py',
                     'src/q2_nikolastarx/chain_pilot.py']
            manifest = 'results/a/pilot/manifest.json'
            contents = {name: name.encode() for name in [own, *other, manifest]}
            for name, raw in contents.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            solver, runner_commit = 'a' * 40, 'b' * 40
            doc = {'solver_commit': solver,
                   'solver_module': 'src.q2_nikolastarx.a',
                   'solver_sources': {name: runner.digest(contents[name]) for name in other},
                   '_manifest_path': root / manifest}
            observed = []

            def fake_git_bytes(commit, path):
                observed.append((commit, path))
                return contents[path]

            tree = '\n'.join([own, *other]) + '\n'
            with mock.patch.object(runner, 'ROOT', root), \
                 mock.patch.object(runner, '__file__', str(root / own)), \
                 mock.patch.object(runner, 'git_bytes', side_effect=fake_git_bytes), \
                 mock.patch.object(runner.subprocess, 'check_output', return_value=tree):
                runner.source_preflight(doc, runner_commit, frozen=True)
            self.assertIn((runner_commit, own), observed)
            self.assertNotIn((solver, own), observed)
            self.assertEqual({path for commit, path in observed if commit == solver}, set(other))


if __name__ == '__main__':
    from unittest import main
    main()
