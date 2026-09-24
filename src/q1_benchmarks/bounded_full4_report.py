"""Read-only 100-case aggregate: 99 new attempts plus exact prior case014.

No solver or evaluator calls. Produces aggregate evidence, never a duplicate
board attempt for the already published case014.
"""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OLD_COMMIT = "4d374dc25b5698491ddbb92837789a23a4ad3102"
OLD_PATH = "results/a/q1-bounded-probe-20260924/20260924T1432Z-bounded014/board-feed.json"
SOLVER = "05f8fa0f7e52f5914f14815f6bdbcb851b631556"


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def blob(path):
    return subprocess.check_output(["git", "show", f"{OLD_COMMIT}:{path}"], cwd=ROOT)


def main():
    batch = ROOT / sys.argv[1]
    if not batch.resolve().is_relative_to(ROOT / "results/a/q1-bounded-full4-20260924"):
        raise ValueError("Wrong report destination")
    feed = json.loads((batch / "board-feed.json").read_text())
    rows = json.loads((batch / "comparison.json").read_text())
    old_raw = blob(OLD_PATH)
    prior = json.loads(old_raw)["records"][0]
    if len(feed["records"]) != 99 or prior["case_id"] != "014" or prior["cores"] != 4:
        raise ValueError("Unexpected execution grid")
    attempts = [*feed["records"], prior]
    assert sorted(r["case_id"] for r in attempts) == [f"{i:03d}" for i in range(1, 101)]
    assert len({r["attempt_id"] for r in attempts}) == 100
    for r in attempts:
        assert r["solver_commit"] == SOLVER
        assert r["cores"] == 4 and r["parameters"]["packet_factor"] == 4
        assert r["algorithm_id"] == "q1-bounded-component-tasks"
        assert r["parameters"]["trigger_ops"] ==4096 and r["parameters"]["chunk_ops"] ==1024
    reference = batch / "references" / "reused-case014"
    reference.mkdir(parents=True, exist_ok=True)
    (reference / "original-board-feed.json").write_bytes(old_raw)
    preserved = {}
    for name, item in {**prior["artifacts"], "baseline": prior["baseline"]["result"]}.items():
        raw = blob(item["path"])
        assert hashlib.sha256(raw).hexdigest() == item["sha256"]
        local = reference / (name + "-" + Path(item["path"]).name)
        local.write_bytes(raw)
        preserved[name] = {"original": item, "preserved_path": local.relative_to(ROOT).as_posix()}
    old_folder = OLD_PATH.rsplit("/", 1)[0]
    old_comparison = json.loads(blob(old_folder + "/comparison.json"))[0]
    old_diagnostics_raw = blob(old_folder + "/cells/014/k4/diagnostics.json")
    (reference / "diagnostics.json").write_bytes(old_diagnostics_raw)
    old_diagnostics = json.loads(old_diagnostics_raw)
    rows.append(old_comparison)
    by_case = {r["case_id"]: r for r in attempts}
    meta = json.loads((batch / "batch.json").read_text())
    for row in rows:
        case = row["case"]
        r = by_case[case]
        row["attempt_id"] = r["attempt_id"]
        row["run_id"] = r["run_id"]
        row["reused"] = case == "014"
        dpath = batch / "cells" / case / "k4/diagnostics.json"
        diag = old_diagnostics if case == "014" else (json.loads(dpath.read_text()) if dpath.exists() else {})
        frontier = diag.get("base", {})
        base = frontier.get("base", {})
        chunks = diag.get("chunks", {})
        row.update(compute_ops=base.get("compute_ops"), components=base.get("components"),
                   largest_component_ops=base.get("largest_component_ops"),
                   actual_tasks=chunks.get("tasks_after"), selection_reason=frontier.get("reason"),
                   frontier_packets=frontier.get("frontier_packet_count"), tail_ops=frontier.get("tail_ops"),
                   oversized_tasks_processed=len(chunks.get("split_tasks", [])),
                   oversized_task_splits=sum(len(t["new_tasks"]) > 1 for t in chunks.get("split_tasks", [])),
                   indivisible_oversize_count=len(chunks.get("oversize_indivisible_components", [])))
    rows.sort(key=lambda r: r["case"])
    ok = [r for r in rows if r["status"] == "ok"]
    summary = {
        "solver_commit": SOLVER, "packet_factor": 4, "trigger_ops":4096, "chunk_ops":1024, "cores": 4,
        "scope": "Fixed-method public development coverage; one recorded attempt per case across two actual runs; not blind or independent acceptance",
        "new_execution_calls": meta["actual_calls"],
        "reused_case014": {"source_commit": OLD_COMMIT, "source_feed": OLD_PATH, "source_feed_sha256": hashlib.sha256(old_raw).hexdigest(),
                           "attempt_id": prior["attempt_id"], "preserved_artifacts": preserved, "new_calls": 0},
        "coverage": {"requested_cases": 100, "successful_cases": len(ok), "new_records": 99, "reused_records": 1,
                     "statuses": dict(Counter(r["status"] for r in rows)), "failed_or_unrun_cases":[{"case":r["case"],"status":r["status"]} for r in rows if r["status"] != "ok"]},
        "mean_baseline_speedup": statistics.mean(r["singlecore_speedup"] for r in ok) if ok else None,
        "mean_fixed64_baseline_speedup_same_success_subset": statistics.mean(r["baseline_cycles"] / r["fixed64_cycles"] for r in ok) if ok else None,
        "versus_fixed64": {"better": sum(r["makespan_cycles"] < r["fixed64_cycles"] for r in ok),
                           "equal": sum(r["makespan_cycles"] == r["fixed64_cycles"] for r in ok),
                           "worse": sum(r["makespan_cycles"] > r["fixed64_cycles"] for r in ok)},
        "versus_singlecore": {"better": sum(r["makespan_cycles"] < r["baseline_cycles"] for r in ok),
                              "equal": sum(r["makespan_cycles"] == r["baseline_cycles"] for r in ok),
                              "worse": sum(r["makespan_cycles"] > r["baseline_cycles"] for r in ok)},
        "base_selection_counts": dict(Counter(r["base_selected"] for r in ok)),
        "cases_with_oversized_tasks_processed": sum(r["oversized_tasks_processed"]>0 for r in ok),
        "cases_with_task_splitting": sum(r["oversized_task_splits"]>0 for r in ok),
        "cases_with_indivisible_oversize": sum(r["indivisible_oversize_count"]>0 for r in ok),
        "spill_case_count": sum((r["spill_bytes"] or 0) > 0 for r in ok),
        "observed_solver_wall_seconds": {"median": statistics.median(r["solver_wall_seconds"] for r in ok),
                                          "maximum": max(r["solver_wall_seconds"] for r in ok),
                                          "minimum": min(r["solver_wall_seconds"] for r in ok)},
        "timing_limit": "Fresh interpreter, OS cache not flushed, non-exclusive host; this is an observed cross-case sample, not controlled repeated latency or program-speedup proof",
        "worst_against_fixed64": sorted(ok, key=lambda r: r["fixed64_speedup"])[:12],
        "worst_against_singlecore": sorted(ok, key=lambda r: r["singlecore_speedup"])[:12],
        "slowest_observed_constructors": sorted(ok, key=lambda r: -r["solver_wall_seconds"])[:8],
    }
    write(batch / "full100-comparison.json", rows)
    write(batch / "full100-summary.json", summary)
    with (batch / "full100-comparison.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({k: v for k, v in summary.items() if k not in {"reused_case014", "worst_against_fixed64", "worst_against_singlecore", "slowest_observed_constructors"}}, indent=2))


if __name__ == "__main__":
    main()
