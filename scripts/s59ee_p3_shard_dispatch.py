"""Dispatch the ten fixed P3 shards with a four-cell pilot and eight-slot cap.

The pinned Q3 feedback runner owns each shard and its online official E0 calls.
This controller does not score, retry, modify manifests, or share output paths.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "2d5459fa042507cce0f0343e544ed43784c8488b"
HANDOFF = ROOT / "results/a/q3-nikolastarx/unified500-handoff-20260925"
AREA = ROOT / "results/a/q3-nikolastarx/unified-full500-20260925-s59"
PILOT = [("001", 1), ("051", 5), ("082", 4), ("062", 5)]
MEMORY_FLOOR = 6 * 1024**3


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def available_bytes():
    output = subprocess.check_output(["vm_stat"], text=True)
    size = int(re.search(r"page size of (\d+) bytes", output).group(1))
    values = dict(re.findall(r"^(Pages (?:free|inactive|speculative|purgeable)):\s+([\d.]+)", output, re.M))
    return size * sum(int(value.replace(".", "")) for value in values.values())


def preflight():
    sys.path.insert(0, str(ROOT))
    from src.q3.feedback_benchmark import validate_manifest, verify_source

    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != SOURCE:
        raise RuntimeError("source HEAD differs from frozen solver")
    manifests = []
    coordinates = []
    for n in range(1, 11):
        path = HANDOFF / f"manifest-s{n:02}.json"
        value = read(path)
        validate_manifest(value)
        if value["solver_commit"] != SOURCE or value["solver_module"] != "src.q3.adaptive_solve":
            raise RuntimeError("shard source changed")
        if len(value["jobs"]) != 50 or value["budget"] != {
            "max_e0_calls": 100, "total_wall_seconds": 360, "per_job_seconds": 90
        }:
            raise RuntimeError("shard scope or budget changed")
        if n <= 4 and (value["jobs"][0]["case_id"], value["jobs"][0]["cores"]) != PILOT[n-1]:
            raise RuntimeError("pilot is not first in its shard")
        coordinates.extend((job["case_id"], job["cores"]) for job in value["jobs"])
        manifests.append((path, value))
    if len(coordinates) != 500 or len(set(coordinates)) != 500 or set(coordinates) != {
        (f"{i:03d}", k) for i in range(1, 101) for k in range(1, 6)
    }:
        raise RuntimeError("ten shards do not partition the exact 500 coordinates")
    code, hashes = verify_source(SOURCE, {case for case, _ in coordinates})
    if code != "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0":
        raise RuntimeError("official aggregate identity changed")
    return manifests, len(hashes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    batch = args.batch.resolve()
    if not batch.is_relative_to(AREA) or batch == AREA:
        parser.error("batch must be under this session's P3 result prefix")
    manifests, checked = preflight()
    available = available_bytes()
    if available < MEMORY_FLOOR:
        raise RuntimeError("less than 6 GiB available before pilot")
    if args.preflight:
        print(json.dumps({"valid": True, "cells": 500, "shards": 10, "max_workers": 8,
                          "source_commit": SOURCE, "hashed_source_inputs": checked,
                          "available_bytes": available, "batch_created": False}))
        return 0
    batch.mkdir(parents=True, exist_ok=False)
    controller = batch / "controller"
    controller.mkdir()
    state_path = batch / "dispatch.json"
    state = {"schema": "p3-ten-shard-dispatch-v1", "source_commit": SOURCE,
             "handoff_commit": "36e9fddc2aece856112ef5faab870e4ca7e91099",
             "runner_commit": SOURCE, "runner_path": "src/q3/feedback_benchmark.py",
             "controller_path": "scripts/s59ee_p3_shard_dispatch.py", "controller_sha256": sha(__file__),
             "started_at": utc(), "finished_at": None, "status": "running", "max_workers": 8,
             "max_solver_calls": 500, "max_E0_calls": 1000, "deadline_seconds": 3600,
             "retries": 0, "pilot": PILOT, "available_bytes_at_start": available,
             "shards": {f"s{i:02}": {"status": "queued", "manifest_sha256": sha(path),
                                    "run_id": value["run_id"], "coordinates": len(value["jobs"])}
                        for i, (path, value) in enumerate(manifests, 1)}}
    write(state_path, state)
    active = {}
    log_files = {}
    deadline = time.monotonic() + 3600
    queue = list(range(5, 11))
    pilot_done = False
    stopped = False

    def launch(n):
        nonlocal stopped
        if time.monotonic() >= deadline:
            stopped = True
            return False
        free = available_bytes()
        if free < MEMORY_FLOOR:
            return False
        tag = f"s{n:02}"
        manifest = manifests[n-1][0]
        output = batch / tag
        stdout = (controller / f"{tag}.stdout.log").open("xb")
        stderr = (controller / f"{tag}.stderr.log").open("xb")
        command = [sys.executable, "-B", "-m", "src.q3.feedback_benchmark", str(manifest), str(output)]
        proc = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                stdout=stdout, stderr=stderr, start_new_session=True,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0",
                                     "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
        log_files[n] = (stdout, stderr)
        active[n] = proc
        state["shards"][tag].update(status="running", pid=proc.pid, started_at=utc(),
                                     available_bytes_at_launch=free,
                                     argv=["python", "-B", "-m", "src.q3.feedback_benchmark",
                                           manifest.relative_to(ROOT).as_posix(), output.relative_to(ROOT).as_posix()])
        write(state_path, state)
        return True

    for n in range(1, 5):
        if not launch(n):
            stopped = True
            break
    while active or queue:
        for n, proc in list(active.items()):
            code = proc.poll()
            if code is None:
                continue
            active.pop(n)
            for f in log_files.pop(n):
                f.close()
            tag = f"s{n:02}"
            output = batch / tag / "batch.json"
            shard = read(output) if output.exists() else {}
            state["shards"][tag].update(status=shard.get("status", "runner_failed"),
                                         finished_at=utc(), exit_code=code,
                                         actual_records=len(shard.get("records", [])),
                                         actual_E0_or_reservation=shard.get("e0_budget_used"))
            if code != 0 or shard.get("status") != "stage_complete":
                stopped = True
            write(state_path, state)
        if not pilot_done and all(state["shards"][f"s{n:02}"]["status"] != "queued" for n in range(1,5)):
            statuses = []
            for n in range(1, 5):
                first = manifests[n-1][1]["jobs"][0]
                key = f"{first['case_id']}-k{first['cores']}-{first['variant']}"
                receipt = batch / f"s{n:02}" / "cells" / key / "run.json"
                statuses.append(read(receipt).get("status") if receipt.exists() else None)
            if all(s == "ok" for s in statuses):
                pilot_done = True
                state["pilot_completed_at"] = utc()
                write(state_path, state)
            elif any(s in ("failed", "timeout") for s in statuses):
                stopped = True
                state["pilot_failure"] = statuses
                write(state_path, state)
        if pilot_done and not stopped:
            while queue and len(active) < 8:
                if not launch(queue[0]):
                    break
                queue.pop(0)
        if stopped and not active:
            break
        if time.monotonic() >= deadline:
            stopped = True
        time.sleep(.5)
    for n, proc in active.items():
        proc.wait()
        for f in log_files[n]:
            f.close()
    state.update(finished_at=utc(), status="complete" if not stopped and not queue and all(
        state["shards"][f"s{n:02}"]["status"] == "stage_complete" for n in range(1,11)
    ) else "stopped", queued_shards=[f"s{n:02}" for n in queue])
    write(state_path, state)
    print(json.dumps({"status": state["status"], "pilot_complete": pilot_done,
                      "shards_complete": sum(x["status"] == "stage_complete" for x in state["shards"].values()),
                      "shards_queued": len(queue)}))
    return 0 if state["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
