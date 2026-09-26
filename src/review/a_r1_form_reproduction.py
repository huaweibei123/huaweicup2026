from pathlib import Path
import datetime, hashlib, json, os, platform, subprocess, sys, time

ROOT = Path(__file__).resolve().parents[2]
import argparse
parser = argparse.ArgumentParser(description='Reproduce fixed FORM scripts and compare their submitted observations.')
parser.add_argument('--output', required=True, help='New results directory relative to project root')
args = parser.parse_args()
RUN = (ROOT / args.output).resolve()
assert RUN.is_relative_to((ROOT / 'results').resolve()), 'Output must remain inside results/'
EXPECTED = 'dab91d612bd26183e12d30848b13d5fb14e071c7'
def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode().strip()
subprocess.run(['git', 'merge-base', '--is-ancestor', EXPECTED, 'HEAD'], cwd=ROOT, check=True)
RUN.mkdir(parents=True, exist_ok=False)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
scripts = [
    'verify_rules_r1.py', 'add_fplan005_fixture.py', 'verify_ftask_r1.py',
    'verify_fexec_r1.py', 'verify_order_r1.py', 'verify_local_r1.py',
    'verify_local2_r1.py', 'verify_spill_r1.py', 'verify_spill_r2.py',
    'verify_time_r1.py', 'verify_l2_r1.py', 'verify_l2_r2.py',
    'verify_metric_r1.py', 'build_dev_samples.py', 'build_ranking_adversarial.py',
    'verify_ranking_fixture.py', 'verify_io_r1.py', 'build_coverage.py',
]
paths = sorted(set(list(ROOT.glob('results/a/form/r1-20260923-farmeruncle123/*.json')) +
                   list(ROOT.glob('tests/adversarial/*')) + [ROOT/'formal/coverage.json']))
originals = {}
for p in paths:
    if p.is_file():
        rel = p.relative_to(ROOT).as_posix()
        raw = p.read_bytes()
        assert raw == subprocess.check_output(['git','show',EXPECTED+':'+rel],cwd=ROOT), 'Restore submitted artifact before rerun: '+rel
        originals[rel] = raw
        dst = RUN/'submitted'/rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(raw)
run = {'candidate_commit': EXPECTED, 'review_branch': git('branch', '--show-current'),
       'driver_command': ['.venv/bin/python','-B','src/review/a_r1_form_reproduction.py','--output',args.output],
       'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'python': sys.version, 'platform': platform.platform(),
       'official_code_hash': 'de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0',
       'scope': 'Reproduce member probes and compare submitted observations; not full evaluator acceptance.',
       'runs': []}
for name in scripts:
    cmd = [str(ROOT/'.venv/bin/python'), '-B', 'src/adversarial/'+name]
    assert (ROOT/'src/adversarial'/name).read_bytes() == subprocess.check_output(['git','show',EXPECTED+':src/adversarial/'+name],cwd=ROOT), 'Member script changed: '+name
    start = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, timeout=360)
        rc, stdout, stderr = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        rc, stdout, stderr = 'timeout_360s', e.stdout or b'', e.stderr or b''
    stem = name.removesuffix('.py')
    (RUN/(stem+'.stdout.txt')).write_bytes(stdout)
    (RUN/(stem+'.stderr.txt')).write_bytes(stderr)
    item = {'script': 'src/adversarial/'+name, 'command': ['.venv/bin/python','-B','src/adversarial/'+name],
            'script_sha256': hashlib.sha256((ROOT/'src/adversarial'/name).read_bytes()).hexdigest(),
            'exit_code': rc, 'seconds': round(time.monotonic()-start, 6)}
    run['runs'].append(item)
    (RUN/'run.json').write_text(json.dumps(run, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(item, ensure_ascii=False), flush=True)
diffs = []
def compare(a, b, p, found):
    if type(a) is not type(b):
        found.append({'path':p,'submitted':a,'reproduced':b}); return
    if isinstance(a, dict):
        for k in sorted(set(a)|set(b)):
            if k not in a or k not in b:
                found.append({'path':p+'/'+str(k),'submitted':a.get(k),'reproduced':b.get(k)})
            else: compare(a[k],b[k],p+'/'+str(k),found)
    elif isinstance(a,list):
        if len(a)!=len(b): found.append({'path':p+'/length','submitted':len(a),'reproduced':len(b)})
        for i,(av,bv) in enumerate(zip(a,b)): compare(av,bv,p+'/'+str(i),found)
    elif a!=b: found.append({'path':p,'submitted':a,'reproduced':b})
for rel, raw in originals.items():
    after = (ROOT/rel).read_bytes()
    dst = RUN/'reproduced'/rel
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_bytes(after)
    changed=[]
    try:
        if rel.endswith('.jsonl'):
            old=[json.loads(x) for x in raw.decode().splitlines() if x.strip()]
            new=[json.loads(x) for x in after.decode().splitlines() if x.strip()]
        else: old,new=json.loads(raw),json.loads(after)
        compare(old,new,'',changed)
    except Exception as e:
        changed=[{'parse_error':str(e)}] if raw!=after else []
    diffs.append({'file':rel,'byte_equal':raw==after,'json_equal':not changed,
                  'submitted_sha256':hashlib.sha256(raw).hexdigest(),
                  'reproduced_sha256':hashlib.sha256(after).hexdigest(),
                  'differences':changed})
(RUN/'comparison.json').write_text(json.dumps(diffs,ensure_ascii=False,indent=2)+'\n')
run['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
run['comparison']={'files':len(diffs),'json_equal':sum(d['json_equal'] for d in diffs),'byte_equal':sum(d['byte_equal'] for d in diffs)}
(RUN/'run.json').write_text(json.dumps(run,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'complete':True,'comparison':run['comparison'],'changed':[{'file':d['file'],'count':len(d['differences'])} for d in diffs if not d['json_equal']]},ensure_ascii=False),flush=True)
