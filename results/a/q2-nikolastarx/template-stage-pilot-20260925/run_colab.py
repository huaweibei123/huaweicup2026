"""Three fixed plans, one E0 each; independent of the frozen full500 solver."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time
import zipfile

root = Path('/content/p2-copyevent500-s8ee-20260925')
archive = Path('/content/p2-template-stage-plans.zip')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(archive) == os.environ['P2_STAGE_ZIP_SHA256']
source = Path('/content/p2-template-stage-plans-venv')
source.mkdir(exist_ok=False)
with zipfile.ZipFile(archive) as z:
    assert all((source / n).resolve().is_relative_to(source) for n in z.namelist())
    z.extractall(source)
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'scripts'))
from q2_copyevent_linux_full500 import preflight
from src.q2_nikolastarx.evaluate_feedback import monitored
preflight()  # no evaluation
manifest = json.loads((source / 'manifest.json').read_bytes())
assert manifest['limits'] == {'E0': 3, 'E2': 0, 'retries': 0, 'batch_seconds': 180,
                              'workers': 1, 'rss_bytes': 4 << 30}
assert [(r['case'], r['cores']) for r in manifest['rows']] == [('044', 5), ('046', 5), ('078', 5)]
config = root / 'data/raw/a/official/data/config.txt'
assert sha(config) == manifest['config_sha256']
for row in manifest['rows']:
    assert sha(source / row['plan_path']) == row['plan_sha256']
    assert sha(root / f"data/raw/a/official/data/case_{row['case']}.json") == row['graph_sha256']
out = Path('/content/p2-template-stage-output'); out.mkdir(exist_ok=False)
def save():
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
report = {'scope': manifest['scope'], 'constructor_commit': manifest['constructor_commit'],
          'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
          'limits': manifest['limits'], 'status': 'running', 'E0_reserved': 0, 'E2': 0,
          'manifest_sha256': sha(source / 'manifest.json'), 'rows': []}
begin = time.perf_counter(); deadline = begin + 180; save()
for original in manifest['rows']:
    row = dict(original); report['rows'].append(row)
    case = row['case']; folder = out / case; folder.mkdir()
    if time.perf_counter() >= deadline:
        report['status'] = 'stopped_deadline'; save(); break
    row['in_flight'] = True; report['E0_reserved'] += 1; save()
    args = [str(root / '.venv/bin/python'), '-B',
            str(root / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'),
            str(root / f'data/raw/a/official/data/case_{case}.json'),
            str(source / row['plan_path']), '--config', str(config),
            '--output', str(folder / 'result.json'), '--trace-output', str(folder / 'trace.json'),
            '--log-output', str(folder / 'official.log')]
    receipt = monitored(args, folder / 'e0-process', deadline, 4 << 30)
    row['process'] = receipt; row['in_flight'] = False
    if receipt['status'] != 'ok' or receipt['surviving_pids']:
        report['status'] = 'stopped_failure'; save(); break
    result = json.loads((folder / 'result.json').read_bytes())
    assert result['scene'] == 'B' and result['num_cores'] == 5
    row.update(M=result['makespan'], movement=result['data_movement_bytes'],
               result_sha256=sha(folder / 'result.json')); save()
else:
    report['status'] = 'completed'
report['wall_seconds'] = time.perf_counter() - begin; save()
zip_path = Path('/content/p2-template-stage-results.zip')
with zipfile.ZipFile(zip_path, 'x', compression=zipfile.ZIP_DEFLATED) as z:
    for prefix, directory in [('output', out), ('inputs', source)]:
        for p in sorted(directory.rglob('*')):
            if p.is_file(): z.write(p, prefix + '/' + p.relative_to(directory).as_posix())
print(json.dumps({'status': report['status'], 'E0': report['E0_reserved'],
                  'rows': [{k: r.get(k) for k in ('case', 'old_selected_M', 'M', 'movement')} for r in report['rows']],
                  'zip_sha256': sha(zip_path), 'bytes': zip_path.stat().st_size}))
