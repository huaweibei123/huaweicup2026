#!/usr/bin/env python3
"""Derived summaries only. Never edits raw plans or evaluator outputs."""
from pathlib import Path
import json,gzip,statistics,math,hashlib,collections
P=Path(__file__).resolve().parents[1];R=P/'results';O=P/'analysis';O.mkdir(exist_ok=True)
suites={};catalog=[]
for d in sorted(R.iterdir()):
 if not d.is_dir() or not (d/'runs.jsonl').exists():continue
 rows=[json.loads(l) for l in (d/'runs.jsonl').read_text().splitlines()];suites[d.name]=rows
 for row in rows:
  folder=d/f"{row['case']}_{row['method']}_q{row['problem']}_n{row['cores']}"
  if row['status']=='ok':
   path=folder/'result.json.gz';actual=json.loads(gzip.decompress(path.read_bytes()));assert actual['makespan']==row['makespan']
  catalog.append({'suite':d.name,**{k:row.get(k) for k in ['case','method','problem','cores','status','makespan','construction_seconds','e0_seconds','wall_seconds']},'folder':folder.relative_to(P).as_posix()})
(O/'official_run_catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2))
# The primary comparison is fixed to two new methods, including all failures.
comparisons={}
for name in ['pilot_v1','validation_v1','q3_transfer_v1','n2_transfer_v1','n5_transfer_v1']:
 bycase=collections.defaultdict(dict)
 for row in suites[name]:bycase[row['case']][row['method']]=row
 out=[]
 for case,rows in bycase.items():
  base=min((rows[k] for k in ['component','cut2','unit']),key=lambda x:x['makespan'])
  new=min((rows[k] for k in ['chain_response','cut2_response']),key=lambda x:x['makespan'])
  out.append({'case':case,'baseline_method':base['method'],'baseline_best3':base['makespan'],'chain_response':rows['chain_response']['makespan'],'cut2_response':rows['cut2_response']['makespan'],'new_best2':new['makespan'],'new_method':new['method'],'reduction_fraction':1-new['makespan']/base['makespan']})
 comparisons[name]=out
(O/'comparisons.json').write_text(json.dumps(comparisons,indent=2))
# Genuine FAST on 5 independent diagnostic pools, not the team's 64-pool gate.
fast=json.loads((R/'p1_fast_complete_rows.json').read_text());errors=[];fps=[]
for case in sorted({x['case'] for x in fast}):
 rows=[x for x in fast if x['case']==case];assert len(rows)==8
 for x in rows:assert x['status']=='ok' and x['e1_equal'] and x['e1_first_difference'] is None
 best=min(x['makespan'] for x in rows);rank=min(rows,key=lambda x:x['rank']['rank_score']);evt=min(rows,key=lambda x:x['event']['metrics']['makespan'])
 errors.extend(abs(x['event']['metrics']['makespan']-x['makespan'])/max(1,x['makespan']) for x in rows)
 fps.append({'case':case,'pool_size':8,'best_e0':best,'rank_top1':rank['method'],'rank_top1_regret':rank['makespan']/best-1,'event_top1':evt['method'],'event_top1_regret':evt['makespan']/best-1})
fs={'scope':'new P1 5x8 diagnostic pools; NOT >=64 release pools','e1_full_object_equal':40,'event_error_median':statistics.median(errors),'event_error_p95_nearest_rank':sorted(errors)[math.ceil(.95*len(errors))-1],'event_max_error':max(errors),'pools':fps}
(O/'fast_diagnostics.json').write_text(json.dumps(fs,indent=2))
# Validity/ownership invariants for all phase-based refinements whose base is available.
bases={}
for suite in ['pilot_v1','validation_v1','q3_transfer_v1','n2_transfer_v1','n5_transfer_v1']:
 for row in suites[suite]:
  if row['method']=='chain_response':bases[row['case'],row['problem'],row['cores']]=P/next(x['folder'] for x in catalog if x['suite']==suite and x['case']==row['case'] and x['method']=='chain_response')
def ownership(plan):
 core={b:k for k,o in enumerate(plan['core_schedules']) for b in o};return {v:core[b] for v,b in plan['node_to_subgraph'].items()}
invs=[]
for x in catalog:
 if x['method'] not in ['refine_response','phasefix_response','window2_response','window8_response','window32_response']:continue
 key=x['case'],x['problem'],x['cores']
 if key not in bases:continue
 b=bases[key];f=P/x['folder'];p1=json.loads((b/'plan.json').read_text());p2=json.loads((f/'plan.json').read_text());r1=json.loads(gzip.decompress((b/'result.json.gz').read_bytes()));r2=json.loads(gzip.decompress((f/'result.json.gz').read_bytes()));same=ownership(p1)==ownership(p2);part=r1['data_movement_bytes']['partition_added_copy_bytes']==r2['data_movement_bytes']['partition_added_copy_bytes'];assert same and part
 invs.append({'folder':x['folder'],'base':str(b.relative_to(P)),'same_op_core_assignment':same,'same_partition_bytes':part,'same_full_movement':r1['data_movement_bytes']==r2['data_movement_bytes']})
(O/'fixed_ownership_checks.json').write_text(json.dumps(invs,indent=2))
# Explicit inventory of harness failures, orphans, and API outputs. No success inflation.
harness=[]
for suite in ['p1_fast','p1_fast_v2','p1_fast_051']:
 d=R/suite
 for f in sorted(x for x in d.iterdir() if x.is_dir()):
  row=json.loads((f/'run.json').read_text()) if (f/'run.json').exists() else None
  a=(f/'e0.json.gz').exists();b=(f/'e1.json.gz').exists();rec={'folder':str(f.relative_to(P)),'run_status':row.get('status') if row else 'missing run receipt (tool interruption)','e0_full_exists':a,'e1_full_exists':b,'error':row.get('error') if row else None}
  if a:rec['e0_makespan']=json.loads(gzip.decompress((f/'e0.json.gz').read_bytes()))['makespan']
  harness.append(rec)
(O/'harness_event_inventory.json').write_text(json.dumps(harness,indent=2))
# short tables
lines=['# 本轮机器可重算的结果摘要','', '所有主表均来自本轮新运行；不是找回295份历史结果。池最好值不是未知全局最优。','']
for name,out in comparisons.items():
 lines += ['## '+name,'','|case|旧三构造最好|串行包矩阵|小张量块矩阵|新二构造最好|时间下降|','|---|---:|---:|---:|---:|---:|']
 for x in out:lines.append(f"|{x['case']}|{x['baseline_best3']}|{x['chain_response']}|{x['cut2_response']}|{x['new_best2']}|{100*x['reduction_fraction']:.2f}%|")
 lines+=['']
lines+=['## FAST 新P1诊断','',json.dumps(fs,ensure_ascii=False,indent=2),'','## 各构造完整运行表','','|suite|case|q|n|method|Makespan|构造s|E0函数s|含存档s|','|---|---|---:|---:|---|---:|---:|---:|---:|']
for x in catalog:
 lines.append(f"|{x['suite']}|{x['case']}|{x['problem']}|{x['cores']}|{x['method']}|{x['makespan']}|{x['construction_seconds']:.4f}|{x['e0_seconds']:.4f}|{x['wall_seconds']:.4f}|")
(O/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'main_runs':len(catalog),'status_counts':dict(collections.Counter(x['status'] for x in catalog)),'formal_cases':sorted(set(x['case'] for x in catalog)),'fixed_ownership_checks':len(invs),'fast_event_median':fs['event_error_median'],'fast_event_p95':fs['event_error_p95_nearest_rank']},indent=2))
