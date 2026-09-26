"""Export the existing 82-cell P1 overload receipts; never run a solver."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOLVER_COMMIT = "3c6e41b938c764d207de45584fb526c64f4eb845"
RUNNER_COMMIT = "8fecaaaf786a9977d30b5d9cd9722e053748bef5"
EVALUATOR_COMMIT = "fd07af3bf6b9fb116d380e45a69eea5771e7edae"
ISSUE = "https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5814790103"
SESSION = "nikolastarx/s-59ee5b053e1c48af8a64bc9ddb6ed5bc"
RUNTIME = "nikolastarx-m5pro-macos-py312-20260924"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    batch = args.batch.resolve()
    if not batch.is_relative_to(ROOT / "results/a/local-q1-overload-gapfill-20260925"):
        p.error("unexpected batch directory")
    meta = read(batch / "batch.json")
    if meta["solver_commit"] != SOLVER_COMMIT:
        raise RuntimeError("unexpected solver identity")
    runner_bytes = subprocess.check_output(["git", "show", f"{RUNNER_COMMIT}:src/local_benchmarks/s59ee_p1_overload_gapfill.py"], cwd=ROOT)
    if hashlib.sha256(runner_bytes).hexdigest() != meta["runner_sha256"]:
        raise RuntimeError("executed runner bytes differ from fixed commit")
    manifest = read(ROOT / "docs/a/source-manifest.json")
    records = []
    if meta["runner_commit"] != RUNNER_COMMIT or meta["status"] not in ("complete", "stopped"):
        raise RuntimeError("unexpected runner commit or unfinished batch")
    requested = [(case, "5") for case in meta["manifest"]["cases"]]
    if len(set(requested)) != len(requested):
        p.error("duplicate case")
    for case, core_text in requested:
        k = int(core_text)
        if case not in {f"{i:03d}" for i in range(1, 101)} or k != 5:
            p.error("invalid case/core")
        run_path = batch / "cells" / case / f"k{k}" / "run.json"
        run = read(run_path)
        if run["status"] not in ("ok", "failed", "timeout", "not_run") or run["case_id"] != case or run["cores"] != k:
            raise RuntimeError(f"case {case} has invalid terminal receipt")
        if any(run["calls"][name] > meta["manifest"]["maximum_calls"][name] for name in ("solver", "E0", "E1", "E2")):
            raise RuntimeError(f"case {case} exceeds call budget")
        invocation = next(x for x in meta["invocations"] if case in x["cases"] and k in x["cores"])
        plan = run["artifacts"].get("plan")
        result = run["artifacts"].get("result")
        if run["status"] == "ok" and (not plan or not result or run["calls"] != {"solver": 1, "E0": 1, "E1": 0, "E2": 0}):
            raise RuntimeError(f"case {case} has incomplete successful evidence")
        baseline = ROOT / "results/benchmark-board/official-singlecore-20260924" / case / "result.json.gz"
        movement = run.get("data_movement_bytes") or {}
        peak_samples = [x.get("peak_rss_bytes_sampled") for x in (run.get("solver", {}), run.get("evaluation", {}))]
        peak = max((x for x in peak_samples if x is not None), default=None)
        child = run.get("evaluation") if run.get("failure", {}).get("stage") == "E0" else run.get("solver")
        failure = None if run["status"] == "ok" else {
            "stage": run.get("failure", {}).get("stage", "queue"),
            "reason": run.get("failure", {}).get("reason", "not dispatched"),
            "exit_code": (child or {}).get("returncode"),
            "elapsed_seconds": (child or {}).get("wall_seconds")}
        artifacts = {"run": artifact(run_path)}
        for name in ("plan", "result", "trace", "log"):
            if name in run["artifacts"]:
                artifacts[name] = {key: run["artifacts"][name][key] for key in ("path", "sha256")}
        missing = {"provenance.environment.threads": "per-process thread count was not sampled; BLAS/OMP/MKL configured to 1",
                   "provenance.measurement.seed": "deterministic structural constructor has no RNG seed"}
        if peak is None:
            missing["provenance.environment.peak_rss_bytes"] = "no child process was launched"
        if run["status"] == "not_run":
            missing["provenance.measurement.started_at"] = "queued coordinate did not start a solver"
            missing["provenance.measurement.finished_at"] = "queued coordinate did not start a solver"
            missing["provenance.measurement.cold_start"] = "no solver process was launched"
        if failure:
            for key in ("exit_code", "elapsed_seconds"):
                if failure[key] is None:
                    missing[f"provenance.measurement.failure.{key}"] = "no child process receipt exists"
        record = {
            "attempt_id": f"nikolastarx-s59ee-p1-overload-{case}-k{k}-r0",
            "revision": 1,
            "run_id": meta["batch_id"],
            "algorithm_id": "q1-component-overload-list",
            "algorithm_name": "P1 分量过载拆分与就绪列表放置",
            "variant": "any-pipe-overload-quotient-ready-list",
            "solver_commit": SOLVER_COMMIT,
            "parameters": {"cores": k, "max_rounds": 64, "max_sinks": 64,
                           "candidate_limit": 1, "solver_timeout_seconds": 30,
                           "evaluation_timeout_seconds": 60, "batch_deadline_seconds": 1200},
            "problem": "P1", "case_id": case, "cores": k, "status": run["status"],
            "metrics": {"makespan_cycles": run.get("makespan_cycles"),
                        "solver_wall_seconds": run.get("solver", {}).get("wall_seconds"),
                        "evaluation_wall_seconds": run.get("evaluation", {}).get("wall_seconds"),
                        "ddr_bytes": movement.get("scheduled_copy_bytes"),
                        "extra_ddr_bytes": movement.get("added_copy_bytes"),
                        "spill_bytes": movement.get("spill_added_copy_bytes"),
                        "cache_hit_rate": None},
            "evaluator": {"route": "E0", "commit": EVALUATOR_COMMIT,
                          "entrypoint": "multicore_cut_evaluate_problem_1.py -> contest_io.run_problem_cli(1)"},
            "identity": {"graph_sha256": run["graph_sha256"],
                         "config_sha256": run["config_sha256"],
                         "official_sha256": run["official_code_hash"],
                         "plan_sha256": plan["sha256"] if plan else None},
            "artifacts": artifacts,
            "runtime_id": RUNTIME,
            "observed_at": run["finished_at"],
            "timing": {"solver_includes_evaluation": False,
                       "evaluation_precision": "outer monotonic process wall seconds, sampled to Python perf_counter precision",
                       "utc": "start/end ISO UTC Z; wall durations use monotonic clock"},
            "provenance": {
                "producer_session": SESSION, "task_url": ISSUE,
                "solver": {"source": {"repo": "huaweibei123/huaweicup2026", "commit": SOLVER_COMMIT,
                                      "path": "src/q1/component_overload.py", "entrypoint": "main"},
                           "authors": ["NikolaStarx"],
                           "method": "split components that overload a compute pipe fair share, then schedule the quotient DAG by ready-list proxy; structural fallback to heavy-suffix; one proposal and no online evaluator",
                           "references": ["https://github.com/huaweibei123/huaweicup2026/blob/3c6e41b938c764d207de45584fb526c64f4eb845/src/q1/component_overload.py"],
                           "upstream": [], "selected_algorithm_id": None, "selected_solver_commit": None},
                "runner": {"source": {"repo": "huaweibei123/huaweicup2026", "commit": RUNNER_COMMIT,
                                      "path": "src/local_benchmarks/s59ee_p1_overload_gapfill.py", "entrypoint": "main"},
                           "argv": ["python", "-B", "src/local_benchmarks/s59ee_p1_overload_gapfill.py",
                                    "--source", "<pinned-solver-worktree>", "--batch", batch.relative_to(ROOT).as_posix()],
                           "working_directory": "."},
                "environment": {"os": meta["environment"]["os"], "cpu": meta["environment"]["cpu"], "gpu": "none",
                                "ram_bytes": meta["environment"]["ram_bytes"], "python": meta["python"],
                                "dependencies": "uv.lock sha256=" + sha(ROOT / "uv.lock") + "; uv sync --locked before T0",
                                "threads": None, "workers": invocation["workers"], "peak_rss_bytes": peak},
                "measurement": {"started_at": run["started_at"] if run["status"] != "not_run" else None,
                                "finished_at": run["finished_at"] if run["status"] != "not_run" else None,
                                "seed": None, "repeat_index": 0, "cold_start": True if run["status"] != "not_run" else None,
                                "solver_scope": "outer subprocess launch through plan publication and process exit; graph read and structural validation included",
                                "evaluation_scope": "independent frozen official P1 CLI launch through result/trace/log publication and exit; excludes offline gzip",
                                "budget": {"wall_seconds": 30, "candidate_limit": 1,
                                           "stop_reason": "completed first deterministic candidate" if run["status"] == "ok" else failure["reason"]},
                                "calls": run["calls"],
                                "offline_costs": "uv sync --locked and frozen case extraction before batch T0; no training, case-specific precompute, or compilation",
                                "failure": failure},
                "missing_reasons": missing},
            "notes": ["P1 component-overload-list k5 gapfill: this run has 82 coordinates; 18 earlier coordinates retain their own run and commit identities.",
                      "Successful cells received an independent frozen official P1 E0 final check; timeout/not_run cells have no verified makespan.",
                      "Runner source bytes matched fixed commit after initial preflight; all runs used the same byte hash.",
                      "Peak RSS is sampled per child process; not a hard whole-batch memory cap."],
            "source_url": ISSUE,
            "baseline": {"graph_sha256": run["graph_sha256"], "config_sha256": run["config_sha256"],
                         "official_sha256": manifest["official_code_hash"], "route": "E0",
                         "entrypoint": "singlecore_evaluate.evaluate_singlecore", "result": artifact(baseline)} if run["status"] == "ok" else None,
            "cache_pair": None,
        }
        records.append(record)
    payload = {"schema_version": 1, "submission_version": 1, "records": records}
    output = args.output.resolve()
    if not output.is_relative_to(batch):
        p.error("feed must be within batch directory")
    if output.exists():
        raise RuntimeError("snapshot feed already exists")
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"feed": output.relative_to(ROOT).as_posix(), "records": len(records), "sha256": sha(output)}))


if __name__ == "__main__":
    main()
