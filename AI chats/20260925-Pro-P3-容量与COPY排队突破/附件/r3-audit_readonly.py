#!/usr/bin/env python3
"""Frozen P3 audit: standard-library parsing, hashing, DAG traversals and integer certificates.
Never imports/executes solver, Task, Step1/2/3, E0/E1/E2. Never constructs a submission.
Usage: python audit_readonly.py --archive q3-theoretical-bound-r3.zip --out ./audit-output
"""
from __future__ import annotations
import argparse, bisect, collections, csv, hashlib, io, json, math, statistics, time, zipfile
from fractions import Fraction
from pathlib import Path

ZIP_SHA='9d50a4260ff72981ea902c115cd39aa109f6fc8f88ee69ae0c0e9f759295ea4f'
ZIP_SIZE=11309176
SOLVER='311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1'
PFX='results/a/q3-nikolastarx/'

def sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def js(b): return json.loads(b)
def dump(p,obj): p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def ceildiv(a,b): return (a+b-1)//b

class PrefixAddMax:
    """Range prefix addition; query maximum on nonempty prefix, with argmax.
    Exact Python integers only. Zero-based leaf coordinates are tail thresholds.
    """
    def __init__(self, values):
        self.n=len(values); self.mx=[0]*(4*self.n); self.lazy=[0]*(4*self.n); self.arg=[0]*(4*self.n)
        def build(x,l,r):
            if l==r:self.mx[x]=values[l];self.arg[x]=l;return
            m=(l+r)//2;build(x*2,l,m);build(x*2+1,m+1,r);self.pull(x)
        build(1,0,self.n-1)
    def pull(self,x):
        y=x*2 if self.mx[x*2]>=self.mx[x*2+1] else x*2+1
        self.mx[x]=self.lazy[x]+self.mx[y];self.arg[x]=self.arg[y]
    def add(self,end,value):
        def rec(x,l,r):
            if r<=end:self.mx[x]+=value;self.lazy[x]+=value;return
            m=(l+r)//2;rec(x*2,l,m)
            if end>m:rec(x*2+1,m+1,r)
            self.pull(x)
        rec(1,0,self.n-1)
    def query(self,end):
        def rec(x,l,r,carry):
            if r<=end:return self.mx[x]+carry,self.arg[x]
            carry+=self.lazy[x];m=(l+r)//2
            left=rec(x*2,l,m,carry)
            if end<=m:return left
            right=rec(x*2+1,m+1,r,carry)
            return left if left[0]>=right[0] else right
        return rec(1,0,self.n-1,0)

