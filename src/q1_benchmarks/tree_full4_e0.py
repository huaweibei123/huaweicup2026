"""Frozen 99-cell P1 development batch; one process at a time, no retry.

`run RUN_ID` starts at most 99 constructors and 99 independent official E0 calls.
`export RUN_ID` only reads existing evidence and exports board-submission-v1.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data/raw/a/official"
RESULT_ROOT = ROOT / "results/a/q1-tree-full4-20260924"
SOLVER = "409886dd4b17b589643d3f5a13af9e94a9783d73"
OLD = "6664a63adc3464d28d1f835d907cdeaea23e6b35"
OLD_FEED = "results/a/local-p1-fixed64-20260924/20260924T1337Z-s59ee/board-feed-full500.json"
CELLS = [(f"{i:03d}", 4) for i in range(1, 101) if i != 2]
SOLVER_PATH = "src/q1/tree_frontier.py"
RUNNER_PATH = "src/q1_benchmarks/tree_full4_e0.py"
REPO = "huaweibei123/huaweicup2026"
SESSION = "nikolastarx/s-6607cb2735304751b36662035723372b"
TASK = "https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5815486806"


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def read(path):
    return json.loads(Path(path).read_text())


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def artifact(path):
    return {"path": Path(path).relative_to(ROOT).as_posix(), "sha256": sha(path)}


def verify():
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Use locked Python 3.12")
    head = git("rev-parse", "HEAD").decode().strip()
    if git("diff", "--name-only", head).strip():
        raise RuntimeError("Tracked worktree differs from frozen runner commit")
    for path, commit in ((SOLVER_PATH, SOLVER), ("src/q1/component_pack.py", SOLVER), (RUNNER_PATH, head)):
        if (ROOT / path).read_bytes() != git("show", f"{commit}:{path}"):
            raise RuntimeError(f"Unfrozen source: {path}")
    manifest = read(ROOT / "docs/a/source-manifest.json")
    files = {x["path"]: x for x in manifest["files"]}
    for path, record in files.items():
        if path.startswith("code/") or path == "data/config.txt":
            if sha(OFFICIAL / path) != record["sha256"]:
                raise RuntimeError(f"Official bytes changed: {path}")
    code_hash = digest("".join(f"{p}\t{files[p]['sha256']}\n" for p in sorted(files) if p.startswith("code/")).encode())
    if code_hash != manifest["official_code_hash"]:
        raise RuntimeError("Official manifest code hash mismatch")
    if sha(ROOT / manifest["case_archive"]["path"]) != manifest["case_archive"]["sha256"]:
        raise RuntimeError("Archive hash mismatch")
    return head, manifest, files


def process(argv, folder, name, timeout, input_root):
    started = utc()
    t0 = time.perf_counter()
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    stdout_path, stderr_path = folder / f"{name}.stdout.txt", folder / f"{name}.stderr.txt"
    cleanup = True
    with stdout_path.open("xb") as out, stderr_path.open("xb") as err:
        child = subprocess.Popen([str(x) for x in argv], cwd=ROOT, env=env, stdout=out, stderr=err, start_new_session=True)
        status = "ok"
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            status = "timeout"
            os.killpg(child.pid, signal.SIGKILL)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cleanup = False
                raise RuntimeError("Cannot confirm child cleanup")
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=10)
    elapsed = time.perf_counter() - t0
    def public(value):
        return str(value).replace(str(input_root), "<verified-inputs>").replace(str(ROOT), ".")
    # Preserve process text except personal path substitution; receipt records it.
    for p in (stdout_path, stderr_path):
        p.write_text(public(p.read_text(errors="replace")))
    return {"argv": [public(x) for x in argv], "cwd": ".", "started_at": started,
            "finished_at": utc(), "wall_seconds": elapsed, "timeout_seconds": timeout,
            "exit_code": child.returncode, "cleanup_confirmed": cleanup,
            "status": status if status == "timeout" else ("ok" if child.returncode == 0 else "failed"),
            "stdout": artifact(stdout_path), "stderr": artifact(stderr_path),
            "log_derivation": "UTF-8 child output with workspace and temporary input root replaced by public labels"}


def compress(path):
    raw = path.read_bytes()
    packed = gzip.compress(raw, compresslevel=6, mtime=0)
    if gzip.decompress(packed) != raw:
        raise RuntimeError("gzip roundtrip mismatch")
    target = path.with_suffix(path.suffix + ".gz")
    target.write_bytes(packed)
    path.unlink()
    return artifact(target)


def environment():
    return {"os": platform.platform(), "cpu": subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"]).decode().strip(),
            "gpu": "none (no accelerator used)", "ram_bytes": int(subprocess.check_output(["sysctl", "-n", "hw.memsize"])),
            "python": sys.version, "dependencies": f"uv.lock sha256={sha(ROOT / 'uv.lock')}; uv sync --locked before batch",
            "threads": None, "workers": 1, "peak_rss_bytes": None}


def run(batch):
    deadline = time.perf_counter() + 1200
    def remaining(limit):
        left = deadline - time.perf_counter()
        if left <= 0:
            raise TimeoutError("1200-second batch deadline reached")
        return min(limit, left)
    head, manifest, files = verify()
    batch.mkdir(parents=True, exist_ok=False)  # Existing batch can never restart.
    meta = {"run_id": batch.name, "solver_commit": SOLVER, "runner_commit": head,
            "official_commit": SOLVER, "official_code_hash": manifest["official_code_hash"],
            "config_sha256": sha(OFFICIAL / "data/config.txt"), "runner_sha256": sha(__file__),
            "input_archive_sha256": manifest["case_archive"]["sha256"], "environment": environment(),
            "started_at": utc(), "finished_at": None, "cells": CELLS, "maximum_calls": {"solver": 99, "E0": 99, "E1": 0, "E2": 0},
            "runner_argv": ["python", "-B", RUNNER_PATH, "run", batch.name],
            "cold_start_definition": "Fresh interpreter process per cell; OS filesystem cache not flushed",
            "concurrency_context": "P2 and Q3 scoring reported stopped before this batch; no exclusive-host reservation or controlled timing claim",
            "stop_policy": "one active cell; stop at first unexpected failure; no retry; constructor 30s, E0 60s",
            "status": "running", "input_preparation_wall_seconds": None, "batch_timeout_seconds": 1200,
            "reused_case002": {"source_commit": "bf65aaca608e0c41493eb29c8482712c0a8d2c73", "feed": "results/a/q1-tree-fine-20260924/20260924T1422Z-treefine1/board-feed.json", "scope": "Original attempt only; excluded from this 99-cell execution and feed"}}
    write(batch / "batch.json", meta)
    stopped = None
    with tempfile.TemporaryDirectory(prefix="q1-tree-input-") as tmp:
        inputs = Path(tmp)
        t0 = time.perf_counter()
        with zipfile.ZipFile(ROOT / manifest["case_archive"]["path"]) as archive:
            for case in sorted({c for c, _ in CELLS}):
                name = f"data/case_{case}.json"
                raw = archive.read(name)
                if digest(raw) != files[name]["sha256"]:
                    raise RuntimeError(f"Input mismatch: {case}")
                (inputs / f"case_{case}.json").write_bytes(raw)
        meta["input_preparation_wall_seconds"] = time.perf_counter() - t0
        for case, cores in CELLS:
            folder = batch / "cells" / case / f"k{cores}"
            folder.mkdir(parents=True)
            r = {"case_id": case, "cores": cores, "status": "not_run", "started_at": None, "finished_at": None,
                 "graph_sha256": files[f"data/case_{case}.json"]["sha256"], "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
                 "failure": None, "artifacts": {}, "makespan_cycles": None}
            if time.perf_counter() >= deadline and stopped is None:
                stopped = "1200-second batch deadline reached before next cell"
            if stopped:
                r["not_run_reason"] = stopped
                write(folder / "run.json", r)
                continue
            r["started_at"] = utc()
            graph = inputs / f"case_{case}.json"
            plan, result, diagnostics = folder / f"case_{case}_multicore_res.json", folder / "result.json", folder / "diagnostics.json"
            stage = "solver"
            try:
                solver_timeout = remaining(30)
                r["calls"]["solver"] = 1
                r["solver"] = process([sys.executable, "-B", SOLVER_PATH, graph, "--output", plan, "--cores", cores, "--packet-factor", "4", "--diagnostics", diagnostics], folder, "solver", solver_timeout, inputs)
                if r["solver"]["status"] != "ok":
                    raise RuntimeError(f"Constructor {r['solver']['status']}")
                if set(read(plan)) != {"node_to_subgraph", "core_schedules"}:
                    raise RuntimeError("Unexpected plan keys")
                r["artifacts"]["plan"] = artifact(plan)
                r["artifacts"]["diagnostics"] = artifact(diagnostics)
                r["diagnostics"] = read(diagnostics)
                r["plan_sha256"] = sha(plan)
                stage = "E0"
                e0_timeout = remaining(60)
                r["calls"]["E0"] = 1
                r["evaluation"] = process([sys.executable, "-B", OFFICIAL / "code/multicore_cut_evaluate_problem_1.py", graph,
                    plan, "--config", OFFICIAL / "data/config.txt", "--output", result,
                    "--trace-output", folder / "trace.json", "--log-output", folder / "official.log"], folder, "E0", e0_timeout, inputs)
                if r["evaluation"]["status"] != "ok":
                    raise RuntimeError(f"E0 {r['evaluation']['status']}")
                obj = read(result)
                if obj.get("scene") != "A" or obj.get("num_cores") != cores or type(obj.get("makespan")) not in (int, float) or obj["makespan"] <= 0:
                    raise RuntimeError("Result identity or Makespan invalid")
                r["makespan_cycles"] = obj["makespan"]
                r["data_movement_bytes"] = obj["data_movement_bytes"]
                r["artifacts"]["result"] = compress(result)
                r["artifacts"]["trace"] = compress(folder / "trace.json")
                r["artifacts"]["log"] = artifact(folder / "official.log")
                r["status"] = "ok"
            except Exception as error:
                process_record = r.get("evaluation" if stage == "E0" else "solver", {})
                r["status"] = "timeout" if isinstance(error, TimeoutError) or process_record.get("status") == "timeout" else "failed"
                r["failure"] = {"stage": stage, "reason": f"{type(error).__name__}: {error}", "exit_code": process_record.get("exit_code"), "elapsed_seconds": process_record.get("wall_seconds")}
                stopped = f"Stopped after {case}/k{cores}: {r['failure']['reason']}"
            finally:
                r["finished_at"] = utc()
                write(folder / "run.json", r)
                print(json.dumps({"case": case, "cores": cores, "status": r["status"], "makespan": r["makespan_cycles"]}), flush=True)
    meta.update(finished_at=utc(), status="stopped" if stopped else "complete", stop_reason=stopped or "all 99 frozen cells complete")
    meta["actual_calls"] = {key: sum(read(batch / "cells" / c / f"k{k}" / "run.json")["calls"][key] for c, k in CELLS) for key in ("solver", "E0", "E1", "E2")}
    write(batch / "batch.json", meta)
    return 1 if stopped else 0


def source(commit, path, entrypoint):
    return {"repo": REPO, "commit": commit, "path": path, "entrypoint": entrypoint}


def export(batch):
    meta = read(batch / "batch.json")
    old = json.loads(git("show", f"{OLD}:{OLD_FEED}"))
    records, comparisons, original_rows = [], [], []
    for case, cores in CELLS:
        folder = batch / "cells" / case / f"k{cores}"
        r = read(folder / "run.json")
        previous = next(x for x in old["records"] if x["case_id"] == case and x["cores"] == cores)
        prior_bytes = git("show", f"{OLD}:{previous['artifacts']['result']['path']}")
        if digest(prior_bytes) != previous["artifacts"]["result"]["sha256"]:
            raise RuntimeError("Historical fixed64 result hash mismatch")
        if json.loads(gzip.decompress(prior_bytes))["makespan"] != previous["metrics"]["makespan_cycles"]:
            raise RuntimeError("Historical fixed64 feed/result Makespan mismatch")
        original_rows.append(previous)
        b = previous["baseline"]
        raw = git("show", f"{OLD}:{b['result']['path']}")
        if digest(raw) != b["result"]["sha256"]:
            raise RuntimeError("Existing baseline hash mismatch")
        bp = batch / "references" / f"singlecore-{case}.json.gz"
        bp.parent.mkdir(exist_ok=True)
        if bp.exists() and bp.read_bytes() != raw:
            raise RuntimeError("Baseline destination mismatch")
        bp.write_bytes(raw)
        baseline = dict(b, result=artifact(bp))
        base_value = json.loads(gzip.decompress(raw))["makespan"]
        movement = r.get("data_movement_bytes", {})
        metrics = {"makespan_cycles": r["makespan_cycles"], "solver_wall_seconds": r.get("solver", {}).get("wall_seconds"),
                   "evaluation_wall_seconds": r.get("evaluation", {}).get("wall_seconds"),
                   "ddr_bytes": movement.get("scheduled_copy_bytes"), "extra_ddr_bytes": movement.get("added_copy_bytes"), "spill_bytes": movement.get("spill_added_copy_bytes")}
        artifacts = {k: v for k, v in r["artifacts"].items() if k != "diagnostics"}
        artifacts["run"] = artifact(folder / "run.json")
        missing = {"provenance.environment.threads": "Thread count was not sampled; OMP/BLAS/MKL thread environment set to 1",
                   "provenance.environment.peak_rss_bytes": "This small batch did not sample peak RSS", "provenance.measurement.seed": "Deterministic construction has no RNG or seed"}
        if r["status"] == "not_run":
            missing.update({"provenance.measurement.started_at": r["not_run_reason"], "provenance.measurement.finished_at": r["not_run_reason"]})
        record = {"attempt_id": f"nikolastarx-{batch.name}-P1-{case}-k{cores}-r0", "revision": 1, "run_id": batch.name,
            "algorithm_id": "q1-tree-frontier-pack", "algorithm_name": "P1 threshold subtree frontier and tail packing", "variant": "threshold-antichain-tail",
            "solver_commit": SOLVER, "parameters": {"cores": cores, "packet_factor": 4, "selected": r.get("diagnostics", {}).get("selected"), "constructor_timeout_seconds": 30, "evaluation_timeout_seconds": 60, "candidate_limit": 1, "batch_timeout_seconds": 1200,
                "workers": 1, "stop_policy": "stop batch on unexpected failure; no retries", "scoring_backend": "none; external E0 only"},
            "problem": "P1", "case_id": case, "cores": cores, "status": r["status"], "metrics": metrics,
            "evaluator": {"route": "E0", "commit": SOLVER, "entrypoint": "multicore_cut_evaluate_problem_1.py -> contest_io.run_problem_cli(1)"},
            "identity": {"graph_sha256": r["graph_sha256"], "config_sha256": meta["config_sha256"], "official_sha256": meta["official_code_hash"], "plan_sha256": r.get("plan_sha256")},
            "artifacts": artifacts, "runtime_id": "nikolastarx-m5pro-macos-py312-20260924", "observed_at": r["finished_at"],
            "timing": {"solver_includes_evaluation": False, "evaluation_precision": "perf_counter outer subprocess wall; includes process wait completion detection", "utc": "ISO UTC Z; duration from monotonic perf_counter"},
            "provenance": {"producer_session": SESSION, "task_url": TASK,
                "solver": {"source": source(SOLVER, SOLVER_PATH, "main"), "authors": ["NikolaStarx"],
                    "method": "On in-tree forests with fewer components than cores, select maximal threshold subtrees, pipe-load-pack antichain Tasks and append one tail Task; otherwise use component-pack; no scoring or search",
                    "references": [f"https://github.com/{REPO}/blob/{SOLVER}/docs/a/Q1_TREE_FRONTIER.md"], "upstream": [],
                    "selected_algorithm_id": "q1-component-pack" if r.get("diagnostics", {}).get("selected") == "component-pack" else None, "selected_solver_commit": "2cf3951af50be1e35ff78acb91629f2d0207bd82" if r.get("diagnostics", {}).get("selected") == "component-pack" else None},
                "runner": {"source": source(meta["runner_commit"], RUNNER_PATH, "run"), "argv": meta["runner_argv"], "working_directory": "."},
                "environment": meta["environment"], "measurement": {"started_at": r["started_at"], "finished_at": r["finished_at"], "seed": None,
                    "repeat_index": 0, "cold_start": True,
                    "solver_scope": "Fresh interpreter launch through graph read, construction, validation, plan and diagnostics publication, process exit; OS file cache not flushed",
                    "evaluation_scope": "Independent official P1 CLI launch through complete result/trace/log publication and exit; gzip/export outside solver and E0 walls",
                    "budget": {"wall_seconds": 30, "candidate_limit": 1, "stop_reason": "direct candidate complete" if r["status"] == "ok" else r.get("not_run_reason", "failure stopped batch")},
                    "calls": r["calls"], "offline_costs": f"uv sync --locked and exact ZIP-byte materialization before cells; no training, search, or case-specific algorithm precompute. Shared input preparation {meta['input_preparation_wall_seconds']} seconds; compression/export excluded and separately identifiable.",
                    "failure": r["failure"]}, "missing_reasons": missing},
            "notes": ["Frozen packet-factor=4 coverage extension, 99 new cases; original case002 attempt is reused only by aggregate report. No online parameter search or independent algorithm acceptance.",
                      "P2 and Q3 scoring reported stopped before this batch; no exclusive-host reservation or controlled timing claim.",
                      "Fresh process timing; OS file cache not flushed. Historical fixed64 used different concurrency and measurement polling, so wall times are descriptive, not controlled speedup.",
                      f"Baseline exact compressed original reused from {OLD}; no baseline evaluation executed."],
            "source_url": TASK, "baseline": baseline}
        records.append(record)
        m = r["makespan_cycles"]
        comparisons.append({"case": case, "cores": cores, "status": r["status"], "selected": r.get("diagnostics", {}).get("selected"), **metrics,
            "baseline_cycles": base_value, "fixed64_cycles": previous["metrics"]["makespan_cycles"],
            "singlecore_speedup": base_value / m if m else None,
            "fixed64_speedup": previous["metrics"]["makespan_cycles"] / m if m else None})
    write(batch / "references" / "fixed64-records.json", {"source_commit": OLD, "source_path": OLD_FEED, "records": original_rows})
    write(batch / "comparison.json", comparisons)
    write(batch / "board-feed.json", {"schema_version": 1, "submission_version": 1, "records": records})
    print(json.dumps({"exported_records": len(records), "statuses": {x: sum(r["status"] == x for r in records) for x in sorted({r["status"] for r in records})}}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "export"))
    parser.add_argument("run_id")
    args = parser.parse_args()
    if not args.run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in args.run_id):
        parser.error("run_id must contain only letters, numbers, dash, underscore")
    batch = RESULT_ROOT / args.run_id
    return run(batch) if args.action == "run" else export(batch)


if __name__ == "__main__":
    raise SystemExit(main())
