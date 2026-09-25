"""Bounded P2 selector with one exact-scored fixed-owner copy-event retime.

The retimer's static witness never decides the winner; only complete-plan
oracle scores do. Unknown scoring stops further requests for outer fail-closed.
"""
from __future__ import annotations

import json

from . import adaptive_hypergap_guarded, copy_event_retime
from .direct import UnsupportedStructure
from .guarded_component import _score


def _key(plan):
    if not isinstance(plan, dict) or set(plan) != {'node_to_subgraph', 'core_schedules'}:
        raise ValueError('complete plan must contain exactly the two P2 keys')
    return json.dumps(plan, sort_keys=True, separators=(',', ':'), allow_nan=False)


def build(graph, cores, config, oracle):
    cache = {}
    requests = 0
    uncertain = False

    def counted(plan):
        nonlocal requests, uncertain
        key = _key(plan)
        if key in cache:
            return cache[key]
        if uncertain or requests >= 4:
            raise RuntimeError('oracle unavailable or four-request cap reached')
        requests += 1  # Attempted request, even when the oracle throws.
        try:
            record = oracle(plan)
        except Exception:
            uncertain = True
            raise
        cache[key] = record
        return record

    seed, base_detail = adaptive_hypergap_guarded.build(graph, cores, config, counted)
    detail = {
        'base_detail': base_detail, 'base_selected': base_detail.get('selected'),
        'base_reason': base_detail.get('reason'), 'retime_detail': None,
        'selected': 'base', 'base_oracle_requests': requests,
        'postprocess_oracle_requests': 0,
        'postprocess_reason': None, 'postprocess_error': None,
        'score_evidence': base_detail.get('score_evidence'),
        'score_scope': 'complete final P2 plans only; no downstream repair',
        'before_score': None, 'after_score': None,
        'oracle_requests': requests, 'oracle_cache_entries': len(cache),
    }

    def finish(reason, *, unknown=False):
        detail['postprocess_reason'] = reason
        detail['oracle_requests'] = requests
        detail['postprocess_oracle_requests'] = requests - detail['base_oracle_requests']
        detail['oracle_cache_entries'] = len(cache)
        if unknown:
            detail['score_evidence'] = 'unknown'
        return seed, detail

    if uncertain or detail['score_evidence'] == 'unknown':
        return finish('base_score_or_construction_unknown', unknown=True)
    try:
        seed_key = _key(seed)
        candidate, retime_detail = copy_event_retime.retime(graph, seed, config)
        detail['retime_detail'] = retime_detail
        candidate_key = _key(candidate)
    except UnsupportedStructure as error:
        detail['postprocess_error'] = {'kind': 'unsupported_structure', 'error': repr(error)}
        return finish('retime_unsupported')
    except Exception as error:
        detail['postprocess_error'] = {'kind': 'unexpected', 'error': repr(error)}
        return finish('retime_error', unknown=True)
    if candidate_key == seed_key:
        return finish('same_complete_plan')

    try:
        before = _score(counted, seed)
    except Exception as error:
        detail['postprocess_error'] = {'stage': 'seed_score', 'error': repr(error)}
        return finish('seed_score_unavailable', unknown=True)
    detail['before_score'] = list(before)
    try:
        after = _score(counted, candidate)
    except Exception as error:
        detail['postprocess_error'] = {'stage': 'retimed_score', 'error': repr(error)}
        return finish('retimed_score_unavailable', unknown=True)
    detail['after_score'] = list(after)
    detail['oracle_requests'] = requests
    detail['postprocess_oracle_requests'] = requests - detail['base_oracle_requests']
    detail['oracle_cache_entries'] = len(cache)
    detail['score_evidence'] = 'injected_oracle_complete_plan_scores'
    if after < before:
        detail['selected'] = 'copy_event_retime'
        detail['postprocess_reason'] = 'strict_lexicographic_improvement'
        return candidate, detail
    return finish('seed_wins_or_ties')


def main(argv=None):
    from .adaptive_guarded import main as guarded_main
    guarded_main(argv, constructor=build, oracle_request_limit=4)


if __name__ == '__main__':
    main()
