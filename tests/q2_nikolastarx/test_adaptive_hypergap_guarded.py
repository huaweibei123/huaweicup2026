"""Injected complete-plan tests; no official graph, solver, or evaluator run."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.q2_nikolastarx import adaptive_guarded, adaptive_hypergap_guarded as route
from src.q2_nikolastarx.direct import UnsupportedStructure

BASE = {'node_to_subgraph': {'1': 0}, 'core_schedules': [[0]]}
GAP = {'node_to_subgraph': {'1': 1}, 'core_schedules': [[1]]}
HYPER = {'node_to_subgraph': {'1': 2}, 'core_schedules': [[2]]}


def exercise(scores=None, *, gap=GAP, hyper=HYPER, byte_pair=(100, 90),
             gap_error=None, refine_error=None, retime_error=None):
    scores = scores or {id(BASE): (100, 100), id(GAP): (95, 100), id(HYPER): (90, 120)}
    seen = []
    def oracle(plan):
        seen.append(plan)
        value = scores[id(plan)]
        if isinstance(value, Exception):
            raise value
        if isinstance(value, dict):
            return value
        return {'status': 'ok', 'makespan': value[0], 'added_copy_bytes': value[1]}
    with patch.object(route.adaptive_budget, 'build', return_value=(BASE, {'full': 'baseline'})):
        with patch.object(route.gap_candidate, 'build',
                          return_value=(gap, {'full': 'gap'}) if gap_error is None else None,
                          side_effect=gap_error) as gap_build:
            with patch.object(route.gap_hyperrefine, 'refine',
                              return_value=(gap, {'before_original_copy_bytes': byte_pair[0],
                                                   'after_original_copy_bytes': byte_pair[1]})
                              if refine_error is None else None,
                              side_effect=refine_error) as refine:
                with patch.object(route.gap_retime, 'retime',
                                  return_value=(hyper, {'full': 'hyper'})
                                  if retime_error is None else None,
                                  side_effect=retime_error) as retime:
                    selected, detail = route.build({}, 2, {}, oracle)
    return selected, detail, seen, (gap_build, refine, retime)


class HypergapRouteTests(unittest.TestCase):
    def test_three_complete_plans_and_strict_lexicographic_choice(self):
        selected, detail, seen, mocks = exercise()
        self.assertIs(selected, HYPER)
        self.assertEqual(seen, [BASE, GAP, HYPER])
        self.assertEqual(detail['oracle_requests'], 3)
        self.assertEqual(detail['constructed_plans'], 3)
        self.assertEqual(detail['selected'], 'hypergap')
        self.assertIn('complete final', detail['score_scope'])
        mocks[1].assert_called_once_with({}, GAP, {}, region_width=16)
        mocks[2].assert_called_once()

    def test_equal_makespan_ddr_gain_and_ties_keep_earliest(self):
        values = {id(BASE): (100, 50), id(GAP): (100, 49), id(HYPER): (100, 49)}
        selected, detail, seen, _ = exercise(values)
        self.assertIs(selected, GAP)
        self.assertEqual(detail['selected'], 'gap')
        self.assertEqual(len(seen), 3)
        tied = {id(BASE): (100, 50), id(GAP): (100, 50), id(HYPER): (100, 50)}
        selected, detail, _, _ = exercise(tied)
        self.assertIs(selected, BASE)
        self.assertEqual(detail['reason'], 'baseline_wins_or_ties')

    def test_no_byte_drop_still_scores_unpruned_gap(self):
        selected, detail, seen, mocks = exercise(byte_pair=(100, 100))
        self.assertIs(selected, GAP)
        self.assertEqual(seen, [BASE, GAP])
        self.assertEqual(detail['oracle_requests'], 2)
        self.assertEqual(detail['hyper_skip_reason'], 'no_strict_original_copy_byte_drop')
        mocks[2].assert_not_called()

    def test_deduplicates_complete_plans(self):
        selected, detail, seen, _ = exercise(gap=BASE, hyper=HYPER)
        self.assertIs(selected, HYPER)
        self.assertEqual(seen, [BASE, HYPER])
        self.assertEqual(detail['unique_plans'], 2)
        selected, detail, seen, _ = exercise(gap=BASE, hyper=BASE)
        self.assertIs(selected, BASE)
        self.assertEqual(seen, [])
        self.assertEqual(detail['oracle_requests'], 0)

    def test_structural_failures_keep_available_route(self):
        selected, detail, seen, mocks = exercise(gap_error=UnsupportedStructure('gap guard'))
        self.assertIs(selected, BASE)
        self.assertEqual(seen, [])
        mocks[1].assert_not_called()
        selected, detail, seen, mocks = exercise(refine_error=UnsupportedStructure('refine guard'))
        self.assertIs(selected, GAP)
        self.assertEqual(seen, [BASE, GAP])
        self.assertEqual(detail['construction_errors'][0]['stage'], 'hyperrefine')
        selected, detail, seen, _ = exercise(retime_error=UnsupportedStructure('retime guard'))
        self.assertIs(selected, GAP)
        self.assertEqual(seen, [BASE, GAP])
        self.assertEqual(detail['construction_errors'][0]['stage'], 'retime')

    def test_unexpected_construction_error_is_unknown_without_scoring(self):
        for kwargs in ({'gap_error': RuntimeError('gap')},
                       {'refine_error': RuntimeError('refine')},
                       {'retime_error': RuntimeError('retime')}):
            selected, detail, seen, _ = exercise(**kwargs)
            self.assertIs(selected, BASE)
            self.assertEqual(seen, [])
            self.assertEqual(detail['score_evidence'], 'unknown')
            self.assertEqual(detail['construction_errors'][0]['kind'], 'unexpected')

    def test_score_failure_fails_closed_and_stops_later_requests(self):
        for bad_label, expected_count in [('baseline', 1), ('gap', 2), ('hyper', 3)]:
            values = {id(BASE): (100, 100), id(GAP): (90, 100), id(HYPER): (80, 100)}
            target = {'baseline': BASE, 'gap': GAP, 'hyper': HYPER}[bad_label]
            values[id(target)] = {'status': 'ok', 'makespan': True,
                                  'added_copy_bytes': 0}
            selected, detail, seen, _ = exercise(values)
            self.assertIs(selected, BASE)
            self.assertEqual(len(seen), expected_count)
            self.assertEqual(detail['score_evidence'], 'unknown')
            self.assertEqual(detail['score_error']['plan'],
                             'hypergap' if bad_label == 'hyper' else bad_label)

    def test_fixed_adapter_caps_and_uncertain_request(self):
        def state():
            return {'calls': {'E0': 0, 'E1': 0, 'E2': 0, 'E2_api_attempted': 0,
                              'native_returns': 0, 'E0_fallback': 0},
                    'request_in_flight': False, 'possible_E0_fallback_calls': 0}
        def native(_):
            return {'route': 'native', 'status': 'ok', 'problem': 2, 'makespan': 1,
                    'data_movement_bytes': {'added_copy_bytes': 0}}
        with tempfile.TemporaryDirectory() as folder:
            ledger = state()
            scorer = adaptive_guarded.score_adapter(native, ledger,
                Path(folder)/'ledger.json', max_requests=3)
            for _ in range(3): scorer(BASE)
            with self.assertRaises(RuntimeError): scorer(BASE)
            self.assertEqual(ledger['calls']['E2_api_attempted'], 3)
            ledger = state()
            scorer = adaptive_guarded.score_adapter(native, ledger,
                Path(folder)/'ledger2.json')
            scorer(BASE);scorer(BASE)
            with self.assertRaises(RuntimeError): scorer(BASE)
            self.assertEqual(ledger['calls']['E2_api_attempted'], 2)
            ledger = state()
            scorer = adaptive_guarded.score_adapter(
                lambda _: (_ for _ in ()).throw(RuntimeError('uncertain')),
                ledger, Path(folder)/'ledger3.json', max_requests=3)
            with self.assertRaises(RuntimeError): scorer(BASE)
            with self.assertRaises(RuntimeError): scorer(BASE)
            self.assertEqual(ledger['calls']['E2_api_attempted'], 1)

    def test_cli_has_fixed_three_request_policy(self):
        with patch.object(adaptive_guarded, 'main') as guarded_main:
            route.main(['dummy.json'])
        guarded_main.assert_called_once_with(
            ['dummy.json'], constructor=route.build, oracle_request_limit=3)


if __name__ == '__main__':
    unittest.main()
