"""Bounded P2 comparison of the frozen forward route and one reverse plan.

The forward route remains the incumbent. Only injected, complete-plan oracle
scores can replace it; construction priorities are never score evidence.
"""
from __future__ import annotations

from . import adaptive_hypergap_guarded, reverse_gap_candidate
from .adaptive_guarded import main as guarded_main
from .guarded_component import _score


_LIMIT = 4


def build(graph, cores, config, oracle):
    scored = []  # (complete plan, validated score); equality deduplicates plans
    requests = 0
    cache_hits = 0

    def recorded_oracle(plan):
        nonlocal requests, cache_hits
        for prior, score, response in scored:
            if plan == prior:
                cache_hits += 1
                return response
        if requests >= _LIMIT:
            raise RuntimeError('four distinct complete-plan oracle starts exhausted')
        requests += 1
        response = oracle(plan)
        score = _score(lambda _: response, plan)
        scored.append((plan, score, response))
        return response

    incumbent, old_detail = adaptive_hypergap_guarded.build(
        graph, cores, config, recorded_oracle)
    detail = {
        'selected': 'incumbent',
        'selected_strategy': old_detail.get('selected_strategy'),
        'reason': 'incumbent_retained',
        'score_evidence': old_detail.get('score_evidence', 'unknown'),
        'score_scope': 'complete final constructor plans; no downstream repair',
        'incumbent_detail': old_detail,
        'reverse_detail': None,
        'scores': {},
        'oracle_requests': requests,
        'oracle_request_limit': _LIMIT,
        'cache_hits': cache_hits,
        'constructed_plans': old_detail.get('constructed_plans', 1),
        'unique_scored_plans': len(scored),
        'skip_reason': None,
    }

    def finish(plan):
        detail['oracle_requests'] = requests
        detail['cache_hits'] = cache_hits
        detail['unique_scored_plans'] = len(scored)
        return plan, detail

    if cores < 2:
        detail['skip_reason'] = 'single_core'
        return finish(incumbent)
    if old_detail.get('score_evidence') == 'unknown':
        detail['skip_reason'] = 'incumbent_score_evidence_unknown'
        return finish(incumbent)

    try:
        reverse, reverse_detail = reverse_gap_candidate.build(graph, cores, config)
    except Exception as error:
        detail['skip_reason'] = 'reverse_construction_unavailable'
        detail['reverse_error'] = repr(error)
        return finish(incumbent)
    detail['reverse_detail'] = reverse_detail
    detail['constructed_plans'] += 1
    if reverse == incumbent:
        detail['skip_reason'] = 'reverse_duplicates_incumbent'
        return finish(incumbent)

    incumbent_score = next((score for plan, score, _ in scored if plan == incumbent), None)
    if incumbent_score is not None:
        cache_hits += 1
    else:
        try:
            incumbent_score = _score(recorded_oracle, incumbent)
        except Exception as error:
            detail['skip_reason'] = 'incumbent_score_unavailable'
            detail['score_error'] = repr(error)
            return finish(incumbent)
    detail['scores']['incumbent'] = list(incumbent_score)
    try:
        reverse_score = _score(recorded_oracle, reverse)
    except Exception as error:
        detail['skip_reason'] = 'reverse_score_unavailable'
        detail['score_error'] = repr(error)
        return finish(incumbent)
    detail['scores']['reverse'] = list(reverse_score)
    detail['score_evidence'] = 'injected_oracle_complete_plan_scores'
    if reverse_score < incumbent_score:
        detail.update(selected='reverse', selected_strategy='reverse_join_gap_candidate',
                      reason='strict_lexicographic_improvement')
        return finish(reverse)
    detail['reason'] = 'incumbent_wins_or_ties'
    return finish(incumbent)


def main(argv=None):
    guarded_main(argv, constructor=build, oracle_request_limit=_LIMIT)


if __name__ == '__main__':
    main()
