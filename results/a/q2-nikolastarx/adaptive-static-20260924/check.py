"""One-worker static audit only; execute from the repository root.

PYTHONPATH=. .venv/bin/python -B results/a/q2-nikolastarx/adaptive-static-20260924/check.py
No official evaluation, Step1/2/3 or compiler calls. Existing output is rejected.
"""
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import time
from unittest.mock import patch

from src.q2_nikolastarx import adaptive_direct, component_envelope
from src.q2_nikolastarx.direct import derive_multicore_plan
from evaluation_validation import check_acyclic, read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config

ROOT=Path.cwd()
OUT=Path(__file__).resolve().parent
SOURCES=['src/q2_nikolastarx/adaptive_direct.py','src/q2_nikolastarx/component_envelope.py',
         'src/q2_nikolastarx/dag_direct.py','src/q2_nikolastarx/direct.py','src/q2_nikolastarx/baseline.py']
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def plan_bytes(plan): return (json.dumps(plan,ensure_ascii=False,indent=2)+'\n').encode()
def utc():return datetime.now(timezone.utc).isoformat()
for name in ['coverage.json','helper-equivalence.json','rows.jsonl']:
 if (OUT/name).exists():raise FileExistsError(f'preserve existing static evidence: {name}')
source_before={p:sha(ROOT/p) for p in SOURCES}
config_path=ROOT/'data/raw/a/official/data/config.txt'
config={**read_evaluation_config(config_path),**read_scene_b_config(config_path)}
report={'scope':'100 original graphs x cores 1..5; static construction and official derive only',
        'not_proven':['official runtime feasibility','official makespan/DDR','end-to-end solver wall','all-metric superiority','optimality'],
        'started_at':utc(),'workers':1,'cases':100,'core_counts':[1,2,3,4,5],
        'source_sha256':source_before,'config_sha256':sha(config_path),
        'runner_sha256':sha(Path(__file__)),'python':platform.python_version(),
        'platform':platform.platform(),'actual_calls':{'E0':0,'E1':0,'E2':0},
        'evaluator_guard':'poison subprocess.Popen, evaluate_scene_b and _build_scene_b_tasks',
        'timing_scope':'function construction only, no process startup/config input read/serialization/write',
        'source_identity':'working-tree byte hashes before parent source commit',
        'rows_file':'rows.jsonl'}
manifest=json.loads((ROOT/'docs/a/source-manifest.json').read_text())
checked=0
for f in manifest['files']:
 if f['path'].startswith(('code/','data/')):
  p=ROOT/'data/raw/a/official'/f['path']
  assert sha(p)==f['sha256'] and p.stat().st_size==f['bytes'],f['path']
  checked+=1
report['official_manifest_files_verified']=checked
stats=Counter(); by_k=defaultdict(Counter); route_cases=defaultdict(lambda:defaultdict(list))
failures=[]; times=[]; equivalence=[]
started=time.perf_counter()
with ExitStack() as guard:
 for entry in ['subprocess.Popen','multicore_cut_evaluate_problem_2.evaluate_scene_b','multicore_cut_evaluate_problem_2._build_scene_b_tasks']:
  guard.enter_context(patch(entry,side_effect=AssertionError('No evaluator/process/compilation in static audit')))
 # Regression gate for the one authorized helper extraction: compare full plan
 # bytes and full function detail to the completed original six-cell run.
 for case in ['014','025']:
  graph=json.loads((ROOT/f'data/raw/a/official/data/case_{case}.json').read_bytes())
  for k in [2,4,5]:
   prior=ROOT/f'results/a/q2-nikolastarx/envelope-pilot-20260924/run/{case}-k{k}'
   old=(prior/'plan.json').read_bytes()
   old_detail=json.loads((prior/'online/solver.json').read_bytes())['attempts'][0]['detail']
   plan,detail=component_envelope.build(graph,k,config)
   row={'case':case,'cores':k,'plan_byte_equal':plan_bytes(plan)==old,
        'function_detail_equal':detail==old_detail,'plan_sha256':hashlib.sha256(old).hexdigest()}
   assert row['plan_byte_equal'] and row['function_detail_equal'],row
   equivalence.append(row)
 (OUT/'helper-equivalence.json').write_text(json.dumps({'scope':'6 plan bytes and function detail preserved; timing ledger not replayed','rows':equivalence,'calls':{'E0':0,'E1':0,'E2':0}},indent=2)+'\n')
 print('helper equivalence: 6/6 plan bytes and detail equal',flush=True)
 with (OUT/'rows.jsonl').open('x') as stream:
  for i in range(1,101):
   case=f'{i:03}'; path=ROOT/f'data/raw/a/official/data/case_{case}.json'; raw=path.read_bytes(); graph=json.loads(raw)
   for k in range(1,6):
    row={'case':case,'cores':k,'input_sha256':hashlib.sha256(raw).hexdigest()}
    try:
     t=time.perf_counter(); plan,detail=adaptive_direct.build(graph,k,config); dt=time.perf_counter()-t
     view=derive_multicore_plan(graph,plan)
     edges=[(a,b,'original subgraph') for a,b in view['dependency_pairs']]
     for seq in plan['core_schedules']:edges.extend((a,b,'core priority') for a,b in zip(seq,seq[1:]))
     check_acyclic(view['subgraph_ids'],edges,'global original DAG plus core priority')
     route=detail['adaptive_route'];stats[route]+=1;by_k[k][route]+=1;route_cases[k][route].append(case);times.append(dt)
     rawplan=plan_bytes(plan)
     row.update(status='ok',route=route,components=detail['components'],eligible_ops=detail['eligible_ops'],
                index_constructions=detail['index_constructions'],plan_sha256=hashlib.sha256(rawplan).hexdigest(),
                plan_bytes=len(rawplan),construct_seconds=dt,official_derive='passed',global_original_order='acyclic')
     assert detail['index_constructions']==1
     if route=='component_envelope':
      row['raw_envelope_certified_cohorts']=sum(r['within_capacity'] for c in detail['per_core'] for r in c['cohorts'])
      row['raw_envelope_uncertified_cohorts']=sum(not r['within_capacity'] for c in detail['per_core'] for r in c['cohorts'])
      row['max_open_components_bound']=max(c['max_open_components_bound'] for c in detail['per_core'])
      row['zero_spill_claim']=detail['zero_spill_claim']
    except Exception as error:
     row.update(status='failed',error=repr(error));failures.append(row)
    stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
   if i%10==0:print(f'static cells {i*5}/500; failures {len(failures)}; elapsed {time.perf_counter()-started:.2f}s',flush=True)
report.update(finished_at=utc(),static_wall_seconds=time.perf_counter()-started,
              route_totals=dict(stats),route_counts_by_cores={str(k):dict(v) for k,v in by_k.items()},
              cases_by_cores_route={str(k):dict(v) for k,v in route_cases.items()},
              passed=sum(stats.values()),failed=len(failures),failures=failures,
              construction_seconds_sum=sum(times),construction_seconds_max=max(times,default=0),
              source_after_sha256={p:sha(ROOT/p) for p in SOURCES},
              rows_sha256=sha(OUT/'rows.jsonl'))
report['source_unchanged']=source_before==report['source_after_sha256']
assert report['source_unchanged']
(OUT/'coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('complete',report['passed'],report['failed'],report['route_totals'],flush=True)
