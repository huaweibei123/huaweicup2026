"""Rebuild native prepared tasks for already-evaluated plans; diagnostic only.
Do not patch E0 or use this snapshot as the official full-result substitute.
"""
import sys,json,gzip,hashlib
from pathlib import Path
from evidence import DEFAULT_OFFICIAL
sys.path.insert(0,str(DEFAULT_OFFICIAL/'code'))
import multicore_cut_evaluate_problem_2 as q2
import multicore_cut_evaluate_problem_3 as q3
from evaluation_validation import read_evaluation_config
ROOT=Path('/mnt/data/r2_research');cfg=read_evaluation_config(str(DEFAULT_OFFICIAL/'data/config.txt'))
selections=[(44,2,ROOT/'runs/first/case_044_p2_comp_lpt'),(44,2,ROOT/'runs/first/case_044_p2_wave_all_band4'),(8,2,ROOT/'runs/affine/case_008_p2_w0_f0.125'),(80,3,ROOT/'runs/affine/case_080_p3_w0_f0.125')]
summary=[]
def conv(v):
 if isinstance(v,dict):return {str(k):conv(x) for k,x in v.items()}
 if isinstance(v,set):return [conv(x) for x in sorted(v)]
 if isinstance(v,(tuple,list)):return [conv(x) for x in v]
 return v
for case,q,run in selections:
 g=json.loads((DEFAULT_OFFICIAL/f'data/case_{case:03d}.json').read_text());p=json.loads((run/'plan.json').read_text());mod=q2 if q==2 else q3
 tasks,links,traffic,metrics,view=mod._build_scene_b_tasks(g,p,cfg['bandwidth'],cfg['capacity'])
 res=json.loads(gzip.decompress((run/'result.json.gz').read_bytes()));ops={(c['core_id'],o['op_id']):o for c in res['per_core_timeline'] for o in c['ops']}
 hits=[];tstats={}
 for core,t in tasks.items():
  renamed={tid:tt for tid,tt in t['tensor_by_id'].items() if tt.get('logical_tid',tid)!=tid and tt.get('pos')!='DDR'}
  for oid,op in t['op_by_id'].items():
   if op['op']!='COPY_IN':continue
   for tid in t['out_tids'][oid]:
    if tid in renamed and ops[core,oid].get('cache_hit'):
     hits.append({'core':core,'op_id':oid,'renamed_tensor':tid,'logical_tid':renamed[tid]['logical_tid'],'bytes':renamed[tid]['size'],'official_timeline':ops[core,oid]})
  tstats[core]={'memory_peak':t['step3'].get('memory_peak'),'memory_dependencies':len(t['step3'].get('memory_dependencies',[])),'renamed_onchip_count':len(renamed),'pipe_counts':{p:len(v) for p,v in t['pipe_ops'].items()}}
 dest=ROOT/'analysis'/f'prepared_{run.name}.json.gz'
 with gzip.open(dest,'wt',encoding='utf-8',compresslevel=3) as f:json.dump(conv({'tasks':tasks,'links':links,'traffic':traffic,'metrics':metrics}),f,ensure_ascii=False)
 summary.append({'case':case,'problem':q,'official_run':str(run),'snapshot':str(dest),'task_stats':tstats,'renamed_copy_in_hits':hits})
(ROOT/'analysis/prepared_witness_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print([(r['case'],r['official_run'].split('/')[-1],len(r['renamed_copy_in_hits'])) for r in summary]);print(json.dumps(summary[-1]['renamed_copy_in_hits'][:1],indent=2))