def static_graph(g):
    ops={o['id']:o for o in g['ops']}; ts={t['id']:t for t in g['tensors']}
    assert len(ops)==len(g['ops']) and len(ts)==len(g['tensors']) and not (ops.keys()&ts.keys())
    co={u:o for u,o in ops.items() if o['op'] not in {'COPY_IN','COPY_OUT'}}
    assert co and all(type(o['cycles']) is int and o['cycles']>0 and o['pipe'] in {'PIPE_M','PIPE_V'} for o in co.values())
    prod=collections.defaultdict(set);cons=collections.defaultdict(set);direct=set()
    for e in g['edges']:
        u,v=e['source'],e['target']
        assert (u in ops or u in ts) and (v in ops or v in ts)
        if u in ops and v in ops:
            if u!=v:direct.add((u,v))
        elif u in ops:prod[v].add(u)
        elif v in ops:cons[u].add(v)
        else:raise AssertionError('tensor-to-tensor edge')
    assert all(len(v)<=1 for v in prod.values())
    full={u:set() for u in ops};edges={(u,v) for u,v in direct if u in co and v in co}
    for u,v in direct:full[u].add(v)
    tensor_compute=set()
    for t,ps in prod.items():
        for u in ps:
            for v in cons[t]:
                if u!=v:
                    full[u].add(v)
                    if u in co and v in co:tensor_compute.add((u,v));edges.add((u,v))
    extra=set()
    # Strictly an audit: do not put excluded-COPY contraction edges into the bound.
    for u in co:
        q=[v for v in full[u] if v not in co];seen=set()
        while q:
            v=q.pop()
            if v in seen:continue
            seen.add(v)
            for w in full[v]:
                if w in co:
                    if w!=u and (u,w) not in edges:extra.add((u,w))
                else:q.append(w)
    succ={u:[] for u in co};pred={u:[] for u in co}
    for u,v in sorted(edges):succ[u].append(v);pred[v].append(u)
    degree={u:len(pred[u]) for u in co};q=collections.deque(sorted(u for u in co if degree[u]==0));order=[]
    d={u:co[u]['cycles'] for u in co};h=dict.fromkeys(co,0);prev={}
    while q:
        u=q.popleft();order.append(u)
        for v in succ[u]:
            x=h[u]+d[u]
            if x>h[v]:h[v]=x;prev[v]=u
            degree[v]-=1
            if degree[v]==0:q.append(v)
    assert len(order)==len(co)
    tail=dict.fromkeys(co,0)
    for u in reversed(order):tail[u]=max((d[v]+tail[v] for v in succ[u]),default=0)
    last=max(co,key=lambda u:(h[u]+d[u],-u));cp=h[last]+d[last];path=[last]
    while path[-1] in prev:path.append(prev[path[-1]])
    path.reverse();assert sum(d[u] for u in path)==cp
    work=collections.Counter()
    for u,o in co.items():work[o['pipe']]+=d[u]
    seen=set();components=[]
    for root in sorted(co):
        if root in seen:continue
        stack=[root];seen.add(root);members=[]
        while stack:
            u=stack.pop();members.append(u)
            for v in succ[u]+pred[u]:
                if v not in seen:seen.add(v);stack.append(v)
        components.append(sorted(members))
    return dict(ops=ops,tensors=ts,compute=co,prod=prod,cons=cons,edges=edges,succ=succ,pred=pred,
                d=d,h=h,t=tail,order=order,cp=cp,path=path,work=work,components=components,
                contraction_extra=sorted(extra),tensor_compute_edges=len(tensor_compute),direct_compute_edges=len(edges-tensor_compute))

def compute_window_certificate(s,k):
    best={'value':0}
    for pipe in ['PIPE_M','PIPE_V']:
        us=[u for u in s['compute'] if s['compute'][u]['pipe']==pipe]
        if not us:continue
        tails=sorted({s['t'][u] for u in us});coord={v:i for i,v in enumerate(tails)}
        groups=collections.defaultdict(list)
        for u in us:groups[s['h'][u]].append(u)
        seg=PrefixAddMax([k*b for b in tails]);largest=-1
        for a in sorted(groups,reverse=True):
            for u in groups[a]:
                j=coord[s['t'][u]];largest=max(largest,j);seg.add(j,s['d'][u])
            val,j=seg.query(largest);b=tails[j];bound=a+ceildiv(val,k)
            if bound>best['value']:
                best={'value':bound,'pipe':pipe,'a':a,'b':b,'work_sum':val-k*b}
    members=sorted(u for u,o in s['compute'].items() if o['pipe']==best['pipe'] and s['h'][u]>=best['a'] and s['t'][u]>=best['b'])
    assert members and best['work_sum']==sum(s['d'][u] for u in members)
    assert best['value']==best['a']+best['b']+ceildiv(best['work_sum'],k)
    best['members_count']=len(members);best['members_sha256']=sha(json.dumps(members,separators=(',',':')).encode())
    return best

def atomic_certificate(s,k):
    best={'value':0}
    for p in s['work']:
        ds=sorted((s['d'][u] for u,o in s['compute'].items() if o['pipe']==p),reverse=True)
        for j,x in enumerate(ds,1):
            v=ceildiv(j,k)*x
            if v>best['value']:best={'value':v,'pipe':p,'j':j,'duration_threshold':x}
    return best

