"""One-shot Colab cell entry for the admitted 014/K1 differential.

This file is sent with ``colab exec --file``. It intentionally has no
``__future__`` import, ``__file__`` use, or command-line parser: that CLI
prepends code and retains the kernel's argv.
"""

import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import zipfile


EXPECTED_CAPSULE_SHA256 = "9a41bc000814f180d99433d8cb5cf645dc134c564c98ad19d63fcfcb5648a3af"
RSS_LIMIT_BYTES = 4 * 1024**3
ROOT = Path("/content/q2-rank-014-fixed")
CAPSULE = Path("/content/q2-rank-014-capsule.zip")
RESULT_ZIP = Path("/content/q2-rank-014-result.zip")
OUT = Path("/content/q2-rank-014-output")


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def child_pids(parent):
    found = {parent}
    while True:
        before = len(found)
        for proc in Path("/proc").iterdir():
            if not proc.name.isdecimal():
                continue
            try:
                stat = (proc / "stat").read_text()
                ppid = int(stat[stat.rfind(")") + 2 :].split()[1])
            except (OSError, ValueError, IndexError):
                continue
            if ppid in found:
                found.add(int(proc.name))
        if len(found) == before:
            return found


def tree_rss(parent):
    total = 0
    for pid in child_pids(parent):
        try:
            for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    total += int(line.split()[1]) * 1024
                    break
        except (OSError, ValueError, IndexError):
            pass
    return total


def run_admitted_attempt():
    receipt = {"schema": "q2-rank-014-colab-cell-v1", "cell_started_utc": utc_now(),
               "capsule_sha256_expected": EXPECTED_CAPSULE_SHA256,
               "preparation_attempts": 0, "planned_e0_calls": 0,
               "planned_native_replays": 0,
               "retry_count": 0, "status": "setup_failed"}
    OUT.mkdir(parents=True, exist_ok=False)
    try:
        actual = hashlib.sha256(CAPSULE.read_bytes()).hexdigest()
        receipt["capsule_sha256_actual"] = actual
        if actual != EXPECTED_CAPSULE_SHA256:
            raise RuntimeError("capsule SHA-256 mismatch")
        if ROOT.exists():
            raise RuntimeError("capsule root already exists")
        ROOT.mkdir()
        with zipfile.ZipFile(CAPSULE) as archive:
            for name in archive.namelist():
                path = Path(name)
                if path.is_absolute() or ".." in path.parts:
                    raise RuntimeError("unsafe capsule member")
            archive.extractall(ROOT)
        setup_start = time.monotonic()
        setup = subprocess.run(["uv", "sync", "--locked"], cwd=ROOT,
                               text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=120)
        receipt["setup_seconds"] = time.monotonic() - setup_start
        (OUT / "setup.log").write_text(setup.stdout)
        if setup.returncode != 0:
            raise RuntimeError(f"uv sync failed: {setup.returncode}")

        command = ["timeout", "--signal=TERM", "--kill-after=2s", "180s",
                   str(ROOT / ".venv/bin/python"), "-B",
                   str(ROOT / "q2_rank_prep_differential.py"), str(ROOT), str(OUT / "new")]
        receipt["command"] = command
        receipt["preparation_attempts"] = 1
        receipt["preparation_t0_utc"] = utc_now()
        start = time.monotonic()
        with (OUT / "runner.log").open("wb") as log:
            process = subprocess.Popen(command, cwd=ROOT, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            peak_rss = 0
            rss_limit_hit = False
            while process.poll() is None:
                peak_rss = max(peak_rss, tree_rss(process.pid))
                if peak_rss > RSS_LIMIT_BYTES:
                    rss_limit_hit = True
                    os.killpg(process.pid, signal.SIGTERM)
                    time.sleep(2)
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                    break
                time.sleep(0.2)
            receipt["child_exit_code"] = process.wait()
        receipt["preparation_elapsed_seconds"] = time.monotonic() - start
        receipt["peak_sampled_process_tree_rss_bytes"] = peak_rss
        receipt["rss_limit_hit"] = rss_limit_hit
        report = OUT / "new/report.json"
        if report.exists():
            receipt["runner_report"] = json.loads(report.read_text())
        else:
            receipt["calls_if_no_runner_report"] = "unknown; do not infer zero from wrapper"
        receipt["status"] = "completed" if receipt["child_exit_code"] == 0 and not rss_limit_hit else "failed"
    except Exception as error:
        receipt["error"] = f"{type(error).__name__}: {error}"
        if receipt["preparation_attempts"]:
            receipt["status"] = "failed"
            receipt["calls_if_no_runner_report"] = "unknown; do not infer zero from wrapper"
    finally:
        receipt["cell_finished_utc"] = utc_now()
        (OUT / "cell-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True))
        with zipfile.ZipFile(RESULT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(OUT.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(OUT))
    print(json.dumps(receipt, sort_keys=True))


run_admitted_attempt()
