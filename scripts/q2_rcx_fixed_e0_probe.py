"""One fixed 069/K5 official E0 on independent Colab CPU; no construction/E1/E2.

Run with ``python -B q2_rcx_fixed_e0_probe.py run`` after separately uploading
this runner and a SHA-pinned capsule. No Git checkout is asserted in Colab.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import time
import zipfile

ROOT = Path('/content/q2-rcx-e0-capsule')
OUT = Path('/content/q2-rcx-e0-output')
RESULT_ZIP = Path('/content/q2-rcx-e0-results.zip')
SCHEMA = 'q2-rcx-069-k5-e0-v1'
GRAPH_SHA = '9632392d98cfc04291ba0546accf1f4c3ede8ff71befd3cd0ae67caf27659e52'
CONFIG_SHA = 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'
PLAN_SHA = '8ace171ac9c837a8986ee8baf950be96a694baabd99ca622023dfa268274b496'
OLD_SHA = '3dc8f94e3806d5baf13655e477f9df1c9202f438df93a37c530335402b918b51'
LIMITS = {'workers': 1, 'wall_seconds': 120, 'rss_bytes': 536870912,
          'E0': 1, 'E1': 0, 'E2': 0, 'constructor': 0, 'retries': 0}
OFFICIAL = {
    'contest_io.py': 'd5936908e4c261c7003b78e783f30bd7d65cb38d6b53a269ea67f0103cac848e',
    'evaluation_validation.py': '103206b8c5c25e37de50cc3193de3989d7c1e01d4a11cc5f509dedd8f9be9a64',
    'multicore_cut_evaluate_problem_1.py': '2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f',
    'multicore_cut_evaluate_problem_2.py': '0b39f84d5ec0a7fba9a4c92a598a9044b97ab79c71393824c1ba130ecfe6c464',
    'schedule_step1.py': 'd8fe721ff3dbe036e34a20c00cce6430960860000a49eb467e63465f76b84034',
    'schedule_step2.py': '2836baac176f4e0bdd9eec59b8d9ce254e209e5f7a251e23837ab684312fa0c3',
    'schedule_step3.py': '50053db0436f1d166dd75436693ba3af49b5c339576beb6e7299477f6b69fc7a',
    'stub_multicore_cut_and_schedule.py': '0a3a3b79b5173b466fc05fc8d33b72d11d90b4df78995435853d91c632a35892',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def safe(name):
    path = PurePosixPath(name)
    if (not name or name.startswith('/') or '\\' in name or
            any(p in ('', '.', '..') for p in name.split('/')) or path.as_posix() != name):
        raise ValueError('unsafe member name')
    return name


def extract(archive):
    with zipfile.ZipFile(archive) as source:
        rows = source.infolist()
        names = [safe(row.filename) for row in rows]
        if (len(rows) > 256 or len(names) != len(set(names)) or 'manifest.json' not in names
                or sum(row.file_size for row in rows) > 128 << 20):
            raise ValueError('capsule count, duplicate, manifest, or expanded-size limit')
        expanded = 0
        for row in rows:
            if (row.is_dir() or row.file_size > 64 << 20 or
                    (row.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('directory, large member, or symlink')
            destination = ROOT / row.filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with source.open(row) as reader, destination.open('xb') as writer:
                while block := reader.read(1 << 20):
                    written += len(block)
                    expanded += len(block)
                    if written > row.file_size or expanded > 128 << 20:
                        raise ValueError('capsule actual expanded size exceeds limit')
                    writer.write(block)
            if written != row.file_size:
                raise ValueError('capsule member size differs from ZIP header')
    return set(names)


def verify(manifest, names):
    if (manifest.get('schema') != SCHEMA or manifest.get('limits') != LIMITS or
            any(not isinstance(manifest.get(k), str) or len(manifest[k]) != 40
                for k in ('source_commit', 'runner_commit'))):
        raise ValueError('manifest schema, provenance, or limits mismatch')
    files, inputs = manifest['files'], manifest['inputs']
    if (set(files) | {'manifest.json'} != names or
            set(inputs) != {'graph', 'config', 'plan', 'reference_result'} or
            any(inputs[k] not in files for k in inputs)):
        raise ValueError('capsule file set or input map mismatch')
    if (not inputs['graph'].endswith('.json') or not inputs['plan'].endswith('.json')
            or not inputs['config'].endswith('.txt')
            or not inputs['reference_result'].endswith('.json.gz')):
        raise ValueError('official CLI requires raw graph/plan JSON and config text')
    for name, expected in files.items():
        if len(expected) != 64 or sha((ROOT / safe(name)).read_bytes()) != expected:
            raise ValueError('capsule member hash mismatch: ' + name)
    runner = 'scripts/q2_rcx_fixed_e0_probe.py'
    if files.get(runner) != sha(Path(__file__).read_bytes()):
        raise ValueError('uploaded runner differs from capsule')
    for name, expected in OFFICIAL.items():
        if files.get('data/raw/a/official/code/' + name) != expected:
            raise ValueError('official code source drift: ' + name)
    def raw(key):
        path = ROOT / inputs[key]
        data = path.read_bytes()
        return gzip.decompress(data) if path.suffix == '.gz' else data
    for key, expected in [('graph', GRAPH_SHA), ('config', CONFIG_SHA),
                          ('plan', PLAN_SHA), ('reference_result', OLD_SHA)]:
        if sha(raw(key)) != expected:
            raise ValueError('fixed input identity mismatch: ' + key)
    old = json.loads(raw('reference_result'))
    plan = json.loads(raw('plan'))
    if (old.get('scene') != 'B' or old.get('num_cores') != 5 or old.get('makespan') != 11962
            or set(plan) != {'node_to_subgraph', 'core_schedules'} or len(plan['core_schedules']) != 5):
        raise ValueError('wrong coordinate, reference score, or candidate plan keys')
    return old


def run():
    start = time.perf_counter()
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    filename = os.environ['P2_RCX_CAPSULE_FILENAME']
    expected = os.environ['P2_RCX_CAPSULE_SHA256']
    if Path(filename).name != filename or not filename.endswith('.zip') or len(expected) != 64:
        raise ValueError('plain capsule zip filename and SHA-256 required')
    archive = Path('/content') / filename
    if ROOT.exists() or RESULT_ZIP.exists():
        raise FileExistsError('single attempt already reserved')
    OUT.mkdir(exist_ok=False)
    receipt = {'status': 'reserved', 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               'capsule_sha256': expected, 'calls': {'E0_started': 0, 'E1': 0, 'E2': 0,
                                                     'constructor': 0}, 'cloud_git_verified': False,
               'timing_scope': 'wall_seconds includes upload-byte verification, extraction, preflight, and E0; e0_process_wall_seconds is subprocess only'}
    save(OUT / 'attempt.json', receipt)
    try:
        if sha(archive.read_bytes()) != expected:
            raise ValueError('uploaded capsule bytes differ from expected SHA-256')
        ROOT.mkdir(exist_ok=False)
        names = extract(archive)
        manifest = json.loads((ROOT / 'manifest.json').read_bytes())
        old = verify(manifest, names)
        receipt.update(manifest_sha256=sha((ROOT / 'manifest.json').read_bytes()),
                       source_commit_provenance=manifest['source_commit'],
                       runner_commit_provenance=manifest['runner_commit'],
                       old_makespan=old['makespan'])
        save(OUT / 'receipt.json', receipt)
        sys.path.insert(0, str(ROOT))
        from src.q2_nikolastarx.evaluate_feedback import monitored
        e0 = OUT / 'e0'
        e0.mkdir()
        args = [sys.executable, '-B', str(ROOT / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'),
                str(ROOT / manifest['inputs']['graph']), str(ROOT / manifest['inputs']['plan']),
                '--config', str(ROOT / manifest['inputs']['config']), '--output', str(e0 / 'result.json'),
                '--trace-output', str(e0 / 'trace.json'), '--log-output', str(e0 / 'official.log')]
        if time.perf_counter() >= start + 120:
            raise TimeoutError('Activity deadline reached before E0 dispatch')
        receipt['calls']['E0_started'] = 1
        receipt['dispatch_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        save(OUT / 'receipt.json', receipt)
        process = monitored(args, e0 / 'process', start + 120, 536870912, cleanup_timeout=5.0)
        receipt['process'] = process
        if process['status'] != 'ok' or process.get('surviving_pids'):
            raise RuntimeError('official E0 failed, timed out, or survived cleanup')
        result = json.loads((e0 / 'result.json').read_bytes())
        if result.get('scene') != 'B' or result.get('num_cores') != 5:
            raise ValueError('official E0 coordinate mismatch')
        receipt.update(status='completed', candidate_makespan=result['makespan'],
                       old_makespan=old['makespan'],
                       candidate_movement=result['data_movement_bytes'],
                       old_movement=old['data_movement_bytes'],
                       e0_process_wall_seconds=process['wall_seconds'],
                       e0_peak_rss_bytes=process['observed_peak_rss_bytes'],
                       e0_cleanup_killed_pids=process.get('cleanup_killed_pids', []),
                       artifacts={p.name: sha(p.read_bytes()) for p in e0.iterdir() if p.is_file()})
    except BaseException as error:
        receipt.update(status='stopped', error=repr(error))
        raise
    finally:
        receipt['wall_seconds'] = time.perf_counter() - start
        save(OUT / 'receipt.json', receipt)
        try:
            with zipfile.ZipFile(RESULT_ZIP, 'x', compression=zipfile.ZIP_DEFLATED) as output:
                for path in sorted(OUT.rglob('*')):
                    if path.is_file():
                        output.write(path, 'output/' + path.relative_to(OUT).as_posix())
        except BaseException as error:
            receipt['zip_error'] = repr(error)
            save(OUT / 'receipt.json', receipt)
            raise
        print(json.dumps({'status': receipt['status'], 'result_zip_sha256': sha(RESULT_ZIP.read_bytes()),
                          'result_zip_bytes': RESULT_ZIP.stat().st_size,
                          'E0_started': receipt['calls']['E0_started'], 'E1': 0, 'E2': 0}))


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'run':
        run()
    else:
        raise SystemExit('usage: q2_rcx_fixed_e0_probe.py run')
