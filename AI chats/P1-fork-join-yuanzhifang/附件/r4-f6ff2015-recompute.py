#!/usr/bin/env python3
"""Read-only P1 R4 audit. Standard library; no official module import/execution.
Parses raw graphs, reconstructs retained compute DAGs, verifies archived scalar
bounds and feed identities, constructs integer compute-only window witnesses.
NEVER invokes solver, Task compiler, simulator, response oracle, E0/E1/E2.
"""
from __future__ import annotations
from pathlib import Path
from collections import defaultdict, deque, Counter
from fractions import Fraction
import argparse, hashlib, json, csv, zipfile, math, time

PIPES=('PIPE_MTE2','PIPE_MTE3','PIPE_M','PIPE_V')
EXCLUDED={'COPY_IN','COPY_OUT'}
def sha(b): return hashlib.sha256(b).hexdigest()
def ceildiv(a,b): return (a+b-1)//b

def graph_view(g):
    allops={o['id']:o for o in g['ops']}
    ops={v:o for v,o in allops.items() if o['op'] not in EXCLUDED}
    ts={t['id']:t for t in g['tensors']}
    ps=defaultdict(set); cs=defaultdict(set); succ={v:set() for v in ops}
    for e in g['edges']:
        a,b=e['source'],e['target']
        if a in allops and b in allops:
            if a in ops and b in ops: succ[a].add(b)
        elif a in allops: ps[b].add(a)
        else: cs[a].add(b)
    cp={t:ps[t]&ops.keys() for t in ts}; cc={t:cs[t]&ops.keys() for t in ts}
    iw={}; ow={}
    for t in ts:
        for p in cp[t]: succ[p].update(cc[t])
        w=max(1,ceildiv(ts[t]['size'],60))
        if not cp[t] and cc[t]: iw[t]=w
        if cp[t] and (not cc[t] or any(allops[x]['op']=='COPY_OUT' for x in cs[t])): ow[t]=w
    pred={v:[] for v in ops}; indeg={v:0 for v in ops}
    for v,ns in succ.items():
        for u in ns: pred[u].append(v); indeg[u]+=1
    todo=deque(sorted(v for v in ops if indeg[v]==0)); topo=[]
    while todo:
        v=todo.popleft();topo.append(v)
        for u in sorted(succ[v]):
            indeg[u]-=1
            if not indeg[u]: todo.append(u)
    assert len(topo)==len(ops), 'retained DAG cycle'
    d={v:max(1,o['cycles']) for v,o in ops.items()}
    r0={v:0 for v in ops};q0=r0.copy();r=r0.copy();q=r0.copy()
    for t,w in iw.items():
        for v in cc[t]: r[v]=max(r[v],w)
    for t,w in ow.items():
        for v in cp[t]: q[v]=max(q[v],w)
    for v in topo:
        for u in succ[v]:
            r0[u]=max(r0[u],r0[v]+d[v]);r[u]=max(r[u],r[v]+d[v])
    for v in reversed(topo):
        for u in succ[v]:
            q0[v]=max(q0[v],d[u]+q0[u]);q[v]=max(q[v],d[u]+q[u])
    pure={p:[] for p in PIPES};aug={p:[] for p in PIPES};ddr=[]
    for v,o in ops.items():
        pure[o['pipe']].append((r0[v],d[v],q0[v],v))
        aug[o['pipe']].append((r[v],d[v],q[v],v))
    for t,w in iw.items():
        job=(0,w,max(d[v]+q[v] for v in cc[t]),f'IN:{t}')
        aug['PIPE_MTE2'].append(job);ddr.append(job)
    for t,w in ow.items():
        job=(max(r[v]+d[v] for v in cp[t]),w,0,f'OUT:{t}')
        aug['PIPE_MTE3'].append(job);ddr.append(job)
    return dict(ops=ops,ts=ts,succ=succ,pred=pred,topo=topo,d=d,r0=r0,q0=q0,r=r,q=q,
                pure=pure,aug=aug,ddr=ddr,iw=iw,ow=ow,cp=cp,cc=cc,
                cp0=max((r0[v]+d[v] for v in ops),default=0),
                cpa=max((r[v]+d[v]+q[v] for v in ops),default=0))

