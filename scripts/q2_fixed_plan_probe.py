"""Owned Colab CPU: verify a frozen fixed-plan capsule and evaluate it once."""
from pathlib import Path
import hashlib
import json
import os
import platform
import sys
import time
import zipfile

name = os.environ['P2_PROBE_NAME']
if not name.startswith('p2-') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in name):
    raise ValueError('unsafe probe name')
archive = Path('/content') / (name + '.zip')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
if sha(archive) != os.environ['P2_PROBE_SHA256']:
    raise ValueError('probe capsule differs')
root = Path('/content') / name; root.mkdir(exist_ok=False)
with zipfile.ZipFile(archive) as z:
    if any(not (root / p).resolve().is_relative_to(root) for p in z.namelist()):
        raise ValueError('unsafe capsule path')
    z.extractall(root)
manifest = json.loads((root / 'manifest.json').read_bytes())
for rel, expected in manifest['files'].items():
    if sha(root / rel) != expected:
        raise ValueError('input drift: ' + rel)
if manifest['limits'] != {'E0': 3, 'E2': 0, 'workers': 1, 'seconds': 180,
                           'rss_bytes': 4 << 30, 'retries': 0}:
    raise ValueError('unexpected fixed budget')
if [(r['case'], r['cores']) for r in manifest['rows']] != [('044', 5), ('046', 5), ('078', 5)]:
    raise ValueError('unexpected probe coordinates')
sys.path.insert(0, str(root))
from src.q2_nikolastarx.evaluate_feedback import monitored
output = Path('/content') / (name + '-output'); output.mkdir(exist_ok=False)
start = time.perf_counter(); deadline = start + 180
report = {'status': 'running', 'scope': manifest['scope'],
          'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
          'constructor_commit': manifest['constructor_commit'], 'E0_reserved': 0, 'E2': 0,
          'platform': platform.platform(), 'python': sys.version,
          'capsule_sha256': sha(archive), 'rows': []}
def save():
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
save()
for old in manifest['rows']:
    row = dict(old); report['rows'].append(row)
    folder = output / row['case']; folder.mkdir()
    if time.perf_counter() >= deadline:
        report['status'] = 'stopped_deadline'; save(); break
    args = [sys.executable, '-B', str(root / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'),
            str(root / f"data/raw/a/official/data/case_{row['case']}.json"),
            str(root / row['plan']), '--config', str(root / 'data/raw/a/official/data/config.txt'),
            '--output', str(folder / 'result.json'), '--trace-output', str(folder / 'trace.json'),
            '--log-output', str(folder / 'official.log')]
    row['in_flight'] = True; report['E0_reserved'] += 1; save()
    proc = monitored(args, folder / 'e0-process', deadline, 4 << 30)
    row['process'] = proc; row['in_flight'] = False
    if proc['status'] != 'ok' or proc['surviving_pids']:
        report['status'] = 'stopped_failure'; save(); break
    result = json.loads((folder / 'result.json').read_bytes())
    if result['scene'] != 'B' or result['num_cores'] != row['cores']:
        raise ValueError('wrong E0 scenario')
    row.update(M=result['makespan'], movement=result['data_movement_bytes'],
               result_sha256=sha(folder / 'result.json')); save()
else:
    report['status'] = 'completed'
report['wall_seconds'] = time.perf_counter() - start; save()
result_zip = Path('/content') / (name + '-results.zip')
with zipfile.ZipFile(result_zip, 'x', compression=zipfile.ZIP_DEFLATED) as z:
    for p in sorted(output.rglob('*')):
        if p.is_file(): z.write(p, 'output/' + p.relative_to(output).as_posix())
    for p in root.glob('*.json'): z.write(p, 'inputs/' + p.name)
print(json.dumps({'status': report['status'], 'E0': report['E0_reserved'],
                  'rows': [{k: r.get(k) for k in ('case', 'old_M', 'M', 'movement')} for r in report['rows']],
                  'result_zip_sha256': sha(result_zip), 'result_zip_bytes': result_zip.stat().st_size}))
