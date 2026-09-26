#!/usr/bin/env python3
"""P2 R4: independently recompute saved-data arithmetic, with exact fractions.
Usage: python r4_saved_audit.py EXTRACTED_R4_DIRECTORY OUTPUT_DIRECTORY
No official evaluator, constructor, solver, network or third-party imports.
The saved summary's baseline.makespan is NOT the fixed official A denominator.
This verifies stored identities/arithmetic, not the absent original graphs,
plans, raw E0 files, or an unproved floating-point DDR-service bound.
"""
from __future__ import annotations
import argparse, csv, hashlib, json
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
from statistics import median

BOUNDS='results/a/q2-nikolastarx/goal-20260924/global-bounds.json'
SUMMARY='results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json'
BASELINE='results/a/q2-yuanzhifang/feedback-20260924/full-coverage/all500/per-cell.csv'
DDR='results/a/q2-nikolastarx/secondary-ddr-full500-20260925/report.json'
CONFIG='data/raw/a/official/data/config.txt'

def require(ok, message):
    if not ok: raise ValueError(message)

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(r,p): return json.loads((r/p).read_bytes())
def readcsv(r,p):
    with (r/p).open(encoding='utf-8', newline='') as f: return list(csv.DictReader(f))
def avg(xs):
    xs=list(xs);return sum(xs,F(0))/len(xs)
