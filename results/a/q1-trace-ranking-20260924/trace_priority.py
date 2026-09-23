"""Frozen-trace entry-relief ranking; offline checks use already-scored pools.

This is a heuristic, not a counterfactual evaluator. A changed partition can
change producer completion times and DDR contention. The selected cases also
informed the rule, so this is development-set inspection, not fresh validation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trace_explain import PRIOR, payload, gates
from profile_candidates import split_plan
from search import OFFICIAL, dump, sha, plan_key
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


def critical_tasks(annotation):
    pending = [t for t, row in annotation['tasks'].items() if row['end'] == annotation['makespan']]
    seen = set()
    while pending:
        task = pending.pop()
        if task not in seen:
            seen.add(task)
            pending.extend(t['task'] for t in annotation['tasks'][task]['controlling'])
    return seen


def prefix_feature(graph, parent, choice, profile, result, annotation):
    task, cut = choice['task'], choice['cut']
    prefix = profile['compute_order'][:cut]
    candidate = split_plan(parent, task, set(profile['compute_order'][cut:]))
    view = derive_multicore_plan(graph, candidate)
    validate_task_order(view)
    timeline = annotation['tasks']
    core = view['core_by_subgraph'][task]
    order = parent['core_schedules'][core]
    i = order.index(task)
    previous = order[i-1] if i else None
    terms = ([timeline[previous]['end'] + result['task_same_core_wait_cycles']] if previous is not None else [0])
    remote = []
    for pred in sorted(view['subgraph_preds'][task]):
        if view['core_by_subgraph'][pred] != core:
            value = timeline[pred]['end'] + result['task_cross_core_wait_cycles']
            terms.append(value)
            remote.append({'task': pred, 'release': value})
    frozen_release = max(terms)
    relief = max(0, timeline[task]['start'] - frozen_release)
    op_by_id = {op['id']: op for op in graph['ops']}
    work = max(sum(max(1, op_by_id[op]['cycles']) for op in prefix if op_by_id[op]['pipe'] == pipe)
               for pipe in ['PIPE_M', 'PIPE_V'])
    critical = task in critical_tasks(annotation)
    return {'task': task, 'cut': cut, 'on_observed_critical_dag': critical,
            'old_start': timeline[task]['start'], 'frozen_prefix_release': frozen_release,
            'entry_relief': relief, 'prefix_compute_work': work,
            'overlap_priority': min(relief, work), 'remote_terms': remote,
            'score': [int(critical and relief > 0), min(relief, work), relief],
            'scope': 'Baseline times frozen; score only, no predicted makespan or guaranteed gain'}


def reorder_pool(graph, parent, pool, result):
    annotation = gates(result)
    if annotation['start_mismatches']:
        raise ValueError('Reference timing does not satisfy reconstructed Task gates')
    profiles = {p['task_id']: p for p in pool['profiles']}
    features = {i: prefix_feature(graph, parent, item['choice'], profiles[item['choice']['task']], result, annotation)
                for i, item in enumerate(pool['candidates']) if item['choice']['kind'] == 'split'}
    slots = list(features)
    ranked = sorted(slots, key=lambda i: tuple(-v for v in features[i]['score']) + (i,))
    order = list(range(len(pool['candidates'])))
    for slot, candidate in zip(slots, ranked):
        order[slot] = candidate
    return order, features


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    protocol = {'cases': ['044','051','002'], 'rounds': [0,1],
                'control': 'Same stored candidate pool; only split slots reorder; merges unchanged',
                'metric': 'Incumbent makespan after 1/2/3/4 calls from stored exact values; no wall-time claim',
                'new_e0_calls':0,'new_e1_calls':0,'development_data_informed_rule':True,
                'scope':'Retrospective order inspection; not independent or prospective quality evidence',
                'source_sha256':sha(Path(__file__))}
    dump(args.output/'protocol.json',protocol)
    (args.output/'trace_priority.py').write_bytes(Path(__file__).read_bytes())
    all_rows=[]
    for case in protocol['cases']:
        folder = PRIOR/('case'+case)
        summary=json.loads((folder/'summary.json').read_text())
        graph=json.loads((OFFICIAL/f'data/case_{case}.json').read_text())
        for round_index in protocol['rounds']:
            parent_path=folder/f'round{round_index}/parent.json'
            parent=json.loads(parent_path.read_text())
            if sha(parent_path)==sha(folder/'seed.json'):
                phase='e0_seed'
            elif plan_key(parent)==plan_key(json.loads((folder/'confirmed_plan.json').read_text())):
                phase='e0_final'
            else:
                raise ValueError('No matching measured timeline; do not reuse stale baseline')
            result=json.loads(payload(case,'execution-evidence',phase+'/result.json'))
            pool=json.loads(payload(case,'execution-evidence',f'round{round_index}/generated.json'))
            order, features=reorder_pool(graph,parent,pool,result)
            # Save pre-existing features and declared order before joining the
            # saved candidate outcomes. This is still explicitly retrospective.
            dump(args.output/f'case{case}-round{round_index}-ranking.json',
                 {'parent_sha256':sha(parent_path),'reference':phase,'order':order,'features':features})
            rows={r['candidate']:r for r in summary['records'][1:] if r['round']==round_index}
            assert set(rows)==set(order) and all(r['result']['status']=='ok' for r in rows.values())
            curves={}
            for label, indices in [('original',list(range(len(order)))),('entry_relief',order)]:
                best=result['makespan'];curve=[]
                for i in indices:
                    best=min(best,rows[i]['result']['makespan'])
                    curve.append(best)
                curves[label]=curve
            all_rows.append({'case':case,'round':round_index,'parent_makespan':result['makespan'],
                             'original_order':list(range(len(order))),'entry_relief_order':order,'prefix_best':curves})
    dump(args.output/'summary.json',{'comparisons':all_rows,'new_evaluator_calls':0,
                                   'scope':'Same-pool retrospective ordering; cannot prove prospective quality or speed'})
    print(json.dumps(all_rows),flush=True)


if __name__ == '__main__':
    main()
