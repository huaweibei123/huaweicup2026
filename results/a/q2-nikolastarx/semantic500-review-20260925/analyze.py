"""Recompute full-matrix and paired statistics from captured immutable inputs.

No external commands, scoring, Git or network. Quantiles use linear
interpolation at (n-1)*q. Output goes to a new directory to preserve reports.
"""
from pathlib import Path
from collections import Counter
import argparse,csv,gzip,hashlib,json,math,statistics
HERE=Path(__file__).resolve().parent

def quantile(values,p):
 a=sorted(values);i=(len(a)-1)*p;lo=math.floor(i);hi=math.ceil(i);return a[lo]+(a[hi]-a[lo])*(i-lo)
def stats(a):return {'n':len(a),'mean':statistics.mean(a),'min':min(a),'p50':quantile(a,.5),'p90':quantile(a,.9),'p95':quantile(a,.95),'p99':quantile(a,.99),'max':max(a),'sum':sum(a)}
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main(out):
 out.mkdir(exist_ok=False)
 capture=json.loads((HERE/'CAPTURE.json').read_text());packed=(HERE/'semantic-feed-500.json.gz').read_bytes();raw=gzip.decompress(packed)
 assert hashlib.sha256(raw).hexdigest()==capture['semantic_feed_raw_sha256']
 assert hashlib.sha256(packed).hexdigest()==capture['semantic_feed_gzip_sha256']
 feed=json.loads(raw)['records'];base=json.loads((HERE/'official-baselines-100.json').read_text());fang=json.loads((HERE/'fang-verified-100.json').read_text())
 assert len(feed)==500 and len(fang)==100 and len(base)==100
 rows=[]
 for r in feed:
  case=r['case_id'];b=base[case];assert r['baseline']['result']==b['result']
  rows.append({'case':case,'cores':r['cores'],'route':r['parameters']['adaptive_route'],'status':r['status'],**r['metrics'],'official_A_baseline':b['makespan'],'speedup':b['makespan']/r['metrics']['makespan_cycles']})
 bycore={}
 for k in range(1,6):
  a=[r for r in rows if r['cores']==k];assert len(a)==100 and len({r['case'] for r in a})==100
  bycore[str(k)]={'count':100,'arithmetic_mean_B_over_M':statistics.mean(r['speedup'] for r in a),'speedup_distribution':stats([r['speedup'] for r in a]),
                 'quality_vs_official_A':dict(Counter('win' if r['speedup']>1 else 'loss' if r['speedup']<1 else 'tie' for r in a)),
                 'solver_wall_seconds':stats([r['solver_wall_seconds'] for r in a]),'ddr_bytes':stats([r['ddr_bytes'] for r in a]),
                 'extra_ddr_bytes':stats([r['extra_ddr_bytes'] for r in a]),'spill_bytes':stats([r['spill_bytes'] for r in a]),'spill_nonzero':sum(r['spill_bytes']>0 for r in a),'routes':dict(Counter(r['route'] for r in a))}
 allstats={k:stats([r[k] for r in rows]) for k in ('makespan_cycles','solver_wall_seconds','evaluation_wall_seconds','ddr_bytes','extra_ddr_bytes','spill_bytes')}
 route_stats={}
 for route in sorted({r['route'] for r in rows}):
  a=[r for r in rows if r['route']==route];route_stats[route]={'cells':len(a),'graphs':len({r['case'] for r in a}),'spill_cells':sum(r['spill_bytes']>0 for r in a),'spill_sum':sum(r['spill_bytes'] for r in a),'extra_sum':sum(r['extra_ddr_bytes'] for r in a),'solver_wall_mean':statistics.mean(r['solver_wall_seconds'] for r in a)}
 o4={r['case']:r for r in rows if r['cores']==4};pairs=[]
 for f in fang:
  o=o4[f['case_id']];B=o['official_A_baseline'];assert B==f['baseline_cycles']
  pairs.append({'case':o['case'],'route':o['route'],'baseline':B,'ours_makespan':o['makespan_cycles'],'fang_makespan':f['makespan_cycles'],
                'ours_speedup':o['speedup'],'fang_speedup':B/f['makespan_cycles'],'ours_over_fang':o['makespan_cycles']/f['makespan_cycles'],
                'mean_delta_contribution':(o['speedup']-B/f['makespan_cycles'])/100,'quality':'win' if o['makespan_cycles']<f['makespan_cycles'] else 'loss' if o['makespan_cycles']>f['makespan_cycles'] else 'tie',
                'ours_ddr':o['ddr_bytes'],'fang_ddr':f['ddr_bytes'],'ours_extra':o['extra_ddr_bytes'],'fang_extra':f['extra_ddr_bytes'],
                'ours_spill':o['spill_bytes'],'fang_spill':f['spill_bytes'],'ours_wall':o['solver_wall_seconds'],'fang_wall':f['solver_wall_seconds'],
                'fang_run_path':f['run_path'],'fang_run_sha256':f['run_sha256'],'fang_result_sha256':f['result_sha256']})
 pairgroups={}
 for route in sorted({r['route'] for r in pairs}):
  a=[r for r in pairs if r['route']==route];pairgroups[route]={'n':len(a),'quality':dict(Counter(r['quality'] for r in a)),'full100_mean_delta_contribution':sum(r['mean_delta_contribution'] for r in a),'ours_spill':sum(r['ours_spill'] for r in a),'fang_spill':sum(r['fang_spill'] for r in a)}
 fangstats={'source':capture['fang_source_commit'],'data':capture['fang_data_commit'],'ours_mean':bycore['4']['arithmetic_mean_B_over_M'],
            'fang_mean':statistics.mean(r['fang_speedup'] for r in pairs),'delta_mean':sum(r['mean_delta_contribution'] for r in pairs),'quality':dict(Counter(r['quality'] for r in pairs)),
            'route_groups':pairgroups,'largest_losses':sorted(pairs,key=lambda r:r['mean_delta_contribution'])[:15],'largest_gains':sorted(pairs,key=lambda r:r['mean_delta_contribution'],reverse=True)[:15],
            'posthoc_pairwise_winner_mean':statistics.mean(max(r['ours_speedup'],r['fang_speedup']) for r in pairs),
            'posthoc_limit':'A per-case mixed envelope only; not a runnable selector or one algorithm score.',
            'wall_comparison_limit':'Our Apple M5 Pro/macOS and Fang AMD Ryzen 5 5600H/Windows were different machines and loads; no causal speed claim.',
            'fang_environments':dict(Counter(f['environment']['os']+'; '+f['environment']['cpu'] for f in fang)),
            'fang_successful100_solver_wall_seconds':stats([f['solver_wall_seconds'] for f in fang]),
            'fang_included_batch_costs':json.loads((HERE/'fang-coverage.json').read_text())['measured_calls_in_included_batches']}
 own1={r['case']:r for r in rows if r['cores']==1}
 regressions=[{**r,'own_k1':own1[r['case']]['makespan_cycles'],'multi_over_own_k1':r['makespan_cycles']/own1[r['case']]['makespan_cycles']} for r in rows if r['cores']>1 and r['makespan_cycles']>own1[r['case']]['makespan_cycles']]
 targets={2:2.26,3:3.18,4:3.96,5:4.53}
 result={'input':capture,'by_core':bycore,'all500':allstats,'route_groups':route_stats,'fang_k4':fangstats,
         'worst_k5':sorted([r for r in rows if r['cores']==5],key=lambda r:r['speedup'])[:15],
         'most_spill':sorted(rows,key=lambda r:r['spill_bytes'],reverse=True)[:15],'slowest_solver':sorted(rows,key=lambda r:r['solver_wall_seconds'],reverse=True)[:15],
         'own_k1_quality_losses':[r for r in rows if r['cores']==1 and r['speedup']<1],
         'multi_worse_than_own_k1':regressions,'target_gaps':{str(k):{'external_unverified_target':v,'actual':bycore[str(k)]['arithmetic_mean_B_over_M'],'absolute_gap':v-bycore[str(k)]['arithmetic_mean_B_over_M']} for k,v in targets.items()},
         'definitions':{'mean':'1/100 sum_i official_A_singlecore_M_i / solver_P2_M_i,k; not ratio of totals or algorithm k1 denominator.',
                        'percentiles':'linear interpolation at index (n-1)*p','success':'Existing E0-backed successful artifact; distinct from competitive quality or optimality.',
                        'whole500_wall':'Sum of 500 per-cell solver walls is aggregate work, not elapsed throughput or exclusive latency.'}}
 write(out/'statistics.json',result)
 for name,rs in [('all500.csv',rows),('fang-k4-pairs.csv',pairs)]:
  with (out/name).open('w',newline='',encoding='utf8') as f:
   w=csv.DictWriter(f,fieldnames=list(rs[0]),lineterminator='\n');w.writeheader();w.writerows(rs)
  assert b'\r' not in (out/name).read_bytes()
 print(json.dumps({'means':{k:v['arithmetic_mean_B_over_M'] for k,v in bycore.items()},'fang':{k:fangstats[k] for k in ('ours_mean','fang_mean','delta_mean','quality','posthoc_pairwise_winner_mean')},'route_pair_groups':pairgroups,'multi_worse_own_k1':len(regressions)},ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);main(p.parse_args().output)
