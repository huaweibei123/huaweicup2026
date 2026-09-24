"""One static construction per062 k2/k4/k5, no official score or task compile.

PYTHONPATH=. .venv/bin/python -B results/a/q2-nikolastarx/tree-packets-first-static-20260925/check.py
"""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import time
from unittest.mock import patch

from src.q2_nikolastarx import tree_packets_first
from src.q2_nikolastarx.direct import derive_multicore_plan
from evaluation_validation import check_acyclic, read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config

ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
SOURCE=['src/q2_nikolastarx/tree_packets_first.py','src/q2_nikolastarx/tree_frontier.py',
        'src/q2_nikolastarx/dag_direct.py','src/q2_nikolastarx/direct.py',
        'src/q2_nikolastarx/adaptive_direct.py','src/q2_nikolastarx/component_envelope.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,value):
 with (OUT/name).open('x') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def own(plan):
 sgcore={sg:c for c,seq in enumerate(plan['core_schedules']) for sg in seq}
 return {u:sgcore[sg] for u,sg in plan['node_to_subgraph'].items()}
if (OUT/'report.json').exists():raise FileExistsError('preserve existing evidence')
source={p:sha(ROOT/p) for p in SOURCE}
assert source['src/q2_nikolastarx/tree_frontier.py']=='0ea6976bc0d29cab898a40d040077cf6bfc07c7584d5141769a616a62f5a8ed2'
path=ROOT/'data/raw/a/official/data/case_062.json';config_path=ROOT/'data/raw/a/official/data/config.txt'
graph=json.loads(path.read_bytes());config={**read_evaluation_config(config_path),**read_scene_b_config(config_path)}
manifest=json.loads((ROOT/'docs/a/source-manifest.json').read_bytes())
for f in manifest['files']:
 if f['path'] in ['data/case_062.json','data/config.txt']:
  assert sha(ROOT/'data/raw/a/official'/f['path'])==f['sha256']
report={'kind':'one intervention static only; no performance score','started_at':datetime.now(timezone.utc).isoformat(),
        'source_sha256':source,'runner_sha256':sha(Path(__file__)),'input_sha256':sha(path),'config_sha256':sha(config_path),
        'workers':1,'seed':None,'python':platform.python_version(),'platform':platform.platform(),
        'candidate':'tree_packets_first','fixed_change':'same pieces/ownership/within-packet word; defer skeleton only',
        'actual_calls':{'structural_candidate_build':3,'E0':0,'E1':0,'E2':0},
        'timing_scope':'function construction only, excludes launch/read/write; not solver wall',
        'not_proven':['official validity','zero spill','makespan improvement','optimality'],'rows':[]}
with ExitStack() as guard:
 for entry in ['subprocess.Popen','multicore_cut_evaluate_problem_2.evaluate_scene_b','multicore_cut_evaluate_problem_2._build_scene_b_tasks']:
  guard.enter_context(patch(entry,side_effect=AssertionError('No scoring or compilation')))
 for k in [2,4,5]:
  prior=ROOT/f'results/a/q2-nikolastarx/tree-pilot-20260924/run/062-k{k}'
  old=json.loads((prior/'plan.json').read_bytes());old_detail=json.loads((prior/'online/solver.json').read_bytes())['attempts'][0]['detail']
  diagnosis=json.loads((ROOT/f'results/a/q2-nikolastarx/tree-trace-diagnosis-20260925/062-k{k}-diagnosis.json').read_bytes())
  start=time.perf_counter();plan,detail=tree_packets_first.build(graph,k,config);dt=time.perf_counter()-start
  assert own(plan)==own(old) and plan['node_to_subgraph']==old['node_to_subgraph']
  for key in ['packets','compute_load_by_core','cut_edges','tensor_copy_bytes_without_spill']:
   assert detail[key]==old_detail[key],key
  assert detail['fixed_compute_fifo_bound_before']==diagnosis['fixed_compute_fifo_bound']
  view=derive_multicore_plan(graph,plan)
  edges=[(a,b,'original') for a,b in view['dependency_pairs']]
  for seq in plan['core_schedules']:edges.extend((a,b,'core order') for a,b in zip(seq,seq[1:]))
  check_acyclic(view['subgraph_ids'],edges,'original plus full core order')
  dump(f'062-k{k}-plan.json',plan);dump(f'062-k{k}-detail.json',detail)
  row={'cores':k,'derive':'passed','original_plus_core_order':'acyclic','index_constructions':detail['index_constructions'],
       'old_plan_sha256':sha(prior/'plan.json'),'plan_sha256':sha(OUT/f'062-k{k}-plan.json'),
       'detail_sha256':sha(OUT/f'062-k{k}-detail.json'),'same_ownership_pieces_cut_bytes':True,
       'old_compute_fifo_bound':detail['fixed_compute_fifo_bound_before'],
       'new_compute_fifo_bound':detail['fixed_compute_fifo_bound_after'],
       'changed_core_orders':detail['changed_core_orders'],
       'raw_peaks_by_core':[p['raw_priority_peak_bytes'] for p in detail['per_core']],
       'all_raw_peaks_fit':all(p['raw_peaks_fit_capacity'] for p in detail['per_core']),
       'function_construction_seconds':dt}
  report['rows'].append(row);print(json.dumps(row),flush=True)
assert source=={p:sha(ROOT/p) for p in SOURCE}
report.update(finished_at=datetime.now(timezone.utc).isoformat(),source_unchanged=True)
dump('report.json',report)
