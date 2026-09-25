"""One admitted Colab CPU Standard attempt; never call before coordinator admission."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
CLI = str(Path.home() / '.local/bin/colab')
NAME = 'p2-reverse-gap-s8ee-20260925'
ZIP = OUT / 'reverse-gap-capsule.zip'
REMOTE_ZIP = '/content/reverse-gap-results.zip'


def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2) + '\n')


def call(stage, args, timeout):
    with (OUT / (stage + '.out')).open('w') as out, (OUT / (stage + '.err')).open('w') as err:
        result = subprocess.run([CLI, '--auth', 'oauth2', *args], stdout=out,
                                stderr=err, timeout=timeout)
    save(stage + '.json', {'returncode': result.returncode})
    if result.returncode:
        raise RuntimeError(stage + ' failed')
    return ((OUT / (stage + '.out')).read_text() + '\n' +
            (OUT / (stage + '.err')).read_text())


def leased(deadline, stage, args, timeout):
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError('lease expired before ' + stage)
    return call(stage, args, min(left, timeout))


def empty_sessions(raw):
    return '\n'.join(line.strip() for line in raw.splitlines() if line.strip()) == (
        '[colab] No active sessions found on server.')


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
    package = json.loads((OUT / 'package.json').read_bytes())
    launch_hashes = json.loads((OUT / 'launch-files.json').read_bytes())
    if set(launch_hashes) != {'bootstrap.py', 'controller.py'}:
        raise ValueError('unexpected launch file set')
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != launch_hashes['controller.py']:
        raise ValueError('controller differs from reviewed launch file')
    if hashlib.sha256((OUT / 'bootstrap.py').read_bytes()).hexdigest() != launch_hashes['bootstrap.py']:
        raise ValueError('bootstrap differs from reviewed launch file')
    digest = hashlib.sha256(ZIP.read_bytes()).hexdigest()
    if digest != package['archive_sha256']:
        raise ValueError('capsule hash differs from offline package receipt')
    with (OUT / 'controller-attempt.json').open('x') as f:
        json.dump({'session': NAME, 'capsule_sha256': digest}, f)
    record = {'session': NAME, 'status': 'preflight', 'new_attempted': False,
              'exec_attempted': False, 'downloaded': False}
    lease = None
    try:
        sessions = call('sessions-before', ['sessions'], 25)
        if not empty_sessions(sessions):
            raise RuntimeError('cloud slot not empty')
        deadline = time.monotonic() + 300
        lease = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                                  'watchdog', str(deadline)], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        record.update(new_attempted=True, lease_pid=lease.pid)
        save('controller-receipt.json', record)
        leased(deadline, 'new', ['new', '-s', NAME], 75)
        leased(deadline, 'upload-capsule', ['upload', '-s', NAME, str(ZIP), '/content/' + ZIP.name], 30)
        leased(deadline, 'upload-bootstrap', ['upload', '-s', NAME, str(OUT / 'bootstrap.py'),
                                            '/content/reverse-gap-bootstrap.py'], 30)
        record['exec_attempted'] = True
        save('controller-receipt.json', record)
        leased(deadline, 'exec', ['exec', '-s', NAME, '-f', str(OUT / 'bootstrap.py'),
                                 '--timeout', '145', '--env', 'P2_REVERSE_CAPSULE_SHA256=' + digest], 155)
        leased(deadline, 'download', ['download', '-s', NAME, REMOTE_ZIP,
                                      str(OUT / 'results.zip')], 30)
        record.update(status='downloaded_unverified', downloaded=True)
    except BaseException as error:
        record.update(status='stopped', error=repr(error))
        if record['exec_attempted'] and not record['downloaded']:
            try:
                call('failure-download', ['download', '-s', NAME, REMOTE_ZIP,
                                          str(OUT / 'results.zip')], 20)
                record['downloaded'] = True
            except BaseException as download_error:
                record['failure_download_error'] = repr(download_error)
    finally:
        if record['new_attempted']:
            try:
                call('stop', ['stop', '-s', NAME], 40)
                sessions = call('sessions-after', ['sessions'], 25)
                if not empty_sessions(sessions):
                    raise RuntimeError('sessions not empty after stop')
                save('released.json', {'stop_returncode': 0, 'own_name_absent': True})
                record['release_confirmed'] = True
            except BaseException as error:
                record['release_error'] = repr(error)
        if lease is not None and (OUT / 'released.json').exists():
            if lease.poll() is None:
                lease.terminate()
            lease.wait(timeout=5)
            record['watchdog_reaped'] = True
        save('controller-receipt.json', record)
    if record['status'] != 'downloaded_unverified' or not record.get('release_confirmed'):
        raise SystemExit(1)


if __name__ == '__main__':
    watchdog(float(sys.argv[2])) if len(sys.argv) > 1 and sys.argv[1] == 'watchdog' else main()
