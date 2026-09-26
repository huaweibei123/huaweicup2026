"""Read fixed archived inputs only; never invokes solvers or evaluators."""
import argparse,csv,json,hashlib,statistics
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--sources',type=Path,required=True);a=ap.parse_args();p=Path(__file__).resolve().parent
def read(n):return json.loads((a.sources/n).read_text(encoding='utf-8'))
def sha(n):return hashlib.sha256((a.sources/n).read_bytes()).hexdigest()
assert sha('completed-summary.json')=='083c3f5b603cb61dd8b132718b6437b35c7706ff3aa165bdcdd490617547a2f2'
s=read('completed-summary.json');rs=s['rows'];assert s['status']=='completed' and s['accepted_cells']==500 and s['limits']['workers']==1
lut={(r['case'],r['cores']):r for r in rs};assert len(lut)==len(rs)==500
assert set(lut)=={(f'{i:03}',k) for i in range(1,101) for k in range(1,6)}
metrics=[];inputs=[]
for f in sorted(a.sources.glob('cases-*.json')):
 inputs.append(dict(file=f.name,sha256=sha(f.name)))
 for r in read(f.name)['records']:
  v=lut[(r['case_id'],r['cores'])];m=r['metrics'];e=r['provenance']['environment'];q=r['provenance']['measurement']
  assert r['status']=='ok' and v['status']=='accepted'
  assert r['solver_commit']==s['solver_commit']=='c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f'
  assert e['workers']==r['parameters']['global_budget']['workers']==1 and e['cpu'] is None
  assert 'online native E2' in q['solver_scope'] and 'independent official E0' in q['evaluation_scope']
  for key in ['graph_sha256','config_sha256']:assert r['identity'][key]==v[key]
  assert m['makespan_cycles']==v['official']['makespan']
  assert m['solver_wall_seconds']==v['solver_process']['wall_seconds']
  assert m['evaluation_wall_seconds']==v['e0_process']['wall_seconds']
  assert m['ddr_bytes']==v['official']['movement']['scheduled_copy_bytes']
  assert m['extra_ddr_bytes']==v['official']['movement']['added_copy_bytes']
  assert m['spill_bytes']==v['official']['movement']['spill_added_copy_bytes']
  assert v['calls']['E0_fallback_confirmed']==v['calls']['E0_fallback_possible']==0
  metrics.append(dict(case=r['case_id'],cores=r['cores'],makespan=m['makespan_cycles'],extra_ddr=m['extra_ddr_bytes'],solver_wall=m['solver_wall_seconds'],evaluation_wall=m['evaluation_wall_seconds'],platform=e['os'],workers=e['workers'],timing_scope=q['solver_scope'],cpu='not recorded',python=e['python'],attempt_id=r['attempt_id'],run_id=r['run_id'],revision=r['revision'],solver_commit=r['solver_commit'],graph_sha256=v['graph_sha256'],config_sha256=v['config_sha256'],raw_plan_sha256=v['plan_sha256'],raw_result_sha256=v['official']['result_sha256'],archive_plan_sha256=r['artifacts']['plan']['sha256'],archive_result_sha256=r['artifacts']['result']['sha256'],feed_file=f.name))
metrics.sort(key=lambda r:(r['case'],r['cores']));assert len(metrics)==500 and len({(r['case'],r['cores']) for r in metrics})==500
assert len({(r['platform'],r['workers'],r['timing_scope']) for r in metrics})==1
def quantile(v,q):
 v=sorted(v);t=(len(v)-1)*q;j=int(t);return v[j]+(v[min(j+1,len(v)-1)]-v[j])*(t-j)
summary=[]
for k in range(1,6):
 g=[r for r in metrics if r['cores']==k];v=[r['solver_wall'] for r in g];assert len(v)==100
 summary.append(dict(cores=k,platform=g[0]['platform'],workers=1,timing_scope=g[0]['timing_scope'],n=len(v),median=statistics.median(v),p95=quantile(v,.95),max=max(v)))
for n,rows in [('metrics.csv',metrics),('summary.csv',summary)]:
 with (p/n).open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
v=[r['solver_wall'] for r in metrics]
proof=dict(summary_sha256=sha('completed-summary.json'),inputs=inputs,verified_cells=500,paired_metric_fields=6,source_identity_checked=['graph','config','solver_commit','attempt','run'],resources={'platform':metrics[0]['platform'],'workers':1,'cpu':'not recorded','python':metrics[0]['python']},summary=summary,overall=dict(n=500,median=statistics.median(v),p95_linear=quantile(v,.95),p95_nearest_rank=sorted(v)[474],max=max(v)),scope='Per-child end-to-end solver including online E2; independent E0 separate. No new experiments. CPU and strict cold-start not measured; no cross-platform speedup.',calls=s['calls'])
(p/'source-verification.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(proof['overall']))
