import json,csv,tarfile,gzip,hashlib,shutil
from pathlib import Path
from collections import Counter
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--sources',type=Path,required=True);args=parser.parse_args();dest=Path(__file__).resolve().parent;out=dest;old=args.sources.parent
sha=lambda b:hashlib.sha256(b).hexdigest()
a=json.loads((args.sources/'audit.json').read_text(encoding='utf-8'));assert sha((args.sources/'evidence.tar.gz').read_bytes())==a['source_archive_sha256']
t=tarfile.open(args.sources/'evidence.tar.gz');rb=t.extractfile('probe/official-p3.json.gz').read();pb=t.extractfile('probe/prepare/prepared.json.gz').read();assert sha(rb)==a['official_result_sha256'] and sha(pb)==a['prepared_sha256'];r=json.loads(gzip.decompress(rb));p=json.loads(gzip.decompress(pb))
ops={(c['core_id'],o['op_id']):o for c in r['per_core_timeline'] for o in c['ops']};assert len(ops)==1678 and max(o['end'] for o in ops.values())==r['makespan']==38024
prepared={(v['core_id'],int(oid)):o for v in p['tasks'].values() for oid,o in v['op_by_id'].items()};assert set(prepared)==set(ops)
for k,o in ops.items():assert o['op']==prepared[k]['op'] and o['pipe']==prepared[k]['pipe'];assert o['duration']==o['end']-o['start']
read=lambda n:list(csv.DictReader((dest/n).open(encoding='utf-8')))
pre=read('prefix_ops.csv');cp=read('critical_path_ops.csv');ev=read('evidence_points.csv');co=read('path_contributions.csv');assert len(pre)==40 and len(cp)==366
for row in pre+cp:
 k=(int(row['source_core_id']),int(row['op_id']));o=ops[k];assert int(row['core'])==k[0]+1
 for f in ['op','pipe','start','end','duration']:assert str(o[f])==row[f],(k,f)
 assert row['cache_hit'].lower()==str(o.get('cache_hit','')).lower()
for row,s in zip(cp,a['critical_path']):
 for k in ['op_id','op','pipe','start','end','duration','minimum_duration','incoming_lag']:assert str(s[k])==row[k]
 assert s['minimum_duration']==prepared[(s['core'],s['op_id'])]['cycles']
for row in ev:
 v=a
 for key in row['source_field'].split('.'):v=v[key]
 assert int(row['cycles'])==v
prefix_lookup={};works={};b={}
for core,x in a['cold_prefixes'].items():
 rows=[rr for rr in pre if rr['prefix_id']=='prefix'+core];assert [int(rr['op_id']) for rr in rows]==x['ops']
 seq=p['tasks'][core]['pipe_ops']['PIPE_MTE2'];assert seq[:len(rows)]==x['ops'];assert int(rows[0]['start'])==0
 for rr in rows:
  k=(int(core),int(rr['op_id']));o=ops[k];assert o['op']=='COPY_IN' and not o.get('cache_hit',False);prefix_lookup[k]='prefix'+core
 works[core]=sum(prepared[(int(core),oid)]['cycles'] for oid in x['ops']);b[core]=len(x['ops'])-1
 assert works[core]==x['work'];assert max(int(rr['end']) for rr in rows)==x['official_finish']
for core,x in a['cold_prefixes'].items():assert works[core]+sum(min(works[j],max(0,works[core]-b[j])) for j in works if j!=core)==x['finish_lower_bound']
c=Counter();prev=None
for s in a['critical_path']:
 c[s['op']]+=s['duration'];c['cross_lag']+=s['incoming_lag'];c['duration_excess_above_minimum']+=s['duration']-s['minimum_duration']
 if prev:assert s['previous']==[prev['core'],prev['op_id']] and s['start']==prev['end']+s['incoming_lag']
 prev=s
assert dict(c)==a['realized_path_contributions'];assert all(int(rr['cycles'])==c[rr['component']] for rr in co);assert sum(v for k,v in c.items() if k!='duration_excess_above_minimum')==38024
assert [int(rr['op_id']) for rr in pre if rr['prefix_id']=='prefix2']==[s['op_id'] for s in a['critical_path'][:7]]
def write(name,rows,fields):
 with (dest/name).open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
variant='prefix044-k5'
events=[dict(variant=variant,event_id=f'c{k[0]}-op{k[1]}',op_id=k[1],core=k[0]+1,pipe=o['pipe'],start=o['start'],end=o['end'],prefix_id=prefix_lookup.get(k,'')) for k,o in ops.items()]
write('events.csv',events,['variant','event_id','op_id','core','pipe','start','end','prefix_id'])
write('results.csv',[dict(variant=variant,case=44,cores=5,makespan=r['makespan'],extra_ddr=r['data_movement_bytes']['added_copy_bytes'],plan_hash=a['plan_sha256'])],['variant','case','cores','makespan','extra_ddr','plan_hash'])
write('markers.csv',[dict(variant=variant,kind='prefix'+core+'_done',event_id=f"c{core}-op{x['ops'][-1]}") for core,x in a['cold_prefixes'].items()],['variant','kind','event_id'])
write('evidence.csv',[dict(kind=k,cycles=a[f],source_ref='28e8c7dd:prefix-realized-path/audit.json#'+f) for k,f in [('optimistic','without_memory_lower_bound'),('conditional_bound','rounded_sharing_model_lower_bound'),('observed','official_makespan')]],['kind','cycles','source_ref'])
proof=dict(original_commit='18a0d9ff36f76f7d897b7f53949022b3df0cbb8f',actual_source_hashes={'archive':sha((args.sources/'evidence.tar.gz').read_bytes()),'audit':sha((args.sources/'audit.json').read_bytes()),'prepared_gzip':sha(pb),'official_gzip':sha(rb)},official_ops_verified=1678,prefix_ops_verified=40,critical_ops_verified=366,evidence_values_verified=15,conditional_prefix_bounds_recomputed=True,contributions=dict(c),original_tables_unchanged={n:sha((dest/n).read_bytes()) for n in ['prefix_ops.csv','critical_path_ops.csv','evidence_points.csv','path_contributions.csv']},boundary='读取固定prepared与官方原件，逐事件和前缀公式核验；未重新执行solver/E0，未以旧持续时间预测新方案。整体条件界引用固定源审计，限该前缀/归核/Task，有理数模型非浮点剪枝证书。')
(out/'source-verification.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(proof,ensure_ascii=False))