def write_csv(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--archive',required=True,type=Path);ap.add_argument('--out',required=True,type=Path);args=ap.parse_args()
    t0=time.perf_counter();args.out.mkdir(parents=True,exist_ok=True)
    raw=args.archive.read_bytes();assert len(raw)==ZIP_SIZE and sha(raw)==ZIP_SHA
    z=zipfile.ZipFile(io.BytesIO(raw));assert len(z.namelist())==104
    m=js(z.read('MANIFEST.json'));assert len(m['files'])==103
    for f in m['files']:
        b=z.read(f['path']);assert len(b)==f['bytes'] and sha(b)==f['sha256'],f['path']
    sm=js(z.read('docs/a/source-manifest.json'));fs={f['path']:f for f in sm['files']}
    code=sorted(f for f in fs if f.startswith('code/'))
    for p in code:
        b=z.read('data/raw/a/official/'+p);assert len(b)==fs[p]['bytes'] and sha(b)==fs[p]['sha256']
    official=sha(''.join(p+'\t'+fs[p]['sha256']+'\n' for p in code).encode());assert official==sm['official_code_hash']==m['official_sha256']
    config=sha(z.read('data/raw/a/official/data/config.txt'));assert config==m['config_sha256']==fs['data/config.txt']['sha256']
    czraw=z.read('data/raw/a/official-cases.zip');assert sha(czraw)==sm['case_archive']['sha256']
    cz=zipfile.ZipFile(io.BytesIO(czraw));assert len(cz.namelist())==100
    az=zipfile.ZipFile(io.BytesIO(z.read(PFX+'global-bounds-20260925/audit-snapshot.zip')))
    old_struct=js(az.read('structures.json'));bases=js(az.read('baselines.json'))
    old={(r['case_id'],int(r['cores'])):r for r in csv.DictReader(io.StringIO(z.read(PFX+'global-bounds-20260925/bounds.csv').decode('utf-8-sig')))}
    joined={(r['case_id'],int(r['cores'])):r for r in csv.DictReader(io.StringIO(z.read('derived/current-gap.csv').decode('utf-8-sig')))}
    rec={};feednames=sorted(n for n in z.namelist() if '/board-feed-s' in n and n.endswith('-revision2.json'))
    for fn in feednames:
        for r in js(z.read(fn))['records']:
            key=(r['case_id'],r['cores']);assert key not in rec
            assert r['solver_commit']==SOLVER and r['status']=='ok' and r['revision']==2 and r['problem']=='P3'
            assert r['evaluator']['route']=='E0'
            assert r['identity']['official_sha256']==official and r['identity']['config_sha256']==config
            for field in ['baseline','cache_pair']:
                assert all(r[field][a]==r['identity'][a] for a in ['graph_sha256','config_sha256','official_sha256'])
            assert r['cache_pair']['plan_sha256']==r['identity']['plan_sha256']==r['artifacts']['plan']['sha256']
            assert r['cache_pair']['cores']==r['cores'] and r['cache_pair']['route']=='E0'
            rec[key]=r
    assert len(rec)==len(old)==len(joined)==500
    cache_audit=js(z.read(PFX+'forest-cachepair-delta-20260925/independent-audit.json'))
    negatives={(r['case_id'],r['cores']):r for r in cache_audit['negative_gain_cells']}
    rows=[];proofs={};stats=[];baseline_sha_matches=0;allzero=[]
    for n in range(1,101):
        case=f'{n:03d}';b=cz.read(f'data/case_{case}.json');gh=sha(b)
        assert gh==fs[f'data/case_{case}.json']['sha256'] and len(b)==fs[f'data/case_{case}.json']['bytes']
        s=static_graph(js(b));os=old_struct[case]
        assert s['cp']==os['critical_path_cycles'] and dict(s['work'])==os['pipe_work_cycles']
        assert len(s['compute'])==os['compute_ops'] and s['contraction_extra']==os['extra_copy_contracted_edges']==[]
        oldpath=os['critical_path_ops'];assert sum(s['d'][u] for u in oldpath)==s['cp'] and all((u,v) in s['edges'] for u,v in zip(oldpath,oldpath[1:]))
        B=bases[case]['makespan_cycles'];assert bases[case]['graph_sha256']==gh and bases[case]['config_sha256']==config and bases[case]['official_sha256']==official
        proofs[case]={'graph_sha256':gh,'compute_ops':len(s['compute']),'pipe_work':dict(s['work']),'cp':s['cp'],'cp_path':s['path'],'certificates':{}}
        for k in range(1,6):
            key=(case,k);r=rec[key];o=old[key];j=joined[key];U=r['metrics']['makespan_cycles']
            assert r['identity']['graph_sha256']==gh
            L0=max(s['cp'],max(ceildiv(w,k) for w in s['work'].values()),max(s['d'].values()))
            assert int(o['lower_bound_cycles'])==L0 and int(o['official_baseline_cycles'])==B and int(j['published_global_lower_L'])==L0 and int(j['current_official_M3_U'])==U and int(j['baseline_B'])==B
            assert o['baseline_result_sha256']==r['baseline']['result']['sha256']==bases[case]['result']['sha256'];baseline_sha_matches+=1
            assert j['current_plan_sha256']==r['identity']['plan_sha256']
            for field,value in [('current_B_over_U',B/U),('relaxed_B_over_L',B/L0),('max_fraction_of_U_reduction',1-L0/U),('certified_ratio_if_L_valid',U/L0),('max_mean_speedup_contribution',(B/L0-B/U)/100)]:
                assert math.isclose(float(j[field]),value,rel_tol=1e-12,abs_tol=1e-12),(key,field)
            win=compute_window_certificate(s,k);atom=atomic_certificate(s,k)
            L=max(L0,win['value'],atom['value']);assert L<=U,(key,L,U)
            proofs[case]['certificates'][str(k)]={'old_L0':L0,'window':win,'atomic':atom,'global_integer_compute_L1':L}
            met=r['metrics'];neg=negatives.get(key)
            if neg:assert neg['p3_m']==U
            row={'case_id':case,'cores':k,'graph_sha256':gh,'config_sha256':config,'official_sha256':official,'solver_commit':SOLVER,'plan_sha256':r['identity']['plan_sha256'],
                 'B_published':B,'U_feed_M3':U,'CP':s['cp'],'work_M':s['work'].get('PIPE_M',0),'work_V':s['work'].get('PIPE_V',0),'L0_recomputed':L0,
                 'L_window':win['value'],'L_atomic':atom['value'],'L1_proved':L,'a':win['a'],'b':win['b'],'window_pipe':win['pipe'],'window_work':win['work_sum'],
                 'B_over_U':B/U,'B_over_L0':B/L0,'B_over_L1':B/L,'max_cycle_reduction_U_minus_L1':U-L,'max_time_fraction_reduction':1-L/U,'optimality_factor_at_most':U/L,
                 'mean_contribution_upper_L0':(B/L0-B/U)/100,'mean_contribution_upper_L1':(B/L-B/U)/100,
                 'scheduled_copy_bytes_feed':met['ddr_bytes'],'extra_copy_bytes_feed':met['extra_ddr_bytes'],'spill_bytes_feed':met['spill_bytes'],'case_byte_hit_rate_feed':met['cache_hit_rate'],
                 'solver_wall_seconds_feed':met['solver_wall_seconds'],'online_E0_calls_declared':r['provenance']['measurement']['calls']['E0'],
                 'same_plan_M2':neg['p2_m'] if neg else None,'CacheGain':neg['ratio'] if neg else None,'cache_pair_numeric_status':'published_negative_cell_summary' if neg else 'not_in_payload',
                 'U_evidence_scope':'hash-bound published successful E0 feed; raw result not in payload','B_evidence_scope':'published fixed baseline and matching hashes; raw baseline not in payload'}
            rows.append(row)
        stats.append({'case_id':case,'nodes':len(s['compute']),'components':len(s['components'])})
        if n%10==0:print(f'checked {n}/100 graphs; {len(rows)} cells; elapsed {time.perf_counter()-t0:.3f}s',flush=True)
    summary={'archive_size':len(raw),'archive_sha256':sha(raw),'zip_members':len(z.namelist()),'manifest_checked':len(m['files']),
             'official_code_files':len(code),'official_sha256':official,'config_sha256':config,'graphs':100,'compute_ops':sum(x['nodes'] for x in stats),
             'cells':len(rows),'baseline_hash_joins':baseline_sha_matches,'per_core':{},'author_cache_pair_summary':cache_audit['per_core'],
             'author_negative_cachegain_cells':cache_audit['negative_gain_cells'],
             'calls_this_audit':{'solver':0,'Task':0,'Step':0,'E0':0,'E1':0,'E2':0},
             'limitations':['No full500 raw P2/P3/baseline results in payload. B/U remain author E0 evidence, not locally revalidated E0.',
              'Compute-only L0,L1 use exact integers and are global under frozen atomic-compute semantics.',
              'The strongest interval-energy bound over (a,b) is searched over original-DAG thresholds only; this is certificate arithmetic, not candidate plan search.',
              'Per-cell M2/CacheGain unknown except four negative values printed in the author audit. Summary means are author values.',
              'Old L0/current-gap values are independently recomputed; new L1 is not an achievable schedule or convergence guarantee.']}
    for k in range(1,6):
        rr=[r for r in rows if r['cores']==k]
        means={key:float(sum((Fraction(r['B_published'],r[col]) for r in rr),Fraction())/100) for key,col in [('current_mean_B_U','U_feed_M3'),('old_mean_B_L0','L0_recomputed'),('new_mean_B_L1','L1_proved')]}
        exact_gap0=sum((Fraction(r['B_published'],r['L0_recomputed'])-Fraction(r['B_published'],r['U_feed_M3']) for r in rr),Fraction())/100
        exact_gap1=sum((Fraction(r['B_published'],r['L1_proved'])-Fraction(r['B_published'],r['U_feed_M3']) for r in rr),Fraction())/100
        means.update(old_headroom=float(exact_gap0),new_headroom=float(exact_gap1),strengthened_cells=sum(r['L1_proved']>r['L0_recomputed'] for r in rr),
                     extra_copy_sum=sum(r['extra_copy_bytes_feed'] for r in rr),spill_sum=sum(r['spill_bytes_feed'] for r in rr),scheduled_copy_sum=sum(r['scheduled_copy_bytes_feed'] for r in rr),
                     mean_case_byte_hit_rate=statistics.fmean(r['case_byte_hit_rate_feed'] for r in rr),
                     solver_wall_sum=sum(r['solver_wall_seconds_feed'] for r in rr),solver_wall_mean=statistics.fmean(r['solver_wall_seconds_feed'] for r in rr),
                     mean_CacheGain_author=cache_audit['per_core'][str(k)]['mean_p2_over_p3'],pooled_byte_hit_rate_author=cache_audit['per_core'][str(k)]['P3_byte_hit_rate_weighted'])
        ranked=sorted(rr,key=lambda r:(-r['mean_contribution_upper_L1'],r['case_id']))
        means['top10']=[{f:r[f] for f in ['case_id','B_published','U_feed_M3','L0_recomputed','L1_proved','B_over_U','B_over_L1','mean_contribution_upper_L1']} for r in ranked[:10]]
        means['top5_sum']=sum(r['mean_contribution_upper_L1'] for r in ranked[:5]);means['top10_sum']=sum(r['mean_contribution_upper_L1'] for r in ranked[:10]);means['top20_sum']=sum(r['mean_contribution_upper_L1'] for r in ranked[:20])
        summary['per_core'][str(k)]=means
    walls=sorted(r['solver_wall_seconds_feed'] for r in rows)
    summary['wall_feed']={'sum':sum(walls),'mean':statistics.fmean(walls),'median':statistics.median(walls),'p95_nearest_rank':walls[math.ceil(.95*len(walls))-1],'max':max(walls),'scope':'500 heterogeneous author observations; shared host; integrated E0 included'}
    summary['online_calls_feed']=sum(r['online_E0_calls_declared'] for r in rows)
    summary['static_audit_wall_seconds']=time.perf_counter()-t0
    write_csv(args.out/'cells_500.csv',rows);dump(args.out/'proofs_100.json',proofs);dump(args.out/'audit_summary.json',summary)
    # Full table in ordinary Markdown for readers without spreadsheet tooling.
    lines=['# 100图×1–5核：U / 新全局计算下界 L1','',
           'U来自固定统一算法feed；L1为本脚本原DAG整数证书。每格 U / L1。完整比值和字节指标见cells_500.csv。','',
           '| 图 | 1核 | 2核 | 3核 | 4核 | 5核 |','|---|---:|---:|---:|---:|---:|']
    for n in range(1,101):
        rr=[r for r in rows if r['case_id']==f'{n:03d}'];lines.append('| '+f'{n:03d}'+' | '+' | '.join(f"{r['U_feed_M3']} / {r['L1_proved']}" for r in rr)+' |')
    (args.out/'all_100_cases.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps({'per_core':{k:{a:b for a,b in v.items() if a!='top10'} for k,v in summary['per_core'].items()},'wall':summary['static_audit_wall_seconds']},indent=2))

if __name__=='__main__':main()
