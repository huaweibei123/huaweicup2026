"""Exactly one static candidate062 x k2/4/5; read existing parent traces only.

PYTHONPATH=. .venv/bin/python -B results/a/q2-nikolastarx/tree-paired-leaves-static-20260925/check.py --prior-run /path/to/tree-packets-first-pilot-20260925/run
"""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
import time
from unittest.mock import patch

from src.q2_nikolastarx import tree_paired_leaves
from src.q2_nikolastarx.direct import derive_multicore_plan
from evaluation_validation import check_acyclic, read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config

ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--prior-run',type=Path,required=True);args=parser.parse_args()
SOURCE=['src/q2_nikolastarx/tree_paired_leaves.py','src/q2_nikolastarx/tree_packets_first.py',
        'src/q2_nikolastarx/tree_frontier.py','src/q2_nikolastarx/dag_direct.py','src/q2_nikolastarx/direct.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def dump(name,value):
 with (OUT/name).open('x') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def own(plan):
 sgcore={sg:c for c,seq in enumerate(plan['core_schedules']) for sg in seq}
 return {u:sgcore[sg] for u,sg in plan['node_to_subgraph'].items()}
if (OUT/'report.json').exists():raise FileExistsError('preserve existing evidence')
source={p:sha(ROOT/p) for p in SOURCE}
assert source['src/q2_nikolastarx/tree_frontier.py']=='0ea6976bc0d29cab898a40d040077cf6bfc07c7584d5141769a616a62f5a8ed2'
assert source['src/q2_nikolastarx/tree_packets_first.py']=='8cd41b9b27ef160f3ee75f70b4d5c38a115bd757421fddd8729e2d9a60e524f4'
path=ROOT/'data/raw/a/official/data/case_062.json';config_path=ROOT/'data/raw/a/official/data/config.txt'
graph=read(path);config={**read_evaluation_config(config_path),**read_scene_b_config(config_path)}
ops={o['id']:o for o in graph['ops'] if o['op'] not in {'COPY_IN','COPY_OUT'}}
manifest=read(ROOT/'docs/a/source-manifest.json')
for f in manifest['files']:
 if f['path'] in ['data/case_062.json','data/config.txt']:assert sha(ROOT/'data/raw/a/official'/f['path'])==f['sha256']
report={'kind':'one same-owner/same-packet local word intervention, static only',
        'started_at':datetime.now(timezone.utc).isoformat(),'source_sha256':source,'runner_sha256':sha(Path(__file__)),
        'input_sha256':sha(path),'config_sha256':sha(config_path),'workers':1,'seed':None,
        'python':platform.python_version(),'platform':platform.platform(),
        'prior_result_layout':'tree-packets-first-pilot-20260925/run/062-kK/062-kK/',
        'actual_calls':{'new_structural_candidate_build':3,'E0':0,'E1':0,'E2':0},
        'timing_scope':'function construction only; all reused construction and diagnostics included, launch/read/write excluded',
        'not_proven':['official validity','zero spill','official makespan improvement','global optimality'],'rows':[]}
with ExitStack() as guard:
 for entry in ['subprocess.Popen','multicore_cut_evaluate_problem_2.evaluate_scene_b','multicore_cut_evaluate_problem_2._build_scene_b_tasks']:
  guard.enter_context(patch(entry,side_effect=AssertionError('No scoring or compilation')))
 for k in [2,4,5]:
  prior=args.prior_run/f'062-k{k}/062-k{k}'
  old=read(prior/'plan.json');old_detail=read(prior/'online/solver.json')['attempts'][0]['detail']
  old_result=read(prior/'final/result.json.gz');trace=read(prior/'final/trace.json.gz')
  assert old_result['data_movement_bytes']['spill_added_copy_bytes']==0
  assert old==read(ROOT/f'results/a/q2-nikolastarx/tree-packets-first-static-20260925/062-k{k}-plan.json')
  start=time.perf_counter();plan,detail=tree_paired_leaves.build(graph,k,config);elapsed=time.perf_counter()-start
  assert own(plan)==own(old) and plan['node_to_subgraph']==old['node_to_subgraph']
  for key in ['packets','compute_load_by_core','cut_edges','tensor_copy_bytes_without_spill']:assert detail[key]==old_detail[key]
  assert detail['fixed_compute_fifo_bound_before']==old_detail['fixed_compute_fifo_bound_after']
  view=derive_multicore_plan(graph,plan)
  edges=[(a,b,'original') for a,b in view['dependency_pairs']]
  for seq in plan['core_schedules']:edges.extend((a,b,'full core priority') for a,b in zip(seq,seq[1:]))
  check_acyclic(view['subgraph_ids'],edges,'original DAG plus full submitted core order')
  actual={e['op_id']:{**e,'core':c['core_id']} for c in old_result['per_core_timeline'] for e in c['ops']}
  trace_ops=[e for e in trace['traceEvents'] if e['ph']=='X' and e.get('cat','').startswith('PIPE_')]
  assert len(trace_ops)==len(actual)
  for e in trace_ops:
   a=actual[e['args']['op_id']];assert (e['args']['core_id'],e['ts'],e['dur'])==(a['core'],a['start'],a['duration'])
  gap_hist=Counter();by_core=defaultdict(Counter);examples=[]
  for p in detail['pairs']:
   for chain in [p['left'],p['right']]:
    for i in range(2,len(chain),2):
     a,b=actual[chain[i-2]],actual[chain[i]];gap=b['start']-a['end']
     gap_hist[gap]+=1;by_core[p['core']][gap]+=1
     if len(examples)<6 or gap!=36:
      examples.append({'core':p['core'],'join':p['join'],'previous_M':a['op_id'],'next_M':b['op_id'],
                       'previous_M_end':a['end'],'next_M_start':b['start'],'gap':gap})
  dump(f'062-k{k}-plan.json',plan);dump(f'062-k{k}-detail.json',detail)
  mechanism={'prior_result_sha256':sha(prior/'final/result.json.gz'),'prior_trace_sha256':sha(prior/'final/trace.json.gz'),
             'prior_plan_sha256':sha(prior/'plan.json'),'prior_solver_sha256':sha(prior/'online/solver.json'),
             'prior_official_makespan':old_result['makespan'],'prior_official_spill_bytes':0,
             'covered_chain_internal_M_gap_histogram':dict(gap_hist),
             'covered_gap_histogram_by_core':{c:dict(h) for c,h in by_core.items()},'gap_examples':examples,
             'interpretation':'old observed gaps; per-core/total gap sums are not predicted global time savings'}
  dump(f'062-k{k}-prior-trace-mechanism.json',mechanism)
  row={'cores':k,'derive':'passed','original_plus_full_core_order':'acyclic','same_ownership_pieces_cut_bytes':True,
       'pairs':len(detail['pairs']),'paired_leaf_chains':detail['paired_leaf_chains'],
       'covered_M_ops':detail['covered_M_work']//300,'total_M_ops':sum(o['pipe']=='PIPE_M' for o in ops.values()),
       'prior_trace_gaps':dict(gap_hist),'rejected_binary_joins':detail['rejected_binary_joins'],
       'prior_compute_fifo_bound':detail['fixed_compute_fifo_bound_before'],'new_compute_fifo_bound':detail['fixed_compute_fifo_bound_after'],
       'raw_peaks_by_core':[p['raw_priority_peak_bytes'] for p in detail['per_core']],
       'all_raw_peaks_fit':all(p['raw_peaks_fit_capacity'] for p in detail['per_core']),
       'plan_sha256':sha(OUT/f'062-k{k}-plan.json'),'detail_sha256':sha(OUT/f'062-k{k}-detail.json'),
       'function_construction_seconds':elapsed,'index_constructions':detail['index_constructions']}
  report['rows'].append(row);print(json.dumps(row),flush=True)
assert source=={p:sha(ROOT/p) for p in SOURCE}
report.update(finished_at=datetime.now(timezone.utc).isoformat(),source_unchanged=True)
dump('report.json',report)
