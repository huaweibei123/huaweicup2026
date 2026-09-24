"""One-worker 062 x k2/4/5 static audit. No scoring or official compilation.

PYTHONPATH=. .venv/bin/python -B results/a/q2-nikolastarx/tree-frontier-static-20260924/check.py
"""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import time
from unittest.mock import patch

from src.q2_nikolastarx import tree_frontier
from src.q2_nikolastarx.direct import derive_multicore_plan
from evaluation_validation import check_acyclic, read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config

ROOT=Path.cwd(); OUT=Path(__file__).resolve().parent
SOURCES=['src/q2_nikolastarx/tree_frontier.py','src/q2_nikolastarx/dag_direct.py',
         'src/q2_nikolastarx/direct.py','src/q2_nikolastarx/baseline.py',
         'src/q2_nikolastarx/adaptive_direct.py','src/q2_nikolastarx/component_envelope.py']
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):
 with path.open('x') as stream: stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def utc():return datetime.now(timezone.utc).isoformat()
if (OUT/'report.json').exists():raise FileExistsError('preserve static evidence')
before={p:sha(ROOT/p) for p in SOURCES}
path=ROOT/'data/raw/a/official/data/case_062.json'; config_path=ROOT/'data/raw/a/official/data/config.txt'
graph=json.loads(path.read_bytes());config={**read_evaluation_config(config_path),**read_scene_b_config(config_path)}
manifest=json.loads((ROOT/'docs/a/source-manifest.json').read_bytes())
verified=[]
for f in manifest['files']:
 if f['path'].startswith('code/') or f['path'] in ['data/case_062.json','data/config.txt']:
  original=ROOT/'data/raw/a/official'/f['path']
  assert sha(original)==f['sha256'] and original.stat().st_size==f['bytes']
  verified.append(f['path'])
report={'scope':'case062 x cores2/4/5, structure and original/core-order acyclicity only',
        'seed':None,'determinism':'no randomness; graph ids break ties',
        'workers':1,'started_at':utc(),'source_sha256':before,'runner_sha256':sha(Path(__file__)),
        'input_sha256':sha(path),'config_sha256':sha(config_path),'manifest_verified':verified,
        'python':platform.python_version(),'platform':platform.platform(),
        'calls':{'E0':0,'E1':0,'E2':0},'rows':[],
        'not_proven':['Step1/2/3 runtime feasibility','official makespan or spill bytes','end-to-end solver latency','optimality'],
        'timing_scope':'function build only, excludes Python startup, input/config read and plan write'}
with ExitStack() as guard:
 for name in ['subprocess.Popen','multicore_cut_evaluate_problem_2.evaluate_scene_b','multicore_cut_evaluate_problem_2._build_scene_b_tasks']:
  guard.enter_context(patch(name,side_effect=AssertionError('No evaluation or official compilation')))
 for cores in [2,4,5]:
  start=time.perf_counter();plan,detail=tree_frontier.build(graph,cores,config);elapsed=time.perf_counter()-start
  view=derive_multicore_plan(graph,plan)
  edges=[(a,b,'original') for a,b in view['dependency_pairs']]
  for seq in plan['core_schedules']:edges.extend((a,b,'priority') for a,b in zip(seq,seq[1:]))
  check_acyclic(view['subgraph_ids'],edges,'global original and per-core priorities')
  assert detail['active_cores']==cores
  dump(OUT/f'062-k{cores}-plan.json',plan);dump(OUT/f'062-k{cores}-detail.json',detail)
  report['rows'].append({'cores':cores,'official_derive':'passed','global_original_priority':'acyclic',
       'plan_sha256':sha(OUT/f'062-k{cores}-plan.json'),'detail_sha256':sha(OUT/f'062-k{cores}-detail.json'),
       'construction_function_seconds':elapsed,'active_cores':detail['active_cores'],
       'packets':detail['packet_count'],'skeleton_ops':detail['skeleton_ops'],
       'cut_edges':len(detail['cut_edges']),'copy_bytes_without_spill':detail['tensor_copy_bytes_without_spill'],
       'compute_load_by_core':detail['compute_load_by_core'],
       'raw_peak_bytes_by_core':[x['raw_priority_peak_bytes'] for x in detail['per_core']]})
report.update(finished_at=utc(),source_after_sha256={p:sha(ROOT/p) for p in SOURCES})
assert before==report['source_after_sha256']
dump(OUT/'report.json',report)
print(json.dumps({'static_cells':len(report['rows']),'calls':report['calls'],'rows':report['rows']},indent=2))
