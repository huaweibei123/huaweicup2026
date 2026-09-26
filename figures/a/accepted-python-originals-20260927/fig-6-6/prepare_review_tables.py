"""Workbench read-only verification of fixed results. No solver/evaluator execution."""
import argparse,csv,gzip,json,hashlib
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--sources',type=Path,required=True);args=ap.parse_args();s=args.sources;p=Path(__file__).resolve().parent
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
audit=json.loads((s/'audit.json').read_text(encoding='utf-8'))
assert sha(s/'audit.json')=='e50a97d724f7f79355bb98e75aafc382dba726a6d23002932e5cf114690b6135'
raw={v:json.loads(gzip.decompress((s/(v+'.json.gz')).read_bytes())) for v in ['p2','p3']}
for v in raw:assert sha(s/(v+'.json.gz'))==audit['source'][v]['gzip_sha256']
plan=sha(s/'plan.json');assert plan==audit['source']['source_plan_sha256']
pair=json.loads((s/'pair-summary.json').read_text(encoding='utf-8'))
cell=next(r for r in pair['negative_cells'] if str(r['case_id'])=='021' and r['cores']==3)
assert cell['source_plan_sha256']==plan and cell['result_sha256']==sha(s/'p2.json.gz') and cell['cache_result_sha256']==sha(s/'p3.json.gz')
for field in ['scene','num_cores','bandwidth_bytes_per_cycle','capacity_bytes','cross_core_copy_delay_cycles','task_dependencies','cross_core_transfers','data_movement_bytes']:
 assert raw['p2'][field]==raw['p3'][field],field
assert raw['p3']['cache_mode']=='read_only' and raw['p3']['problem']==3
def flatten(d):return {(c['core_id'],o['task_id'],o['op_id']):o for c in d['per_core_timeline'] for o in c['ops']}
ops={v:flatten(d) for v,d in raw.items()};assert set(ops['p2'])==set(ops['p3']) and len(ops['p2'])==8881
for a,b in zip(raw['p2']['per_core_timeline'],raw['p3']['per_core_timeline']):
 for pipe in ['PIPE_MTE2','PIPE_M','PIPE_V','PIPE_MTE3']:
  assert [(o['task_id'],o['op_id']) for o in a['ops'] if o['pipe']==pipe]==[(o['task_id'],o['op_id']) for o in b['ops'] if o['pipe']==pipe]
rows=list(csv.DictReader((p/'aligned_ops.csv').open(encoding='utf-8')));assert len(rows)==8881
seen=set();changes={x:0 for x in ['start','end','duration']}
for r in rows:
 key=tuple(int(r[x]) for x in ['source_core_id','task_id','op_id']);assert key not in seen;seen.add(key);assert int(r['core'])==key[0]+1
 a,b=ops['p2'][key],ops['p3'][key]
 for field in ['op','pipe','subgraph_id']:assert a[field]==b[field]
 for field in ['op','pipe']:assert r[field]==a[field]
 for field in changes:
  for v in raw:assert int(r[v+'_'+field])==ops[v][key][field]
  assert int(r[field+'_diff'])==b[field]-a[field];changes[field]+=a[field]!=b[field]
 assert r['p3_cache_hit']==str(b.get('cache_hit','')) and r['p3_memory_path']==b.get('memory_path','')
assert changes=={'start':7485,'end':7808,'duration':2392}
for field,expect in [('end',1000004905),('start',1000006255)]:
 ks=[k for k in seen if ops['p2'][k][field]!=ops['p3'][k][field]]
 first=min(ks,key=lambda k:(min(ops['p2'][k][field],ops['p3'][k][field]),k));assert first[-1]==expect
slower=[k for k in seen if ops['p2'][k]['op']=='COPY_IN' and ops['p2'][k]['start']==ops['p3'][k]['start'] and ops['p2'][k]['duration']<ops['p3'][k]['duration']]
assert len(slower)==3 and min(slower,key=lambda k:(ops['p2'][k]['start'],k))[-1]==1000006089
for field in ['first_start_change','first_completion_time_change','first_same_start_slower_copy_in']:
 a=audit[field];k=tuple(a[x] for x in ['core_id','task_id','op_id'])
 for v in raw:
  for x in ['start','end','duration']:assert a[v+'_'+x]==ops[v][k][x]
summary={r['metric']:float(r['value']) for r in csv.DictReader((p/'summary_metrics.csv').open(encoding='utf-8'))}
for v in raw:assert summary['makespan_'+v+'_cycles']==raw[v]['makespan']==max(o['end'] for o in ops[v].values())
assert raw['p3']['makespan']-raw['p2']['makespan']==143
for k,v in raw['p2']['data_movement_bytes'].items():assert summary[k]==v
for k in ['copy_in_hits','copy_in_misses','hit_bytes','miss_bytes','hit_rate']:assert summary['cache_'+k]==raw['p3']['cache_stats'][k]
assert abs(summary['cache_hit_rate']-summary['cache_hit_bytes']/(summary['cache_hit_bytes']+summary['cache_miss_bytes']))<1e-15
def write(name,rs):
 with (p/name).open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
events=[dict(variant=v,event_id='-'.join(map(str,k)),op_id=k[2],core=k[0]+1,pipe=o['pipe'],start=o['start'],end=o['end']) for v in raw for k,o in ops[v].items()]
write('events.csv',events);write('results.csv',[dict(variant=v,case=21,cores=3,makespan=d['makespan'],extra_ddr=d['data_movement_bytes']['added_copy_bytes'],plan_hash=plan) for v,d in raw.items()])
write('markers.csv',[dict(variant=v,kind=str(k[-1]),event_id='-'.join(map(str,k))) for v in raw for k in sorted(seen) if k[-1] in [1000004905,1000006255,1000006089]])
proof=dict(operation_count=8881,checked_event_endpoints=17762,changes=changes,plan_sha256=plan,makespans={v:d['makespan'] for v,d in raw.items()},movement_equal=True,per_pipe_order_equal=True,source_hashes={f.name:sha(f) for f in s.iterdir() if f.is_file()},original_csv_hashes={n:sha(p/n) for n in ['aligned_ops.csv','summary_metrics.csv','key_events.csv']},boundary='Source results and paired summary inspected; no new solver/E0 run; events do not establish full causality.')
(p/'source-verification.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:proof[k] for k in ['operation_count','checked_event_endpoints','changes','makespans']}))