def resource(jobs,c):
    w=sum(x[1] for x in jobs);r=min((x[0] for x in jobs),default=0);q=min((x[2] for x in jobs),default=0)
    return dict(job_count=len(jobs),capacity=c,work_cycles=w,minimum_release_cycles=r,
                minimum_tail_cycles=q,load_bound_cycles=ceildiv(w,c),
                release_load_tail_bound_cycles=r+ceildiv(w,c)+q)

class PrefixTree:
    def __init__(self,vals):
        self.n=len(vals);self.mx=[0]*(4*self.n);self.arg=[0]*(4*self.n);self.lazy=[0]*(4*self.n)
        def build(x,l,r):
            if l==r:self.mx[x]=vals[l];self.arg[x]=l;return
            mid=(l+r)//2;build(x*2,l,mid);build(x*2+1,mid+1,r);self.pull(x)
        build(1,0,self.n-1)
    def pull(self,x):
        j=x*2 if self.mx[x*2]>=self.mx[x*2+1] else x*2+1
        self.mx[x]=self.mx[j]+self.lazy[x];self.arg[x]=self.arg[j]
    def add(self,p,val):
        def go(x,l,r):
            if r<=p:self.mx[x]+=val;self.lazy[x]+=val;return
            mid=(l+r)//2;go(x*2,l,mid)
            if p>mid:go(x*2+1,mid+1,r)
            self.pull(x)
        go(1,0,self.n-1)
    def maximum(self,p):
        def go(x,l,r,carry):
            if r<=p:return self.mx[x]+carry,self.arg[x]
            mid=(l+r)//2;carry+=self.lazy[x];a=go(x*2,l,mid,carry)
            if p>mid:
                b=go(x*2+1,mid+1,r,carry)
                if b[0]>a[0]:a=b
            return a
        return go(1,0,self.n-1,0)

def window(jobs,c):
    if not jobs:return dict(bound=0,empty=True)
    groups=defaultdict(int)
    for r,d,q,_ in jobs:groups[(r,q)]+=d
    qs=sorted({q for r,q in groups}); qi={q:i for i,q in enumerate(qs)}
    levels=defaultdict(list)
    for (r,q),d in groups.items():levels[r].append((q,d))
    tree=PrefixTree([c*q for q in qs]);active_hi=-1;best=-1;wa=wb=0
    for a in sorted(levels,reverse=True):
        for q,d in levels[a]:
            j=qi[q];tree.add(j,d);active_hi=max(active_hi,j)
        value,j=tree.maximum(active_hi)
        candidate=a+ceildiv(value,c)
        if candidate>best:best=candidate;wa=a;wb=qs[j]
    ids=[v for r,d,q,v in jobs if r>=wa and q>=wb]
    work=sum(d for r,d,q,v in jobs if r>=wa and q>=wb)
    assert ids and wa+wb+ceildiv(work,c)==best
    return dict(bound=best,empty=False,a=wa,b=wb,selected_work=work,
                selected_count=len(ids),selected_id_sha256=sha(json.dumps(sorted(ids),separators=(',',':')).encode()),
                distinct_rq=len(groups))

def separator_structure(v):
    """Universal retained-compute vertices, checked in a common topo order.
    Forward unique remaining source => reaches all later vertices.
    Reverse unique remaining sink => reached from all earlier vertices.
    """
    topo=v['topo'];indeg={u:len(v['pred'][u]) for u in topo}
    ready={u for u in topo if not indeg[u]};forward=set()
    for u in topo:
        assert u in ready
        if len(ready)==1:forward.add(u)
        ready.remove(u)
        for w in v['succ'][u]:
            indeg[w]-=1
            if not indeg[w]:ready.add(w)
    outdeg={u:len(v['succ'][u]) for u in topo};ready={u for u in topo if not outdeg[u]};backward=set()
    for u in reversed(topo):
        assert u in ready
        if len(ready)==1:backward.add(u)
        ready.remove(u)
        for w in v['pred'][u]:
            outdeg[w]-=1
            if not outdeg[w]:ready.add(w)
    universal=forward&backward;anchors=[u for u in topo if u in universal]
    blocks=[];work={p:0 for p in PIPES};count=0;left=None
    for u in topo:
        if u in universal:
            blocks.append(dict(left=left,right=u,op_count=count,pipe_work=work))
            left=u;work={p:0 for p in PIPES};count=0
        else:
            work[v['ops'][u]['pipe']]+=v['d'][u];count+=1
    blocks.append(dict(left=left,right=None,op_count=count,pipe_work=work))
    return dict(anchors=anchors,anchor_work=sum(v['d'][u] for u in anchors),blocks=blocks)

