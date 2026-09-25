"""Run only after separate coordinator admission. Own CPU VM, one dispatch."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CLI = str(Path.home() / '.local/bin/colab')
NAME = 'p2-native2-069-s8ee-20260925'
ARCHIVE = OUT / 'p2-packet-native2-069-k5-s8ee-20260925.zip'
RUNNER = ROOT / 'scripts/q2_packet_native_pilot.py'


def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2) + '\n')


def call(stage, args, timeout):
    started = time.perf_counter()
    with (OUT / (stage + '.out')).open('w') as out, (OUT / (stage + '.err')).open('w') as err:
        result = subprocess.run([CLI, '--auth', 'oauth2', *args], stdout=out, stderr=err,
                                timeout=timeout)
    save(stage + '.json', {'returncode': result.returncode,
                          'wall_seconds': time.perf_counter() - started})
    if result.returncode:
        raise RuntimeError(stage + ' failed')
    return ((OUT / (stage + '.out')).read_text() + '\n'
            + (OUT / (stage + '.err')).read_text())


def empty_sessions(text):
    normalized = '\n'.join(line.strip() for line in text.splitlines() if line.strip())
    return normalized == '[colab] No active sessions found on server.'


def live_call(deadline, stage, args, timeout):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Lease expired before ' + stage)
    return call(stage, args, min(timeout, remaining))


def verify_launch():
    hashes = json.loads((OUT / 'launch-files.json').read_bytes())
    if set(hashes) != {'controller.py', 'bootstrap.py'}:
        raise ValueError('Unexpected launcher file set')
    for name, expected in hashes.items():
        path = Path(__file__).resolve() if name == 'controller.py' else OUT / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Launcher changed: ' + name)
    freeze = json.loads((OUT / 'freeze.json').read_bytes())
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != freeze['capsule_sha256']:
        raise ValueError('Capsule changed')
    with zipfile.ZipFile(ARCHIVE) as z:
        raw = z.read('manifest.json')
        manifest = json.loads(raw)
    if hashlib.sha256(raw).hexdigest() != freeze['manifest_sha256']:
        raise ValueError('Manifest changed')
    if hashlib.sha256(RUNNER.read_bytes()).hexdigest() != manifest['files']['scripts/q2_packet_native_pilot.py']:
        raise ValueError('External runner changed')
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() != freeze['runner_commit']:
        raise ValueError('Runner commit changed')
    return freeze


def watchdog(deadline):
    while time.monotonic() < deadline:
        if (OUT / 'released.json').exists():
            return
        time.sleep(min(1, max(0, deadline - time.monotonic())))
    try:
        call('lease-stop', ['stop', '-s', NAME], 40)
    except BaseException as error:
        save('lease-stop-error.json', {'error': repr(error)})


def main():
    freeze = verify_launch()
    with (OUT / 'controller-attempt.json').open('x') as f:
        json.dump({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   'session': NAME, 'capsule_sha256': freeze['capsule_sha256']}, f)
    record = {'session': NAME, 'status': 'preflight', 'new_attempted': False, 'exec_attempted': False}
    lease = None
    try:
        sessions = call('sessions-before', ['sessions'], 25)
        if not empty_sessions(sessions):
            raise RuntimeError('Cloud slot is not empty; no VM creation')
        deadline = time.monotonic() + 300
        lease = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                                  'watchdog', str(deadline)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
        record.update(new_attempted=True, lease_pid=lease.pid)
        save('controller-receipt.json', record)
        live_call(deadline, 'new', ['new', '-s', NAME], 75)
        live_call(deadline, 'upload-capsule', ['upload', '-s', NAME, str(ARCHIVE), '/content/' + ARCHIVE.name], 30)
        live_call(deadline, 'upload-runner', ['upload', '-s', NAME, str(RUNNER), '/content/' + RUNNER.name], 30)
        if time.monotonic() >= deadline:
            raise TimeoutError('Lease expired before exec dispatch')
        record['exec_attempted'] = True
        save('controller-receipt.json', record)
        live_call(deadline, 'exec', ['exec', '-s', NAME, '-f', str(OUT / 'bootstrap.py'), '--timeout', '160',
                     '--env', 'P2_PACKET_NATIVE_CAPSULE_FILENAME=' + ARCHIVE.name,
                     '--env', 'P2_PACKET_NATIVE_CAPSULE_SHA256=' + freeze['capsule_sha256']], 170)
        live_call(deadline, 'download', ['download', '-s', NAME, '/content/q2-packet-native-results.zip',
                         str(OUT / 'results.zip')], 30)
        record['status'] = 'completed_downloaded_unverified'
    except BaseException as error:
        record.update(status='stopped', error=repr(error))
        if record['exec_attempted'] and not (OUT / 'results.zip').exists():
            try:
                call('failure-download', ['download', '-s', NAME, '/content/q2-packet-native-results.zip',
                                          str(OUT / 'results.zip')], 20)
            except BaseException as download_error:
                record['failure_download_error'] = repr(download_error)
    finally:
        if record['new_attempted']:
            try:
                call('stop', ['stop', '-s', NAME], 40)
                sessions = call('sessions-after', ['sessions'], 25)
                if NAME in sessions:
                    raise RuntimeError('Own session remains after stop')
                save('released.json', {'stop_returncode': 0, 'own_name_absent_from_fresh_sessions': True})
                record['release_confirmed'] = True
            except BaseException as stop_error:
                record['release_error'] = repr(stop_error)
        if lease is not None and (OUT / 'released.json').exists():
            if lease.poll() is None:
                lease.terminate()
            lease.wait(timeout=5)
            record['watchdog_reaped'] = True
        save('controller-receipt.json', record)
        print(json.dumps(record), flush=True)
    if record['status'] != 'completed_downloaded_unverified' or not record.get('release_confirmed'):
        raise SystemExit(1)


if __name__ == '__main__':
    watchdog(float(sys.argv[2])) if len(sys.argv) > 1 and sys.argv[1] == 'watchdog' else main()
