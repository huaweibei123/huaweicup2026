"""One-use host dispatcher. Requires exclusive scheduler admission; no retry."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

CAPSULE_SHA = 'c0d25765b29f8958ebc93c3ef39fdae76179b26963835745052d8abfa05a0a74'
CONTROLLER_SHA = 'decf7de359ae3035b34f95464cbaee1a2187fa1048330678c2cfa5d6aa765bb6'
CAPSULE_BYTES = 517312
SESSION = 'q2-r05-pair-20260925'
REMOTE = '/content/q2-r05-pair-20260925.zip'
RESULT = '/content/q2-r05-pair-20260925-results.zip'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def empty_sessions(text):
    return text.strip() in ('[]', '[colab] No active sessions found on server.')


def cell_wrapper(controller):
    header = (f'import os\nos.environ["P2_R05_PAIR_MODE"]="run"\n'
              f'os.environ["P2_R05_PAIR_SHA256"]="{CAPSULE_SHA}"\n')
    return header.encode() + controller


def stop_proven(receipt):
    return (receipt.get('stop_rc') == 0 and receipt.get('sessions_after_rc') == 0
            and receipt.get('session_absent') is True)


def finish(receipt, command, watchdog, cli, out):
    """Always attempt stop/readback; preserve watchdog unless both prove stop."""
    try:
        receipt['stop_rc'] = command([cli, '--auth', 'oauth2', 'stop', '--session', SESSION], out / 'stop.log')
    except Exception as error:
        receipt['stop_error'] = repr(error)
    try:
        receipt['sessions_after_rc'] = command([cli, '--auth', 'oauth2', 'sessions'], out / 'sessions-after.log')
        if receipt['sessions_after_rc'] == 0:
            receipt['session_absent'] = empty_sessions((out / 'sessions-after.log').read_text())
    except Exception as error:
        receipt['sessions_after_error'] = repr(error)
    receipt['stop_proven'] = stop_proven(receipt)
    if receipt['stop_proven']:
        if watchdog.poll() is None:
            watchdog.terminate()
        try:
            watchdog.wait(timeout=3)
        except subprocess.TimeoutExpired:
            watchdog.kill()
            watchdog.wait()
    receipt['watchdog_retained'] = not receipt['stop_proven']
    receipt['watchdog_exit_code'] = watchdog.poll()
    receipt['status'] = ('completed' if receipt.get('workload_completed') is True
                         and receipt['stop_proven'] else 'failed_or_unknown')
    return receipt


def collect_and_finish(receipt, command, watchdog, cli, out):
    """Malformed/missing downloaded evidence cannot bypass stop and readback."""
    try:
        try:
            receipt['download_rc'] = command(
                [cli, '--auth', 'oauth2', 'download', '--session', SESSION,
                 RESULT, str(out / 'result.zip')], out / 'download.log')
        except Exception as error:
            receipt['download_error'] = repr(error)
        if (out / 'result.zip').exists():
            try:
                with zipfile.ZipFile(out / 'result.zip') as z:
                    raw = z.read('output/batch.json')
                    batch = json.loads(raw)
                    receipt['batch_status'] = batch.get('status')
                    receipt['batch_sha256'] = hashlib.sha256(raw).hexdigest()
                    receipt['batch_calls'] = batch.get('calls')
                    receipt['batch_rows'] = len(batch.get('rows', []))
            except Exception as error:
                receipt['batch_error'] = repr(error)
    finally:
        calls = receipt.get('batch_calls')
        receipt['workload_completed'] = (
            receipt.get('exec_rc') == 0 and receipt.get('download_rc') == 0
            and receipt.get('batch_status') == 'completed'
            and receipt.get('batch_rows') == 2 and isinstance(calls, dict)
            and calls.get('E0_reserved') == 2)
        finish(receipt, command, watchdog, cli, out)
    return receipt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--admitted', action='store_true')
    ap.add_argument('--capsule', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--colab', type=Path, default=Path('~/.local/bin/colab').expanduser())
    ap.add_argument('--pythonpath', type=Path, help='optional existing Colab CLI fork module root')
    a = ap.parse_args()
    if not a.admitted:
        ap.error('scheduler admission required')
    capsule = a.capsule.resolve(strict=True)
    if capsule.stat().st_size != CAPSULE_BYTES or sha(capsule) != CAPSULE_SHA:
        ap.error('fixed capsule identity mismatch')
    with zipfile.ZipFile(capsule) as z:
        controller = z.read('scripts/q2_r05_pair_colab.py')
        if hashlib.sha256(controller).hexdigest() != CONTROLLER_SHA:
            ap.error('fixed controller identity mismatch')
    cli_path = a.colab.expanduser().absolute()
    if not cli_path.is_file():
        ap.error('Colab CLI path missing')
    cli = str(cli_path)
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    if a.pythonpath:
        env['PYTHONPATH'] = str(a.pythonpath.expanduser().resolve(strict=True))
    # All CLI calls use this environment; no hidden global CLI alias.
    def command(argv, log, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('600-second host deadline exhausted')
        with log.open('wb') as stream:
            return subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT,
                                  timeout=remaining, env=env, check=False).returncode
    t0_epoch = time.time()
    t0_monotonic = time.monotonic()
    deadline = t0_monotonic + 600
    if command([cli, '--auth', 'oauth2', 'sessions'], out / 'sessions-before.log', min(deadline, time.monotonic() + 20)) != 0:
        raise RuntimeError('Cannot verify empty sessions')
    if not empty_sessions((out / 'sessions-before.log').read_text()):
        raise RuntimeError('Nonempty or unrecognized sessions; no VM created')
    receipt = {'schema': 'q2-r05-pair-host-v1', 'session': SESSION,
               'capsule_sha256': CAPSULE_SHA, 'controller_sha256': CONTROLLER_SHA,
               'workload_completed': False, 'calls_authority': 'result.zip/output/batch.json',
               'calls_without_result': 'unknown', 'status': 'armed',
               't0_utc': datetime.fromtimestamp(t0_epoch, timezone.utc).isoformat(),
               't0_epoch': t0_epoch, 'deadline_epoch': t0_epoch + 600}
    # Detached watchdog survives controller failure. It is armed before create.
    script = ('import subprocess,sys,time; '
              'time.sleep(max(0,float(sys.argv[1])-time.time())); '
              'subprocess.run([sys.argv[2],"--auth","oauth2","stop","--session",sys.argv[3]],timeout=25)')
    with (out / 'watchdog.log').open('wb') as stream:
        watchdog = subprocess.Popen([sys.executable, '-c', script, str(t0_epoch + 600), cli, SESSION],
                                    stdout=stream, stderr=subprocess.STDOUT,
                                    start_new_session=True, env=env)
    receipt['watchdog_pid'] = watchdog.pid
    receipt['watchdog_armed_utc'] = datetime.now(timezone.utc).isoformat()
    (out / 'host-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    wrapper = out / 'colab-cell.py'
    wrapper.write_bytes(cell_wrapper(controller))
    try:
        operation_deadline = deadline - 60
        if command([cli, '--auth', 'oauth2', 'new', '--session', SESSION], out / 'new.log', operation_deadline):
            raise RuntimeError('VM create failed')
        if command([cli, '--auth', 'oauth2', 'upload', '--session', SESSION, str(capsule), REMOTE],
                   out / 'upload.log', operation_deadline):
            raise RuntimeError('Capsule upload failed')
        exec_timeout = max(1, int(operation_deadline - time.monotonic()))
        receipt['exec_dispatched'] = True
        receipt['exec_rc'] = command([cli, '--auth', 'oauth2', 'exec', '--session', SESSION, '--file', str(wrapper),
                                      '--timeout', str(exec_timeout)], out / 'exec.log',
                                     operation_deadline)
    except Exception as error:
        receipt['workload_error'] = repr(error)
    finally:
        def download_or_cleanup(argv, log):
            return command(argv, log, deadline - 20 if argv[3] == 'download' else deadline)
        collect_and_finish(receipt, download_or_cleanup, watchdog, cli, out)
        (out / 'host-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return 0 if receipt['status'] == 'completed' else 1


if __name__ == '__main__':
    sys.exit(main())
