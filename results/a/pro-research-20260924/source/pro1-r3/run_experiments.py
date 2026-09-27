#!/usr/bin/env python3
"""Sequential bounded prototype comparisons. Saves full untouched E0 objects.
No services, no original modifications. Function timing excludes serialization;
recorded wall_seconds includes generation and all evidence serialization.
"""
from __future__ import annotations
import argparse, contextlib, gzip, hashlib, io, json, os, sys, time, traceback
from pathlib import Path
from packet_construct import construct
sys.path.insert(0,str(Path(__file__).parent/'legacy'))
from probe_runner import component_pack
from probe_candidates import make_candidate

def digest(b):return hashlib.sha256(b).hexdigest()
def encoded(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def writegz(path,x):
    raw=json.dumps(x,ensure_ascii=False,separators=(',',':')).encode()
    path.write_bytes(gzip.compress(raw,compresslevel=6,mtime=0));return digest(raw)

def main():
    a=argparse.ArgumentParser();a.add_argument('--official',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--cases',nargs='+',required=True);a.add_argument('--methods',nargs='+',required=True);a.add_argument('--problems',nargs='+',type=int,default=[2]);a.add_argument('--cores',type=int,default=4);a.add_argument('--timeout',type=int,default=60)
    args=a.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    sys.dont_write_bytecode=True;sys.path.insert(0,str(args.official/'code'))
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import evaluate_scene_a,read_scene_a_config
    from multicore_cut_evaluate_problem_2 import evaluate_scene_b,read_scene_b_config
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3,read_cache_config
    conf=read_evaluation_config(args.official/'data/config.txt');ca=read_scene_a_config(args.official/'data/config.txt');cb=read_scene_b_config(args.official/'data/config.txt');cc=read_cache_config(args.official/'data/config.txt')
    import signal
    def alarm(*a):raise TimeoutError('research per-call timeout (NOT official invalid)')
    signal.signal(signal.SIGALRM,alarm)
    for case in args.cases:
        graphpath=args.official/'data'/f'{case}.json';raw=graphpath.read_bytes();g=json.loads(raw)
        for method in args.methods:
            for problem in args.problems:
                folder=args.output/f'{case}_{method}_q{problem}_n{args.cores}';folder.mkdir()
                row={'constructor_sha256':digest((Path(__file__).parent/'packet_construct.py').read_bytes()),'runner_sha256':digest(Path(__file__).read_bytes()),'case':case,'method':method,'problem':problem,'cores':args.cores,'status':'unstarted','graph_sha256':digest(raw),'config_sha256':digest((args.official/'data/config.txt').read_bytes()),'plan':str(folder/'plan.json'),'result':str(folder/'result.json.gz')}
                st=time.perf_counter();buf=io.StringIO();plan=None
                try:
                    signal.alarm(args.timeout)
                    with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):
                        if method=='component':plan=component_pack(g,args.cores,'sum');diag={}
                        elif method in ('cut2','unit'):plan=make_candidate(g,args.cores,method,problem);diag={}
                        else:
                            kind,prof=method.rsplit('_',1);plan,diag=construct(g,args.cores,kind,prof=='response')
                        gen=time.perf_counter()-st
                        (folder/'plan.json').write_bytes(encoded(plan));(folder/'construct.json').write_text(json.dumps(diag,ensure_ascii=False,indent=2))
                        row['plan_sha256']=digest((folder/'plan.json').read_bytes());row['construction_seconds']=gen
                        start=time.perf_counter()
                        if problem==1:r=evaluate_scene_a(g,plan,**conf,cross_core_wait=ca['task_cross_core_wait_cycles'],same_core_wait=ca['task_same_core_wait_cycles'])
                        elif problem==2:r=evaluate_scene_b(g,plan,**conf,cross_core_copy_delay=cb['cross_core_copy_delay_cycles'])
                        else:r=evaluate_problem_3(g,plan,**conf,cross_core_copy_delay=cb['cross_core_copy_delay_cycles'],**cc)
                        row['e0_seconds']=time.perf_counter()-start
                        row.update({'status':'ok','makespan':r['makespan'],'movement':r['data_movement_bytes'],'cache_stats':r.get('cache_stats'),'construct':diag,'full_result_sha256':writegz(folder/'result.json.gz',r)})
                    signal.alarm(0)
                except Exception as e:
                    signal.alarm(0);row.update({'status':'timeout' if isinstance(e,TimeoutError) else 'exception','exception_type':type(e).__name__,'error':str(e)})
                    (folder/'exception.txt').write_text(traceback.format_exc())
                row['wall_seconds']=time.perf_counter()-st;(folder/'stdout_stderr.txt').write_text(buf.getvalue());(folder/'run.json').write_text(json.dumps(row,ensure_ascii=False,indent=2))
                with (args.output/'runs.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
                print(json.dumps({k:row[k] for k in ('case','method','problem','status','makespan','wall_seconds') if k in row}),flush=True)
if __name__=='__main__':main()
