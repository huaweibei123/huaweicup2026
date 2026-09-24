"""Read-only 100-case aggregate: 99 new attempts plus exact prior case002.

No solver or evaluator calls. Produces aggregate evidence, never a duplicate
board attempt for the already published case002.
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
OLD_COMMIT = "bf65aaca608e0c41493eb29c8482712c0a8d2c73"
OLD_PATH = "results/a/q1-tree-fine-20260924/20260924T1422Z-treefine1/board-feed.json"
SOLVER = "409886dd4b17b589643d3f5a13af9e94a9783d73"


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def blob(path):
    return subprocess.check_output(["git", "show", f"{OLD_COMMIT}:{path}"], cwd=ROOT)


def main():
    batch = ROOT / sys.argv[1]
    if not batch.resolve().is_relative_to(ROOT / "results/a/q1-tree-full4-20260924"):
        raise ValueError("Wrong report destination")
    feed = json.loads((batch / "board-feed.json").read_text())
    rows = json.loads((batch / "comparison.json").read_text())
    old_raw = blob(OLD_PATH)
    prior = json.loads(old_raw)["records"][0]
    if len(feed["records"]) != 99 or prior["case_id"] != "002" or prior["cores"] != 4:
        raise ValueError("Unexpected execution grid")
    attempts = [*feed["records"], prior]
    assert sorted(r["case_id"] for r in attempts) == [f"{i:03d}" for i in range(1, 101)]
    assert len({r["attempt_id"] for r in attempts}) == 100
    for r in attempts:
        assert r["solver_commit"] == SOLVER
        assert r["cores"] == 4 and r["parameters"]["packet_factor"] == 4
        assert r["algorithm_id"] == "q1-tree-frontier-pack"
    reference = batch / "references" / "reused-case002"
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
    old_diagnostics_raw = blob(old_folder + "/cells/002/k4/diagnostics.json")
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
        row["reused"] = case == "002"
        dpath = batch / "cells" / case / "k4/diagnostics.json"
        diag = old_diagnostics if case == "002" else (json.loads(dpath.read_text()) if dpath.exists() else {})
        base = diag.get("base", {})
        row.update(compute_ops=base.get("compute_ops"), components=base.get("components"),
                   largest_component_ops=base.get("largest_component_ops"),
                   actual_tasks=diag.get("tasks", base.get("tasks")), selection_reason=diag.get("reason"),
                   frontier_packets=diag.get("frontier_packet_count"), tail_ops=diag.get("tail_ops"))
    rows.sort(key=lambda r: r["case"])
    ok = [r for r in rows if r["status"] == "ok"]
    summary = {
        "solver_commit": SOLVER, "packet_factor": 4, "cores": 4,
        "scope": "Fixed-method public development coverage; one recorded attempt per case across two actual runs; not blind or independent acceptance",
        "new_execution_calls": meta["actual_calls"],
        "reused_case002": {"source_commit": OLD_COMMIT, "source_feed": OLD_PATH, "source_feed_sha256": hashlib.sha256(old_raw).hexdigest(),
                           "attempt_id": prior["attempt_id"], "preserved_artifacts": preserved, "new_calls": 0},
        "coverage": {"requested_cases": 100, "successful_cases": len(ok), "new_records": 99, "reused_records": 1,
                     "statuses": dict(Counter(r["status"] for r in rows))},
        "mean_baseline_speedup": statistics.mean(r["singlecore_speedup"] for r in ok) if ok else None,
        "mean_fixed64_baseline_speedup_same_success_subset": statistics.mean(r["baseline_cycles"] / r["fixed64_cycles"] for r in ok) if ok else None,
        "versus_fixed64": {"better": sum(r["makespan_cycles"] < r["fixed64_cycles"] for r in ok),
                           "equal": sum(r["makespan_cycles"] == r["fixed64_cycles"] for r in ok),
                           "worse": sum(r["makespan_cycles"] > r["fixed64_cycles"] for r in ok)},
        "versus_singlecore": {"better": sum(r["makespan_cycles"] < r["baseline_cycles"] for r in ok),
                              "equal": sum(r["makespan_cycles"] == r["baseline_cycles"] for r in ok),
                              "worse": sum(r["makespan_cycles"] > r["baseline_cycles"] for r in ok)},
        "selection_counts": dict(Counter(r["selected"] for r in ok)),
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
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({k: v for k, v in summary.items() if k not in {"reused_case002", "worst_against_fixed64", "worst_against_singlecore", "slowest_observed_constructors"}}, indent=2))


if __name__ == "__main__":
    main()
