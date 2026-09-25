from pathlib import Path
import hashlib,json,os,platform,shutil,subprocess,sys,time,zipfile
ARCHIVE_SHA='5fec90b6170b2d9d1bce4708ab12e05565372d1360b9470edda96dbea41476e8'
name='p2-copyguard-linux-s8ee-20260925'
archive=Path('/content')/(name+'.zip')
assert hashlib.sha256(archive.read_bytes()).hexdigest()==ARCHIVE_SHA
root=Path('/content')/name; root.mkdir(exist_ok=False)
output=Path('/content')/(name+'-output')
result_zip=Path('/content')/(name+'-results.zip')
with zipfile.ZipFile(archive) as z:
 for member in z.namelist():
  assert (root/member).resolve().is_relative_to(root)
 z.extractall(root)
manifest=json.loads((root/'capsule-manifest.json').read_bytes())
setup={'capsule_sha256':ARCHIVE_SHA,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'stages':[],'scoring_started':False}
start=time.perf_counter()
def command(label,argv,timeout,env=None):
 s=time.perf_counter()
 r=subprocess.run(argv,cwd=root,text=True,capture_output=True,timeout=timeout,env=env)
 (root/(label+'-stdout.txt')).write_text(r.stdout); (root/(label+'-stderr.txt')).write_text(r.stderr)
 setup['stages'].append({'stage':label,'argv':argv,'returncode':r.returncode,'wall_seconds':time.perf_counter()-s})
 (root/'setup.json').write_text(json.dumps(setup,indent=2)+'\n')
 print(json.dumps({'stage':label,'returncode':r.returncode,'wall_seconds':setup['stages'][-1]['wall_seconds']}),flush=True)
 if r.returncode: raise RuntimeError(label+' failed: '+r.stderr[-1500:])
 return r
try:
 # Make the runtime Git identity explicit; upstream identity remains the frozen capsule manifest.
 command('git-init',['git','init','-q'],10)
 command('git-add',['git','add','--',*manifest['files'].keys(),'capsule-manifest.json'],20)
 command('git-commit',['git','-c','user.name=Frozen capsule','-c','user.email=capsule@invalid.local','commit','-qm','Import frozen source capsule'],20)
 tools=root/'runtime-tools'
 command('uv-bootstrap',[sys.executable,'-m','pip','install','--target',str(tools),'uv==0.11.15'],120)
 env=dict(os.environ,PYTHONPATH=str(tools),UV_CACHE_DIR=str(root/'uv-cache'),UV_PYTHON_INSTALL_DIR=str(root/'uv-python'))
 command('uv-sync',[sys.executable,'-m','uv','sync','--locked','--python','3.12'],240,env)
 python=str(root/'.venv/bin/python')
 compiler=shutil.which('g++')
 if not compiler: raise RuntimeError('g++ unavailable; no implicit compiler install')
 args=[python,'-B',str(root/'scripts/e2_linux_native.py')]
 fixed=['--root',str(root/'e2-src'),'--source-manifest',str(root/'fixed-p2-manifest.json'),'--out',str(root/'e2-linux-build.json')]
 command('native-build',args+['build',*fixed,'--compiler',compiler],120)
 command('native-verify',args+['verify',*fixed],30)
 receipt=root/'e2-linux-build.json'; data=json.loads(receipt.read_bytes())
 identity={'linux_receipt_sha256':hashlib.sha256(receipt.read_bytes()).hexdigest(),'linux_binary_sha256':data['binary']['sha256']}
 (root/'runtime-identity.json').write_text(json.dumps(identity,indent=2)+'\n')
 setup.update(scoring_started=True,setup_seconds=time.perf_counter()-start)
 command('pilot',[python,'-B',str(root/'results/a/q2-nikolastarx/copyevent-linux-pilot-20260925/runner.py'),'--output',str(output)],615)
 setup['status']='completed'
except BaseException as error:
 setup.update(status='stopped',error=repr(error))
finally:
 setup['launcher_total_seconds']=time.perf_counter()-start
 (root/'setup.json').write_text(json.dumps(setup,indent=2)+'\n')
 with zipfile.ZipFile(result_zip,'w',compression=zipfile.ZIP_DEFLATED) as z:
  if output.exists():
   for p in sorted(output.rglob('*')):
    if p.is_file(): z.write(p,'output/'+p.relative_to(output).as_posix())
  for p in sorted(root.iterdir()):
   if p.is_file() and (p.name.endswith('.txt') or p.name in ['setup.json','capsule-manifest.json','runtime-identity.json','e2-linux-build.json']):z.write(p,p.name)
  binary=root/'e2-src/research/a/e2_search/native/libreplay_bc.so'
  if binary.exists(): z.write(binary,'linux-native/libreplay_bc.so')
 print(json.dumps({'status':setup.get('status'),'error':setup.get('error'),'setup_seconds':setup.get('setup_seconds'),'total_seconds':setup['launcher_total_seconds'],'result_zip':str(result_zip),'result_sha256':hashlib.sha256(result_zip.read_bytes()).hexdigest(),'bytes':result_zip.stat().st_size}),flush=True)
 if (root/'pilot-stdout.txt').exists(): print((root/'pilot-stdout.txt').read_text()[-4000:])
 if setup.get('status')!='completed': print('Stopped; do not rerun implicitly.',flush=True)
