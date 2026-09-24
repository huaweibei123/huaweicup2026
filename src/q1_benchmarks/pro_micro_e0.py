"""Six frozen synthetic Pro assertions checked against unmodified official P1 E0.

No real case, search, author-model execution, or benchmark-board export. Five
plans are reused byte-for-byte; only the specified C plan is encoded locally.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
RUNNER = Path(__file__).relative_to(ROOT).as_posix()
RESULT_ROOT = ROOT / "results/a/review/p1-pro-micro-e0-20260924"


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def artifact(path):
    p = Path(path)
    return {"path": p.relative_to(ROOT).as_posix(), "sha256": digest(p.read_bytes()), "bytes": p.stat().st_size}


def verify(manifest, head):
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Expected locked Python 3.12")
    if git("rev-parse", "HEAD").decode().strip() != head or git("diff", "--name-only", head).strip():
        raise RuntimeError("Runner HEAD changed or tracked tree is dirty")
    if (ROOT / RUNNER).read_bytes() != git("show", f"{head}:{RUNNER}"):
        raise RuntimeError("Unfrozen runner")
    material = ROOT / manifest["material_local_root"]
    for record in manifest["source_files"]:
        local = material / record["path"]
        if digest(local.read_bytes()) != record["sha256"]:
            raise RuntimeError(f"Material identity mismatch: {record['path']}")
    for record in manifest["official_files"]:
        local = ROOT / record["path"]
        if digest(local.read_bytes()) != record["sha256"]:
            raise RuntimeError(f"Official identity mismatch: {record['path']}")
    if digest((ROOT / "uv.lock").read_bytes()) != manifest["uv_lock_sha256"]:
        raise RuntimeError("Dependency lock changed")


def group_gone(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    return False


def e0(argv, folder, batch_deadline, on_start):
    start = time.perf_counter()
    deadline = min(start + 30, batch_deadline)
    # Reserve the last second inside the 30-second envelope for kill/wait.
    wait_budget = deadline - start - 1
    if wait_budget <= 0:
        raise TimeoutError("No remaining E0 and cleanup budget")
    receipt = {"argv": argv, "cwd": ".", "started_at": utc(), "pid": None,
               "process_group_id": None, "limit_including_cleanup_seconds": deadline - start,
               "execution_wait_budget_seconds": wait_budget, "cleanup_reserve_seconds": 1,
               "status": "starting", "cleanup_confirmed": False, "exit_code": None}
    write(folder / "e0-process.json", receipt)
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    child = None
    timed_out = False
    try:
        with (folder / "e0.stdout.txt").open("xb") as out, (folder / "e0.stderr.txt").open("xb") as err:
            child = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=out, stderr=err, start_new_session=True)
            receipt.update(pid=child.pid, process_group_id=child.pid, status="running")
            write(folder / "e0-process.json", receipt)
            on_start()
            try:
                child.wait(timeout=max(0, deadline - time.perf_counter() - 1))
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=max(0, deadline - time.perf_counter()))
    finally:
        if child is not None:
            if child.poll() is None or not group_gone(child.pid):
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                if child.poll() is None:
                    child.wait(timeout=max(0, deadline - time.perf_counter()))
            receipt.update(exit_code=child.returncode,
                           cleanup_confirmed=child.poll() is not None and group_gone(child.pid))
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt.update(finished_at=utc(), wall_seconds=time.perf_counter() - start,
                       timed_out=timed_out, user_cpu_seconds=after.ru_utime - before.ru_utime,
                       system_cpu_seconds=after.ru_stime - before.ru_stime,
                       child_peak_rss_bytes_cumulative=after.ru_maxrss,
                       rss_scope="Darwin RUSAGE_CHILDREN cumulative maximum, not isolated per process",
                       status="timeout" if timed_out else "ok" if receipt["exit_code"] == 0 else "failed")
        for name in ("stdout", "stderr"):
            path = folder / f"e0.{name}.txt"
            if path.exists():
                receipt[name] = artifact(path)
        receipt["text_derivation"] = "Unmodified raw subprocess stdout/stderr; relative argv paths"
        write(folder / "e0-process.json", receipt)
    if not receipt["cleanup_confirmed"]:
        raise RuntimeError("Cannot confirm all owned process-group members exited")
    return receipt


def overlap(result):
    total = 0
    for core in result["per_core_timeline"]:
        m = sorted((x["start"], x["end"]) for x in core["ops"] if x["pipe"] == "PIPE_M")
        v = sorted((x["start"], x["end"]) for x in core["ops"] if x["pipe"] == "PIPE_V")
        i = j = 0
        while i < len(m) and j < len(v):
            total += max(0, min(m[i][1], v[j][1]) - max(m[i][0], v[j][0]))
            if m[i][1] <= v[j][1]:
                i += 1
            else:
                j += 1
    return total


def run(batch, manifest):
    head = git("rev-parse", "HEAD").decode().strip()
    verify(manifest, head)
    authorization = read(batch / "EXECUTION_AUTHORIZATION.json")
    if (authorization.get("gate") != "AUTHORIZED" or authorization.get("runner_commit") != head
            or authorization.get("source_commit") != manifest["source_commit"]):
        raise RuntimeError("Waiting for root resource release and exact-run authorization")
    # Single-use gate is durable before any C encoding or E0 launch.
    with (batch / "STARTED.json").open("x") as f:
        json.dump({"started_at": utc(), "runner_commit": head, "controller_pid": os.getpid()}, f)
        f.write("\n")
    t0 = time.perf_counter()
    deadline = t0 + 240
    material = ROOT / manifest["material_local_root"]
    meta = {"run_id": batch.name, "synthetic": True, "formal_board_eligible": False,
            "started_at": utc(), "finished_at": None, "runner_commit": head,
            "source_commit": manifest["source_commit"], "manifest": artifact(batch / "manifest.json"),
            "execution_authorization": artifact(batch / "EXECUTION_AUTHORIZATION.json"),
            "runner": artifact(ROOT / RUNNER), "controller_pid": os.getpid(),
            "environment": {"platform": platform.platform(), "python": sys.version,
                "machine": platform.machine(), "cpu": subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"]).decode().strip(),
                "ram_bytes": int(subprocess.check_output(["sysctl", "-n", "hw.memsize"])),
                "workers": 1, "accelerator": "none", "uv_lock_sha256": manifest["uv_lock_sha256"],
                "concurrency": "Parent reports P2/P3 released; shared host, no exclusivity or controlled speed claim"},
            "calls": {"official_solver": 0, "prototype_solver_process": 0, "C_encode": 0,
                      "reused_author_plans": 0, "E0": 0, "E1": 0, "E2": 0},
            "status": "running", "gate": "RUNNING", "owned_processes_released": False,
            "rows": [{"id": cell["id"], "status": "not_run"} for cell in manifest["cells"]]}
    write(batch / "batch.json", meta)
    sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))
    from evaluation_validation import validate_graph, validate_task_order
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    current = None
    try:
        for index, cell in enumerate(manifest["cells"]):
            if time.perf_counter() >= deadline:
                raise TimeoutError("240-second batch deadline reached")
            verify(manifest, head)
            folder = batch / cell["id"]
            folder.mkdir()
            current = meta["rows"][index]
            current.update(status="preparing", started_at=utc())
            input_path = folder / "input.json"
            input_path.write_bytes((material / cell["input"]).read_bytes())
            plan_path = folder / "plan.json"
            if cell["plan_mode"] == "reuse_author_bytes":
                plan_path.write_bytes((material / cell["plan"]).read_bytes())
                meta["calls"]["reused_author_plans"] += 1
                current["solver_wall_seconds"] = None
                current["plan_origin"] = "Existing author bytes; no local constructor process"
            else:
                ts = time.perf_counter()
                spec = importlib.util.spec_from_file_location("frozen_pro_phase_cut", material / "p1_phase_cut.py")
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                graph = read(input_path)
                _, components, _, _, _ = module.recognize(graph)
                meta["calls"]["C_encode"] += 1
                write(batch / "batch.json", meta)
                plan = module.encode(components, graph["ops"], **cell["encode_parameters"])
                write(plan_path, plan)
                current["in_controller_generation_wall_seconds"] = time.perf_counter() - ts
                current["generation_scope"] = "Import fixed source, read graph, recognize, encode once, write plan; no child solver or model scoring"
                current["plan_origin"] = "Specified C encode parameters, one local encode"
            graph, plan = read(input_path), read(plan_path)
            if set(plan) != {"node_to_subgraph", "core_schedules"}:
                raise ValueError("Plan has unexpected top-level keys")
            validate_graph(graph)
            view = derive_multicore_plan(graph, plan)
            validate_task_order(view)
            if view["num_cores"] != 1:
                raise ValueError("Expected one simulated core")
            current.update(input=artifact(input_path), plan=artifact(plan_path),
                           task_count=len(view["subgraph_ids"]), legality="Official validate_graph/derive_multicore_plan/validate_task_order passed")
            write(folder / "run.json", current)
            write(batch / "batch.json", meta)
            argv = [".venv/bin/python", "-B", "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py",
                    input_path.relative_to(ROOT).as_posix(), plan_path.relative_to(ROOT).as_posix(),
                    "--config", "data/raw/a/official/data/config.txt", "--output", (folder / "result.json").relative_to(ROOT).as_posix(),
                    "--trace-output", (folder / "trace.json").relative_to(ROOT).as_posix(),
                    "--log-output", (folder / "official.log").relative_to(ROOT).as_posix()]
            def launched():
                meta["calls"]["E0"] += 1
                write(batch / "batch.json", meta)
            receipt = e0(argv, folder, deadline, launched)
            current["e0"] = receipt
            if receipt["status"] != "ok":
                raise RuntimeError(f"Official E0 {receipt['status']}: exit={receipt['exit_code']}")
            result = read(folder / "result.json")
            read(folder / "trace.json")
            for name in ("result.json", "trace.json", "official.log"):
                current[name] = artifact(folder / name)
            if result["scene"] != "A" or result["num_cores"] != 1 or not result["makespan"] > 0:
                raise ValueError("Official result identity/value mismatch")
            movement = result["data_movement_bytes"]
            observed = {"makespan_cycles": result["makespan"], **movement,
                        "M_V_overlap_cycles_sum_over_cores": overlap(result),
                        "memory_dependency_count": sum(x["memory_dependency_count"] for x in result["step3_by_task"].values())}
            checks = {key: {"expected": val, "actual": observed[key], "passed": observed[key] == val}
                      for key, val in cell["assertions"].items()}
            current.update(observed=observed, assertions=checks)
            current["status"] = "ok" if all(x["passed"] for x in checks.values()) else "model_assertion_failed"
            current["finished_at"] = utc()
            write(folder / "run.json", current)
            write(batch / "batch.json", meta)
            print(json.dumps({"id": cell["id"], "status": current["status"], "observed": observed,
                              "pid": receipt["pid"], "cleanup": receipt["cleanup_confirmed"]}), flush=True)
            if current["status"] != "ok":
                raise AssertionError("Explicit model assertion violated; stopping remaining cells")
        meta["status"] = "complete"
    except BaseException as exc:
        meta["status"] = "stopped"
        meta["error"] = f"{type(exc).__name__}: {exc}"
        (batch / "failure.txt").write_text(traceback.format_exc())
        if current is not None:
            if current["status"] not in ("ok", "model_assertion_failed"):
                current["status"] = "failed"
            current.update(error=meta["error"], finished_at=utc())
            write(batch / current["id"] / "run.json", current)
    finally:
        receipts = [read(p) for p in batch.glob("*/e0-process.json")]
        released = all(r["cleanup_confirmed"] and group_gone(r["pid"]) for r in receipts)
        meta.update(finished_at=utc(), wall_seconds=time.perf_counter() - t0,
                    gate="CLOSED", owned_processes_released=released,
                    statuses={status: sum(x["status"] == status for x in meta["rows"])
                              for status in sorted({x["status"] for x in meta["rows"]})})
        write(batch / "batch.json", meta)
        write(batch / "resource-release.json", {"checked_at": utc(), "E0_calls": meta["calls"]["E0"],
            "all_owned_child_groups_exited": released, "pids": [r["pid"] for r in receipts], "gate": "CLOSED"})
        print(json.dumps({k: meta[k] for k in ("status", "calls", "statuses", "owned_processes_released", "wall_seconds")}), flush=True)
    return 0 if meta["status"] == "complete" and meta["owned_processes_released"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "run"))
    parser.add_argument("run_id")
    args = parser.parse_args()
    if Path(args.run_id).name != args.run_id:
        raise ValueError("Invalid run id")
    batch = RESULT_ROOT / args.run_id
    manifest = read(batch / "manifest.json")
    head = git("rev-parse", "HEAD").decode().strip()
    if args.action == "preflight":
        verify(manifest, head)
        print(json.dumps({"runner_commit": head, "cells": len(manifest["cells"]), "scoring_calls": 0, "preflight": "passed"}))
        return 0
    return run(batch, manifest)


if __name__ == "__main__":
    raise SystemExit(main())
