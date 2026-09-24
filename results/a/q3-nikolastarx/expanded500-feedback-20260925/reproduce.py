import argparse,csv,gzip,hashlib,json,statistics
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--old-root',type=Path,required=True);ap.add_argument('--new-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
oldrel=Path('results/a/q3-nikolastarx/unified-full500-20260925-s59/20260924T1741Z-s59ee/board-feed-500-verified.json')
newrel=Path('results/a/q3-nikolastarx/expanded-full500-20260925-s59/20260924T1837Z-s59ee')
oldsource='2d5459fa042507cce0f0343e544ed43784c8488b';newsource='a5dafdf94d0694132fb9ec7121f5fe1fe0d6ee3b'
h=lambda b:hashlib.sha256(b).hexdigest()
ob=(a.old_root/oldrel).read_bytes();assert h(ob)=='f7d2d03f65584221cb4c7641ca0805ae3941079662ffac3190ff341f64c2eedd'
old=json.loads(ob)['records'];assert len(old)==500
expected={(f'{i:03d}',k) for i in range(1,101) for k in range(1,6)}
key=lambda r:(r['case_id'],r['cores'])
om={key(r):r for r in old};assert set(om)==expected and len(om)==len(old)
new=[];inputs={};batches=[]
for i in range(1,11):
 rel=newrel/f's{i:02d}'/'batch.json';raw=(a.new_root/rel).read_bytes();d=json.loads(raw);inputs[str(rel)]=h(raw)
 assert d['solver_commit']==newsource and d['solver_module']=='src.q3.expanded_solve' and d['status']=='stage_complete'
 new+=d['records'];batches.append(d)
assert len(new)==500 and {key(r) for r in new}==expected
rows=[];bases={}
for n in new:
 o=om[key(n)];assert n['status']==o['status']=='ok' and o['solver_commit']==oldsource
 for k in ['graph_sha256','config_sha256','official_sha256']:assert n['identity'][k]==o['identity'][k]
 case,k=key(n)
 if case not in bases:
  ref=o['baseline']['result'];b=(a.old_root/ref['path']).read_bytes();assert h(b)==ref['sha256'];v=json.loads(gzip.decompress(b));assert v['scene']=='A' and v['num_cores']==1;bases[case]={'makespan':v['makespan'],'path':ref['path'],'sha256':ref['sha256']}
 base=bases[case]['makespan'];ometrics=o['metrics'];nc=n['cache_stats'];bytes_total=nc['hit_bytes']+nc['miss_bytes'];hit=nc['hit_bytes']/bytes_total if bytes_total else 0
 rows.append({'case_id':case,'cores':k,'baseline_M':base,'old_M':ometrics['makespan_cycles'],'new_M':n['makespan_cycles'],'old_speedup':base/ometrics['makespan_cycles'],'new_speedup':base/n['makespan_cycles'],'speedup_delta':base/n['makespan_cycles']-base/ometrics['makespan_cycles'],'old_solver_wall':ometrics['solver_wall_seconds'],'new_solver_wall':n['solver_process']['wall_seconds'],'old_extra_ddr':ometrics['extra_ddr_bytes'],'new_extra_ddr':n['data_movement_bytes']['added_copy_bytes'],'old_spill':ometrics['spill_bytes'],'new_spill':n['data_movement_bytes']['spill_added_copy_bytes'],'old_byte_hit':ometrics['cache_hit_rate'],'new_byte_hit':hit,'selected_strategy':n['solver_receipt']['selected_strategy']})
rows.sort(key=lambda r:(r['case_id'],r['cores']));summary=[]
for k in range(1,6):
 rr=[r for r in rows if r['cores']==k];assert len(rr)==100
 q={'cores':k,'n':100,'M_improved':sum(r['new_M']<r['old_M'] for r in rr),'M_equal':sum(r['new_M']==r['old_M'] for r in rr),'M_regressed':sum(r['new_M']>r['old_M'] for r in rr)}
 for c in ['old_speedup','new_speedup','old_solver_wall','new_solver_wall','old_byte_hit','new_byte_hit']:q['mean_'+c]=statistics.mean(r[c] for r in rr)
 for c in ['old_extra_ddr','new_extra_ddr','old_spill','new_spill']:q['sum_'+c]=sum(r[c] for r in rr)
 q['max_new_solver_wall']=max(r['new_solver_wall'] for r in rr);q['screenshot_target']={2:2.28,3:3.23,4:4.09,5:4.76}.get(k);q['numerical_target_met']=q['mean_new_speedup']>=q['screenshot_target'] if k>1 else None
 summary.append(q)
out={'scope':'One frozen algorithm per full500 run; batch identity and 100 original singlecore bytes read back; producer final-result audit separate; no scoring rerun','old_source':oldsource,'new_source':newsource,'old_feed_path':str(oldrel),'old_feed_sha256':h(ob),'new_batch_sha256':inputs,'baselines':bases,'by_core':summary,'calls':{k:sum(r['calls'][k] for r in new) for k in ['solver','E0','E1','E2']},'identity_matched_coordinates':500,'observations':'one parallel-process observation per coordinate; OS file cache uncontrolled; no stable runtime speedup claim; ratios are official singlecore/M, not same-core CacheGain'}
a.output.mkdir(parents=True,exist_ok=False);(a.output/'summary.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
with (a.output/'cells.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
prior=Path(__file__).resolve().parent.parent/'unified500-feedback-20260925'/'k5-gaps.csv'
gaps=list(csv.DictReader(prior.open()))
five={r['case_id']:r for r in rows if r['cores']==5}
for r in gaps:
 n=five[r['case_id']]
 assert r['graph_sha256']==om[(r['case_id'],5)]['identity']['graph_sha256']
 r['new_M']=n['new_M'];r['route_or_strategy']=n['selected_strategy'];r['solver_seconds']=n['new_solver_wall']
 r['speedup_remaining_upper_gap']=float(r['baseline_M'])/float(r['LB_B'])-float(r['baseline_M'])/r['new_M']
 r['fraction_gap_closed']=(float(r['baseline_M'])-r['new_M'])/(float(r['baseline_M'])-float(r['LB_B'])) if float(r['baseline_M'])>float(r['LB_B']) else None
gaps.sort(key=lambda r:-r['speedup_remaining_upper_gap'])
with (a.output/'k5-gaps.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(gaps[0]),lineterminator="\n");w.writeheader();w.writerows(gaps)
print(json.dumps({'by_core':summary,'calls':out['calls'],'top5_k5':sorted([r for r in rows if r['cores']==5],key=lambda r:-r['speedup_delta'])[:5]},indent=2))
