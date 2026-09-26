"""Pinned P1/P2/P3 multi-core benchmark; preserve every failed or timed-out cell.

Existing solvers run unchanged in separate checkouts/snapshots. This controller
does not invent plans, select old per-case winners, or retry failed cells.
Use the same output directory to resume missing cells without rerunning receipts.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data/raw/a/official"
VERSIONS = {
    "P1": "4dff90ef699fd51845cf482951e8477066f5f566",
    "P2": "0b58c123cccf02fc993b741d79dcd8511e4dd38f",
    "P3": "a4e7ee13310d693ec4fb5cc236669ceb3b172d1f",
    "E1": "5bfe53a29c1ba05167239f51ea937e602f7f85b4",
}
ALGORITHMS = {"P1": "q1_search_32_seed0", "P2": "q2_contiguous_baseline",
              "P3": "q3_structure_selected_online"}
FIELDS = ["case", "problem", "cores", "algorithm", "status", "makespan_cycles",
          "singlecore_cycles", "multicore_speedup", "solver_wall_seconds", "e0_wall_seconds",
          "data_movement_bytes", "cache_hit_rate", "no_cache_makespan_cycles", "cache_speedup",
          "error", "source_commit", "result_path"]
PRINT_LOCK = threading.Lock()
STOP = threading.Event()
LAUNCH_LOCK = threading.Lock()
HARNESS_SHA = None


class FatalRunStop(RuntimeError):
    """No additional processes may start after uncertain cleanup."""


def check_running():
    if STOP.is_set():
        raise FatalRunStop("benchmark stopped after a fatal worker error")


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1 << 20), b""):
            value.update(part)
    return value.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def utc():
    return datetime.now(timezone.utc).isoformat()


def portable(value, roots):
    text = str(value)
    for name, root in sorted(roots.items(), key=lambda item: -len(str(item[1]))):
        text = text.replace(str(root), f"<{name}>")
    return text


def run_process(argv, cwd, folder, limit, roots):
    check_running()
    folder.mkdir(parents=True, exist_ok=False)
    receipt = {"argv": [portable(v, roots) for v in argv], "cwd": portable(cwd, roots),
               "started_at": utc(), "timeout_seconds": limit, "status": "reserved",
               "harness_sha256": HARNESS_SHA}
    save(folder / "process.json", receipt)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0",
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    started = time.perf_counter()
    try:
        with (folder / "stdout.txt").open("wb") as stdout, (folder / "stderr.txt").open("wb") as stderr:
            with LAUNCH_LOCK:
                check_running()
                process = subprocess.Popen([str(v) for v in argv], cwd=cwd, env=env, stdout=stdout, stderr=stderr,
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                           start_new_session=os.name != "nt")
            receipt["pid"] = process.pid
            save(folder / "process.json", receipt)
            try:
                receipt["returncode"] = process.wait(timeout=limit)
                receipt["status"] = "ok" if process.returncode == 0 else "error"
            except subprocess.TimeoutExpired:
                receipt["status"] = "timeout"
                try:
                    # Only this newly created process tree / process group.
                    if os.name == "nt":
                        cleanup = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                                 capture_output=True, timeout=15)
                        receipt["cleanup_returncode"] = cleanup.returncode
                        if cleanup.returncode != 0:
                            raise RuntimeError("taskkill did not confirm process-tree cleanup")
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
                    receipt["returncode"] = process.returncode
                    receipt["cleanup_confirmed"] = True
                except Exception as error:
                    with LAUNCH_LOCK:
                        STOP.set()
                    receipt.update(status="fatal_cleanup", cleanup_unconfirmed=True,
                                   cleanup_error=portable(f"{type(error).__name__}: {error}", roots))
                    raise FatalRunStop("child process cleanup could not be confirmed") from error
    finally:
        receipt.update(wall_seconds=time.perf_counter() - started, finished_at=utc())
        save(folder / "process.json", receipt)
    return receipt


def compress_generated(path):
    """Losslessly compress our new large CLI artifacts; retain raw-byte hash."""
    if not path.exists():
        return None
    expected = sha(path)
    target = path.with_suffix(path.suffix + ".gz")
    with path.open("rb") as source, target.open("xb") as output:
        with gzip.GzipFile(filename="", fileobj=output, mode="wb", compresslevel=1, mtime=0) as zipped:
            shutil.copyfileobj(source, zipped, 1 << 20)
    actual = hashlib.sha256()
    with gzip.open(target, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            actual.update(chunk)
    if actual.hexdigest() != expected:
        raise IOError("compressed evidence differs from original bytes")
    path.unlink()  # Only this run's generated file, exactly recoverable from gzip.
    return {"raw_sha256": expected, "gzip_sha256": sha(target), "file": target.name}


def validate_roots(roots):
    manifest = read(ROOT / "docs/a/source-manifest.json")
    identities = {}
    for role in ("P1", "P2", "P3", "E1"):
        root = roots[role]
        if (root / "snapshot.json").exists():
            identity = read(root / "snapshot.json")
            actual = identity["commit"]
            for name, data in identity["files"].items():
                if sha(root / name) != data["sha256"]:
                    raise ValueError(f"changed downloaded source {role}:{name}")
        else:
            actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root):
                raise ValueError(f"tracked source checkout changed: {role}")
        if actual != VERSIONS[role]:
            raise ValueError(f"unexpected source commit for {role}")
        for record in manifest["files"]:
            name = record["path"]
            if name.startswith("code/") or name == "data/config.txt":
                if sha(root / "data/raw/a/official" / name) != record["sha256"]:
                    raise ValueError(f"official source/config mismatch: {role}:{name}")
        package = "eval_exact" if role == "E1" else role.lower().replace("p", "q")
        identities[role] = {"commit": actual, "source_sha256": {
            p.relative_to(root).as_posix(): sha(p) for p in sorted((root / "src" / package).glob("*.py"))}}
    return identities


def official_command(mode, graph, output, plan=None):
    argv = [sys.executable, "-B", ROOT / "src/benchmarks/p123_evaluate.py", "--mode", mode,
            "--graph", graph, "--config", OFFICIAL / "data/config.txt", "--official-root", OFFICIAL,
            "--manifest", ROOT / "docs/a/source-manifest.json", "--output-dir", output]
    if plan is not None:
        argv += ["--plan", plan]
    return argv


def baseline(case, out, roots):
    check_running()
    folder = out / "baselines" / case
    summary_path = folder / "e0/summary.json"
    if summary_path.exists():
        return read(summary_path)
    if folder.exists():
        raise RuntimeError(f"unfinished baseline {case}: inspect before retry")
    receipt = run_process(official_command("single", OFFICIAL / f"data/case_{case}.json", folder / "e0"),
                          ROOT, folder / "process", 180, roots)
    if not summary_path.exists():
        save(summary_path, {"status": receipt["status"], "makespan_cycles": None,
                            "official_calls": "unknown; reserve one", "graph": f"case_{case}.json"})
    return read(summary_path)


def cell(problem, case, cores, out, roots, single):
    check_running()
    folder = out / "cells" / problem / case / f"k{cores}"
    receipt_path = folder / "cell.json"
    if receipt_path.exists():
        return read(receipt_path)
    if folder.exists():
        raise RuntimeError(f"unfinished cell {problem}/{case}/{cores}: inspect before retry")
    folder.mkdir(parents=True)
    row = dict.fromkeys(FIELDS)
    row.update(case=case, problem=problem, cores=cores, algorithm=ALGORITHMS[problem], status="error",
               source_commit=VERSIONS[problem], singlecore_cycles=single.get("makespan_cycles"), error="")
    evidence = {"started_at": utc(), "row": row, "processes": [], "evidence": {},
                "harness_sha256": HARNESS_SHA}
    graph = OFFICIAL / f"data/case_{case}.json"
    plan = folder / "plan.json"
    started = time.perf_counter()
    try:
        if problem == "P1":
            graph = roots["P1"] / f"data/raw/a/official/data/case_{case}.json"
            if sha(graph) != sha(OFFICIAL / f"data/case_{case}.json"):
                raise ValueError("P1 graph differs from frozen shared input")
            command = [sys.executable, "-B", roots["P1"] / "src/q1/search.py", "search", graph,
                       folder / "search", "--evaluator-root", roots["E1"], "--cores", str(cores),
                       "--seed", "0", "--candidates", "32", "--budget", "60",
                       "--candidate-timeout", "5", "--confirm-timeout", "30"]
            process = run_process(command, roots["P1"], folder / "solver", 150, roots)
            evidence["processes"].append(process)
            row["solver_wall_seconds"] = process["wall_seconds"]
            if process["status"] != "ok":
                row["status"] = process["status"]
                raise RuntimeError("P1 solver process failed; inspect preserved stderr")
            summary = read(folder / "search/summary.json")
            evidence["p1_search"] = {k: summary[k] for k in (
                "attempts", "evaluations", "search_seconds", "e0_best", "e0_baseline",
                "e0_confirms_selected_makespan", "parameters")}
            if not summary["e0_confirms_selected_makespan"]:
                raise RuntimeError("P1 exact incumbent was not confirmed by official E0")
            result_path = folder / "search/e0_best/result.json"
            result = read(result_path)
            shutil.copy2(folder / "search/best_plan.json", plan)
            for label in ("e0_best", "e0_baseline"):
                for name in ("result.json", "trace.json"):
                    target = folder / "search" / label / name
                    evidence["evidence"][f"{label}/{name}"] = compress_generated(target)
            row["result_path"] = (result_path.with_suffix(".json.gz")).relative_to(out).as_posix()
            row["e0_wall_seconds"] = summary["e0_best"]["seconds"]
            evidence["timing_note"] = "P1 solver wall includes online E1 and both final/stub E0 CLI confirmations; e0_wall is an included subcomponent, do not add it again"
        elif problem == "P2":
            command = [sys.executable, "-B", "-m", "src.q2.construct", graph,
                       "--cores", str(cores), "--output", plan]
            process = run_process(command, roots["P2"], folder / "solver", 120, roots)
            evidence["processes"].append(process)
            row["solver_wall_seconds"] = process["wall_seconds"]
            if process["status"] != "ok":
                row["status"] = process["status"]
                raise RuntimeError("P2 construction failed; inspect preserved stderr")
            checked = run_process(official_command("P2", graph, folder / "e0", plan), ROOT,
                                  folder / "e0_process", 180, roots)
            evidence["processes"].append(checked)
            row["e0_wall_seconds"] = checked["wall_seconds"]
            if checked["status"] != "ok":
                row["status"] = checked["status"]
                raise RuntimeError("P2 official evaluation failed; inspect preserved evidence")
            summary = read(folder / "e0/summary.json")
            result = {"makespan": summary["makespan_cycles"], "data_movement_bytes": summary["data_movement_bytes"]}
            row["result_path"] = (folder / "e0/result.json.gz").relative_to(out).as_posix()
            evidence["timing_note"] = "P2 construction wall excludes the separately listed final official evaluation"
        else:
            command = [sys.executable, "-B", "-m", "src.q3.solve", graph,
                       "--cores", str(cores), "-o", plan, "--evidence", folder / "online"]
            process = run_process(command, roots["P3"], folder / "solver", 180, roots)
            evidence["processes"].append(process)
            row["solver_wall_seconds"] = process["wall_seconds"]
            if process["status"] != "ok":
                row["status"] = process["status"]
                raise RuntimeError("P3 online solver failed; inspect preserved stderr")
            summary = read(folder / "online/receipt.json")
            with gzip.open(folder / "online/result.json.gz", "rt", encoding="utf-8") as stream:
                result = json.load(stream)
            if result["makespan"] != summary["makespan"] or sha(plan) != summary["plan_sha256"]:
                raise ValueError("P3 saved result/plan receipt mismatch")
            if sha(folder / "online/result.json.gz") != summary["result_sha256"]:
                raise ValueError("P3 compressed result identity mismatch")
            row["e0_wall_seconds"] = summary["official_import_config_evaluate_seconds"]
            row["cache_hit_rate"] = result["cache_stats"]["hit_rate"]
            row["result_path"] = (folder / "online/result.json.gz").relative_to(out).as_posix()
            evidence["p3_strategy"] = summary["strategy"]
            checked = run_process(official_command("P2", graph, folder / "no_cache", plan), ROOT,
                                  folder / "no_cache_process", 180, roots)
            evidence["processes"].append(checked)
            if checked["status"] == "ok":
                no_cache = read(folder / "no_cache/summary.json")
                row["no_cache_makespan_cycles"] = no_cache["makespan_cycles"]
                row["cache_speedup"] = no_cache["makespan_cycles"] / result["makespan"]
            else:
                evidence["cache_pair_error"] = checked["status"]
            evidence["timing_note"] = "P3 solver wall includes its one online P3 E0; e0_wall is an included component. Paired P2 no-cache evaluation is separate experimental work."
        row.update(makespan_cycles=result["makespan"],
                   data_movement_bytes=json.dumps(result["data_movement_bytes"], separators=(",", ":")))
        if single.get("status") == "ok":
            row["multicore_speedup"] = single["makespan_cycles"] / result["makespan"]
        evidence["plan_sha256"] = sha(plan)
        row["status"] = "ok"
    except FatalRunStop as error:
        row.update(status="fatal_cleanup", error=str(error))
        raise
    except Exception as error:
        row["error"] = portable(f"{type(error).__name__}: {error}", roots)
        if row["status"] == "ok":
            row["status"] = "error"
    finally:
        if row["status"] != "ok":
            for key in ("makespan_cycles", "multicore_speedup", "cache_speedup"):
                row[key] = None
        evidence.update(finished_at=utc(), cell_wall_seconds=time.perf_counter() - started)
        save(receipt_path, evidence)
    return evidence


def completed_jobs(function, jobs, workers):
    """Cancel pending work on fatal errors; active work retains its deadlines."""
    pool = ThreadPoolExecutor(max_workers=workers)
    futures = {}
    try:
        futures = {pool.submit(function, *job): job for job in jobs}
        for future in as_completed(futures):
            yield futures[future], future.result()
    except BaseException:
        with LAUNCH_LOCK:
            STOP.set()
        for future in futures:
            future.cancel()
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


def pin_protocol(out, protocol, revision_note):
    """Keep the original protocol immutable; explicitly record harness-only fixes."""
    protocol_path = out / "protocol.json"
    if not protocol_path.exists():
        save(protocol_path, protocol)
    original = read(protocol_path)
    comparable = json.loads(json.dumps(protocol))
    comparable["source_sha256"]["p123_run.py"] = original["source_sha256"]["p123_run.py"]
    if comparable != original:
        raise ValueError("experimental protocol changed: use a new run")
    original_hash = original["source_sha256"]["p123_run.py"]
    harness = out / "harness"
    harness.mkdir(exist_ok=True)
    initial = harness / f"p123_run-{original_hash}.py"
    if original_hash != HARNESS_SHA and (not initial.exists() or sha(initial) != original_hash):
        raise ValueError("archive original controller source before any revision")
    ledger_path = harness / "revisions.json"
    ledger = read(ledger_path) if ledger_path.exists() else {
        "original_protocol_sha256": sha(protocol_path), "revisions": [
            {"sha256": original_hash, "note": "original preflight controller"}]}
    if ledger["original_protocol_sha256"] != sha(protocol_path):
        raise ValueError("original protocol bytes changed")
    if HARNESS_SHA not in {item["sha256"] for item in ledger["revisions"]}:
        if not revision_note:
            raise ValueError("explicit --harness-revision-note required for a new controller revision")
        ledger["revisions"].append({"sha256": HARNESS_SHA, "recorded_at": utc(), "note": revision_note})
    snapshot = harness / f"p123_run-{HARNESS_SHA}.py"
    if not snapshot.exists():
        shutil.copy2(Path(__file__), snapshot)
    if sha(snapshot) != HARNESS_SHA:
        raise ValueError("controller snapshot hash mismatch")
    save(ledger_path, ledger)


def aggregate(out):
    receipts = [read(path) for path in sorted((out / "cells").glob("*/*/k*/cell.json"))]
    baseline_rows = []
    for path in sorted((out / "baselines").glob("*/e0/summary.json")):
        baseline_result = read(path)
        case = path.parent.parent.name
        for problem in ("P1", "P2"):
            row = dict.fromkeys(FIELDS)
            row.update(case=case, problem=problem, cores=1, algorithm="official_singlecore_baseline",
                       status=baseline_result["status"], makespan_cycles=baseline_result.get("makespan_cycles"),
                       singlecore_cycles=baseline_result.get("makespan_cycles"),
                       multicore_speedup=1.0 if baseline_result["status"] == "ok" else None,
                       source_commit="f27ef37bb76dcf556f35d3f2328e405d92241d9c",
                       result_path=(path.parent / "result.json.gz").relative_to(out).as_posix(),
                       data_movement_bytes=json.dumps(baseline_result.get("data_movement_bytes")), error="")
            baseline_rows.append(row)
    path = out / "comparison.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(sorted([*baseline_rows, *(item["row"] for item in receipts)],
                               key=lambda row: (row["problem"], row["case"], row["cores"])))
    counts = {p: {"ok": 0, "failed": 0} for p in ("P1", "P2", "P3")}
    for item in receipts:
        row = item["row"]
        counts[row["problem"]]["ok" if row["status"] == "ok" else "failed"] += 1
    save(out / "progress.json", {"updated_at": utc(), "completed_cells": len(receipts), "counts": counts,
                                  "full_target_cells": {"P1": 400, "P2": 400, "P3": 500}})
    return counts


def main():
    global HARNESS_SHA
    HARNESS_SHA = sha(Path(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("p1-root", "p2-root", "p3-root", "e1-root", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--cases", default="all")
    parser.add_argument("--cores", default="2,3,4,5")
    parser.add_argument("--problems", default="P1,P2,P3")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--include-p3-one", action="store_true")
    parser.add_argument("--harness-revision-note")
    args = parser.parse_args()
    if args.workers not in (1, 2):
        parser.error("only one or two concurrent benchmark units are allowed")
    cases = [f"{i:03d}" for i in range(1, 101)] if args.cases == "all" else args.cases.split(",")
    cores = [int(k) for k in args.cores.split(",")]
    problems = args.problems.split(",")
    if any(c not in {f"{i:03d}" for i in range(1, 101)} for c in cases) or any(k not in range(2, 6) for k in cores):
        parser.error("cases must be 001..100 and multicore columns 2..5")
    if any(p not in ALGORITHMS for p in problems):
        parser.error("unknown problem")
    out = args.output_dir.resolve()
    roots = {"P1": args.p1_root.resolve(), "P2": args.p2_root.resolve(), "P3": args.p3_root.resolve(),
             "E1": args.e1_root.resolve(), "BENCHMARK": ROOT, "OUTPUT": out,
             "PYTHON": Path(sys.executable)}
    identity = validate_roots(roots)
    out.mkdir(parents=True, exist_ok=True)
    protocol = {"versions": identity, "algorithms": ALGORITHMS, "python": sys.version,
                "platform": platform.platform(), "workers": args.workers,
                "official_source_manifest_sha256": sha(ROOT / "docs/a/source-manifest.json"),
                "uv_lock_sha256": sha(ROOT / "uv.lock"),
                "source_sha256": {name: sha(ROOT / "src/benchmarks" / name)
                                  for name in ("p123_run.py", "p123_evaluate.py")},
                "P1_parameters": {"candidates": 32, "budget": 60, "candidate_timeout": 5,
                                  "confirm_timeout": 30, "seed": 0},
                "full_scope": "100 baselines; P1/P2 2..5 cores; P3 1..5 cores with same-plan P2 pairs",
                "full_upper_call_reservations": {"E1": 12800, "E0": 2300},
                "resource_note": "At most two active benchmark units; Q1 has its own bounded proposal/evaluator children. No measured RSS or hard memory guarantee is claimed. Timeouts are wall deadlines plus explicit cleanup, not hard real-time.",
                "missing_policy": "failed/timed-out cells remain NA, no automatic reruns; preflight cells retained",
                "metric": "P1/P2 mean of per-case official_single/multicore cycles; P3 cache ratio same-plan P2/P3"}
    pin_protocol(out, protocol, args.harness_revision_note)
    invocation = {"started_at": utc(), "harness_sha256": HARNESS_SHA,
                  "cases": cases, "cores": cores, "problems": problems,
                  "include_p3_one": args.include_p3_one, "workers": args.workers,
                  "status": "running"}
    invocation_path = out / "invocations" / f"{uuid.uuid4().hex}.json"
    save(invocation_path, invocation)
    singles = {}
    try:
        for job, result in completed_jobs(baseline, [(c, out, roots) for c in cases], args.workers):
            case = job[0]
            singles[case] = result
            if len(singles) % 10 == 0 or len(cases) < 10:
                print(json.dumps({"stage": "baseline", "completed": len(singles), "case": case,
                                  "status": singles[case]["status"]}), flush=True)
        jobs = [(p, c, k, out, roots, singles[c]) for c in cases for p in problems
                for k in ([1, *cores] if p == "P3" and args.include_p3_one else cores)]
        for completed, (_, item) in enumerate(completed_jobs(cell, jobs, args.workers), 1):
            if completed % 10 == 0 or len(jobs) < 10 or item["row"]["status"] != "ok":
                counts = aggregate(out)
                print(json.dumps({"stage": "cells", "completed_in_invocation": completed,
                                  "total_in_invocation": len(jobs), "last": {k: item["row"][k]
                                      for k in ("problem", "case", "cores", "status", "makespan_cycles")},
                                  "counts": counts}), flush=True)
        invocation["status"] = "complete"
    except BaseException as error:
        invocation.update(status="stopped", error=portable(f"{type(error).__name__}: {error}", roots))
        raise
    finally:
        invocation.update(finished_at=utc(), counts=aggregate(out))
        save(invocation_path, invocation)
    print(json.dumps({"finished_at": utc(), "counts": invocation["counts"]}), flush=True)


if __name__ == "__main__":
    main()