def separator_bound(st,k,tau=1000):
    parts=[]
    for block in st['blocks']:
        endpoints=int(block['left'] is not None)+int(block['right'] is not None)
        bypipe={}
        for p,w in block['pipe_work'].items():
            # Envelope max_c sum (x-release_c-tail_c)_+ over all possible anchor cores.
            # Two anchors on the same core maximizes this capacity envelope.
            bypipe[p]=min(w,ceildiv(w+endpoints*tau*(k-1),k)) if endpoints else ceildiv(w,k)
        parts.append(dict(**block,endpoints=endpoints,bounds=bypipe,bound=max(bypipe.values())))
    return dict(bound=st['anchor_work']+sum(x['bound'] for x in parts),anchors=st['anchors'],
                anchor_work=st['anchor_work'],blocks=parts,scope='integer retained-compute and exact Task cross-core gates; arbitrary legal partition')

def fractionsummary(rows,Lkey,official_one=True):
    out=[]
    for k in range(1,6):
        rs=[x for x in rows if x['cores']==k]
        candidate_A=sum((Fraction(x['B'],x['U']) for x in rs),Fraction())/100
        A=Fraction(1) if k==1 and official_one else candidate_A
        C=sum((Fraction(x['B'],x[Lkey]) for x in rs),Fraction())/100
        gap=C-A;rel=C/A-1
        out.append(dict(cores=k,n=len(rs),A=float(A),C=float(C),C_minus_A=float(gap),relative_mean_gain_cap=float(rel),
                        A_fraction=str(A),C_fraction=str(C),current_candidate_A=float(candidate_A),
                        exact_matches=sum(x['U']==x[Lkey] for x in rs),
                        lower_exceeds_U=sum(x[Lkey]>x['U'] for x in rs),
                        unweighted_mean_cell_speed_gain=sum(x['U']/x[Lkey]-1 for x in rs)/100))
    return out

