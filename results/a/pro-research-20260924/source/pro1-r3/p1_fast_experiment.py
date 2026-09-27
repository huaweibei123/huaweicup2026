#!/usr/bin/env python3
"""P1 cover-fusion candidates; genuine supplied E1/E2 compared to independent E0.
Small diagnostic pools, NOT the >=64 pool release gate. No engine modifications.
"""
from __future__ import annotations
import argparse,contextlib,gzip,hashlib,io,json,sys,time,traceback,statistics
from pathlib import Path
from packet_construct import construct
from cover_fusion import fuse_cover
sys.path.insert(0,str(Path(__file__).parent/'legacy'))
from probe_runner import component_pack
from probe_candidates import make_candidate

def rawjson(x):return json.dumps(x,ensure_ascii=False,separators=(',',':')).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def savegz(p,r):p.write_bytes(gzip.compress(rawjson(r),compresslevel=6,mtime=0))

def main():
    p=argparse.ArgumentParser();p.add_argument('--official',type=Path,required=True);p.add_argument('--team',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--cases',nargs='+',required=True);a=p.parse_args();a.out.mkdir(exist_ok=False)
    sys.dont_write_bytecode=True;sys.path.insert(0,str(a.official/'code'));sys.path.insert(0,str(a.team))
    import multicore_cut_evaluate_problem_1 as E0
    from evaluation_validation import read_evaluation_config
    from src.eval_exact.problem1 import evaluate_scene_a as E1
    from src.eval_proxy.model import prepare_graph,evaluate as E2rank
    from src.eval_proxy.event_model import evaluate_event as E2event
    from src.eval_exact.benchmark import _first_difference
    cfg=a.official/'data/config.txt';params=read_evaluation_config(cfg);sc=E0.read_scene_a_config(cfg);params.update(cross_core_wait=sc['task_cross_core_wait_cycles'],same_core_wait=sc['task_same_core_wait_cycles'])
    allrows=[];pools=[]
    for case in a.cases:
        raw=(a.official/'data'/f'{case}.json').read_bytes();g=json.loads(raw);st=time.perf_counter();context=prepare_graph(g,problem=1,**params);prept=time.perf_counter()-st
        cgstart=time.perf_counter()
        chain,diag=construct(g,4,'chain',True)
        # The seed uses a B-inspired construction. Here E0 judges its Q1 transfer;
        # it is NOT claimed to be a dedicated Q1 optimum.
        chain_time=time.perf_counter()-cgstart
        generators=[('component',lambda:component_pack(g,4,'sum')),('cut2',lambda:make_candidate(g,4,'cut2',1)),('unit',lambda:make_candidate(g,4,'unit',1)),('chain',lambda:chain)]
        for cap in [16,64]:
            for guard in [False,True]:
                generators.append((f'cover{cap}_guard{int(guard)}',lambda cap=cap,guard=guard:fuse_cover(g,chain,cap,guard)[0]))
        rows=[]
        for method,gen in generators:
            folder=a.out/f'{case}_{method}';folder.mkdir();rrow={'case':case,'method':method,'question':1,'cores':4,'graph_sha256':sha(raw),'config_sha256':sha(cfg.read_bytes()),'fast_commit':'3357d7ef9c1ad443dd0799f6ecb5b813df6753b3','status':'unstarted'};buf=io.StringIO();st=time.perf_counter()
            try:
                with contextlib.redirect_stdout(buf),contextlib.redirect_stderr(buf):
                    cst=time.perf_counter();plan=gen();rrow['construction_seconds']=time.perf_counter()-cst+(chain_time if method.startswith('cover') or method=='chain' else 0)
                    (folder/'plan.json').write_bytes(rawjson(plan));rrow['plan_sha256']=sha(rawjson(plan))
                    # Alternate order of E0/E1 across candidate identities. One pair is
                    # diagnostic timing only; a repeated isolated measurement comes later.
                    calls=[('e0',E0.evaluate_scene_a),('e1',E1)]
                    if len(rows)%2:calls.reverse()
                    results={}
                    for name,fn in calls:
                        ts=time.perf_counter();r=fn(g,plan,**params);rrow[name+'_seconds']=time.perf_counter()-ts;results[name]=r;savegz(folder/(name+'.json.gz'),r)
                    diff=_first_difference(results['e0'],results['e1']);rrow['e1_first_difference']=diff
                    for name,fn in [('rank',E2rank),('event',E2event)]:
                        ts=time.perf_counter();r=fn(context,plan);rrow[name+'_seconds']=time.perf_counter()-ts
                        (folder/(name+'.json')).write_bytes(rawjson(r));rrow[name]=r
                    rrow.update(status='ok',makespan=results['e0']['makespan'],e1_equal=diff is None,movement=results['e0']['data_movement_bytes'],tasks=sum(map(len,plan['core_schedules'])))
                rrow['wall_seconds']=time.perf_counter()-st
            except Exception as e:
                rrow.update(status='exception',error=str(e),error_type=type(e).__name__);(folder/'exception.txt').write_text(traceback.format_exc())
            (folder/'stdout_stderr.txt').write_text(buf.getvalue());(folder/'run.json').write_text(json.dumps(rrow,ensure_ascii=False,indent=2));rows.append(rrow);allrows.append(rrow)
            print(json.dumps({k:rrow[k] for k in ('case','method','status','makespan','e1_equal','e0_seconds','e1_seconds') if k in rrow}),flush=True)
        pools.append({'case':case,'proxy_prepare_seconds':prept,'rows':rows})
        (a.out/'pools.json').write_text(json.dumps(pools,ensure_ascii=False,indent=2));(a.out/'runs.json').write_text(json.dumps(allrows,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
