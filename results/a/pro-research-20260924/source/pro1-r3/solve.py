#!/usr/bin/env python3
"""Budgeted research solver: fixed finite constructors, unchanged official CLI.
No E2 screening, no model service, no hidden offline plans. Every candidate's
parse/compile/simulate/JSON+Trace cost is paid. Not a full competition solver.
Works with the frozen config only; `--official` points to the original directory.
"""
from __future__ import annotations
import time
START=time.perf_counter()
import argparse,contextlib,hashlib,io,json,os,shutil,subprocess,sys,traceback
from pathlib import Path
sys.dont_write_bytecode=True

def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
 p=argparse.ArgumentParser();p.add_argument('graph',type=Path);p.add_argument('--official',type=Path,required=True);p.add_argument('--problem',type=int,choices=[1,2,3],required=True);p.add_argument('--cores',type=int,choices=range(1,6),required=True);p.add_argument('--budget-seconds',type=float,default=300);p.add_argument('--portfolio',choices=['legacy3','augment'],default='augment');p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--with-window',action='store_true',help='one additional fixed-factor8 reference-window candidate for Q2/Q3')
 a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=False);root=a.output_dir
 official=a.official.resolve();graph=a.graph.resolve();cfg=official/'data/config.txt'
 sys.path.insert(0,str(official/'code'));sys.path.insert(0,str(Path(__file__).parent/'legacy'))
 from packet_construct import construct
 from cover_fusion import fuse_cover
 from probe_runner import component_pack
 from probe_candidates import make_candidate
 from evaluation_validation import read_evaluation_config
 from multicore_cut_evaluate_problem_1 import read_scene_a_config
 from multicore_cut_evaluate_problem_2 import read_scene_b_config
 from multicore_cut_evaluate_problem_3 import read_cache_config
 c=read_evaluation_config(cfg);ca=read_scene_a_config(cfg);cb=read_scene_b_config(cfg);cc=read_cache_config(cfg)
 if (c!={'capacity':{'L1':524288,'UB':131072},'bandwidth':60} or ca!={'task_cross_core_wait_cycles':1000,'task_same_core_wait_cycles':100} or cb!={'cross_core_copy_delay_cycles':500} or cc!={'cache_capacity_bytes':1048576,'cache_bandwidth_bytes_per_cycle':250}):
  raise ValueError('prototype models only the frozen competition config')
 g=json.loads(graph.read_bytes());deadline=START+a.budget_seconds;reserve=max(.3,min(2.0,a.budget_seconds*.05))
 methods=['component','cut2','unit'] if a.portfolio=='legacy3' else (['component','cut2','chain_response','unit','cover16','cover64'] if a.problem==1 else ['component','cut2','chain_response','cut2_response','unit','nr_response','refine_response'])
 if a.with_window and a.portfolio=='augment' and a.problem in (2,3):methods.append('window8_response')
 env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'};rows=[];best=None;seen={};chain=None
 report={'kind':'new experiment; independent official CLI, CPU, finite pool','graph_sha256':h(graph),'config_sha256':h(cfg),'problem':a.problem,'cores':a.cores,'portfolio':a.portfolio,'budget_seconds':a.budget_seconds,'methods':methods,'records':rows,'solver_sha256':h(Path(__file__))}
 for method in methods:
  if time.perf_counter()>deadline-reserve:break
  folder=root/method;folder.mkdir();planpath=folder/(graph.stem+'_multicore_res.json');rpath=folder/'result.json';trace=folder/'trace.json';log=folder/'log.txt';buf=io.StringIO();st=time.perf_counter();row={'method':method,'status':'unstarted'}
  try:
   with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):
    if method=='component':plan=component_pack(g,a.cores,'sum')
    elif method in ('unit','cut2'):plan=make_candidate(g,a.cores,method,a.problem)
    elif method.startswith('cover'):
     if chain is None:chain,_=construct(g,a.cores,'chain',True)
     plan,_=fuse_cover(g,chain,int(method[5:]),True)
    else:
     kind,resp=method.rsplit('_',1);plan,_=construct(g,a.cores,kind,resp=='response')
     if method=='chain_response':chain=plan
   row['construction_seconds']=time.perf_counter()-st;dump(planpath,plan);row['plan_sha256']=h(planpath)
   if row['plan_sha256'] in seen:
    row.update(status='duplicate',same_as=seen[row['plan_sha256']])
   else:
    remaining=deadline-time.perf_counter()-reserve
    if remaining<=0:row['status']='budget_before_e0'
    else:
     cmd=[sys.executable,'-B',str(official/'code'/f'multicore_cut_evaluate_problem_{a.problem}.py'),str(graph),str(planpath),'--config',str(cfg),'-o',str(rpath),'--trace-output',str(trace),'--log-output',str(log)]
     row['command']=cmd;ts=time.perf_counter();proc=subprocess.run(cmd,capture_output=True,text=True,env=env,timeout=remaining)
     row['e0_cli_seconds']=time.perf_counter()-ts;row['returncode']=proc.returncode;(folder/'stdout.txt').write_text(proc.stdout);(folder/'stderr.txt').write_text(proc.stderr)
     if proc.returncode==0 and rpath.exists():
      r=json.loads(rpath.read_text());row.update(status='ok',makespan=r['makespan'],movement=r['data_movement_bytes'],result_sha256=h(rpath));seen[row['plan_sha256']]=method
      if best is None or (r['makespan'],r['data_movement_bytes']['added_copy_bytes'])<(best[0],best[1]):best=(r['makespan'],r['data_movement_bytes']['added_copy_bytes'],folder,planpath.name,method)
     else:row['status']='official_cli_nonzero' # inspect exact stderr, not every nonzero is an invalid plan
  except subprocess.TimeoutExpired as e:
   row.update(status='budget_timeout',error=str(e))
  except Exception as e:
   row.update(status='constructor_or_harness_exception',exception_type=type(e).__name__,error=str(e));(folder/'exception.txt').write_text(traceback.format_exc())
  row['candidate_wall_seconds']=time.perf_counter()-st;(folder/'construction_output.txt').write_text(buf.getvalue());dump(folder/'run.json',row);rows.append(row);dump(root/'run.json',report)
 if best:
  _,_,folder,planname,method=best
  for name in [planname,'result.json','trace.json','log.txt']:shutil.copyfile(folder/name,root/name)
  report.update(selected_method=method,makespan=best[0],selected_plan=planname,status='ok')
 else:report.update(status='no_confirmed_solution')
 report['total_wall_seconds']=time.perf_counter()-START;report['budget_overrun_seconds']=max(0,report['total_wall_seconds']-a.budget_seconds);dump(root/'run.json',report)
 print(json.dumps({k:report[k] for k in ('status','selected_method','makespan','total_wall_seconds','budget_overrun_seconds') if k in report},ensure_ascii=False))
 return 0 if best else 2
if __name__=='__main__':raise SystemExit(main())
