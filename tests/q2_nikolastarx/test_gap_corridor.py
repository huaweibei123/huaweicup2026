"""Synthetic fixed-calendar corridor tests; no solver evaluation."""
import unittest
from unittest.mock import patch

from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
from src.q2_nikolastarx.direct import derive_multicore_plan
from src.q2_nikolastarx.gap_candidate import build as seed_build, build_with_witness
from src.q2_nikolastarx.gap_corridor import build, repair_gap_witness
from tests.q2_nikolastarx.test_gap_candidate import CONFIG, diamond


def corridor_fixture(block_target=False, low_lag=False):
    rows = [(1, 'PIPE_M', 0), (2, 'PIPE_M', 10), (3, 'PIPE_V', 0)]
    if block_target:
        rows.append((4, 'PIPE_M', 0))
    graph = {'ops': [{'id': u, 'op': 'COMPUTE', 'pipe': p, 'cycles': 10}
                     for u, p, _ in rows],
             'tensors': [{'id': 10, 'pos': 'UB', 'size': 50}],
             'edges': [{'source': 10, 'target': u} for u in (1, 2, 3)]}
    delays = {}
    if low_lag:
        graph['edges'].append({'source': 1, 'target': 2, 'data_size': 0})
        delays[0, 1] = 10
    chains = [[u] for u, _, _ in rows]
    placement = {j: (0 if u in (1, 2) else 1) for j, (u, _, _) in enumerate(rows)}
    starts = {u: start for u, _, start in rows}
    mapping = {str(u): j for j, (u, _, _) in enumerate(rows)}
    seed = {'node_to_subgraph': mapping, 'core_schedules': [
        [mapping[str(u)] for u in (1, 2)],
        [mapping[str(u)] for u in ([3, 4] if block_target else [3])]]}
    return graph, seed, dict(chains=chains, placement=placement,
                             starts=starts, delays=delays, cores=2, mapping=mapping)


class GapCorridorTests(unittest.TestCase):
    def test_seed_build_two_value_behavior_and_independent_bytes(self):
        graph = diamond()
        seed, meta = seed_build(graph, 2, CONFIG)
        self.assertEqual((seed, meta), build_with_witness(graph, 2, CONFIG)[:2])
        _, _, witness = build_with_witness(graph, 2, CONFIG)
        with patch('src.q2_nikolastarx.gap_candidate.build_with_witness',
                   return_value=(seed, meta, witness)):
            same, _ = build(graph, 2, CONFIG)
        self.assertIs(same, seed)
        candidate, detail = build(graph, 2, CONFIG)
        derive_multicore_plan(graph, candidate)
        self.assertEqual(detail['independent_original_copy_bytes_after'],
                         mandatory_copy_work(graph, candidate, 60)['transfer_bytes'])
        self.assertLessEqual(detail['independent_original_copy_bytes_after'],
                             detail['independent_original_copy_bytes_before'])
        if detail['independent_original_copy_bytes_before'] == detail['independent_original_copy_bytes_after']:
            self.assertEqual(candidate, seed)

    def test_two_groups_have_joint_saving(self):
        graph, seed, witness = corridor_fixture()
        plan, detail = repair_gap_witness(graph, **witness)
        derive_multicore_plan(graph, plan)
        self.assertEqual(detail['saved_pre_step2_bytes'], 50)
        self.assertEqual(detail['flow_calls'], 1)
        self.assertEqual(plan['core_schedules'], [[], [0, 2, 1]])
        self.assertEqual(mandatory_copy_work(graph, seed, 60)['transfer_bytes'], 100)
        self.assertEqual(mandatory_copy_work(graph, plan, 60)['transfer_bytes'], 50)

    def test_target_no_idle_rejects_moves(self):
        graph, seed, witness = corridor_fixture(block_target=True)
        plan, detail = repair_gap_witness(graph, **witness)
        self.assertEqual(set(plan['core_schedules'][0]) & {0, 1}, {0, 1})
        outward = next(row for row in detail['pairs']
                       if row['source_core'] == 0 and row['target_core'] == 1)
        self.assertEqual(outward['moved_groups'], [])
        self.assertEqual(outward['saving_bytes'], 0)

    def test_low_slack_chain_group_moves_together(self):
        graph, _, witness = corridor_fixture(low_lag=True)
        plan, detail = repair_gap_witness(graph, **witness)
        self.assertEqual(detail['tight_group_count'], 2)
        self.assertEqual(detail['saved_pre_step2_bytes'], 50)
        self.assertEqual(plan['core_schedules'], [[], [0, 2, 1]])


if __name__ == '__main__':
    unittest.main()
