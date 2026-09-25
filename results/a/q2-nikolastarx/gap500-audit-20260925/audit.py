#!/usr/bin/env python3
"""Independent read-only audit of the frozen 100x1-5 adaptive-gap run.
Requires a complete accepted batch. Never invokes solver or evaluator.
"""
import argparse, csv, gzip, hashlib, json, math, statistics, subprocess, sys
from pathlib import Path
SOLVER='923b25ecb0b9d6d0e2d3f149fccef431b5403f99'
RUNNER='9db8247f9a864a3279f3bd315aa09d8ad7dd5206'
MANIFEST_SHA='fa603090ef99f56e4ead7b37cc16b2fa961f884334cf1c23ed33b6baba3af0a2'
OLD_SOURCE='2794ceba93acc1f7fc119154f61082511843d4b3'
FIELDS=('original_graph_copy_bytes','scheduled_copy_bytes','added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes')
EXPECTED={(f'{i:03d}',k) for i in range(1,101) for k in range(1,6)}
def sha(b):return hashlib.sha256(b).hexdigest()
def decode(b):return json.loads(gzip.decompress(b) if b[:2]==b'\x1f\x8b' else b)
def canonical(plan):return sha(json.dumps(plan,sort_keys=True,allow_nan=False).encode())
def speedup(baseline_singlecore, makespan):return baseline_singlecore/makespan
def paired_baseline(row,spec,old_record,B,newM):
 """Keep official single-core B separate from same-cell old algorithm M."""
 oldM=old_record['metrics']['makespan_cycles']
 if row.get('baseline_m')!=oldM or spec.get('baseline_m')!=oldM:raise ValueError('old same-cell baseline_m mismatch')
 if type(B) not in (int,float) or type(oldM) not in (int,float) or type(newM) not in (int,float) or min(B,oldM,newM)<=0:raise ValueError('invalid Makespan')
 return {'B_i':B,'old_M':oldM,'new_M':newM,'old_B_over_M':speedup(B,oldM),'new_B_over_M':speedup(B,newM)}
def stats(vals):
 x=sorted(vals);return {'n':len(x),'mean':statistics.fmean(x),'median':statistics.median(x),'p95_nearest_rank':x[math.ceil(.95*len(x))-1],'max':x[-1]}
