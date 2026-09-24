"""Unexecuted fake-target seam. The production helper and subprocess stay real."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

_DRIVER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_DRIVER_DIR))
import common as _common
if Path(_common.__file__).resolve() != _DRIVER_DIR / "common.py":
    raise RuntimeError("unexpected common module origin")
from common import ROOT, gated_request, require, save, digest, fake_argv
from win_support import API


def main():
    case, request = gated_request()
    api = API()
    proof = api.exact_membership(request["job"])
    require(proof["api_success"] and proof["member"] and proof["query_closed"], "seam Job")
    require((case / "ack.private.json").is_file(), "seam not admitted")
    row = request["case"]
    require(row["kind"] == "fake_contract", "real CLI must not use seam")
    sys.path.insert(0, str(ROOT))
    path = ROOT / "research/a/e2_search/_full_cli.py"
    require(digest(path) == request["helper_sha256"], "real helper bytes")
    spec = importlib.util.spec_from_file_location("_review_real_full_cli", path)
    require(spec and spec.loader, "helper loader")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    require(Path(helper.main.__code__.co_filename).resolve() == path.resolve(), "real main origin")
    require(helper.main.__globals__ is helper.__dict__, "real main globals")
    verify = helper.verify_official_code
    require(verify.__module__ == "src.eval_exact._official", "real verifier")
    verify()  # Same verifier also remains in main; no evaluation is performed here.
    original = dict(helper.__dict__)
    genuine_run = subprocess.run
    fake_dir = case / "目标 空间"
    helper.OFFICIAL_CODE_DIR = fake_dir
    require([k for k in original if helper.__dict__[k] is not original[k]] == ["OFFICIAL_CODE_DIR"],
            "unapproved helper rebinding")
    require(helper.verify_official_code is verify and subprocess.run is genuine_run,
            "verifier or subprocess replaced")
    sys.argv = [str(path), *fake_argv(row)]
    if row["id"] == "F-startfail":
        missing = case / "missing interpreter.exe"
        require(not missing.exists(), "startup failure executable exists")
        helper.sys.executable = str(missing)
    attempts = []
    expected_tokens = [helper.sys.executable,
                       str(fake_dir / f"multicore_cut_evaluate_problem_{row['problem']}.py"),
                       *fake_argv(row)]

    def audit(event, args):
        if event == "subprocess.Popen":
            require(not attempts, "second helper creation request forbidden")
            require(subprocess.run is genuine_run, "subprocess replaced")
            require(isinstance(args[1], str), "expected Windows audit command-line string")
            # CPython's Windows path leaves executable=None when that keyword
            # is omitted; CreateProcess derives the image from command_line.
            require(args[0] is None and
                    args[1] == subprocess.list2cmdline(expected_tokens), "audit command line differs from fixed tokens")
            attempts.append({"raw_executable": args[0], "raw_executable_type": type(args[0]).__name__,
                             "expected_image_token": expected_tokens[0], "command_line": args[1],
                             "command_line_type": type(args[1]).__name__,
                             "expected_tokens": expected_tokens,
                             "cwd": args[2], "env_is_none": args[3] is None})
            save(case / "helper-create-attempt.json", attempts, exclusive=True)

    sys.addaudithook(audit)
    save(case / "wrapper.ready.json", {"pid": os.getpid(), "ppid": os.getppid(),
         "helper_sha256": digest(path), "verifier_unchanged": True,
         "subprocess_real": True, "allowed_rebindings": row["seam_identity"]["allowed_rebindings"],
         "membership": proof, "qpc": api.qpc()}, exclusive=True)
    try:
        helper.main(row["problem"])
    except SystemExit as exc:
        save(case / "wrapper.exit.json", {"SystemExit_code": exc.code,
             "create_attempts": len(attempts), "qpc": api.qpc()}, exclusive=True)
        raise
    except OSError as exc:
        save(case / "wrapper.start_error.json", {"error_class": type(exc).__name__,
             "winerror": getattr(exc, "winerror", None), "errno": exc.errno,
             "create_attempts": len(attempts), "qpc": api.qpc()}, exclusive=True)
        raise
    raise RuntimeError("helper returned instead of SystemExit")


if __name__ == "__main__":
    main()
