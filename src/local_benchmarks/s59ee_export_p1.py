"""Export existing P1 fixed64 receipts to board-submission-v1; never run a solver."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOLVER_COMMIT = "4dff90ef699fd51845cf482951e8477066f5f566"
RUNNER_COMMIT = "556077b23ae903ddea246f9f9965b50e59c37dca"
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
    p.add_argument("--cases", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    batch = args.batch.resolve()
    if not batch.is_relative_to(ROOT / "results/a/local-p1-fixed64-20260924"):
        p.error("unexpected batch directory")
    meta = read(batch / "batch.json")
    if meta["solver_commit"] != SOLVER_COMMIT:
        raise RuntimeError("unexpected solver identity")
    runner_bytes = subprocess.check_output(["git", "show", f"{RUNNER_COMMIT}:src/local_benchmarks/s59ee_p1_fixed64.py"], cwd=ROOT)
    if hashlib.sha256(runner_bytes).hexdigest() != meta["runner_sha256"]:
        raise RuntimeError("executed runner bytes differ from fixed commit")
    manifest = read(ROOT / "docs/a/source-manifest.json")
    records = []
    requested = [tuple(item.split(":")) for item in args.cases.split(",")]
    if len(set(requested)) != len(requested):
        p.error("duplicate case")
    for case, core_text in requested:
        k = int(core_text)
        if case not in {f"{i:03d}" for i in range(1, 101)} or k not in (1, 2, 3, 4, 5):
            p.error("invalid case/core")
        run_path = batch / "cells" / case / f"k{k}" / "run.json"
        run = read(run_path)
        if run["status"] != "ok" or run["case_id"] != case or run["cores"] != k or run["calls"] != {"solver": 1, "E0": 1, "E1": 0, "E2": 0}:
            raise RuntimeError(f"case {case} has no complete successful receipt")
        invocation = next(x for x in meta["invocations"] if case in x["cases"] and k in x["cores"])
        plan = run["artifacts"]["plan"]
        result = run["artifacts"]["result"]
        baseline = ROOT / "results/benchmark-board/official-singlecore-20260924" / case / "result.json.gz"
        movement = run["data_movement_bytes"]
        peak = max(run["solver"]["peak_rss_bytes_sampled"], run["evaluation"]["peak_rss_bytes_sampled"])
        record = {
            "attempt_id": f"nikolastarx-s59ee-p1-fixed64-{case}-k{k}-r0",
            "revision": 1,
            "run_id": meta["batch_id"],
            "algorithm_id": "q1-fixed64-local-finish",
            "algorithm_name": "P1 固定64块局部完成时间构造",
            "variant": "propose-fixed64-e0",
            "solver_commit": SOLVER_COMMIT,
            "parameters": {"cores": k, "kind": "fixed64", "seed": 0,
                           "candidate_limit": 1, "solver_timeout_seconds": 120,
                           "evaluation_timeout_seconds": 180, "batch_deadline_seconds": 7200},
            "problem": "P1", "case_id": case, "cores": k, "status": "ok",
            "metrics": {"makespan_cycles": run["makespan_cycles"],
                        "solver_wall_seconds": run["solver"]["wall_seconds"],
                        "evaluation_wall_seconds": run["evaluation"]["wall_seconds"],
                        "ddr_bytes": movement["scheduled_copy_bytes"],
                        "extra_ddr_bytes": movement["added_copy_bytes"],
                        "spill_bytes": movement["spill_added_copy_bytes"],
                        "cache_hit_rate": None},
            "evaluator": {"route": "E0", "commit": EVALUATOR_COMMIT,
                          "entrypoint": "multicore_cut_evaluate_problem_1.py -> contest_io.run_problem_cli(1)"},
            "identity": {"graph_sha256": run["graph_sha256"],
                         "config_sha256": run["config_sha256"],
                         "official_sha256": run["official_code_hash"],
                         "plan_sha256": plan["sha256"]},
            "artifacts": {"plan": {k: plan[k] for k in ("path", "sha256")},
                          "result": {k: result[k] for k in ("path", "sha256")},
                          "run": artifact(run_path),
                          "trace": {k: run["artifacts"]["trace"][k] for k in ("path", "sha256")},
                          "log": {k: run["artifacts"]["log"][k] for k in ("path", "sha256")}},
            "runtime_id": RUNTIME,
            "observed_at": run["finished_at"],
            "timing": {"solver_includes_evaluation": False,
                       "evaluation_precision": "outer monotonic process wall seconds, sampled to Python perf_counter precision",
                       "utc": "start/end ISO UTC Z; wall durations use monotonic clock"},
            "provenance": {
                "producer_session": SESSION, "task_url": ISSUE,
                "solver": {"source": {"repo": "huaweibei123/huaweicup2026", "commit": SOLVER_COMMIT,
                                      "path": "src/q1/search.py", "entrypoint": "propose --kind fixed64"},
                           "authors": ["NikolaStarx"],
                           "method": "fixed64 graph partition with seed 0 followed by local-duration earliest-finish core placement; one proposal, no E1 scoring",
                           "references": ["https://github.com/huaweibei123/huaweicup2026/blob/4dff90ef699fd51845cf482951e8477066f5f566/src/q1/search.py"],
                           "upstream": [], "selected_algorithm_id": None, "selected_solver_commit": None},
                "runner": {"source": {"repo": "huaweibei123/huaweicup2026", "commit": RUNNER_COMMIT,
                                      "path": "src/local_benchmarks/s59ee_p1_fixed64.py", "entrypoint": "main"},
                           "argv": ["python", "-B", "src/local_benchmarks/s59ee_p1_fixed64.py",
                                    "--source", "../local-p1-fixed-4dff", "--batch", batch.relative_to(ROOT).as_posix(),
                                    "--cases", ",".join(invocation["cases"]),
                                    "--cores", ",".join(map(str, invocation["cores"])),
                                    "--workers", str(invocation["workers"])],
                           "working_directory": "."},
                "environment": {"os": platform.platform(), "cpu": "Apple M5 Pro", "gpu": "none",
                                "ram_bytes": 51539607552, "python": meta["python"],
                                "dependencies": "uv.lock sha256=" + sha(ROOT / "uv.lock") + "; uv sync --locked before T0",
                                "threads": None, "workers": invocation["workers"], "peak_rss_bytes": peak},
                "measurement": {"started_at": run["started_at"], "finished_at": run["finished_at"],
                                "seed": 0, "repeat_index": 0, "cold_start": True,
                                "solver_scope": "outer subprocess launch through plan publication and process exit; graph read and structural validation included",
                                "evaluation_scope": "independent frozen official P1 CLI launch through result/trace/log publication and exit; excludes offline gzip",
                                "budget": {"wall_seconds": 120, "candidate_limit": 1,
                                           "stop_reason": "completed first deterministic candidate"},
                                "calls": run["calls"],
                                "offline_costs": "uv sync --locked and frozen case extraction before batch T0; no training, case-specific precompute, or compilation",
                                "failure": None},
                "missing_reasons": {"provenance.environment.threads": "per-process thread count was not sampled; BLAS/OMP/MKL configured to 1"}},
            "notes": ["True P1 fixed64 constructor result, independently evaluated by frozen official E0; no search/E1 or old seed was run.",
                      "Runner source bytes matched fixed commit after initial preflight; all runs used the same byte hash.",
                      "Peak RSS is sampled per child process; not a hard whole-batch memory cap."],
            "source_url": ISSUE,
            "baseline": {"graph_sha256": run["graph_sha256"], "config_sha256": run["config_sha256"],
                         "official_sha256": manifest["official_code_hash"], "route": "E0",
                         "entrypoint": "singlecore_evaluate.evaluate_singlecore", "result": artifact(baseline)},
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