def plain(x):
    if isinstance(x,F): return float(x)
    if isinstance(x,dict): return {k:plain(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [plain(v) for v in x]
    return x

def writecsv(p,rows):
    if not rows: return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader()
        for row in rows: w.writerow(plain(row))

def nearest(xs,p):
    xs=sorted(xs);return xs[(len(xs)*p+99)//100-1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('root',type=Path);ap.add_argument('output',type=Path)
    a=ap.parse_args();r=a.root.resolve();out=a.output.resolve()
    require(r!=out and not r.is_relative_to(out),'Use a separate output directory')
    out.mkdir(parents=True,exist_ok=True)
    manifest=load(r,'MANIFEST.json'); entries={e['path']:e for e in manifest['entries']}
    for e in entries.values():
        p=r/e['path'];require(p.stat().st_size==e['bytes'] and sha(p)==e['sha256'],'Manifest mismatch: '+e['path'])
    bounds=load(r,BOUNDS);summ=load(r,SUMMARY);ddr=load(r,DDR)
    for name,digest in bounds['official_source_sha256'].items():
        require(sha(r/'data/raw/a/official/code'/name)==digest,'Official source identity mismatch: '+name)
    require(sha(r/'src/q2_nikolastarx/global_bounds.py')==bounds['certificate_source_sha256'],'Bound generator hash mismatch')
    expected={(f'{i:03d}',k) for i in range(1,101) for k in range(1,6)}
    aa={}
    for x in readcsv(r,BASELINE):
        key=(x['case_id'],int(x['cores']));require(key not in aa,'Duplicate A coordinate');aa[key]=int(x['baseline_cycles'])
    require(set(aa)==expected,'A coverage')
    for i in range(1,101): require(len({aa[f'{i:03d}',k] for k in range(1,6)})==1,'A differs across k')
    cert={};witness=Counter()
    for g in bounds['records']:
        case=Path(g['graph_file']).stem.split('_')[-1]
        require(g['supported'] and g['precedence_supported'] and not g['multiple_eligible_producer_tensor_ids'],'Saved proof-domain flag fails')
        for b in g['by_core_count']:
            k=b['cores'];key=(case,k);require(key not in cert,'Duplicate bound coordinate')
            components=[g['retained_compute_critical_path_cycles']]
            for p,w in b['pipe_load_bounds'].items():
                val=w['cycles'];components.append(val);work=g['pipe_work'][p]
                require(val>=(work+k-1)//k,'Load weaker than reported work/k')
                if w['kind']=='total_work': require(val==(work+k-1)//k,'Work arithmetic')
                else: require(w['largest_jobs']==(w['jobs_on_one_core']-1)*k+1 and val==w['smallest_q_sum'],'Packing witness arithmetic')
                witness[w['kind']]+=1
            for p,w in b['pipe_window_bounds'].items():
                components.append(w['cycles'])
                if w['cycles']:
                    require(w['cycles']==w['threshold']+(w['selected_pipe_work']+k-1)//k+w['minimum_other'],'Window arithmetic')
                    require(w['selected_pipe_work']<=g['pipe_work'][p],'Window work exceeds total')
                    witness['nonempty_window']+=1
            require(max(components)==b['makespan_lower_bound_cycles'],'Max-composition arithmetic')
            cert[key]=(g,b)
    require(set(cert)==expected,'Bound coverage')
    rows=[];seen=set();cfgsha=sha(r/CONFIG)
    for x in summ['rows']:
        key=(x['case'],x['cores']);require(key not in seen,'Duplicate result');seen.add(key)
        g,b=cert[key]
        require(x['status']=='accepted' and x['solver_process']['status']=='ok' and x['e0_process']['status']=='ok','Saved result not successful')
        require(x['graph_sha256']==g['graph_sha256'] and x['config_sha256']==cfgsha,'Graph/config identity mismatch')
        A=aa[key];L=b['makespan_lower_bound_cycles'];U=x['official']['makespan'];k=key[1]
        require(0<L<=U and A>0,'Invalid L/U/A arithmetic')
        d=x['official']['movement'];m=g['mandatory_boundary_io']
        require(d['scheduled_copy_bytes']-d['original_graph_copy_bytes']==d['added_copy_bytes']==d['partition_added_copy_bytes']+d['spill_added_copy_bytes'],'COPY decomposition mismatch')
        count=max((g['pipe_work']['PIPE_MTE2']+m['input_tensor_count']+k-1)//k,
                  (g['pipe_work']['PIPE_MTE3']+m['output_tensor_count']+k-1)//k)
        rows.append({'case':key[0],'cores':k,'A':A,'L':L,'U':U,'speedup':F(A,U),'speedup_ceiling':F(A,L),
          'speedup_gap':F(A,L)-F(A,U),'mean_gap_contribution':(F(A,L)-F(A,U))/100,
          'makespan_reduction_cap_pct':100*F(U-L,U),'speedup_relative_gain_cap_pct':100*(F(U,L)-1),
          'within_1pct':100*U<=101*L,'within_5pct':20*U<=21*L,'within_10pct':10*U<=11*L,'exact':U==L,
          'boundary_event_count_bound':count,'count_strengthened_L':max(L,count),
          'scheduled_copy_bytes':d['scheduled_copy_bytes'],'extra_ddr_bytes':d['added_copy_bytes'],'spill_bytes':d['spill_added_copy_bytes'],
          'solver_wall_seconds_saved':x['solver_process']['wall_seconds'],'E0_wall_seconds_saved':x['e0_process']['wall_seconds'],
          'graph_sha256':x['graph_sha256'],'config_sha256':cfgsha,'plan_sha256':x['plan_sha256'],'result_sha256':x['official']['result_sha256'],
          'A_source_url':entries[BASELINE]['url'],'L_source_url':entries[BOUNDS]['url'],'U_source_url':entries[SUMMARY]['url']})
    require(seen==expected,'Current result coverage');rows.sort(key=lambda x:(x['cores'],x['case']));bykey={(x['case'],x['cores']):x for x in rows}
    derived=readcsv(r,'DERIVED/gap-cells.csv');require(len(derived)==500 and {(x['case'],int(x['cores'])) for x in derived}==expected,'DERIVED coverage')
    differences=[]
    for d in derived:
        x=bykey[d['case'],int(d['cores'])]
        for a,b in [('baseline_cycles','A'),('lower_bound_cycles','L'),('makespan_cycles','U')]: require(int(d[a])==x[b],'DERIVED integer mismatch')
        for a,b in [('speedup','speedup'),('speedup_ceiling','speedup_ceiling'),('possible_speedup_gain','speedup_gap'),('possible_relative_makespan_reduction_pct','makespan_reduction_cap_pct'),('relative_suboptimality_upper_bound_pct','speedup_relative_gain_cap_pct')]:
            err=abs(float(d[a])-float(x[b]));differences.append(err);require(err<1e-10,'DERIVED ratio mismatch')
    agg=[]
    for k in range(1,6):
        xs=[x for x in rows if x['cores']==k];s=avg(x['speedup'] for x in xs);c=avg(x['speedup_ceiling'] for x in xs)
        agg.append({'cores':k,'n':100,'mean_speedup':s,'mean_ceiling':c,'mean_gap':c-s,
          'relative_mean_speedup_gain_cap_pct':100*(c/s-1),
          'mean_per_case_makespan_reduction_cap_pct':avg(x['makespan_reduction_cap_pct'] for x in xs),
          'median_per_case_makespan_reduction_cap_pct':median(x['makespan_reduction_cap_pct'] for x in xs),
          'mean_per_case_speedup_gain_cap_pct':avg(x['speedup_relative_gain_cap_pct'] for x in xs),
          'median_per_case_speedup_gain_cap_pct':median(x['speedup_relative_gain_cap_pct'] for x in xs),
          'near_1pct_count':sum(x['within_1pct'] for x in xs),'near_5pct_count':sum(x['within_5pct'] for x in xs),
          'near_10pct_count':sum(x['within_10pct'] for x in xs),'exact_count':sum(x['exact'] for x in xs)})
    k5=sorted([dict(x) for x in rows if x['cores']==5],key=lambda x:(-x['speedup_gap'],x['case']));total=sum(x['speedup_gap'] for x in k5)
    for i,x in enumerate(k5,1): x.update(rank=i,share_of_k5_gap_pct=100*x['speedup_gap']/total)
    dist=[];edges=[0,1,5,10,25,50,100,None]
    for lo,hi in zip(edges,edges[1:]):
        xs=[x for x in k5 if x['speedup_relative_gain_cap_pct']>lo and (hi is None or x['speedup_relative_gain_cap_pct']<=hi)]
        part=sum((x['speedup_gap'] for x in xs),F(0))
        dist.append({'U_over_L_minus_1_pct_interval':f'({lo},{hi if hi is not None else "inf"}]','count':len(xs),'mean_gap_contribution':part/100,'share_of_gap_pct':100*part/total,'cases':','.join(x['case'] for x in xs)})
    paired=Counter();totals=Counter();ds=set()
    for x in ddr['cells']:
        key=(x['case'],x['cores']);require(key not in ds,'Duplicate DDR coordinate');ds.add(key);z=bykey[key]
        require(x['new_makespan']==z['U'] and x['new_extra']==z['extra_ddr_bytes'] and x['new_spill']==z['spill_bytes'],'DDR/current disagreement')
        cmp=lambda a,b:'improved' if a<b else ('same' if a==b else 'regressed')
        paired[cmp(x['new_makespan'],x['old_makespan'])+'_M__'+cmp(x['new_extra'],x['old_extra'])+'_DDR']+=1
        for f in ('old_extra','new_extra','old_spill','new_spill','old_partition','new_partition'):totals[f]+=x[f]
    require(ds==expected and dict(paired)==ddr['all500']['comparison'] and dict(totals)==ddr['all500']['totals_bytes'],'DDR aggregate disagreement')
    results={'scope':'Saved arithmetic and stored certificate metadata only; no raw-graph recertification; zero evaluator/constructor calls.',
      'manifest_entries_checked':len(entries),'coverage':500,'source_hashes':{p:sha(r/p) for p in ('MANIFEST.json',BOUNDS,SUMMARY,BASELINE,DDR,CONFIG)},
      'witness_arithmetic_checks':dict(witness),'max_abs_difference_from_DERIVED':max(differences),
      'by_core':agg,'k5_top_gap_shares_pct':{str(n):100*sum(x['speedup_gap'] for x in k5[:n])/total for n in (5,10,20)},
      'k5_near_1pct_cases':sorted(x['case'] for x in k5 if x['within_1pct']),
      'k5_near_5pct_cases':sorted(x['case'] for x in k5 if x['within_5pct']),
      'k5_distribution':dist,'k5_top10':k5[:10],'safe_boundary_count_improved_cells':sum(x['count_strengthened_L']>x['L'] for x in rows),
      'new_full_augmented_event_bound':'NOT COMPUTED: original graph incidences absent',
      'paired_M_DDR':dict(paired),'DDR_totals':dict(totals),'DDR_total_growth_pct':100*F(totals['new_extra']-totals['old_extra'],totals['old_extra']),
      'saved_solver_wall_seconds':{'mean':sum(x['solver_wall_seconds_saved'] for x in rows)/500,'p95_nearest_rank':nearest([x['solver_wall_seconds_saved'] for x in rows],95),'max':max(x['solver_wall_seconds_saved'] for x in rows)},
      'warnings':['Raw graphs, raw E0 and plans were not supplied/revalidated.','Certificate scalar witnesses are not standalone original-graph proof objects.','summary.baseline.makespan must not replace official A.','No previous floating-point DDR lemma accepted.']}
    writecsv(out/'r4-cells.csv',rows);writecsv(out/'r4-by-core.csv',agg);writecsv(out/'r4-k5-ranked.csv',k5);writecsv(out/'r4-k5-distribution.csv',dist)
    (out/'r4-audit.json').write_text(json.dumps(plain(results),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(plain({k:results[k] for k in ('coverage','by_core','k5_top_gap_shares_pct','paired_M_DDR','DDR_total_growth_pct','safe_boundary_count_improved_cells')}),indent=2))

if __name__=='__main__': main()
