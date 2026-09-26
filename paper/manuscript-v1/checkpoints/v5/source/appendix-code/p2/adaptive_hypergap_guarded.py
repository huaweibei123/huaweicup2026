"""One bounded P2 route comparing complete baseline, gap, and hypergap plans.

The original-COPY byte drop gates retiming only; it never predicts official
Makespan or prunes the unrefined gap candidate. Scores are requested only for
distinct complete plans, in construction order, with a fixed three-call cap.
"""
from __future__ import annotations

from . import adaptive_budget, gap_candidate, gap_hyperrefine, gap_retime
from .direct import UnsupportedStructure
from .guarded_component import _score


def build(graph, cores, config, oracle):
    baseline, baseline_detail = adaptive_budget.build(graph, cores, config)
    detail = {
        'selected': 'baseline', 'selected_strategy': 'adaptive_budget',
        'reason': 'only_one_unique_plan', 'score_evidence': 'not_requested',
        'score_scope': 'complete final constructor plans; no downstream repair',
        'baseline_detail': baseline_detail, 'gap_detail': None,
        'hyperrefine_detail': None, 'retime_detail': None,
        'construction_errors': [], 'constructed_plans': 1,
        'unique_plans': 1, 'oracle_requests': 0, 'scores': {},
        'region_width': 16,
    }
    plans = [('baseline', baseline)]
    try:
        gap, gap_detail = gap_candidate.build(graph, cores, config)
    except UnsupportedStructure as error:
        detail['construction_errors'].append({'stage': 'gap_candidate', 'kind': 'unsupported_structure',
                                              'error': repr(error)})
        detail['reason'] = 'gap_structure_unsupported'
        return baseline, detail
    except Exception as error:
        detail['construction_errors'].append({'stage': 'gap_candidate', 'kind': 'unexpected',
                                              'error': repr(error)})
        detail.update(reason='gap_construction_error', score_evidence='unknown')
        return baseline, detail
    detail['gap_detail'] = gap_detail
    detail['constructed_plans'] += 1
    if gap != baseline:
        plans.append(('gap', gap))

    try:
        refined, refine_detail = gap_hyperrefine.refine(
            graph, gap, config, region_width=16)
    except UnsupportedStructure as error:
        detail['construction_errors'].append({'stage': 'hyperrefine', 'kind': 'unsupported_structure',
                                              'error': repr(error)})
    except Exception as error:
        detail['construction_errors'].append({'stage': 'hyperrefine', 'kind': 'unexpected',
                                              'error': repr(error)})
        detail.update(reason='hyperrefine_construction_error', score_evidence='unknown')
        return baseline, detail
    else:
        detail['hyperrefine_detail'] = refine_detail
        before = refine_detail.get('before_original_copy_bytes')
        after = refine_detail.get('after_original_copy_bytes')
        if type(before) is not int or type(after) is not int or before < 0 or after < 0:
            detail.update(reason='hyperrefine_invalid_byte_evidence', score_evidence='unknown')
            return baseline, detail
        if type(before) is int and type(after) is int and 0 <= after < before:
            try:
                hyper, retime_detail = gap_retime.retime(graph, refined, config)
            except UnsupportedStructure as error:
                detail['construction_errors'].append({'stage': 'retime', 'kind': 'unsupported_structure',
                                                      'error': repr(error)})
            except Exception as error:
                detail['construction_errors'].append({'stage': 'retime', 'kind': 'unexpected',
                                                      'error': repr(error)})
                detail.update(reason='retime_construction_error', score_evidence='unknown')
                return baseline, detail
            else:
                detail['retime_detail'] = retime_detail
                detail['constructed_plans'] += 1
                if all(hyper != prior for _, prior in plans):
                    plans.append(('hypergap', hyper))
        else:
            detail['hyper_skip_reason'] = 'no_strict_original_copy_byte_drop'
    detail['unique_plans'] = len(plans)
    if len(plans) == 1:
        detail['reason'] = 'only_one_unique_plan'
        return baseline, detail

    scored = []
    for label, plan in plans:
        detail['oracle_requests'] += 1
        try:
            value = _score(oracle, plan)
        except Exception as error:
            detail.update(reason='score_unavailable', score_evidence='unknown',
                          score_error={'plan': label, 'error': repr(error)})
            return baseline, detail
        detail['scores'][label] = list(value)
        scored.append((label, plan, value))
    detail['score_evidence'] = 'injected_oracle_complete_plan_scores'
    winner_label, winner_plan, winner_score = scored[0]
    for label, plan, value in scored[1:]:
        if value < winner_score:
            winner_label, winner_plan, winner_score = label, plan, value
    detail['selected'] = winner_label
    detail['selected_strategy'] = {
        'baseline': 'adaptive_budget', 'gap': 'join_gap_candidate',
        'hypergap': 'hypergap_retime',
    }[winner_label]
    detail['reason'] = ('strict_lexicographic_improvement' if winner_label != 'baseline'
                        else 'baseline_wins_or_ties')
    return winner_plan, detail


def main(argv=None):
    from .adaptive_guarded import main as guarded_main
    guarded_main(argv, constructor=build, oracle_request_limit=3)


if __name__ == '__main__':
    main()
