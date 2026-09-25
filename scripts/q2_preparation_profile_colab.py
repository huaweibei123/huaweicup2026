"""Fresh, one-shot CPU Colab preparation profile; no scoring or retries."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile

NAME = 'p2-prepprofile-s8ee-20260925'
ROOT = Path('/content') / NAME
OUTPUT = ROOT.with_name(NAME + '-output')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
archive = ROOT.with_suffix('.zip')
if sha(archive) != os.environ['P2_PROFILE_SHA256']:
    raise ValueError('capsule SHA mismatch')
ROOT.mkdir(exist_ok=False)
with zipfile.ZipFile(archive) as z:
    if len(z.namelist()) != len(set(z.namelist())):
        raise ValueError('duplicate capsule entries')
    for n in z.namelist():
        if not (ROOT / n).resolve().is_relative_to(ROOT):
            raise ValueError('unsafe member')
    z.extractall(ROOT)
m = json.loads((ROOT / 'manifest.json').read_bytes())
for rel, expected in m['files'].items():
    if sha(ROOT / rel) != expected:
        raise ValueError('capsule file differs: '+rel)
receipt = dict(status='preparing_environment',
               started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               capsule_sha256=sha(archive), preparation_attempts=0,
               native_attempts=0, E0_attempts=0, stages=[])
def save():
    (ROOT / 'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
def command(label, argv, seconds, env=None):
    begin=time.perf_counter()
    result=subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                          timeout=seconds, env=env)
    (ROOT/(label+'-stdout.txt')).write_text(result.stdout)
    (ROOT/(label+'-stderr.txt')).write_text(result.stderr)
    receipt['stages'].append(dict(stage=label, returncode=result.returncode,
                                 seconds=time.perf_counter()-begin)); save()
    if result.returncode:
        raise RuntimeError(label+' failed')
save()
try:
    tools=ROOT/'runtime-tools'
    command('uv-bootstrap', [sys.executable,'-m','pip','install','--target',str(tools),'uv==0.11.15'],120)
    env=dict(os.environ,PYTHONPATH=str(tools),UV_CACHE_DIR=str(ROOT/'uv-cache'),
             UV_PYTHON_INSTALL_DIR=str(ROOT/'uv-python'))
    command('uv-sync', [sys.executable,'-m','uv','sync','--locked','--python','3.12'],240,env)
    sys.path.insert(0,str(ROOT))
    from src.q2_nikolastarx.evaluate_feedback import monitored
    # Reserve before crossing the monitored child boundary; a failure is not retried.
    receipt.update(status='running',preparation_attempts=1,
                   dispatch_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    save()
    os.environ.update(P2_PROFILE_ROOT=str(ROOT),P2_PROFILE_OUTPUT=str(OUTPUT))
    result=monitored([str(ROOT/'.venv/bin/python'),'-B',str(ROOT/'scripts/q2_preparation_profile.py')],
                     ROOT/'process',time.perf_counter()+180,4<<30)
    receipt.update(status='completed' if result['status']=='ok' else 'failed',process=result)
except BaseException as error:
    receipt.update(status='failed', error=repr(error))
    raise
finally:
    save()
    resultzip=ROOT.with_name(NAME+'-results.zip')
    with zipfile.ZipFile(resultzip,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for label,folder in [('output',OUTPUT),('process',ROOT/'process')]:
            if folder.exists():
                for p in folder.rglob('*'):
                    if p.is_file(): z.write(p,label+'/'+p.relative_to(folder).as_posix())
        for p in ROOT.iterdir():
            if p.is_file() and p.suffix in ('.json','.txt'):
                z.write(p,'inputs/'+p.name)
    print(json.dumps(dict(status=receipt['status'],preparations=receipt['preparation_attempts'],
                         sha256=sha(resultzip),bytes=resultzip.stat().st_size)),flush=True)
