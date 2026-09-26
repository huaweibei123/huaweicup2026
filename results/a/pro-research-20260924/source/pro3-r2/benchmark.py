"""Paired, event-preserving full-result benchmark. Repeats are fresh evaluations.
Timing: parsed input -> complete result object, including all candidate-dependent work.
No memoization, no profiler, one Python thread; I/O and comparisons outside timed call.
"""
from runtime import *
from plans import *
import argparse,gc,statistics,hashlib

def run(case,q,repeats,kind):
 out=ROOT/f'results/benchmark/{case}_q{q}_{kind}';out.mkdir(parents=True,exist_ok=True)
 t=time.perf_counter();e=load();f=load(ROOT/'fast_code');loading=time.perf_counter()-t;cfg=settings(e)
 t=time.perf_counter();g=json.loads((OFF/f'data/case_{case}.json').read_bytes());parse=time.perf_counter()-t
 t=time.perf_counter();p=component_plan(g,cores=4) if kind=='components' else intervals(g,cores=4,chunks=8);construct=time.perf_counter()-t
 save_json(out/'plan.json',p)
 report={'case':case,'q':q,'kind':kind,'repeats_requested':repeats,'predeclared_repetitions':repeats,'warmups_per_engine':1,'timing':'parsed input through full result object; all plan-dependent work; no result memoization; no profiler; one Python thread; default GC enabled during call; comparison and output writing excluded','load_seconds':loading,'input_parse_seconds':parse,'construct_seconds':construct,'runs':[]}
 engines={'E0':e,'R2':f}
 # Warm up on the same workload (not recorded as benchmark result).
 warm=[]
 for name in engines:
  gc.collect();t=time.perf_counter();r=evaluate(engines[name],q,g,p,cfg);elapsed=time.perf_counter()-t;warm.append(r)
  save_json(out/(name+'.full.json.gz'),r);report.setdefault('warmups',{})[name]=elapsed
 strict_equal(*warm);reference=warm[0];del warm
 save_json(out/'summary.json',report)
 for rep in range(repeats):
  row={'rep':rep,'order':['E0','R2'] if rep%2==0 else ['R2','E0']}
  for name in row['order']:
   gc.collect();t=time.perf_counter();r=evaluate(engines[name],q,g,p,cfg);row[name+'_seconds']=time.perf_counter()-t
   strict_equal(reference,r);row[name+'_full_equal']=True;del r
  report['runs'].append(row);save_json(out/'summary.json',report);print(case,q,kind,row,flush=True)
 for name in engines:report[name+'_median_seconds']=statistics.median(r[name+'_seconds'] for r in report['runs'])
 report['speedup']=report['E0_median_seconds']/report['R2_median_seconds'];report['makespan']=reference['makespan'];report['completed']=True
 save_json(out/'summary.json',report);print('SUMMARY',case,q,report['speedup'],flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);ap.add_argument('--q',type=int,default=1);ap.add_argument('--repeats',type=int,default=5);ap.add_argument('--kind',default='components');a=ap.parse_args();run(a.case,a.q,a.repeats,a.kind)
