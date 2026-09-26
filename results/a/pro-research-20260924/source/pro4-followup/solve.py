"""Bounded constructive portfolio; subprocess limits cover both construction and E0.
Only fully successful E0 results can replace the incumbent. No learned model is required.
"""
from __future__ import annotations
import argparse,json,subprocess,time,sys,hashlib,shutil,os
from pathlib import Path
from graph_features import Graph

def main():
    p=argparse.ArgumentParser();p.add_argument('graph',type=Path);p.add_argument('--official',type=Path,required=True)
    p.add_argument('--cores',type=int,default=4);p.add_argument('--problem',type=int,choices=[1,2,3],default=2)
    p.add_argument('--budget',type=float,default=300);p.add_argument('--strategy',choices=['baseline','frontier'],default='frontier')
    p.add_argument('--output',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args();start=time.perf_counter();deadline=start+a.budget
    a.evidence.mkdir(parents=True,exist_ok=False)
    g=Graph(json.loads(a.graph.read_text()));ww=[sum(g.duration(o) for o in c) for c in g.components]
    ass='component' if len(ww)>=a.cores and max(ww)<=1.5*sum(ww)/a.cores else 'chain'
    # Q1 has separate Task semantics: do not use the singleton pipeline portfolio.
    if a.problem==1:queue=[(ass,'coarse',1),('topo64','coarse',1)]
    elif a.strategy=='baseline':queue=[(ass,'coarse',1),('topo64','coarse',1),(ass,'id',1),(ass,'unguarded',1)]
    else:queue=[(ass,'coarse',1),('topo64','coarse',1),(ass,'unguarded',1),(ass,'stage_tail',.5)]
    if a.problem!=1 and a.strategy=='frontier' and ass=='component':queue.append((ass,'word',1))
    records=[];seen={};best=None
    for i,(assign,method,gamma) in enumerate(queue):
        remaining=deadline-time.perf_counter()
        if remaining<=.1:break
        d=a.evidence/f'{i:02d}_{assign}_{method}';d.mkdir();pp=d/'plan.json'
        rec={'assignment':assign,'method':method,'gamma':gamma};t=time.perf_counter()
        cmd=[sys.executable,str(Path(__file__).with_name('construct.py')),str(a.graph),'--cores',str(a.cores),'--assignment',assign,'--method',method,'--gamma',str(gamma),'--output',str(pp)]
        try:
            cp=subprocess.run(cmd,capture_output=True,timeout=max(.01,deadline-time.perf_counter()))
        except subprocess.TimeoutExpired:
            rec['status']='construction_timeout';records.append(rec);break
        (d/'construct_stdout.txt').write_bytes(cp.stdout);(d/'construct_stderr.txt').write_bytes(cp.stderr)
        rec['construct_wall_s']=time.perf_counter()-t
        if cp.returncode:
            rec['status']='constructor_unsupported_or_error';records.append(rec);continue
        meta=json.loads(pp.with_suffix('.meta.json').read_text());rec['constructor']=meta
        if a.problem!=1 and a.strategy=='frontier' and method=='unguarded' and not meta.get('no_spill_sufficient',False):
            queue.extend([(ass,'frontier',1),(ass,'frontier',.5)])
        h=hashlib.sha256(pp.read_bytes()).hexdigest();rec['plan_sha256']=h
        if h in seen:
            rec.update(status='identical_plan_reuse',source=seen[h]);records.append(rec);continue
        seen[h]=str(d)
        cmd=[sys.executable,str(a.official/'code'/f'multicore_cut_evaluate_problem_{a.problem}.py'),str(a.graph),str(pp),'--config',str(a.official/'data/config.txt'),'-o',str(d/'result.json'),'--trace-output',str(d/'trace.json'),'--log-output',str(d/'log.txt')]
        rec['e0_command']=cmd;t=time.perf_counter()
        try:cp=subprocess.run(cmd,capture_output=True,timeout=max(.01,deadline-time.perf_counter()))
        except subprocess.TimeoutExpired:
            rec.update(status='e0_timeout',e0_wall_s=time.perf_counter()-t);records.append(rec);break
        (d/'stdout.txt').write_bytes(cp.stdout);(d/'stderr.txt').write_bytes(cp.stderr);rec['e0_wall_s']=time.perf_counter()-t
        if cp.returncode:rec['status']='e0_nonzero';records.append(rec);continue
        result=json.loads((d/'result.json').read_text());rec.update(status='ok',makespan=result['makespan'],data_movement_bytes=result['data_movement_bytes'])
        if best is None or (result['makespan'],result['data_movement_bytes']['added_copy_bytes'])<(best[0],best[1]):
            best=(result['makespan'],result['data_movement_bytes']['added_copy_bytes'],pp)
            a.output.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(pp,a.output)
        rec['incumbent']=best[0];records.append(rec)
    report={'status':'ok' if best else 'no_e0_confirmed_solution','strategy':a.strategy,'problem':a.problem,'cores':a.cores,
      'budget_s':a.budget,'wall_s':time.perf_counter()-start,'best_makespan':best[0] if best else None,
      'e0_calls':sum('e0_wall_s' in r for r in records),'records':records,'note':'Portable prototype; startup/file-finalization small overhead is not a hard-real-time guarantee. Q1 limited coarse portfolio.'}
    (a.evidence/'solver_report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    if best is None:return 2
    return 0
if __name__=='__main__':sys.exit(main())
