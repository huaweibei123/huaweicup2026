"""Verify recorded frontier-pilot evidence without running any evaluator."""
from datetime import datetime, timezone
import gzip, hashlib, json, os, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
HOME = Path(__file__).resolve().parent
SOURCE = 'ee1b8fd39efab8c8ed8140bbebe4c08e778052b9'
RUNNER = '64e0133b97eb7dee50aa835e9c1714d84ce508eb'
OLD = '571536962b3f6ad9468584a0e5ae04398e684543'
def sha(b): return hashlib.sha256(b).hexdigest()
def read(p):
 b=Path(p).read_bytes()
 return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)
def git_bytes(commit,path): return subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)
def main():
 run=HOME/'run'; base=run/'056-k5'; cell=base/'056-k5'
 batch,context,receipt=read(run/'batch.json'),read(base/'context.json'),read(cell/'run.json')
 feed_path=base/'board-feed-056-k5.json'; feed=read(feed_path)
 assert len(feed['records'])==1; row=feed['records'][0]
 assert batch['source_commit']==context['source_commit']==row['solver_commit']==SOURCE
 assert batch['runner_commit']==context['runner_commit']==RUNNER
 assert batch['status']=='completed' and receipt['status']=='ok'
 assert receipt['calls']=={'solver':1,'E0':1,'E1':0,'E2':0}
 assert row['evaluator']['commit']==SOURCE and row['evaluator']['route']=='E0'
 assert row['identity']['graph_sha256']==context['hashes']['inputs']['data/case_056.json']
 assert row['identity']['config_sha256']==context['hashes']['inputs']['data/config.txt']
 manifest=read(cell/'manifest.json')
 for path,e in manifest.items():
  b=(cell/path).read_bytes(); assert sha(b)==e['sha256'] and len(b)==e['bytes'],path
 for e in row['artifacts'].values(): assert sha((ROOT/e['path']).read_bytes())==e['sha256'],e['path']
 compression=read(cell/'archive.json')['compression']
 for e in compression.values():
  b=(cell/e['stored']).read_bytes(); raw=gzip.decompress(b)
  assert sha(b)==e['stored_sha256'] and len(b)==e['stored_bytes']
  assert sha(raw)==e['raw_sha256'] and len(raw)==e['raw_bytes']
 procs=[read(cell/'solver-process/process.json'),read(cell/'final/process.json')]
 driver=read(run/'056-k5-driver/process.json')
 procs.append(driver)
 expected={89930,90058,90085}; assert {p['pid'] for p in procs}==expected
 pid_states=[]
 for p in procs:
  assert p['status']=='ok' and p['exit_code']==0 and p['surviving_pids']==[]
  try: os.kill(p['pid'],0)
  except ProcessLookupError: state='absent'
  except PermissionError: state='present_or_recycled_unknown'
  else: state='present_or_recycled_unknown'
  pid_states.append({'pid':p['pid'],'state':state})
 assert all(x['state']=='absent' for x in pid_states)
 result,plan,online=read(cell/'final/result.json.gz'),read(cell/'plan.json'),read(cell/'online/solver.json')
 assert online['calls']=={'E0':0,'E1':0,'E2':0} and len(online['attempts'])==1
 static=json.loads(git_bytes(SOURCE,'results/a/q2-nikolastarx/dominant-route-static-20260925/056-k5/plan.json'))
 assert plan==static
 graph=json.loads((ROOT/'data/raw/a/official/data/case_056.json').read_text())
 eligible={o['id'] for o in graph['ops'] if o['op'] not in ('COPY_IN','COPY_OUT')}
 node_map={int(u):sg for u,sg in plan['node_to_subgraph'].items()}
 scheduled=[sg for word in plan['core_schedules'] for sg in word]
 assert len(scheduled)==len(set(scheduled))
 assert set(node_map)==eligible and all(node_map[u] in set(scheduled) for u in eligible)
 inputs={'graph':'data/raw/a/official/data/case_056.json','config':'data/raw/a/official/data/config.txt'}
 input_hashes={k:sha((ROOT/v).read_bytes()) for k,v in inputs.items()}
 assert input_hashes['graph']==row['identity']['graph_sha256'] and input_hashes['config']==row['identity']['config_sha256']
 old_path='results/a/q2-nikolastarx/semantic-benchmark-s59ee-20260925/20260924T1729Z-s59ee/cells/056/k5/result.json.gz'
 old_raw=git_bytes(OLD,old_path); old=json.loads(gzip.decompress(old_raw))
 assert old['scene']=='B' and old['num_cores']==5 and old['makespan']==253392
 assert result['scene']=='B' and result['num_cores']==5 and result['makespan']==165886
 assert result['data_movement_bytes']['added_copy_bytes']==row['metrics']['extra_ddr_bytes']==7222022
 assert result['data_movement_bytes']['spill_added_copy_bytes']==row['metrics']['spill_bytes']==0
 reduction=1-result['makespan']/old['makespan']
 report={'observed_at':datetime.now(timezone.utc).isoformat(),'source_commit':SOURCE,'runner_commit':RUNNER,'reference_data_commit':OLD,'old_result_stored_sha256':sha(old_raw),'old_makespan':old['makespan'],'new_makespan':result['makespan'],'makespan_reduction_fraction':reduction,'old_movement':old['data_movement_bytes'],'new_movement':result['data_movement_bytes'],'solver_seconds':row['metrics']['solver_wall_seconds'],'final_e0_seconds':row['metrics']['evaluation_wall_seconds'],'calls':receipt['calls'],'online_calls':online['calls'],'manifest_entries_verified':len(manifest),'feed_refs_verified':len(row['artifacts']),'compression_roundtrips_verified':len(compression),'input_hashes':input_hashes,'static_plan_semantic_match':True,'unique_compute_coverage':len(eligible),'pids':pid_states,'scope':'One cell only; this is not a full 500-cell replacement or causal proof. Audit ran no solver/evaluator and adds zero scoring.'}
 (run/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
 (run/'SUMMARY.md').write_text(f'''# Frontier pilot receipt: one cell

Case 056, five cores: Makespan **{old['makespan']:,} → {result['makespan']:,} cycles** ({100*reduction:.2f}% lower). Extra DDR movement is **{old['data_movement_bytes']['added_copy_bytes']:,} → {result['data_movement_bytes']['added_copy_bytes']:,} bytes**; spill is zero in the new E0 result. The movement increase means the result is a tradeoff, and aggregate totals alone do not establish causation.

The completed run records one solver ({row['metrics']['solver_wall_seconds']:.9f} s), one final external E0 ({row['metrics']['evaluation_wall_seconds']:.9f} s), and zero online E0/E1/E2 calls. No retries are recorded. The actual plan is semantically equal to the fixed static plan at source `{SOURCE}`. Graph/config hashes match the feed identity. Runner: `{RUNNER}`; old comparator data read from `{OLD}`.

Unique compute coverage: all {len(eligible):,} eligible operators assigned once. Manifest entries ({len(manifest)}), feed artifact references ({len(row['artifacts'])}), both gzip/raw roundtrips, and all three recorded process IDs were checked. This audit performed no solver or evaluator call and adds zero scoring. It is one single-cell evidence item, not a replacement for the full 500-cell evidence set, nor a causal proof from totals.
''')
 print(json.dumps({'old_makespan':old['makespan'],'new_makespan':result['makespan'],'reduction_pct':round(100*reduction,3),'new_extra_ddr_bytes':result['data_movement_bytes']['added_copy_bytes'],'checks':'passed'}))
if __name__=='__main__': main()
