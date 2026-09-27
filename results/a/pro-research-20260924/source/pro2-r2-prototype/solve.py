"""Self-contained bounded constructor portfolio using unmodified E0 only.
Usage: python solve.py GRAPH -n 4 -q 2 --official OFFICIAL --output OUTDIR
Default cap: 300 wall seconds, 24 unique candidates, one E0 subprocess at a time.
No E1/E2, GPU, precomputed answer table, network, or external service is required.
"""
import argparse,json,time,hashlib,sys,os
from pathlib import Path
from scan import index_graph
from product import bundle_products
from construct import make
from evidence import run_e0,DEFAULT_OFFICIAL,sha

COMMON=[('components',{'kind':'component'}),('whole',{'kind':'whole'}),('topo_contiguous',{'kind':'topo'})]

def baseline_specs(a,k,q):
    for wave in [0,1,2,4,8,16]:
        for assignment in ['lpt','contiguous']:
            yield f'component_{assignment}_w{wave}',{'kind':'component','assignment':assignment,'wave':wave}
    for chunk in [8,32,64,128,256]:
        for order in ['id','depth']:
            yield f'topo_{order}_{chunk}',{'kind':'topo','chunk':chunk,'order':order}
    for wave in [1,2,4,8,16]:yield f'component_rr_w{wave}',{'kind':'component','assignment':'rr','wave':wave}

def structured_specs(a,k,q,best):
    n=len(a['top']);large=max(map(len,a['components']),default=0)>n/2
    # Coarsening is prioritized for a dominant coupled component, not for independent-job grids.
    if large:
        for tau in [2,64,1024,8192]:yield f'heavy{tau}',{'kind':'heavy','tau':tau,'problem':q}
    if q==1:
        for band in [16,8,32,4]:yield f'band{band}',{'kind':'component','band':band}
    else:
        if best and best.get('movement',{}).get('spill_added_copy_bytes',0)>0:
            for band in [4,8,16,32]:yield f'band{band}',{'kind':'component','band':band}
        for lag in [.125,.25,.5]:yield f'affine{lag}',{'kind':'affine','lag_fraction':lag}
        for band in [4,16,8,32]:yield f'band{band}',{'kind':'component','band':band}
        for wave in [4,8]:
            yield f'wave{wave}_band4',{'kind':'component','wave':wave,'band':4}
    prod=bundle_products(a)['products'];nontrivial=[p for p in prod if min(p['shape'])>1]
    if len(nontrivial)==1 and len(nontrivial[0]['jobs'])==len(a['components']):
        R,C=nontrivial[0]['shape']
        shapes=[(nr,nc) for nr in range(1,k+1) for nc in range(1,k+1) if nr*nc<=k and nr<=R and nc<=C and nr*nc>=max(2,k-1)]
        # Dynamic input-union expression is not used to discard nonwinning grid candidates.
        shapes.sort(key=lambda z:(-z[0]*z[1],abs(z[0]-z[1]),z))
        for grid in shapes:yield f'grid{grid[0]}x{grid[1]}',{'kind':'component','assignment':'product','grid':grid}
    if not large:
        for tau in [2,64,1024,8192]:yield f'heavy{tau}',{'kind':'heavy','tau':tau,'problem':q}
    yield from baseline_specs(a,k,q)

def lower_bound(a,k):
    pipes={o['pipe'] for o in a['eligible'].values()}
    work=max((sum(max(1,o['cycles']) for o in a['eligible'].values() if o['pipe']==p)/k for p in pipes),default=0)
    path={}
    for u in a['top']:path[u]=max(1,a['eligible'][u]['cycles'])+max((path[v] for v in a['pred'][u]),default=0)
    return max(work,max(path.values(),default=0))

