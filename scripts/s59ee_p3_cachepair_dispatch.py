"""Evaluate fixed P3 plans once with official no-L2 P2 E0, with bounded concurrency."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "c2d628ba0fe8dce4630e5f9c0a5c8fb810fcd41a"
ARTIFACT = "f0ead1a3722f70a59a084acc70700a963945b567"
OFFICIAL = "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0"
AREA = ROOT / "results/a/q3-nikolastarx/witness-cachepair-20260925-s59"
PILOT = [("001", 1), ("051", 5), ("082", 4), ("062", 5)]


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def git_blob(path):
    return subprocess.check_output(["git", "show", f"{ARTIFACT}:{path}"], cwd=ROOT)


def available_bytes():
    output = subprocess.check_output(["vm_stat"], text=True)
    size = int(re.search(r"page size of (\d+) bytes", output).group(1))
    values = dict(re.findall(r"^(Pages (?:free|inactive|speculative|purgeable)):\s+([\d.]+)", output, re.M))
    return size * sum(int(v.replace(".", "")) for v in values.values())


def verify(manifest, *, include_blobs):
    sys.path.insert(0, str(ROOT))
    from src.q3.feedback_benchmark import verify_source

    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != SOURCE:
        raise RuntimeError("execution checkout does not have the frozen c2 source HEAD")
    if manifest["schema"] != "q3-same-plan-nol2-pair-v1" or manifest["source_commit"] != SOURCE \
            or manifest["artifact_commit"] != ARTIFACT or manifest["official_code_hash"] != OFFICIAL:
        raise RuntimeError("fixed manifest identity changed")
    budget = manifest["budget"]
    if budget != {"max_p2_e0_calls": 500, "max_solver_calls": 0, "max_p3_e0_calls": 0,
                  "max_workers": 4, "per_cell_seconds": 90, "batch_seconds": 3600, "retries": 0}:
        raise RuntimeError("fixed call/time/worker budget changed")
    if manifest["pilot"] != [{"case_id": c, "cores": k} for c, k in PILOT]:
        raise RuntimeError("four pilot cells changed")
    if manifest["controller_sha256"] != sha(Path(__file__).read_bytes()):
        raise RuntimeError("controller source differs from frozen manifest")
    jobs = manifest["jobs"]
    coords = [(j["case_id"], j["cores"]) for j in jobs]
    if len(jobs) != 500 or len(set(coords)) != 500 or set(coords) != {
        (f"{i:03d}", k) for i in range(1, 101) for k in range(1, 6)
    } or coords[:4] != PILOT:
        raise RuntimeError("pilot/full500 partition changed")
    code, hashes = verify_source(SOURCE, {case for case, _ in coords})
    if code != OFFICIAL:
        raise RuntimeError("official source hash changed")
    if include_blobs:
        plans = {}
        for j in jobs:
            key = f"{j['case_id']}-k{j['cores']}"
            graph = ROOT / f"data/raw/a/official/data/case_{j['case_id']}.json"
            if sha(graph.read_bytes()) != j["graph_sha256"] or sha((ROOT / "data/raw/a/official/data/config.txt").read_bytes()) != j["config_sha256"]:
                raise RuntimeError(f"frozen graph/config identity differs: {key}")
            plan_raw = git_blob(j["plan"]["path"])
            result_raw = git_blob(j["cache_result"]["path"])
            if sha(plan_raw) != j["plan"]["sha256"] or sha(result_raw) != j["cache_result"]["sha256"]:
                raise RuntimeError(f"fixed P3 plan/result blob hash differs: {key}")
            plan = json.loads(plan_raw)
            result = json.loads(gzip.decompress(result_raw))
            if set(plan) != {"node_to_subgraph", "core_schedules"} or result.get("scene") != "B" \
                    or result.get("problem") != 3 or result.get("cache_mode") != "read_only" \
                    or result.get("num_cores") != j["cores"] or result.get("makespan") != j["cache_makespan"]:
                raise RuntimeError(f"fixed P3 plan/result semantics differ: {key}")
            plans[key] = plan_raw
        return plans, len(hashes)
    return {}, len(hashes)


def stop_active(active):
    for p in active.values():
        if p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    time.sleep(.5)
    for p in active.values():
        if p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    for p in active.values():
        p.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    manifest_path, batch = args.manifest.resolve(), args.batch.resolve()
    if not manifest_path.is_relative_to(AREA) or not batch.is_relative_to(AREA) or batch == AREA:
        parser.error("manifest/batch must stay in this producer's P3 pair result area")
    manifest = read(manifest_path)
    manifest_sha = sha(manifest_path.read_bytes())
    started = time.monotonic()
    plans, checked = verify(manifest, include_blobs=True)
    if available_bytes() < 6 * 1024**3:
        raise RuntimeError("less than 6 GiB available before pair pilot")
    if args.preflight:
        print(json.dumps({"valid": True, "cells": 500, "pilot": 4, "new_e0_calls": 0,
                          "manifest_sha256": manifest_sha, "source_inputs_checked": checked,
                          "elapsed_seconds": time.monotonic() - started}))
        return 0
    batch.mkdir(parents=True, exist_ok=False)
    (batch / "inputs").mkdir()
    (batch / "cells").mkdir()
    for key, raw in plans.items():
        with (batch / "inputs" / f"{key}.json").open("xb") as f:
            f.write(raw)
    (batch / "manifest.json").write_bytes(manifest_path.read_bytes())
    jobs = manifest["jobs"]
    state = {"schema": "q3-same-plan-nol2-dispatch-v1", "manifest_sha256": manifest_sha,
             "controller_sha256": sha(Path(__file__).read_bytes()), "source_commit": SOURCE,
             "artifact_commit": ARTIFACT, "started_at": utc(), "finished_at": None,
             "status": "running", "budget": manifest["budget"], "attempted_e0_reservations": 0,
             "successful_e0_calls": 0, "solver_calls": 0, "p3_e0_calls": 0,
             "pilot_completed_at": None, "records": {}}
    write(batch / "dispatch.json", state)
    active = {}
    handles = {}
    launched_at = {}
    queue = list(jobs[4:])
    pilot_pending = set(f"{j['case_id']}-k{j['cores']}" for j in jobs[:4])
    deadline = started + 3600
    stopped_reason = None

    def launch(job):
        nonlocal stopped_reason
        if time.monotonic() >= deadline:
            stopped_reason = "global deadline before dispatch"
            return False
        if available_bytes() < 4 * 1024**3:
            return False
        key = f"{job['case_id']}-k{job['cores']}"
        folder = batch / "cells" / key
        folder.mkdir(exist_ok=False)
        plan = batch / "inputs" / f"{key}.json"
        result = folder / "result.json.gz"
        graph = ROOT / f"data/raw/a/official/data/case_{job['case_id']}.json"
        command = [sys.executable, "-B", "-m", "src.q3.oracle", str(graph), str(plan), "2", str(result)]
        record = {"case_id": job["case_id"], "cores": job["cores"], "status": "reserved",
                  "started_at": utc(), "finished_at": None,
                  "source_plan_sha256": job["plan"]["sha256"], "cache_result_sha256": job["cache_result"]["sha256"],
                  "cache_makespan": job["cache_makespan"], "graph_sha256": job["graph_sha256"],
                  "config_sha256": job["config_sha256"], "official_sha256": OFFICIAL,
                  "command": ["python", "-B", "-m", "src.q3.oracle",
                              f"data/raw/a/official/data/case_{job['case_id']}.json",
                              result.parent.parent.parent.relative_to(ROOT).as_posix() + f"/inputs/{key}.json",
                              "2", result.relative_to(ROOT).as_posix()],
                  "p2_e0_reserved": 1, "p2_e0_confirmed": 0, "retry": 0}
        state["attempted_e0_reservations"] += 1
        state["records"][key] = record
        write(batch / "dispatch.json", state)
        stdout = (folder / "stdout.json").open("xb")
        stderr = (folder / "stderr.txt").open("xb")
        try:
            proc = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                    start_new_session=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                                                                 "PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "1",
                                                                 "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
        except BaseException:
            stdout.close(); stderr.close()
            record["status"] = "spawn_failed"
            record["finished_at"] = utc()
            write(folder / "run.json", record)
            write(batch / "dispatch.json", state)
            stopped_reason = f"spawn failed: {key}"
            return False
        record["status"] = "running"
        record["pid"] = proc.pid
        write(batch / "dispatch.json", state)
        active[key] = proc
        handles[key] = (stdout, stderr)
        launched_at[key] = time.monotonic()
        return True

    for job in jobs[:4]:
        if not launch(job):
            stopped_reason = stopped_reason or "pilot memory floor blocked dispatch"
            break
    while active or queue:
        for key, proc in list(active.items()):
            elapsed = time.monotonic() - launched_at[key]
            if proc.poll() is None and elapsed < 90 and time.monotonic() < deadline:
                continue
            if proc.poll() is None:
                stopped_reason = f"per-cell/global timeout: {key}"
                stop_active({key: proc})
            active.pop(key)
            for handle in handles.pop(key):
                handle.close()
            record = state["records"][key]
            record.update(finished_at=utc(), wall_seconds=elapsed, exit_code=proc.returncode)
            result_path = batch / "cells" / key / "result.json.gz"
            try:
                if proc.returncode != 0 or not result_path.exists():
                    raise RuntimeError(f"official P2 process exit={proc.returncode}")
                result_raw = result_path.read_bytes()
                result = json.loads(gzip.decompress(result_raw))
                summary = read(batch / "cells" / key / "stdout.json")
                if result.get("scene") != "B" or result.get("num_cores") != record["cores"] \
                        or result.get("makespan") != summary.get("makespan") \
                        or type(result.get("makespan")) is not int or result["makespan"] <= 0 \
                        or result.get("data_movement_bytes") != summary.get("data_movement_bytes"):
                    raise RuntimeError("official P2 full result/summary identity differs")
                record.update(status="ok", p2_e0_confirmed=1, no_l2_makespan=result["makespan"],
                              cache_gain=result["makespan"] / record["cache_makespan"],
                              result_sha256=sha(result_raw),
                              data_movement_bytes=result["data_movement_bytes"],
                              summary_sha256=sha((batch / "cells" / key / "stdout.json").read_bytes()))
                state["successful_e0_calls"] += 1
            except BaseException as error:
                record["status"] = "failed" if elapsed < 90 else "timeout"
                record["error"] = f"{type(error).__name__}: {error}"
                stopped_reason = f"first abnormal result: {key}: {record['error']}"
            write(batch / "cells" / key / "run.json", record)
            write(batch / "dispatch.json", state)
            pilot_pending.discard(key)
        if not pilot_pending and state["pilot_completed_at"] is None and not stopped_reason:
            state["pilot_completed_at"] = utc()
            write(batch / "dispatch.json", state)
        if stopped_reason:
            break
        if state["pilot_completed_at"] is not None:
            while queue and len(active) < 4 and available_bytes() >= 4 * 1024**3:
                if not launch(queue.pop(0)):
                    break
        if time.monotonic() >= deadline:
            stopped_reason = "global 3600 second deadline"
            break
        time.sleep(.2)
    if stopped_reason:
        stop_active(active)
        for key, proc in active.items():
            for handle in handles[key]:
                handle.close()
            record = state["records"][key]
            record.update(status="interrupted_by_controller", finished_at=utc(), exit_code=proc.returncode)
            write(batch / "cells" / key / "run.json", record)
        state["status"] = "stopped"
    else:
        state["status"] = "complete" if len(state["records"]) == 500 and state["successful_e0_calls"] == 500 else "stopped"
    state.update(finished_at=utc(), stop_reason=stopped_reason, queued=len(queue),
                 elapsed_wall_seconds=time.monotonic() - started)
    write(batch / "dispatch.json", state)
    print(json.dumps({"status": state["status"], "successful_e0_calls": state["successful_e0_calls"],
                      "attempted_e0_reservations": state["attempted_e0_reservations"],
                      "elapsed_wall_seconds": state["elapsed_wall_seconds"], "stop_reason": stopped_reason}))
    return 0 if state["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
