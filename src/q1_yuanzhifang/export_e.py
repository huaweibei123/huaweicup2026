"""Export and independently read back Stage E-4; zero solver/evaluator calls."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import json
import statistics
from pathlib import Path

from benchmark import ROOT, dump, git, sha
from benchmark_e import SESSION, BASE, OUTPUT, INDEX, SOLVER, CAPTAIN, SCRIPT, ALGORITHM, VARIANT
from reuse_e import require, GitBlobs, verify_record, exact_match

REPO = "huaweibei123/huaweicup2026"


def artifact(path):
    return {"path": path.as_posix(), "sha256": sha((ROOT / path).read_bytes())}


def source(commit, path, entrypoint):
    git("cat-file", "-e", f"{commit}:{path}")
    return {"repo": REPO, "commit": commit, "path": path, "entrypoint": entrypoint}


def read_json(path):
    raw = (ROOT / path).read_bytes()
    return json.loads(gzip.decompress(raw) if str(path).endswith(".gz") else raw)


def timings(values):
    values = sorted(values)
    if not values:
        return {"n": 0, "sum": 0, "p50": None, "p95": None, "max": None}
    position = (len(values) - 1) * .95
    lo = int(position)
    p95 = values[lo] + (values[min(lo + 1, len(values) - 1)] - values[lo]) * (position - lo)
    return {"n": len(values), "sum": sum(values), "p50": statistics.median(values), "p95": p95,
            "max": max(values), "quantile_method": "linear interpolation at (n-1)*p"}


def export(output):
    exporter_commit = git("rev-parse", "HEAD").decode().strip()
    exporter_path = "src/q1_yuanzhifang/export_e.py"
    require((ROOT / exporter_path).read_bytes() == git("show", f"{exporter_commit}:{exporter_path}"), "Exporter must be committed before use")
    protocol = read_json(Path(OUTPUT) / "protocol.json")
    rows = read_json(Path(OUTPUT) / "rows.json")
    completion = read_json(Path(OUTPUT) / "completion.json")
    index = read_json(Path(INDEX))
    manifest = read_json(Path("docs/a/source-manifest.json"))
    require(sha((ROOT / INDEX).read_bytes()) == protocol["evidence_index"]["sha256"], "Changed evidence index")
    require(protocol["solver_commit"] == SOLVER, "Different solver source")
    require(len({r["case_id"] for r in rows}) == len(rows), "Duplicate scenario attempt")
    for key, value in completion["calls"].items():
        require(sum(r["calls"][key] for r in rows) == value <= protocol["budget"][key], "Call ledger mismatch")
    require(completion["records"] == len(rows), "Completion count mismatch")
    require(len(rows) + len(completion["unrun"]) == 100, "Missing attempted/unrun accounting")
    prior = {e["record"]["case_id"]: e for e in index["entries"] if e["candidate"] == "bounded"}
    records, comparisons = [], []
    algorithm_source = source(SOLVER, SCRIPT, "construct / main")
    runner_source = source(protocol["runner_commit"], "src/q1_yuanzhifang/benchmark_e.py", "main")
    upstream = [source(CAPTAIN, "src/q1/bounded_tasks.py", "construct"),
                source("0bf12cfe3164b155b02cc85896dabdfee72f9d37", "src/q1_yuanzhifang/fork_frontier.py", "construct")]
    with GitBlobs() as blobs:
        for row in rows:
            case, cores = row["case_id"], row["cores"]
            root = Path(OUTPUT) / f"{case}-k4"
            require(read_json(root / "run.json") == row, "Rows and original run receipt differ")
            artifacts = {"run": artifact(root / "run.json"), "manifest": artifact(Path(OUTPUT) / "protocol.json")}
            plan_path = root / f"case_{case}_multicore_res.json"
            plan_sha = None
            result, trace, historical = None, None, None
            if (ROOT / plan_path).exists():
                artifacts["plan"] = artifact(plan_path)
                plan_sha = artifacts["plan"]["sha256"]
                if row.get("plan_sha256"):
                    require(plan_sha == row["plan_sha256"], "Current plan hash mismatch")
            if "reuse" in row:
                require(row["calls"]["E0"] == 0 and row["evaluation"]["wall_seconds"] is None, "Reused E0 incorrectly counted or timed")
                match = exact_match(index, case, cores, row["selected"], (ROOT / plan_path).read_bytes())
                require(match is not None, "Missing exact-byte match for reuse")
                original, checked = verify_record(blobs, match["commit"], match["record"], manifest)
                require(checked == match["checked"] and original["plan"] == (ROOT / plan_path).read_bytes(), "Reused original differs")
                historical = row["reuse"]
                require(historical["record"] == match["record"] and historical["checked"] == checked, "Reused identity receipt differs")
                for kind, ref in historical["copied_originals"].items():
                    copied = (ROOT / ref["path"]).read_bytes()
                    require(copied == original[kind] and sha(copied) == ref["sha256"], "Copied historical original differs")
                for kind in ("result", "trace"):
                    artifacts[kind] = historical["copied_originals"][kind]
                result, trace = (read_json(Path(artifacts[k]["path"])) for k in ("result", "trace"))
                evaluator = historical["record"]["evaluator"]
            else:
                evaluator = {"route": "E0", "commit": protocol["runner_commit"], "entrypoint": "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"}
                for kind in ("result", "trace"):
                    ref = row["artifacts"].get(kind + ".json")
                    if ref:
                        packed = (ROOT / ref["path"]).read_bytes()
                        require(sha(packed) == ref["sha256"] and sha(gzip.decompress(packed)) == ref["raw_sha256"], "New E0 artifact hash mismatch")
                        artifacts[kind] = {"path": ref["path"], "sha256": ref["sha256"]}
                        if row["status"] == "ok":
                            if kind == "result":
                                result = json.loads(gzip.decompress(packed))
                            else:
                                trace = json.loads(gzip.decompress(packed))
                if (ROOT / root / "result.txt").exists():
                    artifacts["log"] = artifact(root / "result.txt")
            if row["status"] == "ok":
                require(result["scene"] == "A" and result["num_cores"] == cores, "Result scenario mismatch")
                require(type(result["makespan"]) is type(row["makespan_cycles"]) and result["makespan"] == row["makespan_cycles"], "Result makespan mismatch")
                require(result["data_movement_bytes"] == row["data_movement_bytes"], "Result movement mismatch")
                require(max(x["ts"] + x["dur"] for x in trace["traceEvents"] if x.get("ph") == "X") == result["makespan"], "Trace/result endpoint mismatch")
            denominator = index["singlecore"][case]
            single_refs = {}
            single_folder = ROOT / BASE / "references" / "singlecore" / case
            single_folder.mkdir(parents=True, exist_ok=True)
            for kind in ("result", "run"):
                ref = denominator[kind]
                original = blobs.read(denominator["commit"], ref["path"])
                require(sha(original) == ref["sha256"], "Singlecore fixed-Git reference hash mismatch")
                # Existing text checkouts can apply CRLF. Preserve the exact Git
                # original in our own byte-preserving evidence scope, never
                # rewrite the shared denominator or normalize its raw receipt.
                destination = single_folder / Path(ref["path"]).name
                if destination.exists():
                    require(destination.read_bytes() == original, "Existing copied denominator differs")
                else:
                    with destination.open("xb") as handle:
                        handle.write(original)
                single_refs[kind] = artifact(destination.relative_to(ROOT))
            baseline = {"graph_sha256": protocol["input_sha256"][f"case_{case}.json"],
                        "config_sha256": protocol["input_sha256"]["config.txt"], "official_sha256": protocol["official_code_hash"],
                        "route": "E0", "entrypoint": "singlecore_evaluate.evaluate_singlecore",
                        "result": single_refs["result"]}
            missing = {"provenance.environment.peak_rss_bytes": "Child peak RSS was not instrumented; RAM and single-worker limit recorded.",
                       "provenance.environment.threads": "OMP/OpenBLAS/MKL environment capped at 1; actual process thread count not sampled.",
                       "provenance.measurement.seed": "Deterministic graph constructions have no RNG or seed."}
            if row["failure"]:
                for field in ("exit_code", "elapsed_seconds"):
                    if row["failure"][field] is None:
                        missing["provenance.measurement.failure." + field] = "Not produced by the terminated/failed stage; complete prior process receipts retained."
            solver, evaluation = row.get("solver", {}), row.get("evaluation", {})
            measurement = {"started_at": row["started_at"], "finished_at": row["finished_at"], "seed": None, "repeat_index": 0,
                           "cold_start": True, "solver_scope": protocol["solver_scope"], "evaluation_scope": protocol["evaluation_scope"],
                           "budget": {"wall_seconds": 30, "candidate_limit": 2, "stop_reason": row["status"] + "; no retries; batch=" + completion["status"]},
                           "calls": row["calls"], "offline_costs": protocol["preparation"] + " Official singlecore denominators reused, 0 new singlecore calls.", "failure": row["failure"]}
            selected = row.get("selected")
            notes = ["Uniform fixed two-construction algorithm over all 100 public official graphs at k4. Full development data, not held-out or a k1-5 result.",
                     "Each fresh solver reconstructs both candidates. Historical plan/result data are accessible only to the benchmark after solver exit; no case-ID or score lookup in solver.",
                     "One worker; coordinated window but no exclusive-host reservation. Cold interpreter, OS caches not flushed. Cross-hardware wall times are not speedup ratios."]
            if historical:
                notes.append("E0 quality reused from exact plan bytes: " + historical["commit"] + " / " + historical["attempt_id"] + "; source observed_at=" + historical["record"]["observed_at"] + "; source runtime=" + historical["record"]["runtime_id"] + ". This attempt has 0 new E0 calls and evaluation_wall_seconds=null; historical timing is only in its original receipt.")
            movement = row.get("data_movement_bytes", {}) if row["status"] == "ok" else {}
            cycles = row.get("makespan_cycles") if row["status"] == "ok" else None
            provenance = {"producer_session": SESSION, "task_url": protocol["task_url"],
                          "solver": {"source": algorithm_source, "authors": ["yuanzhifang30-sudo", "NikolaStarx"],
                                     "method": "Pinned captain bounded constructor and Stage C fork-stage constructor; choose strict minimum of gate-compute plus mandatory DDR service, ties bounded. Heuristic has no performance guarantee.",
                                     "references": [protocol["task_url"]], "upstream": upstream,
                                     "selected_algorithm_id": {"bounded": "q1-bounded-component-tasks", "fork": "q1-fork-stage-frontier"}.get(selected),
                                     "selected_solver_commit": SOLVER if selected else None},
                          "runner": {"source": runner_source, "argv": solver.get("argv", []), "working_directory": "."},
                          "environment": {k: protocol["environment"][k] for k in ("os", "cpu", "gpu", "ram_bytes", "python", "dependencies", "threads", "workers", "peak_rss_bytes")},
                          "measurement": measurement, "missing_reasons": missing}
            record = {"attempt_id": f"fang-q1-stage-e4-20260925-{case}-k4-r0", "revision": 1, "run_id": "fang-q1-stage-e4-20260925",
                      "algorithm_id": ALGORITHM, "algorithm_name": "P1 two-structure gate and DDR selector", "variant": VARIANT, "solver_commit": SOLVER,
                      "parameters": {**protocol["parameters"], "cores": cores, "internal_E0_E1_E2_calls": 0, "batch_budget": protocol["budget"],
                                     "batch_actual_calls": completion["calls"], "batch_wall_seconds": completion["wall_seconds"]},
                      "problem": "P1", "case_id": case, "cores": cores, "status": row["status"],
                      "metrics": {"makespan_cycles": cycles, "solver_wall_seconds": solver.get("wall_seconds"), "evaluation_wall_seconds": evaluation.get("wall_seconds"),
                                  "ddr_bytes": movement.get("scheduled_copy_bytes"), "extra_ddr_bytes": movement.get("added_copy_bytes"), "spill_bytes": movement.get("spill_added_copy_bytes")},
                      "evaluator": evaluator, "identity": {"graph_sha256": protocol["input_sha256"][f"case_{case}.json"], "config_sha256": protocol["input_sha256"]["config.txt"],
                                                          "official_sha256": protocol["official_code_hash"], "plan_sha256": plan_sha},
                      "artifacts": artifacts, "runtime_id": "fang-windows-q1-stage-e4-20260925", "observed_at": row["finished_at"],
                      "timing": {"solver_includes_evaluation": False, "evaluation_precision": "Outer perf_counter around new CLI only; null for historical exact-byte reuse", "utc": "UTC ISO8601 Z"},
                      "provenance": provenance, "notes": notes, "source_url": protocol["task_url"], "baseline": baseline, "cache_pair": None}
            records.append(record)
            old = prior[case]
            old_cycles = old["checked"]["makespan_cycles"]
            single = denominator["makespan_cycles"]
            comparisons.append({"case_id": case, "cores": cores, "status": row["status"], "selected": selected, "quality_source": row.get("quality_source"),
                                "makespan_cycles": cycles, "singlecore_cycles": single, "singlecore_speedup": single / cycles if cycles else None,
                                "bounded_cycles": old_cycles, "bounded_speedup": single / old_cycles,
                                "makespan_delta_vs_bounded": cycles - old_cycles if cycles else None,
                                "quality_comparison": "win" if cycles and cycles < old_cycles else "loss" if cycles and cycles > old_cycles else "tie" if cycles else "unavailable",
                                "extra_ddr_bytes": movement.get("added_copy_bytes"), "bounded_extra_ddr_bytes": old["checked"]["data_movement_bytes"]["added_copy_bytes"],
                                "solver_wall_seconds": solver.get("wall_seconds"), "new_E0_wall_seconds": evaluation.get("wall_seconds"),
                                "new_E0_calls": row["calls"]["E0"], "historical_E0_wall_seconds": historical["checked"]["historical_evaluation"]["wall_seconds"] if historical else None,
                                "historical_E0_attempt_id": historical["attempt_id"] if historical else None, "bounded_source_commit": old["commit"],
                                "bounded_attempt_id": old["record"]["attempt_id"], "plan_sha256": plan_sha})
    completed = [c for c in comparisons if c["status"] == "ok"]
    summary = {"solver_commit": SOLVER, "runner_commit": protocol["runner_commit"], "exporter_commit": exporter_commit, "cases_ok": len(completed), "cases_expected": 100,
               "status_counts": dict(Counter(r["status"] for r in rows)), "unrun": completion["unrun"], "calls": completion["calls"],
               "reused_E0_results": completion["reused_E0_results"], "selected_counts": dict(Counter(r.get("selected", "none") for r in rows)),
               "uniform_algorithm_full100_mean_speedup": statistics.mean(c["singlecore_speedup"] for c in completed) if len(completed) == 100 else None,
               "observed_success_only_mean_speedup": statistics.mean(c["singlecore_speedup"] for c in completed) if completed else None,
               "bounded_same_success_subset_mean_speedup": statistics.mean(c["bounded_speedup"] for c in completed) if completed else None,
               "captain_bounded_full100_mean_speedup": statistics.mean(index["singlecore"][case]["makespan_cycles"] / e["checked"]["makespan_cycles"] for case, e in prior.items()),
               "history_best_of_only_portfolio_and_bounded_mean": statistics.mean(max(c["singlecore_speedup"], c["bounded_speedup"]) for c in completed) if len(completed) == 100 else None,
               "comparison_counts": dict(Counter(c["quality_comparison"] for c in comparisons)),
               "screenshot_k4_threshold": 3.14, "screenshot_threshold_exceeded": len(completed) == 100 and statistics.mean(c["singlecore_speedup"] for c in completed) > 3.14,
               "solver_wall_seconds": timings([r["solver"]["wall_seconds"] for r in rows if "solver" in r]),
               "new_E0_wall_seconds": timings([r["evaluation"]["wall_seconds"] for r in rows if r.get("evaluation", {}).get("wall_seconds") is not None]),
               "batch_wall_seconds": completion["wall_seconds"], "preflight_wall_seconds": protocol["preflight_wall_seconds"],
               "environment": protocol["environment"], "scope": "Arithmetic mean of 100 per-case official singlecore/multicore ratios; quality from new E0 or audited exact-byte old E0. No cross-platform wall speedup, no all-k claim, no global historical-best claim."}
    dump(output, {"schema_version": 1, "submission_version": 1, "records": records})
    dump(ROOT / BASE / "summary.json", summary)
    with (ROOT / BASE / "comparison.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
        writer.writeheader(); writer.writerows(comparisons)
    dump(ROOT / BASE / "readback.json", {"records_checked": len(rows), "successful_result_trace_plan_run_records_checked": len(completed),
                                        "failed_records_preserved": len(rows) - len(completed), "all_present_artifact_hashes_checked": True,
                                        "singlecore_fixed_originals_copied": len(rows), "exporter_commit": exporter_commit,
                                        "new_calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
                                        "scope": "Independent static readback of raw artifacts and copied fixed Git originals; no reevaluation."})
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / BASE / "board-feed-stage-e-4.json")
    export(parser.parse_args().output)
