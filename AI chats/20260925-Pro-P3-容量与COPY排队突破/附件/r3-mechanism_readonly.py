#!/usr/bin/env python3
"""Read-only audit of SAVED 044 results and frozen source AST. No official imports/calls.
Usage: python mechanism_readonly.py --archive q3-theoretical-bound-r3.zip --out audit-output
"""
from __future__ import annotations
import argparse, ast, collections, gzip, hashlib, io, json, time, zipfile
from pathlib import Path

def sha(x): return hashlib.sha256(x).hexdigest()
def js(x): return json.loads(x)
def out(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def ops(r):
    ans={}
    for c in r['per_core_timeline']:
        for o in c['ops']:
            key=c['core_id'],o['op_id']; assert key not in ans
            assert o['end']>=o['start'] and o['duration']==o['end']-o['start']
            ans[key]=o
    assert max(x['end'] for x in ans.values())==r['makespan']
    return ans

def pipe_words(r):
    words={}
    for c in r['per_core_timeline']:
        for p in ['PIPE_M','PIPE_V','PIPE_MTE2','PIPE_MTE3']:
            seq=sorted((o for o in c['ops'] if o['pipe']==p),key=lambda o:(o['start'],o['end'],o['op_id']))
            assert all(a['end']<=b['start'] for a,b in zip(seq,seq[1:]))
            words[c['core_id'],p]=[o['op_id'] for o in seq]
    return words

def cache(r):
    reads=[e for e in r['cache_events'] if e['event'] in ('hit','miss')]
    counts=collections.Counter();sizes={}; first_miss=repeat_hit=repeat_miss=0; hb=mb=0
    for e in reads:
        t=e['tensor_id']; b=e['size_bytes']
        assert t not in sizes or sizes[t]==b
        sizes[t]=b
        if not counts[t]: assert e['event']=='miss'; first_miss+=b
        elif e['event']=='hit':repeat_hit+=b
        else: repeat_miss+=b
        if e['event']=='hit':hb+=b
        else:mb+=b
        counts[t]+=1
    assert hb==r['cache_stats']['hit_bytes'] and mb==r['cache_stats']['miss_bytes']
    hit_cap=sum((n-1)*sizes[t] for t,n in counts.items())
    return {'accesses':len(reads),'unique_keys':len(counts),'hit_bytes':hb,'miss_bytes':mb,
        'first_miss_bytes':first_miss,'repeat_hit_bytes':repeat_hit,'repeat_miss_bytes':repeat_miss,
        'fixed_multiset_hit_upper':hit_cap,'byte_hit_rate':hb/(hb+mb),
        'eviction_events':sum(e['event'] in ('evict','eviction') for e in r['cache_events']),
        'read_multiset':sorted((t,sizes[t],n) for t,n in counts.items())}

def main():
    a=argparse.ArgumentParser(description=__doc__); a.add_argument('--archive',type=Path,required=True);a.add_argument('--out',type=Path,required=True);args=a.parse_args()
    t0=time.perf_counter();raw=args.archive.read_bytes();assert sha(raw)=='9d50a4260ff72981ea902c115cd39aa109f6fc8f88ee69ae0c0e9f759295ea4f'
    z=zipfile.ZipFile(io.BytesIO(raw)); pref='results/a/q3-nikolastarx/partial-preload-linux-20260925T0603Z/receipt-public/'
    checks=js(z.read(pref+'SHA256SUMS.json'));checked=[];notprovided=[]
    for p,s in checks.items():
        if pref+p in z.namelist(): assert sha(z.read(pref+p))==s;checked.append(p)
        else:notprovided.append(p)
    results={}
    for key,name in [('candidate_p2','candidate-p2.json.gz'),('candidate_p3','candidate-p3.json.gz'),('control_p2','control-p2.json.gz'),('control_p3','reused-full-prefix-044-p3.json.gz')]:
        r=js(gzip.decompress(z.read(pref+'artifacts/'+name)));results[key]=r
        assert r['num_cores']==5 and r['capacity_bytes']=={'L1':524288,'UB':131072}
        assert r['bandwidth_bytes_per_cycle']==60 and r['cross_core_copy_delay_cycles']==500
        ops(r);pipe_words(r)
    plans={key:js(z.read(pref+'artifacts/'+name+'-case_044_multicore_res.json')) for key,name in [('candidate','candidate'),('control','control')]}
    cz=zipfile.ZipFile(io.BytesIO(z.read('data/raw/a/official-cases.zip')));g=js(cz.read('data/case_044.json'));co={o['id']:o for o in g['ops'] if o['op'] not in {'COPY_IN','COPY_OUT'}}
    owners={};compute_words={}
    for name,p in plans.items():
        assert set(p)=={'node_to_subgraph','core_schedules'} and len(p['core_schedules'])==5
        mapping={int(u):s for u,s in p['node_to_subgraph'].items()};assert set(mapping)==set(co)
        sg_owner={s:c for c,seq in enumerate(p['core_schedules']) for s in seq}
        assert len(sg_owner)==sum(map(len,p['core_schedules'])) and set(sg_owner)==set(mapping.values())
        owners[name]={u:sg_owner[s] for u,s in mapping.items()}
        compute_words[name]={(c,pipe):[oid for oid in pipe_words(results[name+'_p3'])[c,pipe] if oid in co] for c in range(5) for pipe in ['PIPE_M','PIPE_V']}
        rops=ops(results[name+'_p3'])
        for u,o in co.items():
            observed=rops[owners[name][u],u];assert observed['op']==o['op'] and observed['pipe']==o['pipe'] and observed['duration']==max(1,o['cycles'])
    assert owners['candidate']==owners['control'] and compute_words['candidate']==compute_words['control']
    paired={}
    for name in ('control','candidate'):
        r2,r3=results[name+'_p2'],results[name+'_p3'];o2,o3=ops(r2),ops(r3)
        assert set(o2)==set(o3) and pipe_words(r2)==pipe_words(r3)
        assert r2['data_movement_bytes']==r3['data_movement_bytes']
        paired[name]={'M2':r2['makespan'],'M3':r3['makespan'],'G':r2['makespan']/r3['makespan'],
            'ops':len(o3),'timeline_equal':all((o2[k]['start'],o2[k]['end'])==(o3[k]['start'],o3[k]['end']) for k in o2),
            'movement':r3['data_movement_bytes'],'cache':cache(r3),
            'step3_memory_dependency_counts':{k:v['memory_dependency_count'] for k,v in r3['step3_by_core'].items()}}
        for x in r3['cross_core_transfers']:
            assert x['copy_in_release']==x['copy_out_end']+500 and x['copy_in_start']>=x['copy_in_release']
    assert paired['candidate']['cache']['read_multiset']==paired['control']['cache']['read_multiset']
    assert paired['candidate']['movement']==paired['control']['movement']
    w0,w1=pipe_words(results['control_p3']),pipe_words(results['candidate_p3'])
    diffwords=[{'core':c,'pipe':p,'first_difference':next(i for i,(u,v) in enumerate(zip(w0[c,p],w1[c,p])) if u!=v)} for c,p in w0 if w0[c,p]!=w1[c,p]]
    coretimes=[]
    for c in range(5):
        row={'core':c}
        for name in ('control','candidate'):
            oo=[o for (cc,u),o in ops(results[name+'_p3']).items() if cc==c]
            row[name+'_first_compute']=min(o['start'] for o in oo if o['op_id'] in co)
            row[name+'_end']=max(o['end'] for o in oo)
        coretimes.append(row)
    base=js(gzip.decompress(z.read(pref+'artifacts/044-baseline-result.json.gz')));assert base['makespan']==154407
    # AST parsing, not importing/executing the official builders.
    sources={i:ast.parse(z.read(f'data/raw/a/official/code/multicore_cut_evaluate_problem_{i}.py')) for i in [2,3]}
    def function(i,name):
        n=next(n for n in sources[i].body if isinstance(n,ast.FunctionDef) and n.name==name)
        if n.body and isinstance(n.body[0],ast.Expr) and isinstance(n.body[0].value,ast.Constant) and isinstance(n.body[0].value.value,str):n.body=n.body[1:]
        return ast.dump(n,include_attributes=False)
    common={name:function(2,name)==function(3,name) for name in ['_prioritize_task_seq','_build_scene_b_tasks']}
    assert all(common.values())
    receipt=js(z.read(pref+'artifacts/run-public.json'))
    report={'scope':'all saved 044 operation records, cache events, plan byte hashes and original compute identities parsed; NOT an official reevaluation or Task validation',
        'sha256_receipt_files_checked':checked,'sha256_receipt_references_not_in_package':notprovided,
        'original_compute_ops':len(co),'total_saved_operation_records':sum(len(ops(r)) for r in results.values()),
        'original_compute_ownership_and_MV_FIFO_preserved':True,'changed_pipe_words':diffwords,'paired':paired,'core_times':coretimes,
        'baseline_B':base['makespan'],'M_reduction':paired['control']['M3']-paired['candidate']['M3'],
        'M_reduction_fraction':1-paired['candidate']['M3']/paired['control']['M3'],
        'P2_P3_frontend_AST_identical_excluding_docstrings':common,
        'author_execution_ledger':receipt['phase_ledger'],'solver_wall_seconds':receipt['solver_wall_seconds'],
        'our_official_or_solver_calls':0,'static_audit_wall_seconds':time.perf_counter()-t0}
    args.out.mkdir(parents=True,exist_ok=True);out(args.out/'mechanism_audit.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ['paired']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
