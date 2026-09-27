#!/usr/bin/env python3
"""Short reproducible probes; imports official evaluators without editing them."""
import argparse,concurrent.futures,contextlib,hashlib,io,json,pathlib,sys,time,traceback
from scan_cases import views,components

def component_pack(g,n,mode='sum'):
    ops,ts,prod,cons,eligible,preds,succs,ets=views(g)
    groups=components(eligible,ets)
    w={i:(sum(ops[o]['cycles'] for o in v if ops[o]['pipe']=='PIPE_M'),sum(ops[o]['cycles'] for o in v if ops[o]['pipe']=='PIPE_V')) for i,v in enumerate(groups)}
    order=sorted(w,key=lambda i:(-sum(w[i]),min(groups[i])))
    loads=[[0,0] for _ in range(n)];mapping={}
    for i in order:
        a,b=w[i]
        c=min(range(n),key=lambda k:((sum(loads[k])+a+b) if mode=='sum' else max(loads[k][0]+a,loads[k][1]+b),sum(loads[k]),k))
        for o in groups[i]:mapping[str(o)]=c
        loads[c][0]+=a;loads[c][1]+=b
    used=set(mapping.values())
    return {'node_to_subgraph':mapping,'core_schedules':[[c] if c in used else [] for c in range(n)]}

def run_one(args):
    root,out,case,problem,mode,n=args
    sys.dont_write_bytecode=True;sys.path.insert(0,str(pathlib.Path(root)/'code'))
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import evaluate_scene_a,read_scene_a_config
    from multicore_cut_evaluate_problem_2 import evaluate_scene_b,read_scene_b_config
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3,read_cache_config
    from singlecore_evaluate import evaluate_singlecore
    start=time.perf_counter();p=pathlib.Path(root)/'data'/f'{case}.json';g=json.loads(p.read_bytes());cfg=pathlib.Path(root)/'data/config.txt'
    config=read_evaluation_config(cfg);asc=read_scene_a_config(cfg);bsc=read_scene_b_config(cfg);cache=read_cache_config(cfg)
    row={'case':case,'problem':problem,'mode':mode,'n':n,'status':'error'}
    folder=pathlib.Path(out)/f'{case}_{mode}_p{problem}_n{n}';folder.mkdir(parents=True,exist_ok=True)
    err=io.StringIO()
    try:
        if mode=='single':plan=None
        elif mode.startswith('component_'):plan=component_pack(g,n,mode.split('_')[1])
        else:
            from probe_candidates import make_candidate
            plan=make_candidate(g,n,mode,problem)
        prep=time.perf_counter()
        with contextlib.redirect_stderr(err),contextlib.redirect_stdout(err):
            if mode=='single':res=evaluate_singlecore(g,**config)
            elif problem==1:res=evaluate_scene_a(g,plan,**config,cross_core_wait=asc['task_cross_core_wait_cycles'],same_core_wait=asc['task_same_core_wait_cycles'])
            elif problem==2:res=evaluate_scene_b(g,plan,**config,cross_core_copy_delay=bsc['cross_core_copy_delay_cycles'])
            elif problem==3:res=evaluate_problem_3(g,plan,**config,cross_core_copy_delay=bsc['cross_core_copy_delay_cycles'],**cache)
            else:raise ValueError(problem)
        row.update({'status':'ok','makespan':res['makespan'],'evaluation_seconds':time.perf_counter()-prep,'preparation_seconds':prep-start,
                    'data_movement_bytes':res['data_movement_bytes'],'memory_peak_by_core':res.get('memory_peak_by_core'),
                    'cache_stats':res.get('cache_stats'),'task_count':res.get('task_count'),'step3_by_core':res.get('step3_by_core')})
        if res.get('cache_events'):
            row['cache_eviction_count']=sum(len(e.get('evicted_tensor_ids',[])) for e in res['cache_events'])
        (folder/'result.json').write_text(json.dumps(res,ensure_ascii=False))
        if plan:(folder/'plan.json').write_text(json.dumps(plan))
    except Exception as exc:
        row.update({'error':str(exc),'error_type':type(exc).__name__,'cycle':getattr(exc,'cycle',None)})
        (folder/'error.txt').write_text(err.getvalue()+'\n'+traceback.format_exc())
    row['wall_seconds']=time.perf_counter()-start
    (folder/'summary.json').write_text(json.dumps(row,ensure_ascii=False,indent=2))
    return row

def main():
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('out');p.add_argument('--cases',nargs='+',default=['case_001']);p.add_argument('--mode',default='single');p.add_argument('--problem',type=int,default=1);p.add_argument('-n',type=int,default=1);p.add_argument('--workers',type=int,default=1);a=p.parse_args()
    cases=[p.stem for p in sorted((pathlib.Path(a.root)/'data').glob('case_*.json'))] if a.cases==['all'] else a.cases
    jobs=[(a.root,a.out,c,a.problem,a.mode,a.n) for c in cases]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for r in pool.map(run_one,jobs):print(json.dumps(r,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
