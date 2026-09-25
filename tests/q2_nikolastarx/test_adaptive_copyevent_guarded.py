"""Injected complete-plan selection; no official graph or evaluator call."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.q2_nikolastarx import adaptive_copyevent_guarded as route
from src.q2_nikolastarx import adaptive_guarded
from src.q2_nikolastarx.direct import UnsupportedStructure


def plan(i):
    return {'node_to_subgraph': {'1': i}, 'core_schedules': [[i]]}


BASE, GAP, HYPER, EVENT = (plan(i) for i in range(4))


def run(scores, *, base_plans=(BASE, GAP, HYPER), selected=HYPER,
        event=EVENT, base_unknown=False, retime_error=None):
    seen = []
    def oracle(p):
        seen.append(p)
        value = scores[id(p)]
        if isinstance(value, Exception):
            raise value
        if isinstance(value, dict):
            return value
        return {'status': 'ok', 'makespan': value[0], 'added_copy_bytes': value[1]}
    def base_build(_, __, ___, scorer):
        if base_unknown:
            try:
                scorer(base_plans[0])
            except Exception:
                pass
            return selected, {'selected': 'baseline', 'reason': 'score_unavailable',
                              'score_evidence': 'unknown'}
        for p in base_plans:
            scorer(p)
        return selected, {'selected': 'hypergap', 'reason': 'strict_lexicographic_improvement',
                          'score_evidence': ('injected_oracle_complete_plan_scores'
                                             if base_plans else 'not_requested')}
    with patch.object(route.adaptive_hypergap_guarded, 'build', side_effect=base_build):
        with patch.object(route.copy_event_retime, 'retime',
                          return_value=(event, {'static': True}) if retime_error is None else None,
                          side_effect=retime_error) as retime:
            result, detail = route.build({}, 2, {}, oracle)
    return result, detail, seen, retime


class CopyEventRouteTests(unittest.TestCase):
    def test_improvement_and_four_request_cap(self):
        scores = {id(BASE): (100, 100), id(GAP): (90, 90),
                  id(HYPER): (80, 80), id(EVENT): (79, 999)}
        result, detail, seen, retime = run(scores)
        self.assertIs(result, EVENT)
        self.assertEqual(seen, [BASE, GAP, HYPER, EVENT])
        self.assertEqual(detail['oracle_requests'], 4)
        self.assertEqual(detail['before_score'], [80, 80])
        self.assertEqual(detail['after_score'], [79, 999])
        self.assertEqual(detail['postprocess_reason'], 'strict_lexicographic_improvement')
        retime.assert_called_once_with({}, HYPER, {})

    def test_regression_and_tie_keep_seed(self):
        common = {id(BASE): (100, 100), id(GAP): (90, 90), id(HYPER): (80, 80)}
        for score in ((110, 0), (80, 80), (80, 81)):
            result, detail, seen, _ = run({**common, id(EVENT): score})
            self.assertIs(result, HYPER)
            self.assertEqual(len(seen), 4)
            self.assertEqual(detail['postprocess_reason'], 'seed_wins_or_ties')
        result, detail, _, _ = run({**common, id(EVENT): (80, 79)})
        self.assertIs(result, EVENT)
        self.assertEqual(detail['after_score'], [80, 79])

    def test_nochange_and_unsupported_add_no_request(self):
        scores = {id(BASE): (100, 100), id(GAP): (90, 90), id(HYPER): (80, 80)}
        result, detail, seen, _ = run(scores, event=plan(2))
        self.assertIs(result, HYPER)
        self.assertEqual(len(seen), 3)
        self.assertEqual(detail['postprocess_reason'], 'same_complete_plan')
        result, detail, seen, _ = run(scores, retime_error=UnsupportedStructure('not singleton'))
        self.assertIs(result, HYPER)
        self.assertEqual(len(seen), 3)
        self.assertEqual(detail['postprocess_reason'], 'retime_unsupported')

    def test_unscored_one_plan_gets_seed_score_first(self):
        scores = {id(BASE): (100, 5), id(EVENT): (99, 500)}
        result, detail, seen, _ = run(scores, base_plans=(), selected=BASE)
        self.assertIs(result, EVENT)
        self.assertEqual(seen, [BASE, EVENT])
        self.assertEqual(detail['oracle_requests'], 2)
        self.assertEqual(detail['before_score'], [100, 5])

    def test_unknown_stops_and_cache_prevents_duplicate_request(self):
        scores = {id(BASE): RuntimeError('uncertain'), id(HYPER): (80, 80)}
        result, detail, seen, retime = run(scores, base_plans=(BASE,),
                                            selected=BASE, base_unknown=True)
        self.assertIs(result, BASE)
        self.assertEqual(seen, [BASE])
        self.assertEqual(detail['score_evidence'], 'unknown')
        retime.assert_not_called()
        scores = {id(BASE): (100, 0), id(GAP): (90, 0), id(HYPER): (80, 0)}
        result, detail, seen, _ = run(scores, event=plan(1))
        self.assertIs(result, HYPER)
        self.assertEqual(seen, [BASE, GAP, HYPER])
        self.assertEqual(detail['after_score'], [90, 0])
        self.assertEqual(detail['oracle_cache_entries'], 3)

    def test_invalid_new_score_is_unknown_and_cli_cap_is_four(self):
        scores = {id(BASE): (100, 0), id(GAP): (90, 0), id(HYPER): (80, 0),
                  id(EVENT): {'status': 'ok', 'makespan': True, 'added_copy_bytes': 0}}
        result, detail, seen, _ = run(scores)
        self.assertIs(result, HYPER)
        self.assertEqual(len(seen), 4)
        self.assertEqual(detail['score_evidence'], 'unknown')
        self.assertEqual(set(result), {'node_to_subgraph', 'core_schedules'})
        with patch.object(adaptive_guarded, 'main') as guarded_main:
            route.main(['dummy.json'])
        guarded_main.assert_called_once_with(
            ['dummy.json'], constructor=route.build, oracle_request_limit=4)

    def test_adapter_explicit_four_and_existing_default_cap(self):
        def state():
            return {'calls': {'E0': 0, 'E1': 0, 'E2': 0,
                              'E2_api_attempted': 0, 'native_returns': 0,
                              'E0_fallback': 0}, 'request_in_flight': False,
                    'possible_E0_fallback_calls': 0}
        def native(_):
            return {'route': 'native', 'status': 'ok', 'problem': 2,
                    'makespan': 1, 'data_movement_bytes': {'added_copy_bytes': 0}}
        with tempfile.TemporaryDirectory() as folder:
            ledger = state()
            scorer = adaptive_guarded.score_adapter(
                native, ledger, Path(folder) / 'four.json', max_requests=4)
            for _ in range(4):
                self.assertEqual(scorer(BASE)['makespan'], 1)
            with self.assertRaisesRegex(RuntimeError, 'four-request|4-request'):
                scorer(BASE)
            self.assertEqual(ledger['calls']['E2_api_attempted'], 4)
            self.assertEqual(ledger['calls']['native_returns'], 4)
            self.assertFalse(ledger['request_in_flight'])
            default = state()
            scorer = adaptive_guarded.score_adapter(
                native, default, Path(folder) / 'two.json')
            scorer(BASE); scorer(BASE)
            with self.assertRaises(RuntimeError):
                scorer(BASE)
            self.assertEqual(default['calls']['E2_api_attempted'], 2)


if __name__ == '__main__':
    unittest.main()
