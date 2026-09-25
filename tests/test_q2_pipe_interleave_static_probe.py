"""Small projection contract check; no graph or retimer execution."""
import importlib.util
from pathlib import Path
import tempfile
from unittest import TestCase

P = Path(__file__).resolve().parents[1] / 'scripts/q2_pipe_interleave_static_probe.py'
S = importlib.util.spec_from_file_location('pipe_probe', P)
m = importlib.util.module_from_spec(S)
S.loader.exec_module(m)


class ProjectionTests(TestCase):
    def test_cross_pipe_reorder_preserves_owner_and_fifo(self):
        pipes = {1: 'PIPE_M', 2: 'PIPE_V', 3: 'PIPE_M'}
        mapping = {'1': 'a', '2': 'b', '3': 'c'}
        before = {'node_to_subgraph': mapping, 'core_schedules': [['a', 'b', 'c']]}
        after = {'node_to_subgraph': mapping, 'core_schedules': [['b', 'a', 'c']]}
        changed = {'node_to_subgraph': mapping, 'core_schedules': [['c', 'a', 'b']]}
        self.assertEqual(m.projection(before, pipes), m.projection(after, pipes))
        self.assertNotEqual(m.projection(before, pipes), m.projection(changed, pipes))
        self.assertTrue(m.rows_follow_global_order(after, [2, 1, 3]))
        self.assertFalse(m.rows_follow_global_order(after, [1, 3, 2]))

    def test_constructor_count_distinguishes_no_dispatch_from_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            self.assertEqual(m.constructor_count(out, False), 0)
            self.assertIsNone(m.constructor_count(out, True))
            (out / 'constructor-start.json').write_text('{"constructor_started": 1}\n')
            self.assertEqual(m.constructor_count(out, True), 1)


if __name__ == '__main__':
    from unittest import main
    main()
