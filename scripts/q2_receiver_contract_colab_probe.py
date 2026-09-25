"""Single-use Colab CPU 069/K5 RCX static probe; never calls E0/E1/E2.

The capsule manifest is byte provenance, not a cloud Git checkout claim.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pickle
import sys
import time
import zipfile

ROOT = Path('/content/q2-rcx-069-k5-capsule')
OUT = Path('/content/q2-rcx-069-k5-output')
RESULT_ZIP = Path('/content/q2-rcx-069-k5-results.zip')
COMMIT = '9f89c2b4a4d0b7acd37da8c88f1b860c364e9c66'
LIMITS = {'workers': 1, 'wall_seconds': 120, 'rss_bytes': 512 << 20,
          'scene_b_prepare': 1, 'constructor': 1, 'E0': 0, 'E1': 0,
          'E2': 0, 'retries': 0}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def safe_name(name):
    p = PurePosixPath(name)
    if (not name or name.startswith('/') or '\\' in name or
            any(part in ('', '.', '..') for part in name.split('/')) or
            p.as_posix() != name):
        raise ValueError('unsafe capsule path: ' + name)
    return name


def extract(archive):
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        names = [safe_name(x.filename) for x in entries]
        if len(names) != len(set(names)) or 'manifest.json' not in names:
            raise ValueError('duplicate or missing capsule member')
        if sum(x.file_size for x in entries) > 128 << 20:
            raise ValueError('capsule expanded size exceeds limit')
        for entry in entries:
            if entry.is_dir() or entry.file_size > 64 << 20 or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('directory, large file, or link in capsule')
            dest = ROOT / entry.filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(entry) as source, dest.open('xb') as target:
                while block := source.read(1 << 20):
                    target.write(block)
    return set(names)


def verify(manifest, names):
    if (manifest.get('schema') != 'q2-rcx-069-k5-colab-v1' or
            manifest.get('constructor_commit') != COMMIT or
            not isinstance(manifest.get('runner_commit'), str) or
            len(manifest['runner_commit']) != 40 or
            manifest.get('limits') != LIMITS):
        raise ValueError('capsule identity or limits differ')
    files = manifest['files']
    if set(files) | {'manifest.json'} != names:
        raise ValueError('capsule file set differs')
    for rel, expected in files.items():
        safe_name(rel)
        if len(expected) != 64 or sha((ROOT / rel).read_bytes()) != expected:
            raise ValueError('capsule file differs: ' + rel)
    inputs = manifest['inputs']
    if set(inputs) != {'graph', 'config', 'plan', 'result', 'run'} or any(
            inputs[k] not in files for k in inputs):
        raise ValueError('input map differs')
    expected_sources = {
        'scripts/q2_receiver_contract_colab_probe.py',
        'scripts/q2_receiver_contract_probe.py',
        'scripts/q2_selected_plan_static_probe.py',
        'data/raw/a/official/code/evaluation_validation.py',
        'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py',
        'src/q2_nikolastarx/prepared_trace_contract.py',
        'src/q2_nikolastarx/receiver_closure_exchange.py',
        'src/q2_nikolastarx/evaluate_feedback.py',
    }
    if not expected_sources <= files.keys() or not any(
            p.startswith('src/q2_nikolastarx/') and p.endswith('.py') for p in files):
        raise ValueError('source set incomplete')
    if sha(Path(__file__).read_bytes()) != files['scripts/q2_receiver_contract_colab_probe.py']:
        raise ValueError('executed runner differs from capsule runner')
    def raw(key):
        p = ROOT / inputs[key]
        b = p.read_bytes()
        return gzip.decompress(b) if p.suffix == '.gz' else b
    row = json.loads(raw('run'))['accepted_row']
    if row['case'] != '069' or row['cores'] != 5:
        raise ValueError('wrong saved coordinate')
    for key, digest in [('graph', row['graph_sha256']),
                        ('config', row['config_sha256']),
                        ('plan', row['plan_sha256']),
                        ('result', row['official']['result_sha256'])]:
        if sha(raw(key)) != digest:
            raise ValueError('saved E0 input identity differs: ' + key)
    return row


def child(manifest_path):
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config, _build_scene_b_tasks
    from src.q2_nikolastarx.prepared_trace_contract import capture, audit
    from src.q2_nikolastarx.receiver_closure_exchange import construct
    manifest = json.loads(manifest_path.read_bytes())
    row = verify(manifest, set(manifest['files']) | {'manifest.json'})
    def load(key):
        p = ROOT / manifest['inputs'][key]
        b = p.read_bytes()
        return json.loads(gzip.decompress(b) if p.suffix == '.gz' else b)
    graph, plan, result = (load(k) for k in ('graph', 'plan', 'result'))
    config_path = ROOT / manifest['inputs']['config']
    config = {**read_evaluation_config(config_path), **read_scene_b_config(config_path)}
    with (OUT / 'prepare-start.json').open('x') as f:
        json.dump({'scene_b_prepare_started': 1}, f)
    started = time.perf_counter()
    prepared = _build_scene_b_tasks(graph, plan, config['bandwidth'], config['capacity'])
    tasks, links, cross, traffic, _ = prepared
    prepare_seconds = time.perf_counter() - started
    if traffic != row['official']['movement'] or cross != row['official']['cross_task_traffic']:
        raise ValueError('fresh preparation differs from saved E0 traffic')
    (OUT / 'prepared.pickle').write_bytes(pickle.dumps(prepared, protocol=5))
    contract = capture(tasks, links)
    (OUT / 'contract.json.gz').write_bytes(gzip.compress(
        json.dumps(contract, sort_keys=True, allow_nan=False).encode(), mtime=0))
    checked = audit(contract, result)
    save(OUT / 'trace-contract-audit.json', checked)
    if not checked['consistent']:
        raise ValueError('prepared/trace contract mismatch; construction barred')
    with (OUT / 'constructor-start.json').open('x') as f:
        json.dump({'constructor_started': 1}, f)
    started = time.perf_counter()
    candidate, meta = construct(graph, plan, config, checked['critical_cross_links'])
    save(OUT / 'candidate-meta.json', meta)
    if candidate is not None:
        save(OUT / 'candidate-plan.json', candidate)
    save(OUT / 'probe-result.json', {
        'status': 'candidate_unscored' if candidate is not None else 'no_candidate',
        'prepare_seconds': prepare_seconds,
        'constructor_seconds': time.perf_counter() - started,
        'seed_makespan': result['makespan'], 'candidate_makespan': None,
        'calls': {'scene_b_prepare': 1, 'constructor': 1, 'E0': 0, 'E1': 0, 'E2': 0},
        'prepared_pickle_sha256': sha((OUT / 'prepared.pickle').read_bytes()),
        'no_official_improvement_claim': True})


def run():
    start = time.perf_counter()
    filename = os.environ['P2_RCX_CAPSULE_FILENAME']
    if Path(filename).name != filename or not filename.endswith('.zip'):
        raise ValueError('capsule filename must be a plain .zip basename')
    expected = os.environ['P2_RCX_CAPSULE_SHA256']
    if len(expected) != 64:
        raise ValueError('missing capsule SHA-256')
    archive = Path('/content') / filename
    OUT.mkdir(exist_ok=False)
    receipt = {'status': 'reserved', 'capsule_sha256': expected,
               'constructor_commit_provenance': COMMIT,
               'cloud_git_verified': False, 'E0': 0, 'E1': 0, 'E2': 0}
    with (OUT / 'attempt.json').open('x') as f:
        json.dump({'capsule_sha256': expected, 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, f)
    save(OUT / 'receipt.json', receipt)
    try:
        if sha(archive.read_bytes()) != expected:
            raise ValueError('capsule SHA-256 differs')
        ROOT.mkdir(exist_ok=False)
        names = extract(archive)
        manifest_path = ROOT / 'manifest.json'
        manifest = json.loads(manifest_path.read_bytes())
        verify(manifest, names)
        sys.path.insert(0, str(ROOT))
        from src.q2_nikolastarx.evaluate_feedback import monitored
        if time.perf_counter() >= start + 120:
            raise TimeoutError('activity deadline reached before dispatch')
        receipt['dispatch_started'] = True
        save(OUT / 'receipt.json', receipt)
        proc = monitored([sys.executable, '-B', str(ROOT / 'scripts/q2_receiver_contract_colab_probe.py'),
                          'child', str(manifest_path)], OUT / 'process', start + 120,
                         512 << 20, cleanup_timeout=5.0)
        receipt['process'] = proc
        if proc['status'] != 'ok' or proc.get('surviving_pids'):
            raise RuntimeError('child failed, timed out, or survived cleanup')
        receipt['status'] = 'completed_unscored'
    except BaseException as error:
        receipt.update(status='stopped', error=repr(error))
        raise
    finally:
        receipt.update(wall_seconds=time.perf_counter() - start,
                       scene_b_prepare_started=int((OUT / 'prepare-start.json').exists()),
                       constructor_started=int((OUT / 'constructor-start.json').exists()))
        save(OUT / 'receipt.json', receipt)
        with zipfile.ZipFile(RESULT_ZIP, 'x', compression=zipfile.ZIP_DEFLATED) as z:
            for p in sorted(OUT.rglob('*')):
                if p.is_file():
                    z.write(p, 'output/' + p.relative_to(OUT).as_posix())
        print(json.dumps({'status': receipt['status'], 'result_zip_sha256': sha(RESULT_ZIP.read_bytes()),
                          'result_zip_bytes': RESULT_ZIP.stat().st_size,
                          'scene_b_prepare_started': receipt['scene_b_prepare_started'],
                          'constructor_started': receipt['constructor_started'],
                          'E0': 0, 'E1': 0, 'E2': 0}))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'child':
        child(Path(sys.argv[2]))
    elif len(sys.argv) == 2 and sys.argv[1] == 'run':
        run()
    else:
        raise SystemExit('usage: q2_receiver_contract_colab_probe.py run')
