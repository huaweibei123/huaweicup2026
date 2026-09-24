"""Read Q3 feedback-batch evidence into board-submission-v1; zero evaluations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .feedback_benchmark import ROOT, REPO, artifact, digest, read


def source(commit, path, entrypoint):
    return {"repo": REPO, "commit": commit, "path": path, "entrypoint": entrypoint}


def checked_ref(ref, root):
    path = (root / ref["path"]).resolve()
    if not path.is_relative_to(root.resolve()) or digest(path) != ref["sha256"]:
        raise ValueError("artifact escaped repository or changed after execution: " + ref["path"])
    return dict(ref)


def explain_nulls(provenance):
    """Explain genuinely unmeasured quantities, never replace them with zero."""
    reasons = {
        "provenance.environment.peak_rss_bytes": "Per-child peak RSS was not measured; no aggregate/high-water proxy is substituted.",
        "provenance.environment.ram_bytes": "Physical memory query was unavailable on this host.",
        "provenance.environment.threads": "Thread count was not sampled; one worker is a dispatch constraint, not an observed thread count.",
        "provenance.measurement.seed": "Deterministic construction; no random generator or seed.",
        "provenance.measurement.cold_start": "Fresh interpreter per job; OS page-cache state is uncontrolled, so strict cold/warm classification is unknown.",
        "provenance.measurement.calls.E0": "Child failed or was interrupted before a validated receipt; actual E0 entries are unknown and the full reservation remains charged.",
        "provenance.measurement.failure.exit_code": "No reaped child exit status was available.",
        "provenance.measurement.failure.elapsed_seconds": "The child did not produce a complete timing receipt.",
    }
    def visit(value, path):
        if value is None:
            if not path.endswith((".failure", ".selected_algorithm_id", ".selected_solver_commit")):
                if path not in reasons:
                    raise ValueError("Unexplained missing provenance: " + path)
                yield path, reasons[path]
        elif isinstance(value, dict):
            for key, child in value.items():
                if key != "missing_reasons":
                    yield from visit(child, path + "." + key)
    return dict(visit(provenance, "provenance"))


def export_batch(batch_path, root=ROOT):
    batch_path = Path(batch_path)
    batch = read(batch_path)
    if batch["status"] == "running":
        raise ValueError("Only a stopped or completed batch snapshot may be exported")
    alg, sha = batch["algorithm"], batch["solver_commit"]
    baseline_path = batch_path.parent / "baselines.json"
    baselines = read(baseline_path) if baseline_path.exists() else {}
    records = []
    for item in batch["records"]:
        stored = read(root / item["run_path"])
        if stored != item:
            raise ValueError("Per-job run receipt and batch index differ")
        stage = next(s for s in batch["stages"] if s["stage_id"] == item["stage_id"])
        refs = {name: checked_ref(ref, root) for name, ref in item["artifacts"].items()}
        refs["run"] = artifact(root / item["run_path"], root)
        refs["manifest"] = checked_ref(stage["manifest"], root)
        result = read(root / refs["result"]["path"]) if "result" in refs else None
        process = item.get("solver_process") or {}
        successful = item["status"] == "ok"
        if successful:
            if not result or not {"plan", "result", "trace"}.issubset(refs):
                raise ValueError("Successful job lacks final artifacts")
            if type(result["makespan"]) is not type(item["makespan_cycles"]) or result["makespan"] != item["makespan_cycles"]:
                raise ValueError("Makespan value or numeric type changed")
        movement = result.get("data_movement_bytes", {}) if successful else {}
        cache = result.get("cache_stats", {}) if successful else {}
        provenance = {
            "producer_session": batch["producer_session"], "task_url": batch["task_url"],
            "solver": {"source": source(sha, batch["solver_module"].replace(".", "/") + ".py", batch["solver_module"] + ".main"),
                       "authors": alg["authors"], "method": alg["method"], "references": alg["references"],
                       "upstream": alg["upstream"], "selected_algorithm_id": None, "selected_solver_commit": None},
            "runner": {"source": source(batch.get("execution", {}).get("runner_commit", sha), "src/q3/feedback_benchmark.py", "src.q3.feedback_benchmark.main"),
                       "argv": stage["runner_argv"], "working_directory": "."},
            "environment": batch["environment"],
            "measurement": {
                "started_at": item["started_at"], "finished_at": item["finished_at"], "seed": None,
                "repeat_index": 0, "cold_start": None,
                "solver_scope": "Fresh child spawn through reaped exit: interpreter/import, read graph, construct, integrated E0 selection/verification, final plan and evidence writes, required cleanup. External parent preflight excluded and retained in batch wall.",
                "evaluation_scope": "No separate external final evaluation. Integrated E0 calls are included in solver wall; internal diagnostics are retained in trace and are not substituted for external timing.",
                "budget": {"wall_seconds": batch["budget"]["per_job_seconds"], "candidate_limit": item["e0_call_limit"],
                           "stop_reason": "completed" if successful else item["status"]},
                "calls": item["calls"], "offline_costs": batch["offline_costs"], "failure": item["failure"]},
            "missing_reasons": {},
        }
        provenance["missing_reasons"] = explain_nulls(provenance)
        notes = [
            "One explicit development batch; no independent-platform or full-suite acceptance is claimed.",
            "Final E0 JSON is preserved unchanged, including scene=B/problem=3/cache_mode=read_only.",
            "ddr_bytes is official scheduled_copy_bytes, not physical DDR traffic.",
            "Fresh process does not imply a cold OS cache; one observation is not a tail-latency estimate.",
            "Whole-batch original deadline and all reservations are retained in batch.json; continuation never resets them.",
        ]
        if not successful:
            notes.append("Failed attempt retained; E0 reservation remains charged when actual entries cannot be proven.")
        if item.get("research_stop"):
            notes.append(item["research_stop"])
        baseline = baselines.get(item["case_id"], {}).get("baseline")
        if baseline:
            checked_ref(baseline["result"], root)
            if any(baseline[k] != item["identity"][k] for k in ("graph_sha256", "config_sha256", "official_sha256")):
                raise ValueError("shared baseline has a different frozen identity")
            notes.append("Official single-core denominator reuses existing bytes; fixed upstream provenance is in baselines.json. No new baseline evaluation.")
        record = {
            "attempt_id": f"{batch['run_id']}-P3-{item['job_key']}", "revision": 1,
            "run_id": batch["run_id"], "algorithm_id": alg["id"], "algorithm_name": alg["name"],
            "variant": item["variant"], "solver_commit": sha,
            "parameters": {**item["parameters"], "solver_args": item["solver_args"], "e0_call_limit": item["e0_call_limit"],
                           "global_budget": batch["budget"], "workers": 1, "retry": False},
            "problem": "P3", "case_id": item["case_id"], "cores": item["cores"], "status": item["status"],
            "metrics": {"makespan_cycles": result["makespan"] if successful else None,
                        "solver_wall_seconds": process.get("wall_seconds"), "evaluation_wall_seconds": None,
                        "ddr_bytes": movement.get("scheduled_copy_bytes"), "extra_ddr_bytes": movement.get("added_copy_bytes"),
                        "spill_bytes": movement.get("spill_added_copy_bytes"), "cache_hit_rate": cache.get("hit_rate")},
            "evaluator": {"route": "E0", "commit": sha,
                          "entrypoint": "multicore_cut_evaluate_problem_3.evaluate_problem_3"},
            "identity": item["identity"], "artifacts": refs, "runtime_id": batch["runtime_id"],
            "observed_at": item["finished_at"], "timing": {"solver_includes_evaluation": True,
                "evaluation_precision": "External perf_counter whole-child wall; no standalone external final-evaluation timer.", "utc": "UTC"},
            "provenance": provenance, "notes": notes, "source_url": batch["task_url"],
            "baseline": baseline, "cache_pair": None,
        }
        records.append(record)
    return {"schema_version": 1, "submission_version": 1, "records": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path, help="batch.json from feedback_benchmark")
    parser.add_argument("output", type=Path, help="new board-feed-<UTC>-<unique>.json")
    args = parser.parse_args()
    output = args.output.resolve()
    batch = read(args.batch)
    area = batch.get("execution", {}).get("output_root", "results/a/q3-nikolastarx")
    declared = ROOT / area
    if (area not in ("results/a/q3-nikolastarx", "results/a/q3-verification")
            or declared.resolve() != declared or not output.is_relative_to(declared)):
        raise ValueError("feed must stay in the Q3 result area")
    feed = export_batch(args.batch)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(feed, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"records": len(feed["records"]), "feed": output.relative_to(ROOT).as_posix(), "evaluations": 0}))


if __name__ == "__main__":
    main()
