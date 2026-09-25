#!/usr/bin/env python3
"""Bounded static count of mandatory COPYs for two saved plan pairs."""
import argparse, gzip, gc, hashlib, importlib.util, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
ARCH=ROOT/'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee'
AUDIT=ROOT/'results/a/q2-nikolastarx/hypergap-full500-audit-20260925'
SUMMARY=AUDIT/'completed-summary.json'
BASE='60afc38b327680fbda0ff10182e3e05a01edd72d'
def sha(b): return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--raw-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 rawroot=a.raw_root.resolve();sp=importlib.util.spec_from_file_location('audit',AUDIT/'audit.py');au=importlib.util.module_from_spec(sp);sp.loader.exec_module(au)
 assert sha(SUMMARY.read_bytes())==json.loads((AUDIT/'report.json').read_text())['summary_sha256']
 summary=json.loads(SUMMARY.read_text()); rows={(r['case'],r['cores']):r for r in summary['rows']}
 old=au.pinned_records(ROOT); out=[]
 for case,cores in [('072',5),('014',2)]:
  graph_path=rawroot/f'case_{case}.json'; graph_raw=graph_path.read_bytes(); graph=json.loads(graph_raw); graph_sha=sha(graph_raw)
  prior=old[case,cores]; current=rows[case,cores]
  assert graph_sha==prior['identity']['graph_sha256']==current['graph_sha256']
  newdir=next(ARCH.glob(f'cases-*/{case}-k{cores}'))
  items=[]
  for label in ('old','new'):
   if label=='old':
    plan_raw=au.git_blob(ROOT,BASE,prior['artifacts']['plan']['path']); plan=json.loads(plan_raw)
    result_raw=au.git_blob(ROOT,BASE,prior['artifacts']['result']['path']); result=json.loads(gzip.decompress(result_raw))
   else:
    plan_raw=(newdir/'plan.json.gz').read_bytes(); plan=json.loads(gzip.decompress(plan_raw))
    result_raw=(newdir/'result.json.gz').read_bytes(); result=json.loads(gzip.decompress(result_raw))
   assert sha(plan_raw)==prior['artifacts']['plan']['sha256'] if label=='old' else sha(gzip.decompress(plan_raw))==current['plan_sha256']
   assert sha(result_raw)==prior['artifacts']['result']['sha256'] if label=='old' else sha(gzip.decompress(result_raw))==current['official']['result_sha256']
   movement=result['data_movement_bytes']
   assert result['makespan']==(prior['metrics']['makespan_cycles'] if label=='old' else current['official']['makespan'])
   work=mandatory_copy_work(graph,plan,60)
   target=movement['original_graph_copy_bytes']+movement['partition_added_copy_bytes']
   assert work['transfer_bytes']==target
   items.append({'version':label,'plan_sha256':sha(plan_raw),'result_sha256':sha(result_raw),
     'result_makespan':result['makespan'],'movement_original_graph_copy_bytes':movement['original_graph_copy_bytes'],
     'movement_partition_added_copy_bytes':movement['partition_added_copy_bytes'],
     'mandatory_copy_work':work})
  cats=[]
  for name in ('boundary_input','boundary_output','cross_tensor','cross_direct'):
   x,y=(z['mandatory_copy_work']['categories'][name] for z in items)
   cats.append({'category':name,'old':x,'new':y,'delta_copy_count':y['copy_count']-x['copy_count'],'delta_transfer_bytes':y['transfer_bytes']-x['transfer_bytes']})
  out.append({'case':case,'cores':cores,'graph_sha256':graph_sha,'graph_bytes':len(graph_raw),'static_only':True,'versions':items,'category_deltas':cats,
    'verified_transfer_identity_per_version':True})
  del graph,graph_raw
  gc.collect()
 result={'scope':'Saved plans only; mandatory original COPY accounting before Step2, no solver/evaluator/runtime.',
   'reproduction_template':'python3 scripts/q2_ddr_regression_categories.py --raw-root <OFFICIAL_DATA_DIRECTORY> --out <OUTPUT_JSON>',
   'candidate_ddr_py_sha256':sha((ROOT/'src/q2_nikolastarx/candidate_ddr.py').read_bytes()),
   'summary_sha256':sha(SUMMARY.read_bytes()),'old_feed_commit':BASE,'records':out,
   'limitation':'Category counts identify static mandatory COPY work, not individual high-fanout tensor attribution or spill reload causes.'}
 a.out.parent.mkdir(parents=True,exist_ok=True)
 a.out.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'output':str(a.out),'cases':[{'case':x['case'],'category_deltas':x['category_deltas']} for x in out]},indent=2))
if __name__=='__main__': main()