class GitObjects:
 def __init__(self,root):self.p=subprocess.Popen(['git','-C',str(root),'cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
 def get(self,commit,path):
  self.p.stdin.write(f'{commit}:{path}\n'.encode());self.p.stdin.flush();h=self.p.stdout.readline().split()
  if len(h)!=3 or h[1]!=b'blob':raise ValueError(f'Git blob missing: {commit}:{path}')
  b=self.p.stdout.read(int(h[2]));self.p.stdout.read(1);return b
 def close(self):self.p.stdin.close();self.p.wait()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo-root',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--run-summary',type=Path,required=True);ap.add_argument('--old-audit-dir',type=Path,required=True);a=ap.parse_args()
 repo=a.repo_root.resolve();manifest_path=a.manifest.resolve();summary_path=a.run_summary.resolve();out=Path(__file__).resolve().parent
 summary_raw=summary_path.read_bytes();s=json.loads(summary_raw);rows=s.get('rows',[]);accepted=sum(r.get('status')=='accepted' for r in rows)
 # Fail closed before loading cell artifacts or deriving partial means.
 if s.get('status')!='completed' or s.get('accepted_cells')!=500 or len(rows)!=500 or accepted!=500:
  print(json.dumps({'status':'incomplete','run_status':s.get('status'),'rows':len(rows),'accepted':accepted,'required':500,'scores_computed':False}));return 2
 mb=manifest_path.read_bytes();m=json.loads(mb)
 if sha(mb)!=MANIFEST_SHA or s.get('manifest_sha256')!=MANIFEST_SHA:raise ValueError('manifest SHA mismatch')
 if s.get('solver_commit')!=SOLVER or s.get('runner_commit')!=RUNNER:raise ValueError('solver/runner commit mismatch')
 if m.get('solver_commit')!=SOLVER or m.get('baseline_commit')!='60afc38b327680fbda0ff10182e3e05a01edd72d' or m.get('baseline_feed',{}).get('commit')!=m.get('baseline_commit'):raise ValueError('manifest source identity mismatch')
 if m.get('coordinates')!=[[f'{i:03d}',k] for i in range(1,101) for k in range(1,6)]:raise ValueError('manifest coordinate order mismatch')
 e2ref=m.get('e2_manifest',{});e2raw=(repo/e2ref.get('path','')).read_bytes()
 if sha(e2raw)!=e2ref.get('sha256') or m.get('e2_commit') not in e2raw.decode(errors='replace'):raise ValueError('pinned E2 source/manifest identity mismatch')
 oldsum=json.loads((a.old_audit_dir.resolve()/'summary.json').read_bytes());prov=oldsum.get('provenance',{})
 if prov.get('new_data_commit')!=m['baseline_commit'] or prov.get('new_unified_feed_sha256')!=m['baseline_feed']['sha256']:raise ValueError('prior active500 audit does not pin this baseline feed')
 if len(rows)!=500 or {(str(r['case']),int(r['cores'])) for r in rows}!=EXPECTED:raise ValueError('run grid is incomplete, duplicated or unexpected')
 feedref=m['baseline_feed'];g=GitObjects(repo);feedraw=g.get(feedref['commit'],feedref['path'])
 if sha(feedraw)!=feedref['sha256']:raise ValueError('baseline feed hash mismatch')
 feed=decode(feedraw);old={};
 for r in feed.get('records',[]):
  key=(str(r['case_id']),int(r['cores']))
  if key in old:raise ValueError(f'duplicate baseline cell {key}')
  if r.get('solver_commit')!=OLD_SOURCE or r.get('status')!='ok':raise ValueError(f'baseline identity/status mismatch {key}')
  old[key]=r
 if set(old)!=EXPECTED:raise ValueError('fixed baseline feed not full 100x1-5')
 baselines={};outrows=[];times=[];time_by={str(k):[] for k in range(1,6)};construction=online=e0count=0
 runroot=summary_path.parent
 for row in rows:
  case=str(row['case']);k=int(row['cores']);key=(case,k);d=runroot/f'{case}-k{k}';ledger=row.get('solver_ledger')
  if key!=(str(m['rows'][len(outrows)]['case']),int(m['rows'][len(outrows)]['cores'])):raise ValueError(f'run/manifest order mismatch {key}')
  if not ledger or row.get('status')!='accepted' or row.get('solver_process_in_flight') or row.get('independent_e0_in_flight'):raise ValueError(f'cell not accepted/quiescent {key}')
  attempts=ledger.get('attempts',[]);calls=ledger.get('calls',{})
  if ledger.get('status')!='ok' or ledger.get('request_in_flight') or (attempts and not ledger.get('source_checked')):raise ValueError(f'bad/unknown solver ledger {key}')
  if attempts and (ledger.get('source',{}).get('commit')!=m['e2_commit'] or ledger.get('source',{}).get('manifest_sha256')!=e2ref['sha256']):raise ValueError(f'E2 source identity mismatch {key}')
  if calls.get('E2_api_attempted')!=len(attempts) or calls.get('native_returns')!=len(attempts) or calls.get('E0_fallback')!=0 or ledger.get('possible_E0_fallback_calls')!=0 or len(attempts)>2:raise ValueError(f'E2 fallback/unknown/retry-like ledger {key}')
  if len({x.get('plan_sha256') for x in attempts})!=len(attempts) or any(x.get('status')!='native' or x.get('record',{}).get('route')!='native' or x.get('record',{}).get('status')!='ok' or x.get('record',{}).get('problem')!=2 for x in attempts):raise ValueError(f'non-native/invalid attempt {key}')
  expected_sources={Path(p).name:h for p,h in m['solver_sources'].items()};expected_sources.update({Path(p).name:h for p,h in m['auxiliary_sources'].items()})
  if ledger.get('solver_source_sha256')!=expected_sources or ledger.get('graph_sha256')!=m['rows'][len(outrows)]['graph']['sha256'] or ledger.get('config_sha256')!=m['config']['sha256'] or ledger.get('cores')!=k:raise ValueError(f'source/input identity mismatch {key}')
  planraw=(d/'plan.json').read_bytes();plan=decode(planraw)
  if sha(planraw)!=ledger.get('plan_sha256'):raise ValueError(f'plan raw hash mismatch {key}')
  comp=row.get('selected_comparison',{});record=comp.get('record',{});canon=canonical(plan)
  if comp.get('plan_canonical_sha256')!=canon or (attempts and comp.get('kind')!='selected_native') or (not attempts and comp.get('kind')!='frozen_baseline_zero_score'):raise ValueError(f'selected plan canonical hash/kind mismatch {key}')
  if attempts:
   selected=[x for x in attempts if x.get('plan_sha256')==canon]
   if len(selected)!=1 or selected[0]['record']!=record:raise ValueError(f'selected native attempt binding mismatch {key}')
  else:
   baseplanref=m['rows'][len(outrows)]['baseline_plan'];oldplanraw=g.get(baseplanref['commit'],baseplanref['path']);oldplan=decode(oldplanraw)
   if sha(oldplanraw)!=baseplanref['sha256'] or plan!=oldplan:raise ValueError(f'zero-call plan differs baseline {key}')
  resultraw=(d/'result.json').read_bytes();result=decode(resultraw)
  if sha(resultraw)!=row.get('result',{}).get('result_sha256') or result.get('scene')!='B' or result.get('num_cores')!=k or result.get('makespan')!=record.get('makespan') or result.get('cross_task_traffic')!=record.get('cross_task_traffic') or result.get('data_movement_bytes')!={f:record['data_movement_bytes'][f] for f in FIELDS}:raise ValueError(f'E0/native result mismatch {key}')
  if row['result'].get('makespan')!=result['makespan'] or row['result'].get('movement')!={f:result['data_movement_bytes'][f] for f in FIELDS} or row['result'].get('cross_task_traffic')!=result['cross_task_traffic']:raise ValueError(f'summary result mismatch {key}')
  for stage,proc in [('solver',row.get('solver_process',{})),('E0',row.get('e0_process',{}))]:
   if proc.get('status')!='ok' or proc.get('exit_code')!=0 or proc.get('surviving_pids')!=[]:raise ValueError(f'{stage} process receipt mismatch {key}')
   disk=d/('solver-process' if stage=='solver' else 'e0-process')/'process.json'
   if json.loads(disk.read_bytes())!=proc:raise ValueError(f'{stage} process file/receipt mismatch {key}')
  base_record=old[(case,1)];old_record=old[key]
  base=base_record.get('baseline',{});bresult=base.get('result',{})
  if base.get('route')!='E0' or base.get('entrypoint')!='singlecore_evaluate.evaluate_singlecore' or base.get('graph_sha256')!=m['rows'][len(outrows)]['graph']['sha256'] or base.get('config_sha256')!=m['config']['sha256'] or base.get('official_sha256')!=old_record['identity']['official_sha256']:raise ValueError(f'official singlecore identity mismatch {case}')
  braw=g.get(feedref['commit'],bresult['path'])
  if sha(braw)!=bresult.get('sha256'):raise ValueError(f'official singlecore baseline hash mismatch {case}')
  bdoc=decode(braw)
  if bdoc.get('scene')!='A' or bdoc.get('num_cores')!=1:raise ValueError(f'official singlecore result identity mismatch {case}')
  B=bdoc['makespan'];baselines[case]=B
  oldM=old_record['metrics']['makespan_cycles'];oldresult=old_record['artifacts']['result'];oldraw=g.get(feedref['commit'],oldresult['path'])
  olddoc=decode(oldraw)
  if sha(oldraw)!=oldresult['sha256'] or olddoc.get('makespan')!=oldM or olddoc.get('scene')!='B' or olddoc.get('num_cores')!=k or olddoc['data_movement_bytes']['added_copy_bytes']!=old_record['metrics']['extra_ddr_bytes']:raise ValueError(f'old algorithm result hash/metrics mismatch {key}')
  if attempts:
   oldplanref=m['rows'][len(outrows)]['baseline_plan'];oldplanraw=g.get(oldplanref['commit'],oldplanref['path'])
   if sha(oldplanraw)!=oldplanref['sha256'] or attempts[0]['plan_sha256']!=canonical(decode(oldplanraw)):raise ValueError(f'first native baseline plan binding mismatch {key}')
   first=attempts[0]['record']
   if first.get('makespan')!=oldM or first.get('cross_task_traffic')!=olddoc.get('cross_task_traffic') or any(first.get('data_movement_bytes',{}).get(f)!=olddoc['data_movement_bytes'][f] for f in FIELDS):raise ValueError(f'first native baseline score mismatch {key}')
  baseline_pair=paired_baseline(row,m['rows'][len(outrows)],old_record,B,result['makespan'])
  solversec=float(row['solver_process']['wall_seconds']);times.append(solversec);time_by[str(k)].append(solversec)
  nconstructed=ledger.get('detail',{}).get('constructed_plans')
  if not isinstance(nconstructed,int) or nconstructed<1:raise ValueError(f'construction count missing {key}')
  construction+=nconstructed;online+=len(attempts);e0count+=1
  outrows.append({'case':case,'cores':k,**baseline_pair,'extra_ddr_delta_bytes':result['data_movement_bytes']['added_copy_bytes']-old_record['metrics']['extra_ddr_bytes'],'solver_wall_seconds':solversec})
 g.close()
 core={}
 for k in range(1,6):
  x=[r for r in outrows if r['cores']==k];diff=[r['new_B_over_M']-r['old_B_over_M'] for r in x]
  core[str(k)]={'n':len(x),'old_mean_B_over_M':statistics.fmean(r['old_B_over_M'] for r in x),'new_mean_B_over_M':statistics.fmean(r['new_B_over_M'] for r in x),'wins':sum(v>0 for v in diff),'losses':sum(v<0 for v in diff),'ties':sum(v==0 for v in diff),'solver_wall_seconds':stats([r['solver_wall_seconds'] for r in x])}
 totals=s.get('calls',{})
 if s.get('call_count_complete') is not True or totals.get('solver_started')!=500 or totals.get('E2_api_attempted')!=online or totals.get('native_returns')!=online or totals.get('unknown_in_flight')!=0 or totals.get('E0_fallback_confirmed')!=0 or totals.get('E0_fallback_possible')!=0 or totals.get('E0_independent_started')!=500 or construction==0:raise ValueError('run call/construction totals mismatch')
 audit={'status':'complete','manifest_sha256':MANIFEST_SHA,'solver_commit':SOLVER,'runner_commit':RUNNER,'cells':500,'core_means':core,'solver_wall_seconds':stats(times),'calls':{'solver':500,'constructed_plans':construction,'online_native_E2':online,'external_E0':e0count,'fallback':0,'unknown':0,'retries':0,'one_solver_start_per_unique_cell':True},'limitations':'One frozen algorithm over this complete input grid. Solver wall is the outer process receipt including online E2; E0 is separate. No evaluator was run by this audit.'}
 audit['summary_sha256']=sha(summary_raw)
 with (out/'paired.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(outrows[0]));writer.writeheader();writer.writerows(outrows)
 (out/'audit.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit,ensure_ascii=False))
if __name__=='__main__':sys.exit(main())
