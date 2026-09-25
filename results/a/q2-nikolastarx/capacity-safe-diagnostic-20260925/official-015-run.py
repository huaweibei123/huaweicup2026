from pathlib import Path
import hashlib,json,os,sys,time,zipfile
root=Path('/content/p2-copyguard-linux-s8ee-20260925')
plan=Path('/content/p2-capacity-safe-015.json')
assert hashlib.sha256(plan.read_bytes()).hexdigest()=='b6e3f6b52751bd98e2de9a6aab4c076ac7110af18792e4512e78e749ac05fb5d'
manifest=json.loads((root/'capsule-manifest.json').read_bytes())
for rel,expected in manifest['files'].items():
 assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==expected
sys.path.insert(0,str(root))
from src.q2_nikolastarx.evaluate_feedback import monitored
out=Path('/content/p2-capacity-safe-015-output');out.mkdir(exist_ok=False)
argv=[str(root/'.venv/bin/python'),'-B',str(root/'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'),str(root/'data/raw/a/official/data/case_015.json'),str(plan),'--config',str(root/'data/raw/a/official/data/config.txt'),'--output',str(out/'result.json'),'--trace-output',str(out/'trace.json'),'--log-output',str(out/'official.log')]
receipt={'scope':'one saved-seed fixed-owner order repair probe, not cold full solver','prototype_commit':'005943b06','E0_reserved':1,'E2':0,'retries':0,'plan_sha256':'b6e3f6b52751bd98e2de9a6aab4c076ac7110af18792e4512e78e749ac05fb5d','old_M':40828,'plan_source':'locally constructed in 0.053831875s from saved seed/target'}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
process=monitored(argv,out/'e0-process',time.perf_counter()+60,4<<30)
receipt['process']=process
if process['status']=='ok' and not process['surviving_pids']:
 result=json.loads((out/'result.json').read_bytes())
 assert result['scene']=='B' and result['num_cores']==5
 receipt.update(status='completed',M=result['makespan'],movement=result['data_movement_bytes'])
else:receipt['status']='stopped'
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
archive=Path('/content/p2-capacity-safe-015-results.zip')
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for p in sorted(out.rglob('*')):
  if p.is_file():z.write(p,p.relative_to(out))
 z.write(plan,'plan.json')
print(json.dumps({k:v for k,v in receipt.items() if k!='process'}))
print(json.dumps({'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size}))
