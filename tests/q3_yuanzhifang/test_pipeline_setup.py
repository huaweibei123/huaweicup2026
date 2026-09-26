import itertools
import random
import unittest

from src.q3_yuanzhifang.construct import SharingIndex
from src.q3_yuanzhifang.pipeline_setup import build, partition
from src.q3_yuanzhifang.pipeline_stages import build as old_build


def recurrence(weights, setup, cuts, jobs):
    """Independent small serial flowshop event table; no closed-form oracle."""
    work = [sum(weights[l:r]) for l, r in zip(cuts, cuts[1:])]
    cold = [sum(setup[l:r]) for l, r in zip(cuts, cuts[1:])]
    done = [[0] * (len(work)+1) for _ in range(jobs+1)]
    for j in range(1, jobs+1):
        for s in range(1, len(work)+1):
            done[j][s] = max(done[j-1][s], done[j][s-1]) + work[s-1]
            if j == 1:
                done[j][s] += cold[s-1]
    return done[-1][-1]


def synthetic_jobs():
    return {'ops': [{'id': u, 'op': 'MUL', 'pipe': 'PIPE_M', 'cycles': 10}
                    for u in range(1, 37)],
            'tensors': [{'id': 100, 'pos': 'L1', 'size': 6000}],
            'edges': [{'source': u, 'target': u+1} for u in range(1, 37) if u % 6] +
                     [{'source': 100, 'target': u} for u in range(6, 37, 6)]}


class ColdSetupPipelineTest(unittest.TestCase):
    def test_dp_matches_independent_exhaustive_event_table(self):
        rng = random.Random(937)
        for _ in range(100):
            n = rng.randint(2, 7)
            k, jobs = rng.randint(1, min(4, n)), rng.randint(1, 6)
            weights = [rng.randint(1, 20) for _ in range(n)]
            setup = [rng.randint(0, 100) for _ in range(n)]
            value = min(recurrence(weights, setup, [0, *inside, n], jobs)
                        for inside in itertools.combinations(range(1, n), k-1))
            cuts, predicted = partition(weights, setup, k, jobs)
            self.assertEqual(predicted, value)
            self.assertEqual(recurrence(weights, setup, cuts, jobs), value)

    def test_late_setup_changes_balanced_work_cut(self):
        cuts, cycles = partition([10]*6, [0, 0, 0, 0, 0, 100], 2, 6)
        self.assertEqual((cuts, cycles), ([0, 4, 6], 260))
        self.assertEqual(recurrence([10]*6, [0, 0, 0, 0, 0, 100], [0, 3, 6], 6), 310)

    def test_build_retains_singletons_and_forward_job_order(self):
        graph = synthetic_jobs()
        plan, meta = build(SharingIndex(graph), 2, 60)
        self.assertTrue(meta['guard'])
        self.assertEqual(meta['cuts'], [0, 4, 6])
        self.assertEqual(meta['stage_first_job_setup_cycles'], [0, 100])
        inverse = {s: int(u) for u, s in plan['node_to_subgraph'].items()}
        actual = [[inverse[s] for s in seq] for seq in plan['core_schedules']]
        self.assertEqual(actual[0], [u for u in range(1, 37) if (u-1) % 6 < 4])
        self.assertEqual(actual[1], [u for u in range(1, 37) if (u-1) % 6 >= 4])
        self.assertEqual(len(set(plan['node_to_subgraph'].values())), 36)

    def test_multi_position_shared_input_uses_unchanged_fallback(self):
        graph = synthetic_jobs()
        graph['edges'] += [{'source': 100, 'target': u} for u in range(5, 36, 6)]
        expected, _ = old_build(SharingIndex(graph), 2, 60)
        actual, meta = build(SharingIndex(graph), 2, 60)
        self.assertFalse(meta['guard'])
        self.assertEqual(meta['reason'], 'shared_input_reused_at_multiple_positions')
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
