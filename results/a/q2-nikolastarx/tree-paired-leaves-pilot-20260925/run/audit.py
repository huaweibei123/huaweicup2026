"""Read original pilot artifacts and write new derived reports; no scoring."""
from pathlib import Path
import gzip, hashlib, json, os
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'docs/a/source-manifest.json').is_file())
HOME=Path(__file__).resolve().parent
read=lambda p:json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,value):
 with (HOME/name).open('x') as f:f.write(json.dumps(value,indent=2)+'\n')
def main():
 assert not (HOME/'verification.json').exists()
 originals={str(p.relative_to(HOME)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in HOME.rglob('*') if p.is_file() and p.name!='audit.py'}
 batch=read(HOME/'batch.json');manifest=read(HOME.parent/'manifest.json')
 assert batch['status']=='completed' and len(batch['cells'])==manifest['max_E0']==manifest['max_solver']==3
 assert batch['source_commit']=='22d773abfa5f78cf18fec65b8fb5759d88f11842'
 assert batch['runner_commit']=='fa92d86add0dd8a52d2d644864925aaf620c7426'
 records=[];rows=[];pids=[];checked=0
 for item,k in zip(batch['cells'],(2,4,5)):
  key=f'062-k{k}';assert item['cell']==key;matrix=HOME/key;folder=matrix/key
  row=read(folder/'run.json');r=read(folder/'final/result.json.gz');ledger=read(folder/'online/solver.json');context=read(matrix/'context.json')
  record=read(matrix/f'board-feed-{key}.json')['records'][0]
  assert row==item['attempt'] and item['accepted'] and row['status']==record['status']=='ok'
  assert row['calls']=={'solver':1,'E0':1,'E1':0,'E2':0} and ledger['calls']=={'E0':0,'E1':0,'E2':0}
  assert context['source_commit']==batch['source_commit'] and context['runner_commit']==batch['runner_commit']
  for cat,items in context['hashes'].items():
   for name,h in items.items():
    path=ROOT/name if cat in ('source','runner') else ROOT/'data/raw/a/official'/name
    assert sha(path)==h
  plan=read(folder/'plan.json');detail=ledger['attempts'][0]['detail']
  assert set(plan)=={'node_to_subgraph','core_schedules'}
  assert sha(folder/'plan.json')==ledger['plan_sha256']==record['identity']['plan_sha256']
  assert r['makespan']==row['makespan_cycles']==record['metrics']['makespan_cycles']
  for metric,key2 in [('ddr_bytes','scheduled_copy_bytes'),('extra_ddr_bytes','added_copy_bytes'),('spill_bytes','spill_added_copy_bytes')]:assert record['metrics'][metric]==r['data_movement_bytes'][key2]
  assert record['metrics']['solver_wall_seconds']==row['solver']['wall_seconds']
  assert record['metrics']['evaluation_wall_seconds']==row['final']['wall_seconds']
  for entry in [*record['artifacts'].values(),record['baseline']['result']]:assert sha(ROOT/entry['path'])==entry['sha256']
  for rel,x in read(folder/'manifest.json').items():
   assert sha(folder/rel)==x['sha256'] and (folder/rel).stat().st_size==x['bytes'];checked+=1
  for x in read(folder/'archive.json')['compression'].values():
   raw=gzip.decompress((folder/x['stored']).read_bytes());assert hashlib.sha256(raw).hexdigest()==x['raw_sha256'] and len(raw)==x['raw_bytes']
  for receipt in (item['driver'],row['solver'],row['final']):
   assert receipt['status']=='ok' and receipt['exit_code']==0 and receipt['surviving_pids']==[];pids.append(receipt['pid'])
   try:os.kill(receipt['pid'],0);raise AssertionError('live process')
   except ProcessLookupError:pass
  old=ROOT/f'results/a/q2-nikolastarx/tree-packets-first-pilot-20260925/run/{key}/{key}'
  oldplan=read(old/'plan.json');oldresult=read(old/'final/result.json.gz');oldrow=read(old/'run.json')
  assert oldplan['node_to_subgraph']==plan['node_to_subgraph']
  rev={sg:int(u) for u,sg in plan['node_to_subgraph'].items()}
  before=[[rev[sg] for sg in seq] for seq in oldplan['core_schedules']];after=[[rev[sg] for sg in seq] for seq in plan['core_schedules']]
  assert {u:c for c,s in enumerate(before) for u in s}=={u:c for c,s in enumerate(after) for u in s}
  expected=[list(s) for s in before]
  for pair in detail['pairs']:
   c,s,t=pair['core'],pair['start'],pair['stop'];left,right=pair['left'],pair['right']
   assert before[c][s:t]==left+right+[pair['join']]
   expected[c][s:t]=[u for ab in zip(left,right) for u in ab]+[pair['join']]
  assert after==expected
  assert oldresult['data_movement_bytes']==r['data_movement_bytes']
  pre=read(matrix/f'precheck-{key}.json');assert pre['exit_code']==0 and json.loads(pre['stdout'])['eligible']==1
  rows.append(dict(case='062',cores=k,old_makespan=oldresult['makespan'],makespan=r['makespan'],reduction_percent=100*(1-r['makespan']/oldresult['makespan']),extra_ddr_bytes=r['data_movement_bytes']['added_copy_bytes'],spill_bytes=0,solver_seconds=row['solver']['wall_seconds'],old_solver_seconds=oldrow['solver']['wall_seconds'],E0_seconds=row['final']['wall_seconds'],fixed_plan_bound=detail['fixed_compute_fifo_bound_after'],bound_gap=r['makespan']-detail['fixed_compute_fifo_bound_after']))
  records.append(record)
 assert all(sha(HOME/name)==x['sha256'] for name,x in originals.items())
 save('verification.json',dict(source=batch['source_commit'],runner=batch['runner_commit'],originals=originals,manifest_entries=checked,pids_confirmed_gone=pids,actual_calls=dict(solver=3,E0=3,E1=0,E2=0,online_E0=0,retries=0),same_owner=True,exact_pair_rewrite=True,official_movement_all_fields_unchanged=True,rows=rows,aggregate_seconds=batch['aggregate_wall_seconds'],central_admission='not asserted'))
 save('board-feed.json',dict(schema_version=1,submission_version=1,records=records))
 lines=['# Paired-leaf official results','', '| Cores | Prior packets-first | Paired leaves | Reduction | Added DDR B | Spill B | Solver s | E0 s |','|---|---:|---:|---:|---:|---:|---:|---:|']
 for r in rows:lines.append(f"|{r['cores']}|{r['old_makespan']}|{r['makespan']}|{r['reduction_percent']:.4f}%|{r['extra_ddr_bytes']}|0|{r['solver_seconds']:.6f}|{r['E0_seconds']:.6f}|")
 lines+=['','Three solver and three unmodified final E0 calls, zero online scoring/retries. Same ownership and exact pair rewrite verified; all official movement fields unchanged. Total batch wall seconds: '+str(batch['aggregate_wall_seconds'])+'. These are three development cells, not a full-suite average or global optimality proof.','', 'Source '+batch['source_commit']+'; runner '+batch['runner_commit']+'. Prior data ae1d8c4d904395e010d742ea090811fb6042f6e8. Nine process IDs are gone. Original hashes, comparisons and bound gaps are in verification.json. Central admission is tracked separately.']
 (HOME/'SUMMARY.md').write_text('\n'.join(lines)+'\n');print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
