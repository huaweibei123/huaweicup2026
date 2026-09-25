from pathlib import Path
import hashlib,json,platform,subprocess,sys,time,zipfile
archive=Path('/content/p2-latency-s8ee-20260925.zip')
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='99aad8f3fef922ad4dba2bc987f5d735df1225482026520b2a9724a7297da7b6'
root=Path('/content/p2-latency-s8ee-20260925'); root.mkdir(exist_ok=False)
with zipfile.ZipFile(archive) as z:
 for name in z.namelist():
  assert (root/name).resolve().is_relative_to(root)
 z.extractall(root)
output=root/'output/probe'; output.parent.mkdir()
command=[sys.executable,'-B',str(root/'results/a/q2-nikolastarx/latency-colab-pilot-20260925/runner.py'),'--output',str(output)]
started=time.perf_counter()
r=subprocess.run(command,cwd=root,text=True,capture_output=True,timeout=375)
completion={'returncode':r.returncode,'launcher_wall_seconds':time.perf_counter()-started,'python':sys.version,'platform':platform.platform(),'capsule_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
(root/'completion.json').write_text(json.dumps(completion,indent=2)+'\n')
(root/'stdout.txt').write_text(r.stdout); (root/'stderr.txt').write_text(r.stderr)
result_zip=Path('/content/p2-latency-results-s8ee.zip')
with zipfile.ZipFile(result_zip,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for p in sorted(output.rglob('*')):
  if p.is_file(): z.write(p,p.relative_to(root))
 for name in ('completion.json','stdout.txt','stderr.txt','capsule-manifest.json'):
  z.write(root/name,name)
print(json.dumps(completion))
print(r.stdout[-4000:]); print(r.stderr[-2000:])
print(json.dumps({'result_zip_bytes':result_zip.stat().st_size,'result_zip_sha256':hashlib.sha256(result_zip.read_bytes()).hexdigest()}))
if r.returncode: raise RuntimeError('pilot failed; artifacts preserved; do not retry')
