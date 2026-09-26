"""Independent, bounded checks for FORM PR17 at dab91d6.

The crafted validator views are unit-level inputs, not claims of public-entry
reachability. All timing comparisons keep graph, configuration and partition
fixed; only core schedules differ. Frozen evaluator modules are read-only.
"""
from pathlib import Path
import copy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
sys.path.insert(0, str(ROOT / 'src/adversarial'))
from evaluation_validation import validate_task_order
import multicore_cut_evaluate_problem_1 as official
from verify_time_r1 import build_two_cores, build_dependent_pair, BANDWIDTH, CAPACITY

OUT = ROOT / 'results/a/review/20260923-captain-dab91d6/captain-probes.json'

def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def main():
    unit_records = []
    for label, orders, dependencies, ids, expected in [
        ('all_singletons', {0:[0],1:[1]}, [[0,1]], [0,1], 'accepted'),
        ('reversed_order_plus_empty_core', {0:[1,0],1:[]}, [[0,1]], [0,1], 'rejected'),
        ('reversed_order_plus_singleton', {0:[1,0],1:[2]}, [[0,1]], [0,1,2], 'rejected'),
        ('forward_order_plus_empty_core', {0:[0,1],1:[]}, [[0,1]], [0,1], 'accepted'),
    ]:
        view = {'core_orders':orders,'dependency_pairs':dependencies,'subgraph_ids':ids}
        error = None
        try:
            validate_task_order(view)
            outcome = 'accepted'
        except Exception as e:
            outcome, error = 'rejected', type(e).__name__+': '+str(e)
        unit_records.append({'case':label,'domain':'crafted validator view (unit-level)',
                             'view':view,'documented_early_return_any_le1':any(len(o)<=1 for o in orders.values()),
                             'source_early_return_all_le1':all(len(o)<=1 for o in orders.values()),
                             'outcome':outcome,'error':error})
        assert outcome == expected, (label,outcome,error)

    graph, base = build_two_cores(True)
    dep_graph, dep_plan = build_dependent_pair(True)
    controls = [
        ('two_independent_chains',graph,base,[('two_tasks_one_active_core',[[0,1],[]]),('two_tasks_two_active_cores',[[0],[1]])]),
        ('dependent_pair',dep_graph,dep_plan,[('one_core',[[0,1]]),('same_assignment_extra_idle_core',[[0,1],[]]),('different_assignment_two_active_cores',[[0],[1]])]),
    ]
    timing_records = []
    for label,g,p,variants in controls:
        for variant,schedule in variants:
            plan=copy.deepcopy(p)
            plan['core_schedules']=schedule
            result=official.evaluate_scene_a(g,plan,BANDWIDTH,CAPACITY,1000,100)
            timing_records.append({'family':label,'variant':variant,'graph':g,'graph_sha256':digest(g),
                                   'plan':plan,'partition_sha256':digest(plan['node_to_subgraph']),
                                   'makespan':result['makespan'],'num_cores':result['num_cores'],
                                   'ddr_contention_log':result.get('ddr_contention_log')})
    dep=[r for r in timing_records if r['family']=='dependent_pair']
    assert dep[0]['graph_sha256']==dep[1]['graph_sha256']==dep[2]['graph_sha256']
    assert dep[0]['makespan']==dep[1]['makespan']
    payload={'reviewed_commit':'dab91d612bd26183e12d30848b13d5fb14e071c7','seed':None,
             'config':{'bandwidth':BANDWIDTH,'capacity':CAPACITY,'cross_core_wait':1000,'same_core_wait':100},
             'unit_records':unit_records,'timing_records':timing_records,
             'limitations':['No E1/E2 candidate was available. These checks do not validate a fast evaluator.',
                            'Unit validator mismatch is a FORM text quantifier error; public entry may reject earlier.',
                            'Timing controls concern chosen plans, not the optimal achievable makespan as core budget grows.']}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'unit':[{k:r[k] for k in ['case','outcome','documented_early_return_any_le1','source_early_return_all_le1']} for r in unit_records],
                      'timing':[{k:r[k] for k in ['family','variant','makespan','num_cores']} for r in timing_records]},ensure_ascii=False))

if __name__=='__main__':
    main()