def solve(graph,k,q,out,official,limit=300,max_evals=24,policy='structured',per_eval=25,certificate_tolerance=.01):
    start=time.perf_counter();out=Path(out);out.mkdir(parents=True,exist_ok=False)
    graph=Path(graph);g=json.loads(graph.read_text());a=index_graph(g)
    if len(a['top'])!=len(a['eligible']):raise ValueError('eligible graph is not a DAG')
    # The official input guarantee excludes intermediate COPY chains. Conservatively reject using this index if such chains exist.
    for t,vs in a['prod'].items():
        if any(u in a['eligible'] for u in vs) and any(a['ops'][v]['op']=='COPY_IN' for v in a['cons'][t]):
            raise ValueError('unsupported nonstandard intermediate COPY_IN; no independent-component certificate')
    lb=lower_bound(a,k);prep=time.perf_counter()-start
    seen=set();history=[];best=None;bestplan=None;count=0;stop='candidate_family_exhausted'
    def consider(name,spec):
        nonlocal best,bestplan,count,stop
        if count>=max_evals:stop='evaluation_cap';return False
        left=limit-(time.perf_counter()-start)
        if left<1.0:stop='wall_clock_budget';return False
        t=time.perf_counter()
        try:plan=make(a,k,spec)
        except (ValueError,RuntimeError) as ex:
            history.append({'name':name,'spec':spec,'status':'constructor_error','error':str(ex),'construction_seconds':time.perf_counter()-t});return True
        ctime=time.perf_counter()-t;raw=json.dumps(plan,ensure_ascii=False,separators=(',',':'))+'\n';h=hashlib.sha256(raw.encode()).hexdigest()
        if h in seen:return True
        seen.add(h);left=limit-(time.perf_counter()-start)
        if left<1.0:stop='wall_clock_budget';return False
        timeout=min(per_eval,max(.1,left-.75));r=run_e0(graph,plan,q,out/f'eval_{count:03d}_{name}',timeout=timeout,official=official,compress=True);count+=1
        r.update(name=name,spec=spec,construction_seconds=ctime,elapsed_seconds=time.perf_counter()-start);history.append(r)
        if r['status']=='ok' and (best is None or r['makespan']<best['makespan']):
            best=r;bestplan=plan
            tmp=out/'incumbent.tmp';tmp.write_text(raw);tmp.replace(out/'incumbent.plan.json')
        (out/'history.json').write_text(json.dumps(history,ensure_ascii=False,indent=2))
        if best and lb>0 and best['makespan']<=lb*(1+certificate_tolerance):stop='certified_gap';return False
        return True
    keep=True
    for name,spec in COMMON:
        if not consider(name,spec):keep=False;break
    if keep:
        specs=baseline_specs(a,k,q) if policy=='baseline' else structured_specs(a,k,q,best)
        for name,spec in specs:
            if not consider(name,spec):break
    result={'policy':policy,'graph':str(graph),'graph_hash':sha(graph),'problem':q,'cores':k,'wall_limit':limit,'max_evaluations':max_evals,'per_evaluation_timeout':per_eval,'preparation_seconds':prep,'elapsed_seconds':time.perf_counter()-start,'stop_reason':stop,'calls':count,'status':'ok' if best else 'no_confirmed_plan','best_makespan':best['makespan'] if best else None,'best_name':best['name'] if best else None,'best_plan_hash':sha(out/'incumbent.plan.json') if best else None,'best_result_directory':next((str(p.parent) for p in out.glob('eval_*/run.json') if json.loads(p.read_text()).get('plan_hash')==best['plan_hash']),None) if best else None,'lower_bound':lb,'gap_upper_bound':best['makespan']/lb-1 if best and lb else None,'certificate_tolerance':certificate_tolerance,'source_environment':'Python 3.13.5 Linux x86_64; see audit/environment.json; outside team Python 3.12 pin'}
    (out/'solve.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('graph',type=Path);p.add_argument('-n','--cores',type=int,default=4);p.add_argument('-q','--problem',type=int,choices=[1,2,3],default=2);p.add_argument('--official',type=Path,default=DEFAULT_OFFICIAL);p.add_argument('--output',type=Path,required=True);p.add_argument('--time-limit',type=float,default=300);p.add_argument('--max-evaluations',type=int,default=24);p.add_argument('--per-evaluation-timeout',type=float,default=25);p.add_argument('--policy',choices=['baseline','structured'],default='structured');p.add_argument('--certificate-tolerance',type=float,default=.01)
    a=p.parse_args();r=solve(a.graph,a.cores,a.problem,a.output,a.official,a.time_limit,a.max_evaluations,a.policy,a.per_evaluation_timeout,a.certificate_tolerance);print(json.dumps(r,ensure_ascii=False));return 0 if r['status']=='ok' else 2
if __name__=='__main__':raise SystemExit(main())
