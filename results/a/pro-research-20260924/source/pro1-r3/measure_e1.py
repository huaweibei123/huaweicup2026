#!/usr/bin/env python3
"""One warm pair + 3 alternating measured pairs. Same machine, same full API.
All returned JSON objects saved. Import/parse/serialization excluded from timings,
so these numbers are NOT CLI speed or a release-matrix acceptance.
"""
import argparse,contextlib,gzip,io,json,sys,time,math,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--official',type=Path,required=True);p.add_argument('--team',type=Path,required=True);p.add_argument('--graph',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(exist_ok=False)
sys.dont_write_bytecode=True;sys.path[:0]=[str(a.official/'code'),str(a.team)]
from multicore_cut_evaluate_problem_1 import evaluate_scene_a as E0,read_scene_a_config
from evaluation_validation import read_evaluation_config
from src.eval_exact.problem1 import evaluate_scene_a as E1
from src.eval_exact.benchmark import _first_difference
cfg=a.official/'data/config.txt';par=read_evaluation_config(cfg);s=read_scene_a_config(cfg);par.update(cross_core_wait=s['task_cross_core_wait_cycles'],same_core_wait=s['task_same_core_wait_cycles'])
g=json.loads(a.graph.read_bytes());plan=json.loads(a.plan.read_bytes());rows=[];buf=io.StringIO()
for rep in range(4):
 rr={};times={}
 for name,fn in ([('e0',E0),('e1',E1)] if rep%2==0 else [('e1',E1),('e0',E0)]):
  with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):
   t=time.perf_counter();r=fn(g,plan,**par);times[name]=time.perf_counter()-t
  rr[name]=r;raw=json.dumps(r,separators=(',',':')).encode();(a.out/f'rep{rep}_{name}.json.gz').write_bytes(gzip.compress(raw,mtime=0))
 diff=_first_difference(rr['e0'],rr['e1']);rows.append({'rep':rep,'warmup':rep==0,'seconds':times,'ratio_e0_over_e1':times['e0']/times['e1'],'first_difference':diff,'makespan':rr['e0']['makespan']})
summary={'graph':str(a.graph),'graph_sha256':hashlib.sha256(a.graph.read_bytes()).hexdigest(),'plan':str(a.plan),'plan_sha256':hashlib.sha256(a.plan.read_bytes()).hexdigest(),'scope':'P1 full in-memory API; parse/import/serialization excluded','rows':rows,'all_equal':all(x['first_difference'] is None for x in rows),'geometric_mean_ratio':math.exp(sum(math.log(x['ratio_e0_over_e1']) for x in rows[1:])/3)}
(a.out/'run.json').write_text(json.dumps(summary,indent=2));(a.out/'stdout_stderr.txt').write_text(buf.getvalue());print(json.dumps({k:v for k,v in summary.items() if k not in ['rows']},ensure_ascii=False))
