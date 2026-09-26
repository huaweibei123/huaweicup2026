"""Inspect real Q3 COPY_IN hits on renamed spill incarnations, frozen config."""
import json,gzip,sys
from pathlib import Path
from evidence import DEFAULT_OFFICIAL
sys.path.insert(0,str(DEFAULT_OFFICIAL/'code'))
import multicore_cut_evaluate_problem_3 as q3
from evaluation_validation import read_evaluation_config
root=Path('/mnt/data/r2_research');run=root/'runs/first/case_044_p3_comp_lpt';graph=DEFAULT_OFFICIAL/'data/case_044.json';cfg=read_evaluation_config(str(DEFAULT_OFFICIAL/'data/config.txt'))
g=json.loads(graph.read_text());p=json.loads((run/'plan.json').read_text());r=json.loads(gzip.decompress((run/'result.json.gz').read_bytes()));tasks,links,traffic,movement,view=q3._build_scene_b_tasks(g,p,cfg['bandwidth'],cfg['capacity'])
lookup={(c['core_id'],o['op_id']):o for c in r['per_core_timeline'] for o in c['ops']};events={(e['core_id'],e['op_id']):e for e in r['cache_events'] if e['event']=='hit'}
hits=[]
for core,t in tasks.items():
 for oid,op in t['op_by_id'].items():
  if op['op']!='COPY_IN':continue
  for tid in t['out_tids'][oid]:
   tt=t['tensor_by_id'][tid]
   if tt.get('logical_tid',tid)!=tid and lookup[core,oid].get('cache_hit'):
    assert lookup[core,oid]['memory_path']=='CACHE_READ'
    assert lookup[core,oid]['cache_tensor_id']==tt['logical_tid']
    hits.append({'core':core,'op_id':oid,'tensor':tt,'op':op,'cache_event':events[core,oid],'official_timeline':lookup[core,oid]})
assert movement==r['data_movement_bytes']
out={'case':'case_044','official_run':str(run),'graph_hash':json.loads((run/'run.json').read_text())['graph_hash'],'plan_hash':json.loads((run/'run.json').read_text())['plan_hash'],'count':len(hits),'hit_bytes_on_renamed':sum(x['tensor']['size'] for x in hits),'total_cache_hits':r['cache_stats']['copy_in_hits'],'total_hit_bytes':r['cache_stats']['hit_bytes'],'full_movement_identical_to_native_prepared':True,'witnesses':hits}
(root/'analysis/spill_logical_tid_hit_witnesses.json').write_text(json.dumps(out,indent=2))
print(out['count'],out['hit_bytes_on_renamed'],out['total_cache_hits']);print(json.dumps(hits[:1],indent=2))
