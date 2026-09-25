"""Colab entrypoint after coordinator admission; keeps failed attempts as result ZIPs."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import zipfile

CAPSULE = Path('/content/reverse-gap-capsule.zip')
ROOT = Path('/content/reverse-gap-capsule')
OUT = Path('/content/reverse-gap-results')
RESULTS = Path('/content/reverse-gap-results.zip')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(obj):
    OUT.mkdir(exist_ok=True)
    (OUT / 'bootstrap.json').write_text(json.dumps(obj, indent=2) + '\n')


def main():
    expected = os.environ['P2_REVERSE_CAPSULE_SHA256']
    if len(expected) != 64 or ROOT.exists() or OUT.exists() or RESULTS.exists():
        raise ValueError('single clean attempt and capsule SHA-256 required')
    receipt = {'status': 'reserved', 'capsule_sha256': expected, 'process_started': False}
    save(receipt)
    child = None
    known = {}
    cleanup_tree = None
    discover = None
    process_snapshot = None
    try:
        if sha(CAPSULE.read_bytes()) != expected:
            raise ValueError('uploaded capsule hash mismatch')
        with zipfile.ZipFile(CAPSULE) as z:
            names = z.namelist()
            if len(names) != len(set(names)) or 'manifest.json' not in names:
                raise ValueError('duplicate/missing archive members')
            manifest = json.loads(z.read('manifest.json'))
            if (manifest['schema'] != 'reverse-gap-colab-capsule-v1' or
                    set(names) != set(manifest['files']) | {'manifest.json'} or
                    manifest['limits'] != {'constructor': 3, 'E0': 3, 'E1': 0, 'E2': 0,
                        'retry': 0, 'workers': 1, 'solver_seconds': 30, 'E0_seconds': 30,
                        'batch_seconds': 120, 'rss_bytes': 536870912}):
                raise ValueError('manifest/scope mismatch')
            ROOT.mkdir()
            for name in names:
                path = Path(name)
                if path.is_absolute() or '..' in path.parts or name.endswith('/'):
                    raise ValueError('unsafe archive path')
                data = z.read(name)
                if name != 'manifest.json' and sha(data) != manifest['files'][name]:
                    raise ValueError('member hash mismatch: ' + name)
                target = ROOT / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        if sha((ROOT / 'freeze.json').read_bytes()) != manifest['freeze_sha256']:
            raise ValueError('freeze identity mismatch')
        receipt.update(status='verified', manifest_sha256=sha((ROOT / 'manifest.json').read_bytes()),
                       source_commit=manifest['source_commit'])
        save(receipt)
        sys.path.insert(0, str(ROOT))
        from src.q2_nikolastarx.evaluate_feedback import process_snapshot, discover, cleanup_tree
        # The frozen runner owns the 120-second batch and 30-second children.
        # This outer watchdog includes its own observer RSS and handles a hung supervisor.
        with (OUT / 'runner.stdout').open('w') as stdout, (OUT / 'runner.stderr').open('w') as stderr:
            child = subprocess.Popen([sys.executable, '-B', str(ROOT / 'launch.py')],
                                     stdout=stdout, stderr=stderr, start_new_session=True)
            receipt.update(process_started=True, pid=child.pid)
            save(receipt)
            deadline = time.monotonic() + 130
            while True:
                snapshot = process_snapshot()
                alive = discover(snapshot, child.pid, known)
                rss = snapshot.get(os.getpid(), {}).get('rss', 0) + sum(
                    snapshot[p]['rss'] for p in alive)
                receipt['observer_inclusive_peak_rss_bytes'] = max(
                    receipt.get('observer_inclusive_peak_rss_bytes', 0), rss)
                if rss > 536870912:
                    receipt['status'] = 'outer_rss_limit'
                    break
                if child.poll() is not None:
                    break
                if time.monotonic() >= deadline:
                    receipt['status'] = 'outer_timeout'
                    break
                time.sleep(.05)
            if receipt['status'] in ('outer_timeout', 'outer_rss_limit'):
                receipt['cleanup_killed_pids'] = cleanup_tree(child.pid, known)
            code = child.wait()
            receipt['exit_code'] = code
            receipt['surviving_pids'] = sorted(discover(process_snapshot(), child.pid, known))
            if receipt['status'] == 'verified':
                receipt['status'] = 'finished' if code == 0 else 'failed'
            if receipt['surviving_pids']:
                receipt['status'] = 'surviving_processes'
            save(receipt)
    except BaseException as error:
        receipt.update(status='stopped', error=repr(error))
        save(receipt)
        raise
    finally:
        if child is not None:
            if cleanup_tree is not None:
                try:
                    receipt['final_cleanup_killed_pids'] = cleanup_tree(child.pid, known)
                    receipt['final_surviving_pids'] = sorted(discover(process_snapshot(), child.pid, known))
                    if receipt['final_surviving_pids']:
                        receipt['status'] = 'surviving_processes'
                except BaseException as cleanup_error:
                    receipt.update(status='cleanup_failed', cleanup_error=repr(cleanup_error))
            elif child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
            child.wait()
        receipt['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        save(receipt)
        with zipfile.ZipFile(RESULTS, 'x', compression=zipfile.ZIP_DEFLATED) as z:
            for path in sorted(OUT.rglob('*')):
                if path.is_file():
                    z.write(path, path.relative_to(OUT))
    if receipt['status'] != 'finished':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
