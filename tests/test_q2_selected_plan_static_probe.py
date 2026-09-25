"""Identity gates only; never constructs a plan or runs an evaluator."""
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
from unittest import TestCase, mock

P = Path(__file__).resolve().parents[1] / 'scripts/q2_selected_plan_static_probe.py'
S = importlib.util.spec_from_file_location('static_probe', P)
m = importlib.util.module_from_spec(S)
S.loader.exec_module(m)


class FreezeGateTests(TestCase):
    def test_synthetic_bytes_and_source_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            graph, config, plan = (root / x for x in ('graph.json', 'config.txt', 'plan.gz'))
            graph.write_text('{}')
            config.write_text('config')
            raw = json.dumps({'node_to_subgraph': {}, 'core_schedules': [[], []]}).encode()
            plan.write_bytes(gzip.compress(raw))
            manifest = {'schema': 'q2-selected-static-003-k2-v1', 'graph': str(graph),
                'config': str(config), 'graph_sha256': m.sha(graph.read_bytes()),
                'config_sha256': m.sha(config.read_bytes()),
                'plan_json_sha256': m.sha(raw), 'plan_gzip_sha256': m.sha(plan.read_bytes()),
                'source_sha256': {'source.py': 'frozen'}, 'source_commit': 'a' * 40,
                'limits': {'workers': 1, 'wall_seconds': 30, 'rss_bytes': 512 << 20,
                           'E0': 0, 'E1': 0, 'E2': 0, 'retries': 0}}
            with mock.patch.object(m, 'PLAN', plan), \
                 mock.patch.object(m, 'PLAN_SHA', manifest['plan_json_sha256']), \
                 mock.patch.object(m, 'GRAPH_SHA', manifest['graph_sha256']), \
                 mock.patch.object(m, 'CONFIG_SHA', manifest['config_sha256']), \
                 mock.patch.object(m, 'sources', return_value=manifest['source_sha256']), \
                 mock.patch.object(m, 'git_head', return_value='a' * 40):
                self.assertEqual(m.verify(manifest), raw)
                manifest['limits']['E0'] = 1
                with self.assertRaises(ValueError):
                    m.verify(manifest)

    def test_existing_marker_blocks_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            manifest = out / 'manifest.json'
            manifest.write_text('{}')
            (out / 'attempt.json').write_text('{}')
            with self.assertRaises(FileExistsError):
                m.reserve_attempt(out, manifest, 1.0)


if __name__ == '__main__':
    from unittest import main
    main()
