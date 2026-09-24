"""Fixed fake target. It is copied by bytes under both official CLI basenames."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys

# Copied fixture finds driver from the controlled request, never ambient PYTHONPATH.
sys.path.insert(0, os.environ["E2_DRIVER_DIR"])
from common import gated_request, require, save, expected_stdin, fake_argv
from win_support import API


def main():
    case, request = gated_request()
    row = request["case"]
    require(row["kind"] == "fake_contract" and row["id"] != "F-startfail", "fake only")
    api = API()
    proof = api.exact_membership(request["job"])
    require(proof["api_success"] and proof["member"] and proof["query_closed"], "fixture Job")
    event = api.event(request["release_event"])
    grandchild = sys.argv[1:] == ["--grandchild"]
    try:
        if grandchild:
            require(row["id"] == "F-cancel", "unexpected grandchild")
            save(case / "grandchild.ready.json", {"pid": os.getpid(), "ppid": os.getppid(),
                 "qpc": api.qpc(), "membership": proof}, exclusive=True)
            require(api.k.WaitForSingleObject(event.value, 10000) == 0, "grandchild unreleased")
            return 0
        data = sys.stdin.buffer.read(8193)
        require(data == expected_stdin(row), "stdin mismatch")
        require(sys.argv[1:] == fake_argv(row), "argv mismatch")
        require(Path.cwd() == case / "工作 空间", "cwd mismatch")
        require(os.environ.get("E2_SENTINEL") == "环境 sentinel λ", "environment mismatch")
        receipt = {"pid": os.getpid(), "ppid": os.getppid(), "argv": sys.argv,
                   "cwd": str(Path.cwd()), "sentinel": os.environ["E2_SENTINEL"],
                   "stdin_sha256": hashlib.sha256(data).hexdigest(),
                   "membership": proof, "qpc": api.qpc()}
        save(case / "target.ready.json", receipt, exclusive=True)
        child = None
        if row["id"] == "F-cancel":
            save(case / "grandchild-create-reservation.json", {"requests": 1}, exclusive=True)
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--grandchild"],
                                     stdin=subprocess.DEVNULL, shell=False, close_fds=True)
            save(case / "grandchild-launcher.json", {"pid": child.pid}, exclusive=True)
        require(api.k.WaitForSingleObject(event.value, 10000) == 0, "target unreleased")
        if row["id"] == "F1":
            sys.stdout.buffer.write(b"O" * (256 * 1024))
            sys.stderr.buffer.write(b"E" * (256 * 1024))
            sys.stdout.buffer.flush()
            sys.stderr.buffer.flush()
        if row["id"] == "F2":
            parser = argparse.ArgumentParser(prog="fixed-fake-target")
            parser.parse_args(["--deliberately-invalid"])
            raise RuntimeError("argparse accepted invalid flag")
        require(child is None, "cancel target unexpectedly released")
        code = row["expected_ordinary_exit_code"]
        save(case / "target.final.json", {"exit_code_requested": code,
             "pid": os.getpid(), "qpc": api.qpc()}, exclusive=True)
        return code
    finally:
        event.close()


if __name__ == "__main__":
    raise SystemExit(main())
