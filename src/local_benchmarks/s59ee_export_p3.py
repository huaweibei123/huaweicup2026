"""Export existing P3 online receipts to board-submission-v1; never run a solver."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOLVER_COMMIT = "a4e7ee13310d693ec4fb5cc236669ceb3b172d1f"
RUNNER_COMMIT = "0263a00933d51bfb83e9e92cd7ffb588178973e6"
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
    if not batch.is_relative_to(ROOT / "results/a/local-p3-20260924"):
        p.error("unexpected batch directory")
    meta = read(batch / "batch.json")
    if meta["solver_commit"] != SOLVER_COMMIT:
        raise RuntimeError("unexpected solver identity")
    runner_bytes = subprocess.check_output(["git", "show", f"{RUNNER_COMMIT}:src/local_benchmarks/s59ee_p3.py"], cwd=ROOT)
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
        q3_receipt = read(ROOT / run["artifacts"]["q3_receipt"]["path"])
        baseline = ROOT / "results/benchmark-board/official-singlecore-20260924" / case / "result.json.gz"
        movement = run["data_movement_bytes"]
        peak = run["solver"]["peak_rss_bytes_sampled"]
        record = {
            "attempt_id": f"nikolastarx-s59ee-p3-{case}-k{k}-r0",
            "revision": 1,
            "run_id": meta["batch_id"],
            "algorithm_id": "q3-structure-selected-online",
            "algorithm_name": "P3 结构选择在线构造",
            "variant": "structure-selected-online-e0/" + q3_receipt["strategy"],
            "solver_commit": SOLVER_COMMIT,
            "parameters": {"cores": k, "strategy_rule": "resource_word if supported else affine_eighth",
                           "selected_strategy": q3_receipt["strategy"], "seed": "none", "candidate_limit": 1,
                           "solver_timeout_seconds": 180, "batch_deadline_seconds": 1800},
            "problem": "P3", "case_id": case, "cores": k, "status": "ok",
            "metrics": {"makespan_cycles": run["makespan_cycles"],
                        "solver_wall_seconds": run["solver"]["wall_seconds"],
                        "evaluation_wall_seconds": None,
                        "ddr_bytes": movement["scheduled_copy_bytes"],
                        "extra_ddr_bytes": movement["added_copy_bytes"],
                        "spill_bytes": movement["spill_added_copy_bytes"],
                        "cache_hit_rate": run["cache_stats"]["hit_rate"]},
            "evaluator": {"route": "E0", "commit": EVALUATOR_COMMIT,
                          "entrypoint": "multicore_cut_evaluate_problem_3.evaluate_problem_3 (online)"},
            "identity": {"graph_sha256": run["graph_sha256"],
                         "config_sha256": run["config_sha256"],
                         "official_sha256": run["official_code_hash"],
                         "plan_sha256": plan["sha256"]},
            "artifacts": {"plan": {k: plan[k] for k in ("path", "sha256")},
                          "result": {k: result[k] for k in ("path", "sha256")},
                          "run": artifact(run_path),
                          "manifest": {key: run["artifacts"]["q3_receipt"][key] for key in ("path", "sha256")}},
            "runtime_id": RUNTIME,
            "observed_at": run["finished_at"],
            "timing": {"solver_includes_evaluation": True,
                       "evaluation_precision": "online component timer only; independent external E0 wall not measured",
                       "utc": "start/end ISO UTC Z; wall durations use monotonic clock"},
            "provenance": {
                "producer_session": SESSION, "task_url": ISSUE,
                "solver": {"source": {"repo": "huaweibei123/huaweicup2026", "commit": SOLVER_COMMIT,
                                      "path": "src/q3/solve.py", "entrypoint": "main -> prepare/select"},
                           "authors": ["NikolaStarx"],
                           "method": "structural guard chooses resource_word or affine_eighth; one integrated official P3 E0 before plan publication",
                           "references": ["https://github.com/huaweibei123/huaweicup2026/blob/a4e7ee13310d693ec4fb5cc236669ceb3b172d1f/src/q3/solve.py"],
                           "upstream": [], "selected_algorithm_id": "q3-" + q3_receipt["strategy"].replace("_", "-"),
                           "selected_solver_commit": SOLVER_COMMIT},
                "runner": {"source": {"repo": "huaweibei123/huaweicup2026", "commit": RUNNER_COMMIT,
                                      "path": "src/local_benchmarks/s59ee_p3.py", "entrypoint": "main"},
                           "argv": ["python", "-B", "src/local_benchmarks/s59ee_p3.py",
                                    "--source", "../local-p3-fixed-a4e7", "--batch", batch.relative_to(ROOT).as_posix(),
                                    "--cases", ",".join(invocation["cases"]), "--cores", ",".join(map(str, invocation["cores"])),
                                    "--workers", str(invocation["workers"])],
                           "working_directory": "."},
                "environment": {"os": platform.platform(), "cpu": "Apple M5 Pro", "gpu": "none",
                                "ram_bytes": 51539607552, "python": meta["python"],
                                "dependencies": "uv.lock sha256=" + sha(ROOT / "uv.lock") + "; uv sync --locked before T0",
                                "threads": None, "workers": invocation["workers"], "peak_rss_bytes": peak},
                "measurement": {"started_at": run["started_at"], "finished_at": run["finished_at"],
                                "seed": None, "repeat_index": 0, "cold_start": True,
                                "solver_scope": "outer Q3 subprocess launch through online official E0 confirmation, plan publication, and exit",
                                "evaluation_scope": "one integrated frozen P3 E0 inside solver wall; component official_import_config_evaluate_seconds in source receipt, no independent external wall",
                                "budget": {"wall_seconds": 180, "candidate_limit": 1,
                                           "stop_reason": "one structural construction accepted by online E0"},
                                "calls": run["calls"],
                                "offline_costs": "uv sync --locked and frozen case extraction before batch T0; no training, case-specific precompute, or compilation",
                                "failure": None},
                "missing_reasons": {"provenance.environment.threads": "per-process thread count was not sampled; BLAS/OMP/MKL configured to 1",
                                    "provenance.measurement.seed": "deterministic solver has no RNG seed"}},
            "notes": ["P3 source itself performed exactly one online frozen official E0 before publishing the plan; no second E0 was run by this batch.",
                      "No same-plan P2 no-cache pair in this batch; cache_gain remains unavailable, while official P3 Makespan and byte hit rate are available.",
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
