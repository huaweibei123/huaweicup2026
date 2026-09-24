"""Read-only audit of three completed shared-wave pilot cells."""
from datetime import datetime, timezone
import gzip, hashlib, json, os, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]; HOME=Path(__file__).resolve().parent
SOURCE='ee1b8fd39efab8c8ed8140bbebe4c08e778052b9'; RUNNER='774cfe8474dad18315d08368db02d030387d6b6d'; OLD='571536962b3f6ad9468584a0e5ae04398e684543'
def sha(b): return hashlib.sha256(b).hexdigest()
def read(p):
 b=Path(p).read_bytes(); return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)
def git_bytes(c,p): return subprocess.check_output(['git','show',c+':'+p],cwd=ROOT)
def main():
 run=HOME/'run'; batch=read(run/'batch.json'); assert len(batch['cells'])==3
 assert batch['status']=='completed' and batch['source_commit']==SOURCE and batch['runner_commit']==RUNNER
 rows=[]; failed=[]
 for case in ('044','083','092'):
  base=run/f'{case}-k4'; cell=base/f'{case}-k4'; rec=read(cell/'run.json'); ctx=read(base/'context.json'); feed=read(base/f'board-feed-{case}-k4.json'); assert len(feed['records'])==1; row=feed['records'][0]
  bcell=next(x for x in batch['cells'] if x.get('attempt',{}).get('case')==case)
  assert bcell['accepted'] is True and rec['status']=='ok' and rec['calls']=={'solver':1,'E0':1,'E1':0,'E2':0}
  assert ctx['source_commit']==row['solver_commit']==SOURCE and ctx['runner_commit']==RUNNER and row['evaluator']['commit']==SOURCE and row['evaluator']['route']=='E0'
  assert row['identity']['config_sha256']==ctx['hashes']['inputs']['data/config.txt']
  graph_path=f'data/raw/a/official/data/case_{case}.json'; graph_bytes=(ROOT/graph_path).read_bytes(); config_bytes=(ROOT/'data/raw/a/official/data/config.txt').read_bytes()
  assert sha(graph_bytes)==row['identity']['graph_sha256'] and sha(config_bytes)==row['identity']['config_sha256']
  plan=read(cell/'plan.json'); graph=json.loads(graph_bytes.decode()); eligible={o['id'] for o in graph['ops'] if o['op'] not in ('COPY_IN','COPY_OUT')}; node_map={int(k):v for k,v in plan['node_to_subgraph'].items()}; scheduled=[s for word in plan['core_schedules'] for s in word]
  assert set(node_map)==eligible and len(scheduled)==len(set(scheduled)) and all(node_map[u] in set(scheduled) for u in eligible)
  manifest=read(cell/'manifest.json')
  for p,e in manifest.items():
   data=(cell/p).read_bytes(); assert sha(data)==e['sha256'] and len(data)==e['bytes']
  for e in row['artifacts'].values(): assert sha((ROOT/e['path']).read_bytes())==e['sha256']
  compression=read(cell/'archive.json')['compression']
  for e in compression.values():
   z=(cell/e['stored']).read_bytes(); raw=gzip.decompress(z); assert sha(z)==e['stored_sha256'] and len(z)==e['stored_bytes'] and sha(raw)==e['raw_sha256'] and len(raw)==e['raw_bytes']
  online=read(cell/'online/solver.json'); assert online['calls']=={'E0':0,'E1':0,'E2':0} and len(online['attempts'])==1
  result=read(cell/'final/result.json.gz'); m=result['data_movement_bytes']; assert result['makespan']==row['metrics']['makespan_cycles'] and m['added_copy_bytes']==row['metrics']['extra_ddr_bytes'] and m['spill_added_copy_bytes']==row['metrics']['spill_bytes']
  procs=[read(cell/'solver-process/process.json'),read(cell/'final/process.json'),read(run/f'{case}-k4-driver/process.json')]; pids=[]
  for p in procs:
   assert p['status']=='ok' and p['exit_code']==0 and p['surviving_pids']==[]
   try: os.kill(p['pid'],0)
   except ProcessLookupError: state='absent'
   else: state='present_or_recycled_unknown'
   assert state=='absent'; pids.append(p['pid'])
  oldpath=f'results/a/q2-nikolastarx/semantic-benchmark-s59ee-20260925/20260924T1729Z-s59ee/cells/{case}/k4/result.json.gz'; ob=git_bytes(OLD,oldpath)
  old=json.loads(gzip.decompress(ob)); assert old['scene']=='B' and old['num_cores']==4 and result['scene']=='B' and result['num_cores']==4
  old_plan_raw=git_bytes(OLD,oldpath.rsplit('/',1)[0]+f'/case_{case}_multicore_res.json'); old_plan=json.loads(old_plan_raw)
  def ownership(p):
   task_core={sg:k for k,word in enumerate(p['core_schedules']) for sg in word}
   return {u:task_core[sg] for u,sg in p['node_to_subgraph'].items()}
  assert plan['node_to_subgraph']==old_plan['node_to_subgraph'] and ownership(plan)==ownership(old_plan)
  assert plan['core_schedules']!=old_plan['core_schedules']
  reduction=1-result['makespan']/old['makespan']
  rows.append({'case':case,'old_makespan':old['makespan'],'new_makespan':result['makespan'],'reduction_fraction':reduction,'old_movement':old['data_movement_bytes'],'new_movement':m,'solver_seconds':row['metrics']['solver_wall_seconds'],'e0_seconds':row['metrics']['evaluation_wall_seconds'],'manifest_entries':len(manifest),'feed_refs':len(row['artifacts']),'gzip_roundtrips':len(compression),'eligible_ops':len(eligible),'process_pids_absent':pids,'old_result_sha256':sha(ob),'old_plan_sha256':sha(old_plan_raw),'same_partition_and_core_assignment':True,'changed_core_order':True})
 report={'observed_at':datetime.now(timezone.utc).isoformat(),'source_commit':SOURCE,'runner_commit':RUNNER,'reference_data_commit':OLD,'cells':rows,'all_passed':True,'scope':'Three accepted cells only; not full-suite results. Audit invokes no solver/evaluator and adds zero scoring.'}
 (run/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
 lines=['# Shared-wave pilot receipt: three cells','',f"Source `{SOURCE}`; runner `{RUNNER}`; historical comparison read from `{OLD}`. Each cell has one solver and one external E0, with zero online E0/E1/E2. All selected process receipts and live PID checks indicate exit; manifest/feed hashes, gzip roundtrips, input hashes, and unique operator coverage passed.",'','| Case / cores | Makespan old → new | Change | Extra DDR old → new | Spill new | Solver / E0 seconds |','|---|---:|---:|---:|---:|---:|']
 for r in rows: lines.append(f"| {r['case']} / 4 | {r['old_makespan']:,} → {r['new_makespan']:,} | {100*r['reduction_fraction']:.2f}% lower | {r['old_movement']['added_copy_bytes']:,} → {r['new_movement']['added_copy_bytes']:,} B | {r['new_movement']['spill_added_copy_bytes']:,} B | {r['solver_seconds']:.3f} / {r['e0_seconds']:.3f} |")
 lines+=['','Each new plan preserves the old node-to-subgraph partition and operator core assignment; only core order differs. This controls the submitted-plan change, but aggregate totals alone do not identify the individual queue or credit mechanism. The 092 result retains substantial spill. These are three single-cell observations, not a full-suite score. Audit performed no solver or evaluator run and adds zero scoring.']
 (run/'SUMMARY.md').write_text('\n'.join(lines)+'\n'); print(json.dumps(rows))
if __name__=='__main__': main()
