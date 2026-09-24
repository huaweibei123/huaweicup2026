"""Capture verified existing scoring evidence, never run a solver/evaluator.

The only Git calls are explicitly authorized read-only `git show` of Fang's
fixed data commit. Our producer feed is addressed by the exact SHA supplied
with its published data commit; producer directories are never written.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,subprocess,time
OUT=Path(__file__).resolve().parent
DATA='571536962b3f6ad9468584a0e5ae04398e684543'
FEED_SHA='b1652e0ef23699bd6c8139de948fff91d03ecacc64cf6b627e15e8d31fe9df3c'
REL='results/a/q2-nikolastarx/semantic-benchmark-s59ee-20260925/20260924T1729Z-s59ee'
FANG='b71d2efbcb45fe96770a22fc68d6a29d9b8fe78c'
FANG_DIR='results/a/q2-yuanzhifang/feedback-20260924/full-coverage/k4-full100/'
sha=lambda b:hashlib.sha256(b).hexdigest()
def stable(p,h=None):
 a=p.stat();b=p.read_bytes();c=p.stat()
 assert (a.st_size,a.st_mtime_ns)==(c.st_size,c.st_mtime_ns),('unstable',str(p))
 if h:assert sha(b)==h,('hash mismatch',str(p))
 return b
def save(n,v):
 with (OUT/n).open('x',encoding='utf8',newline='\n') as f:f.write(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def main(root):
 start=time.monotonic();p=root/REL;raw=stable(p/'board-feed-500.json',FEED_SHA);records=json.loads(raw)['records']
 assert len(records)==500 and {(r['case_id'],r['cores']) for r in records}=={(f'{i:03}',k) for i in range(1,101) for k in range(1,6)}
 assert len({r['attempt_id'] for r in records})==500
 smraw=stable(root/'docs/a/source-manifest.json');sm=json.loads(smraw);graphs={x['path']:x['sha256'] for x in sm['files']}
 bmraw=stable(root/'results/benchmark-board/official-singlecore-20260924/manifest.json');bm=json.loads(bmraw)
 assert bm['source_manifest_sha256']==sha(smraw) and bm['official_code_hash']==sm['official_code_hash']
 baselines={};evidence=[];totalraw=0
 for r in records:
  case=r['case_id'];i=r['identity'];bl=r['baseline'];br=bl['result'];bp=root/br['path']
  assert r['status']=='ok' and r['problem']=='P2' and r['evaluator']['route']=='E0'
  assert r['solver_commit']==r['provenance']['solver']['source']['commit']=='b7c05cf2205bd42ec23680e618a10796b37562f6'
  assert r['provenance']['runner']['source']['commit']=='b7e56b70dfa99542f1ba1d7223e04b2baf2db176'
  assert bl['route']=='E0' and bl['entrypoint']=='singlecore_evaluate.evaluate_singlecore'
  assert all(bl[k]==i[k] for k in ('graph_sha256','config_sha256','official_sha256'))
  assert i['graph_sha256']==graphs[f'data/case_{case}.json'] and i['config_sha256']==graphs['data/config.txt']==bm['config_sha256'] and i['official_sha256']==sm['official_code_hash']
  if case not in baselines:
   packed=stable(bp,br['sha256']);b=json.loads(gzip.decompress(packed));rr=stable(bp.parent/'run.json');receipt=json.loads(rr)
   assert b['scene']=='A' and b['num_cores']==1 and b['execution_mode']=='singlecore' and b['input_graph']==f'case_{case}.json'
   assert receipt['status']=='ok' and receipt['returncode']==0 and receipt['official_calls']==1 and receipt['entrypoint']=='singlecore_evaluate.evaluate_singlecore'
   assert b['makespan']==receipt['makespan_cycles'] and type(b['makespan']) is int and b['makespan']>0
   assert receipt['graph_sha256']==i['graph_sha256'] and receipt['config_sha256']==i['config_sha256'] and receipt['official_code_hash']==i['official_sha256']
   baselines[case]={'makespan':b['makespan'],'result':br,'run_sha256':sha(rr),'identity':i.copy(),'scene':'A','num_cores':1,'entrypoint':receipt['entrypoint']}
   baselines[case]['identity'].pop('plan_sha256')
  assert baselines[case]['result']['sha256']==br['sha256']
  runref=r['artifacts']['run'];runraw=stable(root/runref['path'],runref['sha256']);run=json.loads(runraw)
  resultref=r['artifacts']['result'];packed=stable(root/resultref['path'],resultref['sha256']);plain=gzip.decompress(packed);result=json.loads(plain);totalraw+=len(plain)
  assert sha(plain)==run['artifacts']['result']['raw_sha256'] and len(plain)==run['artifacts']['result']['raw_bytes']
  assert result['scene']=='B' and result.get('problem')!=3 and result['num_cores']==r['cores']
  assert result['makespan']==run['makespan_cycles']==r['metrics']['makespan_cycles'] and type(result['makespan']) is int and result['makespan']>0
  assert run['status']=='ok' and run['solver_commit']==r['solver_commit'] and run['case_id']==case and run['cores']==r['cores']
  for field,key in (('ddr_bytes','scheduled_copy_bytes'),('extra_ddr_bytes','added_copy_bytes'),('spill_bytes','spill_added_copy_bytes')):assert result['data_movement_bytes'][key]==run['data_movement_bytes'][key]==r['metrics'][field]
  assert run['solver']['wall_seconds']==r['metrics']['solver_wall_seconds'] and run['evaluation']['wall_seconds']==r['metrics']['evaluation_wall_seconds']
  assert run['solver']['status']==run['evaluation']['status']=='ok' and run['solver']['returncode']==run['evaluation']['returncode']==0
  assert run['solver_evidence']['calls']=={'E0':0,'E1':0,'E2':0} and run['solver_evidence']['route']==r['parameters']['adaptive_route']
  assert run['calls']==r['provenance']['measurement']['calls']=={'solver':1,'E0':1,'E1':0,'E2':0}
  evidence.append({'case':case,'cores':r['cores'],'run':runref,'result':resultref,'raw_result_sha256':sha(plain),'raw_result_bytes':len(plain),'all_metrics_match':True})
 assert stable(p/'board-feed-500.json')==raw
 def git(path):return subprocess.check_output(['git','show',FANG+':'+path],cwd=root)
 craw=git(FANG_DIR+'coverage.json');coverage=json.loads(craw);assert coverage['solver_commit']=='e64723bdf99669c44f76d8e90ab0379a8578522e'
 fang=[]
 for r in coverage['rows']:
  case=r['case_id'];rr=git(r['run_path']);run=json.loads(rr);ref=run['artifacts']['result'];packed=git(ref['path']);assert sha(packed)==ref['sha256']==r['result_sha256'];result=json.loads(gzip.decompress(packed))
  assert run['solver_commit']==coverage['solver_commit'] and run['status']=='ok' and run['cores']==4 and run['case_id']==case
  assert result['scene']=='B' and result.get('problem')!=3 and result['num_cores']==4 and result['makespan']==run['metrics']['makespan_cycles']==r['makespan_cycles']
  assert all(run['identity'][k]==baselines[case]['identity'][k] for k in ('graph_sha256','config_sha256','official_sha256'))
  assert r['baseline_cycles']==baselines[case]['makespan']
  assert result['data_movement_bytes']['added_copy_bytes']==r['extra_ddr_bytes'] and result['data_movement_bytes']['spill_added_copy_bytes']==r['spill_bytes']
  assert run['stages']['solver']['wall_seconds']==r['solver_wall_seconds'] and run['stages']['E0']['wall_seconds']==r['E0_wall_seconds']
  fang.append({**r,'run_sha256':sha(rr),'result':ref,'identity':run['identity'],'source_commit':run['solver_commit'],'environment':run['environment'],'ddr_bytes':result['data_movement_bytes']['scheduled_copy_bytes']})
 assert len(fang)==100 and len({r['case_id'] for r in fang})==100
 packed=gzip.compress(raw,mtime=0)
 with (OUT/'semantic-feed-500.json.gz').open('xb') as f:f.write(packed)
 with (OUT/'fang-coverage.json').open('xb') as f:f.write(craw)
 save('official-baselines-100.json',baselines);save('semantic-artifact-checks.json',evidence);save('fang-verified-100.json',fang)
 save('CAPTURE.json',{'semantic_data_commit':DATA,'semantic_feed_path':REL+'/board-feed-500.json','semantic_feed_raw_sha256':sha(raw),'semantic_feed_gzip_sha256':sha(packed),'commit_mapping':'Published data commit and raw feed SHA provided by owner; all local bytes verified against exact SHA. No semantic Git command executed.',
      'fang_data_commit':FANG,'fang_source_commit':coverage['solver_commit'],'fang_coverage_path':FANG_DIR+'coverage.json','fang_coverage_sha256':sha(craw),'fang_input':'Read with git show at fixed local data commit; no fetch or mutation.',
      'official_baseline_manifest_sha256':sha(bmraw),'official_source_manifest_sha256':sha(smraw),'baseline_results_and_receipts_checked':100,'semantic_results_and_receipts_checked':500,'semantic_result_raw_roundtrips':500,'semantic_raw_result_bytes':totalraw,'fang_results_and_receipts_checked':100,'feed_stable_after_reads':True,
      'new_solver_E0_E1_E2_calls':0,'capture_wall_seconds':time.monotonic()-start,'limits':'Existing evidence verification, not new execution, central import or complete scientific acceptance. Plans and traces not separately revalidated here.'})
 print(json.dumps({'semantic':500,'baselines':100,'fang':100,'seconds':time.monotonic()-start}))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--producer-root',required=True,type=Path);main(a.parse_args().producer_root)
