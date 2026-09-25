"""Preparation-only differential checks; no E0 or native replay calls."""
import pickle
import unittest
from pathlib import Path

from research.a.e2_search._official_b import load_bundle, read_config
from research.a.e2_search._rank_b import install
from research.a.e2_search.scene_b import SceneBEvaluator
from research.a.e2_search.tests.test_scene_b import micro


class RankLookupTest(unittest.TestCase):
    def test_private_bundle_only_and_shape(self):
        engine = SceneBEvaluator(micro(0)[0], problem=2)
        self.assertEqual(engine.rank_optimization, {'core_orders': 1, 'lookups': 4})
        self.assertIsNot(engine._runtime._build_scene_b_tasks,
                         engine._fast_runtime._build_scene_b_tasks)

    def test_prepared_tasks_or_error_match_frozen_builder(self):
        config_path = Path('data/raw/a/official/data/config.txt')
        for problem in (2, 3):
            original, _ = load_bundle(problem)
            fast, _ = load_bundle(problem)
            self.assertEqual(install(fast), {'core_orders': 1, 'lookups': 4})
            config = read_config(config_path, problem=problem)
            for seed in range(20):
                graph, plan = micro(seed)

                def prepared(fn):
                    try:
                        value = fn(graph, plan, config['bandwidth'], config['capacity'])
                    except Exception as error:
                        return ('error', type(error).__name__, str(error))
                    return ('ok', pickle.dumps(value, protocol=5))

                with self.subTest(problem=problem, seed=seed):
                    self.assertEqual(prepared(original._build_scene_b_tasks),
                                     prepared(fast._build_scene_b_tasks))


if __name__ == '__main__':
    unittest.main()
