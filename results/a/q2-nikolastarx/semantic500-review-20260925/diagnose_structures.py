"""Read-only structure/ledger inspection for the three largest paired losses.

Computes connected components of eligible tensor/direct edges only. No plans,
solver calls, evaluator calls, Git operations or network requests are created.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,json,hashlib,gzip
OUT=Path(__file__).resolve().parent
SHA=lambda b:hashlib.sha256(b).hexdigest()
def main(root):
 feed=json.loads(gzip.decompress((OUT/'semantic-feed-500.json.gz').read_bytes()))['records']
 rows={r['case_id']:r for r in feed if r['cores']==4}
 stat=json.loads((OUT/'report/statistics.json').read_text())
 cases=[r['case'] for r in stat['fang_k4']['largest_losses'][:3]]
 result=[]
 for case in cases:
  r=rows[case];gpath=root/f'data/raw/a/official/data/case_{case}.json';raw=gpath.read_bytes();assert SHA(raw)==r['identity']['graph_sha256'];g=json.loads(raw)
  runraw=(root/r['artifacts']['run']['path']).read_bytes();assert SHA(runraw)==r['artifacts']['run']['sha256'];run=json.loads(runraw)
  ref=run['artifacts']['online_ledger'];lr=(root/ref['path']).read_bytes();assert SHA(lr)==ref['sha256'];ledger=json.loads(lr);d=ledger['attempts'][0]['detail']
  assert d['adaptive_route']=='component_envelope'
  ops={o['id']:o for o in g['ops'] if o['op'] not in ('COPY_IN','COPY_OUT')};tensors={t['id']:t for t in g['tensors']}
  parents={u:u for u in ops}
  def find(u):
   while parents[u]!=u:parents[u]=parents[parents[u]];u=parents[u]
   return u
  def union(a,b):
   a,b=find(a),find(b)
   if a!=b:parents[b]=a
  producers,consumers=defaultdict(set),defaultdict(set)
  for e in g['edges']:
   a,b=e['source'],e['target']
   if a in ops and b in ops:union(a,b)
   if a in ops and b in tensors:producers[b].add(a)
   if a in tensors and b in ops:consumers[a].add(b)
  for t,ps in producers.items():
   for a in ps:
    for b in consumers[t]:union(a,b)
  comps=defaultdict(list)
  for u in ops:comps[find(u)].append(u)
  assert len(comps)==d['components'] and len(ops)==d['eligible_ops']
  hist=Counter(tuple(sorted(Counter(ops[u]['op'] for u in group).items())) for group in comps.values())
  shared={t:{find(u) for u in cs} for t,cs in consumers.items() if len({find(u) for u in cs})>1}
  shared_by_pool=Counter()
  for t in shared:shared_by_pool[tensors[t]['pos']]+=tensors[t]['size']
  percore=[]
  for c in d['per_core']:
   percore.append({'core':c['core'],'components':c['components'],'shared_tensors':c['shared_tensors'],'cohorts':len(c['cohorts']),
                   'uncertified_cohorts':sum(not x['within_capacity'] for x in c['cohorts']),'max_open_components':c['max_open_components_bound'],
                   'max_shared_bytes':{pool:max(x['shared_reserve_bytes'][pool] for x in c['cohorts']) for pool in ('L1','UB')},
                   'max_raw_envelope_bytes':{pool:max(x['raw_priority_envelope_bytes'][pool] for x in c['cohorts']) for pool in ('L1','UB')}})
  pair=next(x for x in stat['fang_k4']['largest_losses'] if x['case']==case)
  result.append({'case':case,'graph_sha256':SHA(raw),'run_sha256':SHA(runraw),'ledger':ref,'eligible_ops':len(ops),'components':len(comps),
                 'component_size_histogram':dict(Counter(len(c) for c in comps.values())),
                 'component_op_histograms':[{'op_counts':dict(k),'component_count':v} for k,v in hist.items()],
                 'shared_tensor_count':len(shared),'shared_tensor_bytes_by_raw_pos':dict(shared_by_pool),
                 'shared_tensor_component_fanout_histogram':dict(Counter(len(v) for v in shared.values())),
                 'capacity_bytes':d['capacity_bytes'],'per_core':percore,'repair_trigger':d['repair_trigger'],'repair_construct_calls':d['repair_construct_calls'],
                 'paired_quality':pair,'ours_partition_bytes':pair['ours_extra']-pair['ours_spill'],'fang_partition_bytes':pair['fang_extra']-pair['fang_spill'],
                 'inference':'Current route emits one-component cohorts even though the shared-input reserve exceeds L1; its only recorded vector repair rejects these mixed CONV/RELU/ADD graphs. A shared-input segmented or matching-op ordering is a candidate to test, not a proven remedy.'})
 p=OUT/'structural-diagnosis.json'
 with p.open('x',encoding='utf8') as f:f.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps([{'case':r['case'],'components':r['components'],'size_hist':r['component_size_histogram'],'op_hist':r['component_op_histograms'],'shared':r['shared_tensor_bytes_by_raw_pos'],'partition_bytes':r['ours_partition_bytes'],'same_partition':r['ours_partition_bytes']==r['fang_partition_bytes']} for r in result]))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--producer-root',required=True,type=Path);main(p.parse_args().producer_root)
