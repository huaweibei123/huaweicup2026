"""Complete-plan selection tests with an injected oracle; no official runs."""
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import adaptive_bidirectional_guarded as route
from src.q2_nikolastarx.direct import UnsupportedStructure


BASE = {'node_to_subgraph': {'1': 0}, 'core_schedules': [[0]]}
GAP = {'node_to_subgraph': {'1': 1}, 'core_schedules': [[1]]}
HYPER = {'node_to_subgraph': {'1': 2}, 'core_schedules': [[2]]}
REVERSE = {'node_to_subgraph': {'1': 3}, 'core_schedules': [[3]]}
FOURTH = {'node_to_subgraph': {'1': 4}, 'core_schedules': [[4]]}


def exercise(values=None, *, old_plans=(BASE, GAP, HYPER), incumbent=HYPER,
             reverse=REVERSE, evidence='injected_oracle_complete_plan_scores',
             reverse_error=None, cores=2):
    values = values or {id(BASE): (110, 8), id(GAP): (105, 9),
                        id(HYPER): (100, 10), id(REVERSE): (90, 20)}
    calls = []

    def oracle(plan):
        calls.append(plan)
        result = values[id(plan)]
        if isinstance(result, Exception):
            raise result
        return {'status': 'ok', 'makespan': result[0], 'added_copy_bytes': result[1]}

    def old_build(graph, count, config, scored_oracle):
        for plan in old_plans:
            scored_oracle(plan)
        return incumbent, {'selected': 'hypergap', 'selected_strategy': 'hypergap_retime',
                           'score_evidence': evidence, 'constructed_plans': len(old_plans),
                           'scores': {'baseline': [110, 8]}}

    with patch.object(route.adaptive_hypergap_guarded, 'build', side_effect=old_build), \
         patch.object(route.reverse_gap_candidate, 'build',
                      return_value=(reverse, {'selected': 'reverse_join_gap_candidate'}),
                      side_effect=reverse_error) as reverse_build:
        chosen, detail = route.build({}, cores, {}, oracle)
    return chosen, detail, calls, reverse_build


class BidirectionalGuardTests(unittest.TestCase):
    def test_reverse_strict_improvement_and_old_scores_reused(self):
        chosen, detail, calls, _ = exercise()
        self.assertIs(chosen, REVERSE)
        self.assertEqual(calls, [BASE, GAP, HYPER, REVERSE])
        self.assertEqual(detail['oracle_requests'], 4)
        self.assertEqual(detail['cache_hits'], 1)
        self.assertEqual(detail['scores'], {'incumbent': [100, 10], 'reverse': [90, 20]})
        self.assertEqual(detail['selected_strategy'], 'reverse_join_gap_candidate')
        self.assertEqual(detail['incumbent_detail']['selected_strategy'], 'hypergap_retime')

    def test_regression_tie_and_ddr_tiebreak(self):
        for reverse_score, expected in [((101, 0), HYPER), ((100, 10), HYPER),
                                        ((100, 11), HYPER), ((100, 9), REVERSE)]:
            values = {id(BASE): (110, 8), id(GAP): (105, 9),
                      id(HYPER): (100, 10), id(REVERSE): reverse_score}
            chosen, detail, _, _ = exercise(values)
            self.assertIs(chosen, expected)
            if expected is HYPER:
                self.assertEqual(detail['selected_strategy'], 'hypergap_retime')

    def test_reverse_score_failure_keeps_old_winner(self):
        values = {id(BASE): (110, 8), id(GAP): (105, 9),
                  id(HYPER): (100, 10), id(REVERSE): RuntimeError('no score')}
        chosen, detail, calls, _ = exercise(values)
        self.assertIs(chosen, HYPER)
        self.assertEqual(calls, [BASE, GAP, HYPER, REVERSE])
        self.assertEqual(detail['skip_reason'], 'reverse_score_unavailable')
        self.assertEqual(detail['oracle_requests'], 4)

    def test_unknown_old_evidence_stops_without_reverse(self):
        chosen, detail, calls, reverse_build = exercise(evidence='unknown')
        self.assertIs(chosen, HYPER)
        self.assertEqual(len(calls), 3)
        self.assertEqual(detail['skip_reason'], 'incumbent_score_evidence_unknown')
        reverse_build.assert_not_called()

    def test_unsupported_and_unexpected_reverse_failures_keep_incumbent(self):
        for error in (UnsupportedStructure('unsupported'), RuntimeError('failed')):
            chosen, detail, calls, _ = exercise(reverse_error=error)
            self.assertIs(chosen, HYPER)
            self.assertEqual(len(calls), 3)
            self.assertEqual(detail['skip_reason'], 'reverse_construction_unavailable')

    def test_duplicate_plan_avoids_extra_request(self):
        chosen, detail, calls, _ = exercise(reverse=HYPER)
        self.assertIs(chosen, HYPER)
        self.assertEqual(len(calls), 3)
        self.assertEqual(detail['skip_reason'], 'reverse_duplicates_incumbent')

    def test_reverse_matching_an_earlier_scored_plan_uses_cache(self):
        chosen, detail, calls, _ = exercise(reverse=GAP)
        self.assertIs(chosen, HYPER)
        self.assertEqual(calls, [BASE, GAP, HYPER])
        self.assertEqual(detail['cache_hits'], 2)

    def test_four_start_cap_keeps_incumbent(self):
        values = {id(BASE): (110, 8), id(GAP): (105, 9),
                  id(HYPER): (100, 10), id(FOURTH): (120, 1),
                  id(REVERSE): (90, 1)}
        chosen, detail, calls, _ = exercise(values, old_plans=(BASE, GAP, HYPER, FOURTH))
        self.assertIs(chosen, HYPER)
        self.assertEqual(calls, [BASE, GAP, HYPER, FOURTH])
        self.assertEqual(detail['oracle_requests'], 4)
        self.assertEqual(detail['skip_reason'], 'reverse_score_unavailable')

    def test_unscored_old_winner_is_scored_before_reverse(self):
        chosen, detail, calls, _ = exercise(old_plans=(), evidence='not_requested')
        self.assertIs(chosen, REVERSE)
        self.assertEqual(calls, [HYPER, REVERSE])
        self.assertEqual(detail['oracle_requests'], 2)

    def test_incumbent_score_failure_keeps_it(self):
        values = {id(HYPER): RuntimeError('unavailable')}
        chosen, detail, calls, _ = exercise(values, old_plans=(), evidence='not_requested')
        self.assertIs(chosen, HYPER)
        self.assertEqual(calls, [HYPER])
        self.assertEqual(detail['skip_reason'], 'incumbent_score_unavailable')

    def test_single_core_skips_reverse(self):
        chosen, detail, calls, reverse_build = exercise(cores=1)
        self.assertIs(chosen, HYPER)
        self.assertEqual(len(calls), 3)
        self.assertEqual(detail['skip_reason'], 'single_core')
        reverse_build.assert_not_called()

    def test_cli_uses_four_request_limit(self):
        with patch.object(route, 'guarded_main') as main:
            route.main(['--example'])
        main.assert_called_once_with(['--example'], constructor=route.build,
                                     oracle_request_limit=4)


if __name__ == '__main__':
    unittest.main()
