"""Synthetic graph/Task-order witnesses, no E0/E1/E2 or public-case solver."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

SOURCE_COMMIT = '4c8c58866cc8ffa5a3fa468adc727f8a0800bd0f'
p = argparse.ArgumentParser()
p.add_argument('--source-root', type=Path, required=True)
a = p.parse_args()
root = a.source_root.resolve()
paths = ['src/q1/heavy_suffix.py','src/q1/sink_peel.py','src/q1/bounded_tasks.py',
         'src/q1/tree_frontier.py','src/q1/component_pack.py','tests/q1/test_component_pack.py']
identity = {}
for path in paths:
    frozen = subprocess.check_output(['git','show',SOURCE_COMMIT+':'+path],cwd=root)
    actual = (root/path).read_bytes()
    assert actual == frozen, path
    identity[path] = hashlib.sha256(actual).hexdigest()
sys.path.insert(0,str(root))
from tests.q1.test_component_pack import graph
from src.q1.heavy_suffix import construct
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order

thresholds = []
for label,nodes in [('exact80',[(1,'V',8),(2,'V',36),(3,'V',36),(10,'V',20),(11,'M',1)]),
                    ('below80',[(1,'V',7),(2,'V',36),(3,'V',36),(10,'V',21),(11,'M',1)])]:
    plan,info = construct(graph(nodes,[(1,2),(1,3)]),3)
    assert (info['selected']=='heavy-suffix') == (label=='exact80')
    thresholds.append({'label':label,'selected':info['selected'],'heavy_pipe_work':info['heavy_pipe_work'],
                       'total_pipe_work':info['total_pipe_work']})
g = graph([(1,'V',10000),(2,'V',40000),(3,'V',40000),
           (10,'M',89000),(11,'M',1),(12,'M',1)],[(1,2),(1,3)])
current, info = construct(g,4)
core_of = {u:c for c,order in enumerate(current['core_schedules'])
           for u,t in current['node_to_subgraph'].items() if t in order}
assert core_of[1] == core_of[10] == 0
assert current['node_to_subgraph'][1] != current['node_to_subgraph'][10]
alternative = {'node_to_subgraph':{1:0,2:1,3:2,10:3,11:3,12:3},
               'core_schedules':[[0],[1],[2],[3]]}
validate_task_order(derive_multicore_plan(g,alternative))
report = {'kind':'synthetic-structural-review-not-official-performance',
          'source_commit':SOURCE_COMMIT,'source_file_sha256':identity,'python':platform.python_version(),
          'calls':{'synthetic_construct':3,'public_case_solver':0,'E0':0,'E1':0,'E2':0,'task_compilation':0},
          'threshold_checks':thresholds,'graph':g,'current_plan':current,'current_info':info,
          'alternative_plan_task_order_validated_only':alternative,
          'current_plan_necessary_lower_bound_cycles':10000+100+89000,
          'current_bound_reason':'Same core: root compute >=10000, then official same-core Task wait >=100, then independent M op >=89000. COPY may increase it.',
          'alternative_compute_only_completion_cycles':89002,
          'alternative_official_makespan':None,
          'alternative_official_upper_bound':None,
          'caveat':'89002 belongs to a simplified compute-resource schedule. Alternative has cross-core 1000 waits and boundary COPY writes/reads under P1; no Task compilation or event replay was performed, so this is not a proven official U or measured result.'}
output = Path(__file__).with_name('witness.json')
with output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({'threshold_checks':'passed','alternative_task_order':'passed','public_case_solver':0,'E0':0,'E1':0,'E2':0}))
