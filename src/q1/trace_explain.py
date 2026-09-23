"""Bounded, source-backed analysis of saved Q1 timing and one missing trace."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import time

from search import ROOT, OFFICIAL, dump, sha
from profile_refine import run_guarded

PRIOR = ROOT / 'results/a/q1-profile-refine-20260924'


def payload(case, archive, member):
    folder = PRIOR / ('case' + case)
    manifest = json.loads((folder / (archive + '.manifest.json')).read_text())
    path = folder / (archive + '.tar.xz')
    assert sha(path) == manifest['sha256']
    identity = next(item for item in manifest['members'] if item['path'] == member)
    with tarfile.open(path) as stream:
        data = stream.extractfile(member).read()
    assert hashlib.sha256(data).hexdigest() == identity['sha256']
    return data


def gates(result):
    tasks = {t['task_id']: dict(t, core_id=c['core_id'])
             for c in result['per_core_timeline'] for t in c['tasks']}
    previous = {t['task_id']: (c['tasks'][i-1]['task_id'] if i else None)
                for c in result['per_core_timeline'] for i, t in enumerate(c['tasks'])}
    preds = {task: [] for task in tasks}
    for edge in result['task_dependencies']:
        preds[edge['target']].append(edge['source'])
    rows = {}
    for task, item in tasks.items():
        terms = []
        if previous[task] is not None:
            p = previous[task]
            wait = result['task_same_core_wait_cycles']
            terms.append({'task': p, 'kind': 'core', 'wait': wait, 'release': tasks[p]['end'] + wait})
        for p in preds[task]:
            if tasks[p]['core_id'] != item['core_id']:
                wait = result['task_cross_core_wait_cycles']
                terms.append({'task': p, 'kind': 'cross', 'wait': wait, 'release': tasks[p]['end'] + wait})
        release = max([0] + [term['release'] for term in terms])
        rows[task] = dict(item, terms=terms, reconstructed_release=release,
                          residual=item['start']-release,
                          controlling=sorted([t for t in terms if t['release']==release], key=lambda t:(t['kind'],t['task'])))
    sink = min(t for t in tasks if tasks[t]['end'] == result['makespan'])
    chain = []
    cursor = sink
    while True:
        row = rows[cursor]
        term = row['controlling'][0] if row['controlling'] else None
        chain.append({'task': cursor, 'duration': row['duration'], 'incoming': term,
                      'start_residual': row['residual']})
        if term is None:
            break
        cursor = term['task']
    chain.reverse()
    return {'tasks': rows, 'start_mismatches': [t for t,r in rows.items() if r['residual'] != 0],
            'canonical_critical_chain': chain,
            'chain_busy': sum(r['duration'] for r in chain),
            'chain_wait': sum(r['incoming']['wait'] for r in chain if r['incoming']),
            'chain_residual': sum(r['start_residual'] for r in chain), 'makespan': result['makespan'],
            'scope': 'Post-hoc identity using observed task durations; not a counterfactual DDR model'}


def serial_difference(before, after, merged):
    a, b = gates(before), gates(after)
    assert not a['start_mismatches'] and not b['start_mismatches']
    active_a = [c for c in before['per_core_timeline'] if c['tasks']]
    active_b = [c for c in after['per_core_timeline'] if c['tasks']]
    assert len(active_a) == len(active_b) == 1
    old, new = a['tasks'], b['tasks']
    changed_other = []
    for task in sorted(set(old) & set(new) - set(merged)):
        if old[task]['duration'] != new[task]['duration']:
            changed_other.append({'task': task, 'before': old[task]['duration'], 'after': new[task]['duration']})
    return {'makespan_delta': after['makespan'] - before['makespan'],
            'busy_delta': sum(t['duration'] for t in new.values()) - sum(t['duration'] for t in old.values()),
            'wait_delta': b['chain_wait'] - a['chain_wait'],
            'old_merged_durations': {str(t): old[t]['duration'] for t in merged},
            'new_merged_duration': new[merged[0]]['duration'],
            'other_duration_changes': changed_other,
            'scope': 'Single-active-core accounting, not isolated attribution to spill bytes'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    protocol = {'fixed_parent_commit': '909f6f1f29fc7f2557395fae98f0f68a853f4c4b',
                'cases': ['051 saved seed/final', '044 saved seed/final and fixed bad merge'],
                'max_new_e0_calls': 1, 'new_input': '044 round0/candidate1 merge(8,10)',
                'wall_limit_new_e0_seconds': 30, 'rss_stop_bytes': 1536 << 20,
                'analysis_wall_scope': 'Read-only derived timing, no new search or broader candidate pool',
                'config_sha256': sha(OFFICIAL/'data/config.txt'), 'source_sha256': sha(Path(__file__)),
                'python': sys.version, 'planned_before_new_e0': True}
    dump(output/'protocol.json', protocol)
    (output/'trace_explain.py').write_bytes(Path(__file__).read_bytes())
    results, annotations = {}, {}
    for case in ['051','044']:
        for phase in ['e0_seed','e0_final']:
            name = case + '_' + phase
            results[name] = json.loads(payload(case, 'execution-evidence', phase+'/result.json'))
            annotations[name] = gates(results[name])
            assert not annotations[name]['start_mismatches']
            assert annotations[name]['chain_busy'] + annotations[name]['chain_wait'] == results[name]['makespan']
    bad = output/'044_bad_merge'; bad.mkdir()
    plan = bad/'plan.json'
    plan.write_bytes(payload('044','candidate-plans','round0/candidate1/plan.json'))
    expected = json.loads((PRIOR/'case044/summary.json').read_text())['records'][2]
    assert expected['choice']['tasks'] == [8,10] and sha(plan) == expected['plan_sha256']
    command = [sys.executable,'-B',str(OFFICIAL/'code/multicore_cut_evaluate_problem_1.py'),
               str(OFFICIAL/'data/case_044.json'),str(plan),'--config',str(OFFICIAL/'data/config.txt'),
               '-o',str(bad/'result.json'),'--trace-output',str(bad/'trace.json'),'--log-output',str(bad/'summary.log')]
    dump(bad/'request.json', {'command':command,'plan_sha256':sha(plan),'graph_sha256':sha(OFFICIAL/'data/case_044.json'),
                             'expected_previous_e1':expected['result']})
    status = run_guarded(command,bad,wall_seconds=30)
    dump(bad/'supervisor.json',status)
    if status['status'] != 'ok':
        raise RuntimeError('Bounded missing-trace replay failed; see supervisor receipt')
    results['044_bad'] = json.loads((bad/'result.json').read_text())
    assert results['044_bad']['makespan'] == expected['result']['makespan']
    assert results['044_bad']['data_movement_bytes'] == expected['result']['data_movement_bytes']
    annotations['044_bad'] = gates(results['044_bad'])
    assert not annotations['044_bad']['start_mismatches']
    before, after = annotations['051_e0_seed'], annotations['051_e0_final']
    old_chain, new_chain = before['canonical_critical_chain'], after['canonical_critical_chain']
    comparison = {'old_tasks':[r['task'] for r in old_chain], 'new_tasks':[r['task'] for r in new_chain],
                  'same_chain_after_550_to_8': [r['task'] for r in old_chain] == [8 if r['task']==550 else r['task'] for r in new_chain],
                  'old_busy':before['chain_busy'],'new_busy':after['chain_busy'],
                  'old_wait':before['chain_wait'],'new_wait':after['chain_wait']}
    comparison['selected_tasks'] = {phase:{str(t):data['tasks'][t] for t in tasks}
                                  for phase,data,tasks in [('before',before,[0,8,19,23]),('after',after,[0,8,19,550,23])]}
    comparison['local_step3'] = {'before':{str(t):results['051_e0_seed']['step3_by_task'][str(t)] for t in [8]},
                               'after':{str(t):results['051_e0_final']['step3_by_task'][str(t)] for t in [8,550]}}
    dump(output/'task_gate_annotations.json',annotations)
    summary = {'051':comparison,
               '044_bad':serial_difference(results['044_e0_seed'],results['044_bad'],[8,10]),
               '044_good':serial_difference(results['044_e0_seed'],results['044_e0_final'],[6,8]),
               'new_e0_calls':1,'missing_trace_replay_matches_prior_e1':True,
               'boundary':'Observed timing accounting; no claim that operation durations stay fixed after another intervention'}
    dump(output/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
