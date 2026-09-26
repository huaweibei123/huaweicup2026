"""Export the separately budgeted Stage G; never execute a solver/evaluator."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path

from benchmark_g import ROOT, SESSION, SOLVER, OUTPUT, VARIANTS, NEW_SCRIPT, OLD_COMMIT, OLD_FEED
from benchmark import sha, dump, git
from trace_c import boundary_metadata

REPO = "huaweibei123/huaweicup2026"


def source(commit, path, entrypoint):
    git("show", f"{commit}:{path}")
    return {"repo": REPO, "commit": commit, "path": path, "entrypoint": entrypoint}


def artifact(path):
    return {"path": path.as_posix(), "sha256": sha((ROOT / path).read_bytes())}


def static_ddr(graph, plan, result):
    boundary, reloads, original, _, _ = boundary_metadata(graph, plan, result["bandwidth_bytes_per_cycle"])
    movement = result["data_movement_bytes"]
    boundary_bytes = sum(b["bytes"] for b in boundary)
    return {"boundary_copy_count": len(boundary), "boundary_copy_bytes": boundary_bytes,
            "original_copy_bytes": original,
            "static_repeat_above_one_load_bytes": sum(x["repeat_above_one_load_bytes"] for x in reloads),
            "static_external_input_repeat_bytes": sum(x["repeat_above_one_load_bytes"] for x in reloads if x["source_kind"] == "external_input"),
            "input_tensors": reloads,
            "official_movement": movement,
            "boundary_plus_spill_matches_official_scheduled": boundary_bytes + movement["spill_added_copy_bytes"] == movement["scheduled_copy_bytes"],
            "boundary_minus_original_matches_official_partition_added": boundary_bytes - original == movement["partition_added_copy_bytes"],
            "scope": "Static repeated Task-boundary loads above one input copy. Not cache availability, trace readiness or unique timing causation; no Task compiler/scorer used."}


def export(output, graphs):
    folder = ROOT / OUTPUT
    protocol = json.loads((folder / "protocol.json").read_bytes())
    rows = json.loads((folder / "rows.json").read_bytes())
    completion = json.loads((folder / "completion.json").read_bytes())
    for key in ("solver", "E0", "E1", "E2"):
        assert sum(r["calls"][key] for r in rows) == completion["calls"][key]
    assert protocol["solver_commit"] == SOLVER
    graph_raw = (graphs / "case_051.json").read_bytes()
    assert sha(graph_raw) == protocol["input_sha256"]["case_051.json"]
    graph = json.loads(graph_raw)
    previous_path = OLD_FEED
    previous_raw = (ROOT / previous_path).read_bytes()
    assert previous_raw == git("show", OLD_COMMIT + ":" + previous_path)
    previous = json.loads(previous_raw)
    prior = {(r["case_id"], r["cores"]): r for r in previous["records"] if r["variant"] == "chain-atomic-grain4" and r["status"] == "ok"}
    records, comparisons, ddr_analyses = [], [], []
    for row in rows:
        case, cores, variant = row["case_id"], row["cores"], row["variant"]
        old = prior[(case, cores)]
        for field, expected in (("graph_sha256", protocol["input_sha256"][f"case_{case}.json"]),
                                ("config_sha256", protocol["input_sha256"]["config.txt"]),
                                ("official_sha256", protocol["official_code_hash"])):
            assert old["identity"][field] == expected
        old_result = old["artifacts"]["result"]
        old_raw = (ROOT / old_result["path"]).read_bytes()
        assert old_raw == git("show", OLD_COMMIT + ":" + old_result["path"])
        assert sha(old_raw) == old_result["sha256"]
        assert json.loads(gzip.decompress(old_raw))["makespan"] == old["metrics"]["makespan_cycles"]
        root = Path(OUTPUT) / f"{case}-k{cores}-{variant}"
        artifacts = {"run": artifact(root / "run.json"), "manifest": artifact(Path(OUTPUT) / "protocol.json")}
        plan_path = root / f"case_{case}_multicore_res.json"
        plan_sha = row.get("plan_sha256")
        if (ROOT / plan_path).is_file():
            artifacts["plan"] = artifact(plan_path)
            if plan_sha:
                assert artifacts["plan"]["sha256"] == plan_sha
            plan_sha = artifacts["plan"]["sha256"]
        result = None
        for kind in ("result", "trace"):
            item = row["artifacts"].get(kind + ".json")
            if item:
                packed = (ROOT / item["path"]).read_bytes()
                assert sha(packed) == item["sha256"]
                raw = gzip.decompress(packed)
                assert sha(raw) == item["raw_sha256"]
                artifacts[kind] = {"path": item["path"], "sha256": item["sha256"]}
                if kind == "result":
                    try:
                        result = json.loads(raw)
                    except (ValueError, UnicodeError):
                        if row["status"] == "ok":
                            raise
        if (ROOT / root / "result.txt").is_file():
            artifacts["log"] = artifact(root / "result.txt")
        if row["status"] == "ok":
            assert result["scene"] == "A" and result["num_cores"] == cores
            assert result["makespan"] == row["makespan_cycles"] and type(result["makespan"]) is type(row["makespan_cycles"])
            assert result["data_movement_bytes"] == row["data_movement_bytes"]
        movement = result["data_movement_bytes"] if result and row["status"] == "ok" else {}
        single_root = Path("results/benchmark-board/official-singlecore-20260924") / case
        single_run = json.loads(git("show", SOLVER + ":" + (single_root / "run.json").as_posix()))
        for key, expected in (("graph_sha256", protocol["input_sha256"][f"case_{case}.json"]),
                              ("config_sha256", protocol["input_sha256"]["config.txt"]),
                              ("official_code_hash", protocol["official_code_hash"])):
            assert single_run[key] == expected
        single_ref = single_run["artifacts"]["result.json"]
        single_packed = (ROOT / single_ref["path"]).read_bytes()
        assert single_packed == git("show", SOLVER + ":" + single_ref["path"])
        assert sha(single_packed) == single_ref["sha256"]
        assert sha(gzip.decompress(single_packed)) == single_ref["raw_sha256"]
        baseline = {"graph_sha256": single_run["graph_sha256"], "config_sha256": single_run["config_sha256"],
                    "official_sha256": single_run["official_code_hash"], "route": "E0",
                    "entrypoint": "singlecore_evaluate.evaluate_singlecore", "result": artifact(single_root / "result.json.gz")}
        missing = {"provenance.environment.peak_rss_bytes": "Child peak RSS not instrumented; physical RAM and worker/thread counts recorded.",
                   "provenance.measurement.seed": "Both methods are deterministic graph constructions with no RNG or seed parameter."}
        if row["failure"]:
            for field in ("exit_code", "elapsed_seconds"):
                if row["failure"][field] is None:
                    missing["provenance.measurement.failure." + field] = (
                        "The process timed out and was terminated/reaped; no normal exit code was reported."
                        if field == "exit_code" and row["status"] == "timeout" else
                        "The failed supervision stage did not produce this value; original failure and prior process timing retained.")
        solver_stage, eval_stage = row.get("solver", {}), row.get("evaluation", {})
        measurement = {"started_at": row["started_at"], "finished_at": row["finished_at"], "seed": None,
                       "repeat_index": 0, "cold_start": True, "solver_scope": protocol["solver_scope"], "evaluation_scope": protocol["evaluation_scope"],
                       "budget": {"wall_seconds": 30, "candidate_limit": 1, "stop_reason": row["status"] + "; no retries; batch=" + completion["status"]},
                       "calls": row["calls"], "offline_costs": protocol["preparation"] + " Existing frozen official singlecore denominator reused; 0 new singlecore calls.",
                       "failure": row["failure"]}
        provenance = {"producer_session": SESSION, "task_url": protocol["task_url"],
                      "solver": {"source": source(row["solver_commit"], NEW_SCRIPT, "construct / main"),
                                 "authors": ["yuanzhifang30-sudo"],
                                 "method": "Guarded intact four-node chains: first round core chain loads 3/3/2/2/2, later rounds 4/2/2/2/2, fixed shared reduction tail on core 0; deterministic structural fallback",
                                 "references": [protocol["task_url"], "https://github.com/" + REPO + "/blob/" + SOLVER + "/src/q1_yuanzhifang/prefetch_frontier.py"],
                                 "upstream": [], "selected_algorithm_id": None, "selected_solver_commit": None},
                      "runner": {"source": source(row["runner_commit"], "src/q1_yuanzhifang/benchmark_g.py", "main"),
                                 "argv": solver_stage.get("argv", []), "working_directory": "."},
                      "environment": {k: protocol["environment"][k] for k in ("os", "cpu", "gpu", "ram_bytes", "python", "dependencies", "threads", "workers", "peak_rss_bytes")},
                      "measurement": measurement, "missing_reasons": missing}
        cycles = row.get("makespan_cycles") if row["status"] == "ok" else None
        record = {"attempt_id": f"fang-q1-stage-g-20260925-{variant}-{case}-k{cores}-r0", "revision": 1,
                  "run_id": "fang-q1-stage-g-20260925-" + variant,
                  "algorithm_id": "q1-guarded-intact-prefetch",
                  "algorithm_name": "结构守卫整链根核预取构造",
                  "variant": variant, "solver_commit": row["solver_commit"],
                  "parameters": {**protocol["parameters"][variant], "cores": cores, "candidate_limit": 1, "internal_full_scores": 0,
                                 "batch_budget": protocol["budget"], "batch_actual_calls": completion["calls"], "batch_wall_seconds": completion["wall_seconds"]},
                  "problem": "P1", "case_id": case, "cores": cores, "status": row["status"],
                  "metrics": {"makespan_cycles": cycles, "solver_wall_seconds": solver_stage.get("wall_seconds"),
                              "evaluation_wall_seconds": eval_stage.get("wall_seconds"), "ddr_bytes": movement.get("scheduled_copy_bytes"),
                              "extra_ddr_bytes": movement.get("added_copy_bytes"), "spill_bytes": movement.get("spill_added_copy_bytes"), "cache_hit_rate": None},
                  "evaluator": {"route": "E0", "commit": row["runner_commit"], "entrypoint": "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"},
                  "identity": {"graph_sha256": protocol["input_sha256"][f"case_{case}.json"], "config_sha256": protocol["input_sha256"]["config.txt"],
                               "official_sha256": protocol["official_code_hash"], "plan_sha256": plan_sha},
                  "artifacts": artifacts, "runtime_id": "fang-windows-q1-stage-g-20260925", "observed_at": row["finished_at"],
                  "timing": {"solver_includes_evaluation": False, "evaluation_precision": "perf_counter seconds around full cold CLI process", "utc": "UTC ISO8601 Z"},
                  "provenance": provenance, "notes": ["One exposed development case: 051/k5; not a 100-case mean or held-out test. Model R 208152 is not an official result. Existing Stage C evidence reused for quality comparison; no new baseline scoring.",
                                                      "One worker for this batch; no full-host isolation. Cold process, not flushed OS caches."],
                  "source_url": protocol["task_url"], "baseline": baseline, "cache_pair": None}
        records.append(record)
        single = json.loads(gzip.decompress((ROOT / single_root / "result.json.gz").read_bytes()))["makespan"]
        comparisons.append({"case_id": case, "cores": cores, "variant": variant, "status": row["status"], "makespan_cycles": cycles,
                            "singlecore_cycles": single, "singlecore_speedup": single / cycles if cycles else None,
                            "solver_wall_seconds": solver_stage.get("wall_seconds"), "evaluation_wall_seconds": eval_stage.get("wall_seconds"),
                            "extra_ddr_bytes": movement.get("added_copy_bytes"), "scheduled_copy_bytes": movement.get("scheduled_copy_bytes"),
                            "spill_bytes": movement.get("spill_added_copy_bytes"), "task_count": row.get("task_count"),
                            "stage_c_cycles": prior[(case, cores)]["metrics"]["makespan_cycles"],
                            "stage_c_solver_wall_seconds": prior[(case, cores)]["metrics"]["solver_wall_seconds"],
                            "stage_c_extra_ddr_bytes": prior[(case, cores)]["metrics"]["extra_ddr_bytes"],
                            "stage_c_attempt_id": prior[(case, cores)]["attempt_id"],
                            "model_r_cycles": row.get("diagnostics", {}).get("model_r_cycles"),
                            "e0_minus_model_r_cycles": cycles - row["diagnostics"]["model_r_cycles"] if cycles else None,
                            "stage_c_cycle_difference": cycles - old["metrics"]["makespan_cycles"] if cycles else None})
        if row["status"] == "ok":
            old_plan_ref = old["artifacts"]["plan"]
            old_plan_raw = git("show", OLD_COMMIT + ":" + old_plan_ref["path"])
            assert sha(old_plan_raw) == old_plan_ref["sha256"]
            ddr_analyses.append({"case_id": case, "cores": cores,
                                 "stage_c_commit": OLD_COMMIT, "stage_c_result_sha256": old_result["sha256"],
                                 "stage_c": static_ddr(graph, json.loads(old_plan_raw), json.loads(gzip.decompress(old_raw))),
                                 "stage_g": static_ddr(graph, json.loads((ROOT / plan_path).read_bytes()), result)})
    dump(output, {"schema_version": 1, "submission_version": 1, "records": records})
    dump(folder / "ddr-analysis.json", {"records": ddr_analyses, "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
                                        "analysis_source_commit": git("rev-parse", "HEAD").decode().strip()})
    with (folder / "comparison.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]) if comparisons else ["case_id", "cores", "status"])
        writer.writeheader(); writer.writerows(comparisons)
    print(json.dumps({"records": len(records), "output": output.as_posix(), "calls": completion["calls"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--graphs", type=Path, required=True)
    args = parser.parse_args()
    export(args.output, args.graphs)
