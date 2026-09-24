"""One admitted case only. Never retry targets or import the evaluator here."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

_DRIVER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_DRIVER_DIR))
import common as _common
if Path(_common.__file__).resolve() != _DRIVER_DIR / "common.py":
    raise RuntimeError("unexpected common module origin")
from common import HERE, ROOT, gated_request, require, save, wait_record, expected_stdin
from win_support import API


def run():
    case, request = gated_request()
    api = API()
    membership = api.exact_membership(request["job"])
    require(membership["api_success"] and membership["member"] and membership["query_closed"], "bootstrap Job")
    save(case / "bootstrap.ready.json", {"pid": os.getpid(), "ppid": os.getppid(),
         "nonce_sha256": hashlib.sha256(request["nonce"].encode()).hexdigest(),
         "membership": membership, "bundle": request["bundle"], "qpc": api.qpc()}, exclusive=True)
    ack = wait_record(case / "ack.private.json", request["work_deadline_tick"], api)
    require(ack["nonce"] == request["nonce"] and ack["pid"] == os.getpid()
            and ack["bundle"] == request["bundle"], "ACK identity")
    require(os.getpid() in ack["complete_ready_pids"], "ACK PID coverage")
    row = request["case"]
    fake = row["kind"] == "fake_contract"
    argv = ([sys.executable, "-I", "-B", "-X", "utf8", str(HERE / "seam.py")] if fake else request["argv"])
    cwd = str(case / "工作 空间") if fake else str(ROOT)
    require(api.tick() < request["work_deadline_tick"], "case deadline before launch")
    save(case / "case-create-reservation.json", {"requests": 1, "argv": argv, "cwd": cwd}, exclusive=True)
    outputs = {"stdout": case / "case.stdout.raw", "stderr": case / "case.stderr.raw"}
    start = api.qpc()
    errors = []
    if row["stdio"] == "PIPE":
        process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, shell=False, close_fds=True)
        save(case / "case-launcher.json", {"pid": process.pid, "qpc": api.qpc()}, exclusive=True)

        def drain(name, stream):
            count = 0
            try:
                with open(outputs[name], "xb") as output:
                    while True:
                        block = stream.read(8192)
                        if not block:
                            break
                        count += len(block)
                        require(count <= 1024 * 1024, "PIPE capture limit")
                        output.write(block)
                    output.flush()
                    os.fsync(output.fileno())
            except BaseException as exc:
                errors.append(repr(exc))
            finally:
                stream.close()

        threads = [threading.Thread(target=drain, args=(name, stream), daemon=True)
                   for name, stream in (("stdout", process.stdout), ("stderr", process.stderr))]
        for thread in threads:
            thread.start()
        process.stdin.write(expected_stdin(row))
        process.stdin.close()
        while process.poll() is None:
            require(not errors and api.tick() < request["work_deadline_tick"], "PIPE failure/deadline")
            time.sleep(0.005)
        for thread in threads:
            thread.join(max(0, (request["work_deadline_tick"] - api.tick()) / 1000))
            require(not thread.is_alive(), "PIPE EOF deadline")
        require(not errors, "PIPE capture errors: " + repr(errors))
    else:
        with open(case / "stdin.bin", "rb") as incoming, open(outputs["stdout"], "xb") as stdout, open(outputs["stderr"], "xb") as stderr:
            process = subprocess.Popen(argv, cwd=cwd, stdin=incoming, stdout=stdout, stderr=stderr,
                                       shell=False, close_fds=True)
            save(case / "case-launcher.json", {"pid": process.pid, "qpc": api.qpc()}, exclusive=True)
            while process.poll() is None:
                require(api.tick() < request["work_deadline_tick"], "case deadline")
                time.sleep(0.005)
    process._handle.Close()  # Pinned CPython Windows Popen handle; no target is alive here.
    require(process._handle.closed, "Popen handle close")
    save(case / "bootstrap.result.json", {"returncode": process.returncode,
         "launcher_pid": process.pid, "start_qpc": start, "end_qpc": api.qpc(),
         "work_finished_tick": api.tick(),
         "stdio": row["stdio"], "drain_errors": errors, "Popen_handle_closed": True}, exclusive=True)


if __name__ == "__main__":
    try:
        run()
    except BaseException as error:
        directory = os.environ.get("E2_CASE_DIR")
        if directory:
            save(Path(directory) / "bootstrap.error.json", {"error": repr(error)})
        raise
