import json,statistics,math,csv
from pathlib import Path
root=Path('/mnt/data/r2_research');rows=json.loads((root/'runs/paired/summary.json').read_text());out=[]
for b in rows:
 if b['policy']!='baseline':continue
 s=next(r for r in rows if (r['case'],r['problem'],r['cores'],r['policy'])==(b['case'],b['problem'],b['cores'],'structured'))
 def hist(r):
  return json.loads((root/'runs/paired'/f"case_{r['case']:03d}_p{r['problem']}_k{r['cores']}_{r['policy']}"/'history.json').read_text())
 bh,sh=hist(b),hist(s);sh=[r for r in sh if 'official_cli_seconds' in r];bh=[r for r in bh if 'official_cli_seconds' in r]
 commoncalls=min(len(sh),len(bh));horizon=min(b['elapsed_seconds'],s['elapsed_seconds'])
 def best(rs):return min((r['makespan'] for r in rs if r['status']=='ok'),default=None)
 sbest_at_calls=best(sh[:commoncalls]);bbest_at_calls=best(bh[:commoncalls])
 sbest_at_time=best([r for r in sh if r['elapsed_seconds']<=horizon]);bbest_at_time=best([r for r in bh if r['elapsed_seconds']<=horizon])
 first_s=next(r['elapsed_seconds'] for r in sh if r.get('makespan')==s['best_makespan']);first_b=next(r['elapsed_seconds'] for r in bh if r.get('makespan')==b['best_makespan'])
 r={'case':b['case'],'problem':b['problem'],'cores':b['cores'],'baseline':b['best_makespan'],'structured':s['best_makespan'],'reduction_pct':100*(1-s['best_makespan']/b['best_makespan']),'speedup_ratio':b['best_makespan']/s['best_makespan'],'baseline_name':b['best_name'],'structured_name':s['best_name'],'baseline_calls':b['calls'],'structured_calls':s['calls'],'baseline_wall':b['process_wall_seconds'],'structured_wall':s['process_wall_seconds'],'baseline_time_to_best':first_b,'structured_time_to_best':first_s,'common_call_prefix':commoncalls,'baseline_at_common_calls':bbest_at_calls,'structured_at_common_calls':sbest_at_calls,'common_internal_time_horizon':horizon,'baseline_at_common_time':bbest_at_time,'structured_at_common_time':sbest_at_time,'global_lower_bound':s['lower_bound'],'structured_gap_upper_bound':s['gap_upper_bound'],'statuses_baseline':{st:sum(x['status']==st for x in bh) for st in sorted({x['status'] for x in bh})},'statuses_structured':{st:sum(x['status']==st for x in sh) for st in sorted({x['status'] for x in sh})}}
 out.append(r)
summary={'pairs':out,'note':'Same 60-second/24-evaluation caps, finite B0 may exhaust earlier; exploratory follow-up, not sealed or cross-family validation. Time-prefix comparisons use internal clock; complete cold process wall is also recorded.','max_process_wall_seconds':max(r['process_wall_seconds'] for r in rows),'strict_improvements':sum(r['structured']<r['baseline'] for r in out),'ties':sum(r['structured']==r['baseline'] for r in out),'regressions':sum(r['structured']>r['baseline'] for r in out),'paired_geomean_makespan_ratio':math.exp(statistics.mean(math.log(r['speedup_ratio']) for r in out))}
(root/'analysis/paired_comparison.json').write_text(json.dumps(summary,indent=2))
with (root/'analysis/paired_comparison.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
for r in out:print(r['case'],r['problem'],r['baseline'],r['structured'],round(r['reduction_pct'],2),'calls',r['baseline_calls'],r['structured_calls'],'prefixcalls',r['baseline_at_common_calls'],r['structured_at_common_calls'],'prefixtime',r['baseline_at_common_time'],r['structured_at_common_time'])
print({k:v for k,v in summary.items() if k!='pairs'})
