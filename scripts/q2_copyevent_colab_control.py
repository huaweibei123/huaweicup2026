"""Owned Colab capsule preparation and bounded full500 supervision.

Run through the Colab CLI with P2_MODE=prepare/start/status/pack. Preparation
uses P2_CAPSULE_SHA256, pinned locally before upload. No access to other VMs.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

NAME = 'p2-copyevent500-s8ee-20260925'
ROOT = Path('/content') / NAME
ARCHIVE = ROOT.with_suffix('.zip')
OUTPUT = Path('/content') / (NAME + '-output')
CONTROL = Path('/content') / (NAME + '-control.py')
RESULT = Path('/content') / (NAME + '-results.zip')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def prepare():
    expected = os.environ['P2_CAPSULE_SHA256']
    if len(expected) != 64 or sha(ARCHIVE) != expected:
        raise ValueError('capsule SHA mismatch')
    ROOT.mkdir(exist_ok=False)
    with zipfile.ZipFile(ARCHIVE) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('duplicate capsule member')
        for member in z.namelist():
            if not (ROOT / member).resolve().is_relative_to(ROOT):
                raise ValueError('unsafe capsule member')
        z.extractall(ROOT)
    manifest = json.loads((ROOT / 'capsule-manifest.json').read_bytes())
    for name, expected in manifest['files'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('capsule file mismatch: ' + name)
    start = time.perf_counter()
    setup = {'status': 'preparing', 'capsule_sha256': sha(ARCHIVE),
             'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
             'scoring_started': False, 'stages': []}

    def command(label, argv, timeout, env=None):
        begin = time.perf_counter()
        r = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True,
                           timeout=timeout, env=env)
        (ROOT / (label + '-stdout.txt')).write_text(r.stdout)
        (ROOT / (label + '-stderr.txt')).write_text(r.stderr)
        setup['stages'].append({'stage': label, 'returncode': r.returncode,
                               'wall_seconds': time.perf_counter() - begin})
        save(ROOT / 'setup.json', setup)
        print(json.dumps(setup['stages'][-1]), flush=True)
        if r.returncode:
            raise RuntimeError(label + ' failed: ' + r.stderr[-1200:])
        return r

    try:
        command('git-init', ['git', 'init', '-q'], 10)
        command('git-add', ['git', 'add', '--', *manifest['files'], 'capsule-manifest.json'], 45)
        command('git-commit', ['git', '-c', 'user.name=Frozen capsule', '-c',
                'user.email=capsule@invalid.local', 'commit', '-qm', 'Import fixed input capsule'], 45)
        tools = ROOT / 'runtime-tools'
        command('uv-bootstrap', [sys.executable, '-m', 'pip', 'install', '--target',
                                  str(tools), 'uv==0.11.15'], 120)
        env = dict(os.environ, PYTHONPATH=str(tools), UV_CACHE_DIR=str(ROOT / 'uv-cache'),
                   UV_PYTHON_INSTALL_DIR=str(ROOT / 'uv-python'))
        command('uv-sync', [sys.executable, '-m', 'uv', 'sync', '--locked', '--python', '3.12'], 240, env)
        python = str(ROOT / '.venv/bin/python')
        compiler = shutil.which('g++')
        if not compiler:
            raise RuntimeError('g++ unavailable')
        args = [python, '-B', str(ROOT / 'scripts/e2_linux_native.py')]
        fixed = ['--root', str(ROOT / 'e2-src'), '--source-manifest',
                 str(ROOT / 'fixed-p2-manifest.json'), '--out', str(ROOT / 'e2-linux-build.json')]
        command('native-build', args + ['build', *fixed, '--compiler', compiler], 120)
        command('native-verify', args + ['verify', *fixed], 30)
        receipt = ROOT / 'e2-linux-build.json'
        build = json.loads(receipt.read_bytes())
        save(ROOT / 'runtime-identity.json', {'linux_receipt_sha256': sha(receipt),
                                             'linux_binary_sha256': build['binary']['sha256']})
        command('preflight', [python, '-B', str(ROOT / 'scripts/q2_copyevent_linux_full500.py'),
                               'preflight'], 90)
        setup['status'] = 'prepared'
    except BaseException as error:
        setup.update(status='stopped', error=repr(error))
        raise
    finally:
        setup['setup_seconds'] = time.perf_counter() - start
        save(ROOT / 'setup.json', setup)
        print(json.dumps(setup), flush=True)


def supervise():
    sys.path.insert(0, str(ROOT))
    from src.q2_nikolastarx.evaluate_feedback import monitored
    outer = Path('/content') / (NAME + '-outer')
    if outer.exists() or OUTPUT.exists():
        raise ValueError('existing run; no retry')
    start = time.perf_counter()
    save(ROOT / 'dispatch.json', {'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
         'pid': os.getpid(), 'instance': NAME, 'outer_seconds': 7200,
         'rss_bytes': 8 << 30, 'runner_sha256': sha(ROOT / 'scripts/q2_copyevent_linux_full500.py'),
         'control_sha256': sha(CONTROL), 'manifest_sha256': sha(ROOT / 'capsule-manifest.json')})
    # Monitor full runner descendants, even children starting new process groups.
    receipt = monitored([str(ROOT / '.venv/bin/python'), '-B',
                         str(ROOT / 'scripts/q2_copyevent_linux_full500.py'), 'run',
                         '--output', str(OUTPUT)], outer, start + 7200, 8 << 30)
    save(ROOT / 'outer-terminal.json', receipt)
    pack()


def start():
    setup = json.loads((ROOT / 'setup.json').read_bytes())
    if setup['status'] != 'prepared' or (ROOT / 'dispatch.json').exists() or OUTPUT.exists():
        raise ValueError('not a fresh prepared capsule')
    # Exclusive marker written before Popen; uncertain launch is never retried.
    with (ROOT / 'start-reservation.json').open('x') as f:
        json.dump({'reserved_at': time.time(), 'control_sha256': sha(CONTROL)}, f)
    with (ROOT / 'supervisor.log').open('x') as out:
        p = subprocess.Popen([str(ROOT / '.venv/bin/python'), '-B', str(CONTROL)],
                             cwd=ROOT, stdout=out, stderr=subprocess.STDOUT,
                             env=dict(os.environ, P2_MODE='supervise'), start_new_session=True)
    print(json.dumps({'supervisor_pid': p.pid, 'launch': 'reserved; confirm dispatch and summary'}))


def status():
    for path in (ROOT / 'setup.json', ROOT / 'dispatch.json', ROOT / 'outer-terminal.json'):
        if path.exists():
            value = json.loads(path.read_bytes())
            if path.name == 'setup.json':
                value = {k: v for k, v in value.items() if k != 'stages'}
            print(json.dumps({'file': path.name, 'value': value}))
    p = OUTPUT / 'summary.json'
    if p.exists():
        s = json.loads(p.read_bytes())
        print(json.dumps({k: s.get(k) for k in ('status', 'accepted_cells', 'in_flight',
                         'calls', 'call_count_complete', 'total_wall_seconds')}))
        print(json.dumps({'last_rows': [{k: r.get(k) for k in ('case', 'cores', 'status',
                   'error', 'solver_wall_seconds', 'official')} for r in s['rows'][-3:]]}))


def pack():
    if RESULT.exists():
        raise ValueError('result zip already exists; no overwrite')
    with zipfile.ZipFile(RESULT, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for prefix, folder in [('output', OUTPUT), ('outer', Path('/content') / (NAME + '-outer'))]:
            if folder.exists():
                for p in sorted(folder.rglob('*')):
                    if p.is_file():
                        z.write(p, prefix + '/' + p.relative_to(folder).as_posix())
        for p in ROOT.iterdir():
            if p.is_file() and p.suffix in ('.json', '.txt', '.log'):
                z.write(p, 'setup/' + p.name)
        z.write(ROOT / 'e2-src/research/a/e2_search/native/libreplay_bc.so', 'linux-native/libreplay_bc.so')
    print(json.dumps({'result_zip': str(RESULT), 'bytes': RESULT.stat().st_size,
                      'sha256': sha(RESULT)}), flush=True)


mode = os.environ.get('P2_MODE')
if mode not in ('prepare', 'start', 'supervise', 'status', 'pack'):
    raise ValueError('explicit P2_MODE required')
globals()[mode]()
