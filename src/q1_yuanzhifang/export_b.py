"""Export Stage B artifacts without executing any solver/evaluator."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path
import statistics

from benchmark_b import ROOT, OUTPUT, SOLVER, BASELINE, SESSION, sha, dump, git, utc

REPO = "huaweibei123/huaweicup2026"


def source(commit, path, entrypoint):
    git("show", f"{commit}:{path}")
    return {"repo": REPO, "commit": commit, "path": path, "entrypoint": entrypoint}


def artifact(path):
    return {"path": path.as_posix(), "sha256": sha((ROOT / path).read_bytes())}


def report():
    """Derive small comparison artifacts from preserved receipts; no scoring."""
    out = ROOT / OUTPUT
    protocol = json.loads((out / "protocol.json").read_bytes())
    completion = json.loads((out / "completion.json").read_bytes())
    rows = json.loads((out / "rows.json").read_bytes())
    base = {}
    for case in protocol["cases"]:
        path = ROOT / "results/benchmark-board/official-singlecore-20260924" / case / "result.json.gz"
        base[case] = json.loads(gzip.decompress(path.read_bytes()))["makespan"]
    fixed = {r["case_id"]: r for r in rows if r["variant"] == "fixed64-propose"}
    table = []
    for row in rows:
        case, movement = row["case_id"], row.get("data_movement_bytes", {})
        cycles = row.get("makespan_cycles")
        ref = fixed[case].get("makespan_cycles")
        table.append({"case_id": case, "variant": row["variant"], "status": row["status"],
                      "makespan_cycles": cycles, "singlecore_cycles": base[case],
                      "singlecore_speedup": base[case] / cycles if cycles else None,
                      "cycles_change_vs_fixed64_percent": (cycles / ref - 1) * 100 if cycles and ref else None,
                      "solver_wall_seconds": row["solver"]["wall_seconds"],
                      "evaluation_wall_seconds": row.get("evaluation", {}).get("wall_seconds"),
                      "extra_ddr_bytes": movement.get("added_copy_bytes"),
                      "scheduled_copy_bytes": movement.get("scheduled_copy_bytes"),
                      "spill_bytes": movement.get("spill_added_copy_bytes"), "task_count": row.get("task_count")})
    with (out / "comparison.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]))
        writer.writeheader(); writer.writerows(table)
    summary = {"scope": "4 public development graphs, P1 k=4, one trial per variant; not full 100 or independent held-out acceptance.",
               "calls": completion["calls"], "batch_wall_seconds": completion["wall_seconds"], "variants": {}}
    for variant in protocol["variants"]:
        selected = [r for r in table if r["variant"] == variant and r["status"] == "ok"]
        timings = sorted(r["solver_wall_seconds"] for r in selected)
        index = (len(timings) - 1) * 0.95
        lo = int(index); hi = min(lo + 1, len(timings) - 1)
        summary["variants"][variant] = {
            "n": len(selected), "mean_singlecore_speedup": statistics.mean(r["singlecore_speedup"] for r in selected),
            "solver_wall_p50_seconds": statistics.median(timings),
            "solver_wall_p95_seconds": timings[lo] + (timings[hi] - timings[lo]) * (index - lo),
            "p95_definition": "linear interpolation at 0.95*(n-1)", "solver_wall_max_seconds": max(timings),
            "solver_wall_sum_seconds": sum(timings), "external_e0_wall_sum_seconds": sum(r["evaluation_wall_seconds"] for r in selected),
            "cycles_wins_ties_losses_vs_fixed64": [sum(r["cycles_change_vs_fixed64_percent"] < 0 for r in selected), sum(r["cycles_change_vs_fixed64_percent"] == 0 for r in selected), sum(r["cycles_change_vs_fixed64_percent"] > 0 for r in selected)],
        }
    summary["failures"] = [r for r in rows if r["status"] != "ok"]
    dump(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if args.report_only:
        report()
        return
    if args.output is None:
        parser.error("--output is required unless --report-only")
    out = ROOT / OUTPUT
    protocol = json.loads((out / "protocol.json").read_bytes())
    rows = json.loads((out / "rows.json").read_bytes())
    completion = json.loads((out / "completion.json").read_bytes())
    assert protocol["solver_commit"] == SOLVER and protocol["baseline_commit"] == BASELINE
    assert sum(r["calls"]["solver"] for r in rows) == completion["calls"]["solver"]
    assert sum(r["calls"]["E0"] for r in rows) == completion["calls"]["E0"]
    records = []
    for row in rows:
        case, variant = row["case_id"], row["variant"]
        old = variant == "fixed64-propose"
        folder = Path(OUTPUT) / f"{case}-{variant}"
        artifacts = {"run": artifact(folder / "run.json"), "manifest": artifact(Path(OUTPUT) / "protocol.json")}
        plan_path = folder / f"case_{case}_multicore_res.json"
        if (ROOT / plan_path).exists():
            artifacts["plan"] = artifact(plan_path)
            assert artifacts["plan"]["sha256"] == row["plan_sha256"]
        result = None
        for name in ("result", "trace"):
            item = row["artifacts"].get(name + ".json")
            if item:
                packed = (ROOT / item["path"]).read_bytes()
                assert sha(packed) == item["sha256"]
                raw = gzip.decompress(packed)
                assert sha(raw) == item["raw_sha256"]
                artifacts[name] = {"path": item["path"], "sha256": item["sha256"]}
                if name == "result":
                    result = json.loads(raw)
        if (ROOT / folder / "result.txt").exists():
            artifacts["log"] = artifact(folder / "result.txt")
        movement = result["data_movement_bytes"] if result else {}
        if row["status"] == "ok":
            assert result["makespan"] == row["makespan_cycles"] and type(result["makespan"]) is type(row["makespan_cycles"])
            assert result["scene"] == "A" and result["num_cores"] == 4
            assert movement == row["data_movement_bytes"]
        baseline_folder = Path("results/benchmark-board/official-singlecore-20260924") / case
        baseline_run = json.loads((ROOT / baseline_folder / "run.json").read_bytes())
        for key, expected in (("graph_sha256", protocol["input_sha256"][f"case_{case}.json"]),
                              ("config_sha256", protocol["input_sha256"]["config.txt"]),
                              ("official_code_hash", protocol["official_code_hash"])):
            assert baseline_run[key] == expected
        baseline = {"graph_sha256": baseline_run["graph_sha256"], "config_sha256": baseline_run["config_sha256"],
                    "official_sha256": baseline_run["official_code_hash"], "route": "E0",
                    "entrypoint": "singlecore_evaluate.evaluate_singlecore",
                    "result": artifact(baseline_folder / "result.json.gz")}
        provenance = {
            "producer_session": SESSION, "task_url": protocol["task_url"],
            "solver": {"source": source(row["solver_commit"], "src/q1/search.py" if old else "src/q1_yuanzhifang/construct.py", "proposal (--kind fixed64)" if old else "construct"),
                       "authors": ["NikolaStarx"] if old else ["yuanzhifang30-sudo"],
                       "method": "Seed 0 randomized topological blocks of 64 with official local Task-duration placement; one candidate, no full online score." if old else "Count weak components: component-pack if count >= cores, otherwise chain-wave; graph-only decision, no measured score lookup",
                       "references": [protocol["task_url"]], "upstream": [], "selected_algorithm_id": None if old else "q1-antichain-pack", "selected_solver_commit": None if old else SOLVER},
            "runner": {"source": source(row["runner_commit"], "src/q1_yuanzhifang/benchmark_b.py", "main"),
                       "argv": row["solver"]["argv"], "working_directory": "."},
            "environment": {k: protocol["environment"][k] for k in ("os", "cpu", "gpu", "ram_bytes", "python", "dependencies", "threads", "workers", "peak_rss_bytes")},
            "measurement": {"started_at": row["started_at"], "finished_at": row["finished_at"], "seed": 0 if old else None,
                            "repeat_index": 0, "cold_start": True, "solver_scope": protocol["solver_scope"],
                            "evaluation_scope": protocol["evaluation_scope"],
                            "budget": {"wall_seconds": 20, "candidate_limit": 1, "stop_reason": row["status"] + "; no retries; batch " + completion["status"]},
                            "calls": row["calls"], "offline_costs": protocol["preparation"] + " Frozen singlecore denominator reused, 0 new singlecore calls.",
                            "failure": row["failure"]},
            "missing_reasons": {"provenance.environment.peak_rss_bytes": "Peak child-process RSS was not instrumented; physical RAM and concurrency are recorded."},
        }
        if not old:
            provenance["missing_reasons"]["provenance.measurement.seed"] = "Deterministic construction has no seed parameter or RNG."
        records.append({
            "attempt_id": f"fang-q1-stage-b-20260924-{variant}-{case}-k4-r0", "revision": 1,
            "run_id": "fang-q1-stage-b-20260924-" + variant,
            "algorithm_id": "q1-bounded-search" if old else "q1-antichain-pack", "algorithm_name": "有预算结构候选搜索" if old else "P1反链打包构造",
            "variant": variant, "solver_commit": row["solver_commit"], "parameters": {"cores": 4, "seed": 0 if old else None, "candidate_limit": 1,
                "kind": "fixed64" if old else variant, "block_size": 64 if old else None, "batch_budget": protocol["budget"],
                "batch_actual_calls": completion["calls"], "batch_wall_seconds": completion["wall_seconds"], "internal_full_scores": 0,
                "official_local_task_compilation_calls": 1 if old else 0,
                "selected_variant": "fixed64" if old else row["diagnostics"]["selected_variant"]},
            "problem": "P1", "case_id": case, "cores": 4, "status": "failed" if row["status"] == "infrastructure_failure" else row["status"],
            "metrics": {"makespan_cycles": row.get("makespan_cycles"), "solver_wall_seconds": row["solver"]["wall_seconds"],
                        "evaluation_wall_seconds": row.get("evaluation", {}).get("wall_seconds"), "ddr_bytes": movement.get("scheduled_copy_bytes"),
                        "extra_ddr_bytes": movement.get("added_copy_bytes"), "spill_bytes": movement.get("spill_added_copy_bytes"), "cache_hit_rate": None},
            "evaluator": {"route": "E0", "commit": row["runner_commit"], "entrypoint": "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"},
            "identity": {"graph_sha256": protocol["input_sha256"][f"case_{case}.json"], "config_sha256": protocol["input_sha256"]["config.txt"],
                         "official_sha256": protocol["official_code_hash"], "plan_sha256": row.get("plan_sha256")},
            "artifacts": artifacts, "runtime_id": "fang-windows-q1-stage-b-20260924", "observed_at": row["finished_at"],
            "timing": {"solver_includes_evaluation": False, "evaluation_precision": "perf_counter seconds; full new CLI process", "utc": "UTC ISO8601 Z"},
            "provenance": provenance,
            "notes": ["4 public development graphs, k=4; not held-out or full-100 validation.", "One worker for this batch; host not exclusively reserved. Cold process, not cold OS disk cache.", protocol["baseline_internal_work"]] if old else ["4 public development graphs, k=4; not held-out or full-100 validation.", "One worker for this batch; host not exclusively reserved. Cold process, not cold OS disk cache."],
            "source_url": protocol["task_url"], "baseline": baseline, "cache_pair": None,
        })
    dump(args.output, {"schema_version": 1, "submission_version": 1, "records": records})
    print(json.dumps({"records": len(records), "output": args.output.as_posix(), "exported_at": utc()}))


if __name__ == "__main__":
    main()