def main(root:Path,out:Path):
    out.mkdir(exist_ok=True,parents=True);start=time.perf_counter()
    manifest=json.loads((root/'MANIFEST.json').read_text()); assert all(sha((root/x['path']).read_bytes())==x['sha256'] and (root/x['path']).stat().st_size==x['size_bytes'] for x in manifest)
    static=json.loads((root/'results/a/q1-lower-bounds-20260924/static_bounds.json').read_text())
    st={Path(c['input_member']).stem[-3:]:c for c in static['cases']}
    feedpath=next(root.glob('results/a/q1-unified-v4*/**/board-feed-500.json'));feedbytes=feedpath.read_bytes();assert sha(feedbytes)=='4cd79828999ad56dc00d34a79cc0dcd921fff783e5aaf793b0c84924b0f10764'
    feed=json.loads(feedbytes)['records'];fd={(x['case_id'],x['cores']):x for x in feed};assert len(fd)==len(feed)==500
    baseidx=json.loads((root/'results/a/q1-yuanzhifang/v4-reuse-audit-20260925/reusable-index.json').read_text())['k4']
    bases={x['case_id']:x for x in baseidx}; assert len(bases)==100
    derived=json.loads((root/'derived/paired-bounds-v4.json').read_text());dr={(x['case_id'],x['cores']):x for x in derived['rows']}
    configsha=sha((root/'data/raw/a/official/data/config.txt').read_bytes())
    official_expected='de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0'
    rows=[];certs=[];graphstats=[];mismatches=[];meta=[];sep_certs=[]
    if sorted(static['core_counts'])!=[1,2,3,4,5]:meta.append(dict(issue='stale_core_counts_metadata',reported=static['core_counts'],actual=[1,2,3,4,5]))
    with zipfile.ZipFile(root/'data/raw/a/official-cases.zip') as z:
        assert len(z.namelist())==100
        for name in sorted(z.namelist()):
            cid=Path(name).stem[-3:];raw=z.read(name);h=sha(raw);g=json.loads(raw);v=graph_view(g)
            assert st[cid]['input_sha256']==h;assert bases[cid]['graph_sha256']==h
            separators=separator_structure(v)
            old={x['cores']:x for x in st[cid]['bounds']}
            gstat=dict(case_id=cid,sha256=h,compute_ops=len(v['ops']),edges=sum(map(len,v['succ'].values())),
                       total_compute_work=sum(v['d'].values()),max_compute_cycles=max(v['d'].values(),default=0),
                       max_tensor_bytes=max((x['size'] for x in g['tensors']),default=0),
                       pipe_work={p:sum(x[1] for x in js) for p,js in v['pure'].items()},
                       inputs=len(v['iw']),outputs=len(v['ow']),multi_compute_producer_tensors=sum(len(x)>1 for x in v['cp'].values()),
                       zero_size_tensors=sum(x['size']==0 for x in g['tensors']))
            gstat['universal_separator_count']=len(separators['anchors']);graphstats.append(gstat)
            for k in range(1,6):
                fr=fd[cid,k];B=bases[cid]['baseline_makespan_cycles'];U=fr['metrics']['makespan_cycles'];dv=dr[cid,k]
                assert fr['status']=='ok' and fr['solver_commit']=='a0537aeb72dc702af86d67d3194587d581ac207c'
                assert fr['identity']['graph_sha256']==fr['baseline']['graph_sha256']==h
                assert fr['identity']['config_sha256']==fr['baseline']['config_sha256']==configsha
                assert fr['identity']['official_sha256']==fr['baseline']['official_sha256']==official_expected
                assert dv['graph_sha256']==h and dv['baseline_makespan_cycles']==B and dv['current_E0_makespan_cycles']==U
                assert fr['baseline']['result']['sha256']==bases[cid]['baseline_gzip_sha256']
                res={p:resource(j,k) for p,j in v['aug'].items()};dres=resource(v['ddr'],1)
                stat0=max(v['cpa'],dres['load_bound_cycles'],*(x['load_bound_cycles'] for x in res.values()))
                stat=max(stat0,dres['release_load_tail_bound_cycles'],*(x['release_load_tail_bound_cycles'] for x in res.values()))
                checks=dict(compute_critical_path_cycles=v['cp0'],relaxed_critical_path_cycles=v['cpa'],
                            mandatory_ddr_service_bound_cycles=dres['load_bound_cycles'],pipe_load_bound_cycles=max(x['load_bound_cycles'] for x in res.values()),
                            base_lower_bound_cycles=stat0,lower_bound_cycles=stat,
                            pipe_resources=res,ddr_resource=dres,retained_compute_edges=gstat['edges'],compute_ops=len(v['ops']))
                for key,val in checks.items():
                    if old[k][key]!=val:mismatches.append(dict(case=cid,cores=k,key=key,expected=old[k][key],actual=val))
                assert dv['candidate_static_lower_bound_cycles']==stat
                for key,val in [('current_speedup',B/U),('conditional_speedup_upper_bound',B/stat),('conditional_max_fractional_makespan_reduction',1-stat/U),('conditional_max_relative_speedup_gain',U/stat-1)]:
                    assert math.isclose(dv[key],val,rel_tol=1e-12,abs_tol=1e-12),(cid,k,key)
                pure_res={p:resource(j,k) for p,j in v['pure'].items()}
                base_compute=max(v['cp0'],*(x['load_bound_cycles'] for x in pure_res.values()))
                mincompute=max(base_compute,*(x['release_load_tail_bound_cycles'] for x in pure_res.values()))
                windows={p:window(j,k) for p,j in v['pure'].items()}
                safe=max(v['cp0'],*(w['bound'] for w in windows.values()))
                assert safe>=mincompute
                sep=separator_bound(separators,k);global_safe=max(safe,sep['bound'])
                sep_certs.append(dict(case_id=cid,cores=k,graph_sha256=h,**sep))
                dominant=[p for p,w in windows.items() if w['bound']==safe]
                if safe==v['cp0']:dominant.append('retained_compute_CP')
                statdom=[]
                if stat==v['cpa']:statdom.append('augmented_CP')
                if stat==dres['release_load_tail_bound_cycles']:statdom.append('DDR_rmin_work_qmin')
                for p,rp in res.items():
                    if rp['release_load_tail_bound_cycles']==stat:statdom.append(p+'_rmin_work_qmin')
                row=dict(case_id=cid,cores=k,graph_sha256=h,config_sha256=configsha,B=B,U=U,L_safe_compute_window=safe,
                         L_safe_global=global_safe,L_safe_separator=sep['bound'],L_safe_compute_base=base_compute,L_safe_compute_min_window=mincompute,L_conditional_archived=stat,
                         A_cell=B/U,C_cell_safe=B/safe,C_cell_safe_global=B/global_safe,C_cell_conditional=B/stat,
                         safe_global_max_makespan_reduction=1-global_safe/U,safe_global_max_relative_speed_gain=U/global_safe-1,
                         safe_max_makespan_reduction=1-safe/U,safe_max_relative_speed_gain=U/safe-1,
                         conditional_max_makespan_reduction=1-stat/U,conditional_max_relative_speed_gain=U/stat-1,
                         compute_window_dominant='|'.join(dominant),conditional_dominant='|'.join(statdom),
                         extra_ddr_bytes=fr['metrics']['extra_ddr_bytes'],spill_bytes=fr['metrics']['spill_bytes'],
                         selected=fr['parameters']['selected'],solver_wall_seconds=fr['metrics']['solver_wall_seconds'],external_E0_wall_seconds=fr['metrics']['evaluation_wall_seconds'])
                rows.append(row);certs.append(dict(case_id=cid,cores=k,graph_sha256=h,cp=v['cp0'],windows=windows,L=safe))
            print(cid,'done',round(time.perf_counter()-start,2),flush=True)
    assert not mismatches,mismatches[:3]
    summaries={name:fractionsummary(rows,key) for name,key in [('official_integer_global','L_safe_global'),('official_integer_compute','L_safe_compute_window'),('conditional_archived','L_conditional_archived'),('compute_base','L_safe_compute_base')]}
    budget=[];regress=[]
    for k in range(1,6):
        vals=[];changed=[];tied=[]
        for cid in sorted(bases):
            opts=[fd[cid,j] for j in range(1,k+1)]
            best=min(opts,key=lambda x:(x['metrics']['makespan_cycles'],x['metrics']['ddr_bytes'],-x['cores']))
            current=fd[cid,k];u=best['metrics']['makespan_cycles']; vals.append(Fraction(bases[cid]['baseline_makespan_cycles'],u))
            if u<current['metrics']['makespan_cycles']:changed.append(cid)
            elif best['metrics']['ddr_bytes']<current['metrics']['ddr_bytes']:tied.append(cid)
            if k>1 and current['metrics']['makespan_cycles']>fd[cid,k-1]['metrics']['makespan_cycles']:regress.append(dict(case_id=cid,from_cores=k-1,to_cores=k,old_U=fd[cid,k-1]['metrics']['makespan_cycles'],new_U=current['metrics']['makespan_cycles']))
        budget.append(dict(cores=k,historical_candidate_envelope=float(sum(vals,Fraction())/100),improved=changed,ddr_only=tied))
    report=dict(scope='Author report: source-based integer compute-only global bounds, pending independent local audit; archived DDR-augmented bounds conditional on numerical bridge',
                calls=dict(solver=0,Task_compiler=0,response_simulator=0,E0=0,E1=0,E2=0),
                input_zip_sha256=sha((root.parent/'p1-pro-r4-fixed-evidence.zip').read_bytes()) if (root.parent/'p1-pro-r4-fixed-evidence.zip').exists() else None,feed_sha256=sha(feedbytes),
                rows=rows,summary=summaries,metadata_findings=meta,archived_scalar_mismatches=mismatches,
                graph_stats=graphstats,historical_core_envelopes=budget,adjacent_core_regressions=regress,
                counters=dict(raw_graphs_parsed=100,paired_cells=500,compute_window_resource_runs=2000,archived_bounds_recomputed=500),
                analysis_wall_seconds=time.perf_counter()-start)
    (out/'audit_tables.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (out/'separator_certificates.json').write_text(json.dumps(sep_certs,ensure_ascii=False,indent=2)+'\n')
    (out/'window_certificates.json').write_text(json.dumps(certs,ensure_ascii=False,indent=2)+'\n')
    with (out/'paired_500_audited.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:v for k,v in report.items() if k not in ['rows','graph_stats']},ensure_ascii=False,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/mnt/data/p1_r4_evidence'));ap.add_argument('--out',type=Path,default=Path('/mnt/data/p1_r4_report'));a=ap.parse_args();main(a.root,a.out)
