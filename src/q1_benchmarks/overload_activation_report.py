"""Read-only report for the frozen overload activation probes; no solver/E0 calls."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import statistics
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import bounded_full4_e0 as h
from src.q1.component_overload import derive_multicore_plan, validate_task_order

PRIOR_PAIR = ("11491834c74b5d5930af11ea70e9e452d4f7666c", "results/a/q1-overload-probe-20260925/20260924T1629Z-overload2")
HEAVY = [
    ("fe67740a90857e127c5d3996d1c444a083efcebc", "results/a/q1-heavy-suffix-20260924/20260924T1556Z-heavy2/board-feed.json"),
    ("5e6db81204fd8dcf8c9557770c3d08882e8cf630", "results/a/q1-heavy-suffix-more-20260925/20260924T1605Z-heavy3/board-feed.json"),
]


def fixed_json(commit, path):
    return json.loads(h.git("show", f"{commit}:{path}"))


def quality(rows):
    ok = [r for r in rows if r["status"] == "ok"]
    return {
        "declared": len(rows), "successful": len(ok),
        "improved": sum(r["makespan_cycles"] < r["bounded_makespan_cycles"] for r in ok),
        "tied": sum(r["makespan_cycles"] == r["bounded_makespan_cycles"] for r in ok),
        "regressed": sum(r["makespan_cycles"] > r["bounded_makespan_cycles"] for r in ok),
        "mean_bounded_over_new": statistics.mean(r["bounded_over_new"] for r in ok) if ok else None,
        "regressions": [{"case": r["case"], "old": r["bounded_makespan_cycles"], "new": r["makespan_cycles"],
                         "percent_increase": 100 * (r["makespan_cycles"] / r["bounded_makespan_cycles"] - 1),
                         "extra_ddr_old": r["bounded_movement_bytes"]["added_copy_bytes"], "extra_ddr_new": r["extra_ddr_bytes"],
                         "spill_old": r["bounded_movement_bytes"]["spill_added_copy_bytes"], "spill_new": r["spill_bytes"]}
                        for r in ok if r["makespan_cycles"] > r["bounded_makespan_cycles"]],
    }


def report(batch):
    meta = h.read(batch / "batch.json")
    assert meta["status"] != "running"
    rows = h.read(batch / "comparison.json")
    by_case = {r["case"]: r for r in rows}
    checks = []
    with zipfile.ZipFile(ROOT / "data/raw/a/official-cases.zip") as archive:
        for case, cores in meta["cells"]:
            folder = batch / "cells" / case / f"k{cores}"
            run = h.read(folder / "run.json")
            if run["status"] != "ok":
                checks.append({"case": case, "status": run["status"], "check": "skipped without successful plan"})
                continue
            raw = archive.read(f"data/case_{case}.json")
            assert h.digest(raw) == run["graph_sha256"]
            planpath = folder / f"case_{case}_multicore_res.json"
            assert h.sha(planpath) == run["plan_sha256"]
            plan = h.read(planpath)
            plan["node_to_subgraph"] = {int(k): v for k, v in plan["node_to_subgraph"].items()}
            start = time.perf_counter()
            view = derive_multicore_plan(json.loads(raw), plan)
            validate_task_order(view)
            checks.append({"case": case, "cores": cores, "graph_sha256": run["graph_sha256"], "plan_sha256": run["plan_sha256"],
                           "check": "official derive/task order passed", "compute_ops": len(plan["node_to_subgraph"]),
                           "tasks": sum(map(len, plan["core_schedules"])), "validation_wall_seconds": time.perf_counter() - start})
    h.write(batch / "STRUCTURAL_CHECK.json", {"scope": "Read-only saved-plan official structural checks, no constructor/evaluator calls", "checks": checks})
    heavy_comparison = []
    for commit, path in HEAVY:
        for old in fixed_json(commit, path)["records"]:
            case = old["case_id"]
            current = by_case[case]
            saved = {}
            for name in ("plan", "result"):
                ref = old["artifacts"][name]
                raw = h.git("show", f"{commit}:{ref['path']}")
                assert h.digest(raw) == ref["sha256"]
                dest = batch / "references" / f"heavy-{case}-{name}-{Path(ref['path']).name}"
                dest.write_bytes(raw)
                saved[name] = h.artifact(dest)
            original = json.loads(gzip.decompress((ROOT / saved["result"]["path"]).read_bytes()))
            assert original["makespan"] == old["metrics"]["makespan_cycles"]
            assert original["scene"] == "A" and original["num_cores"] == current["cores"] == 5
            heavy_comparison.append({"case": case, "status": current["status"], "heavy_makespan": original["makespan"],
                                     "overload_makespan": current["makespan_cycles"],
                                     "heavy_over_overload": original["makespan"] / current["makespan_cycles"] if current["makespan_cycles"] else None,
                                     "heavy_extra_ddr": original["data_movement_bytes"]["added_copy_bytes"], "overload_extra_ddr": current["extra_ddr_bytes"],
                                     "heavy_spill": original["data_movement_bytes"]["spill_added_copy_bytes"], "overload_spill": current["spill_bytes"],
                                     "source_commit": commit, "source_feed": path, "attempt_id": old["attempt_id"], "preserved": saved})
    heavy_comparison.sort(key=lambda r: r["case"])
    h.write(batch / "heavy-comparison.json", heavy_comparison)
    prior_commit, prior_path = PRIOR_PAIR
    prior_rows = fixed_json(prior_commit, prior_path + "/comparison.json")
    combined = sorted(rows + prior_rows, key=lambda r: r["case"])
    assert len({r["case"] for r in combined}) == 18
    h.write(batch / "activation18-comparison.json", [
        {"case": r["case"], "cores": r["cores"], "status": r["status"],
         "bounded_makespan_cycles": r["bounded_makespan_cycles"], "overload_makespan_cycles": r["makespan_cycles"],
         "bounded_over_overload": r["bounded_over_new"],
         "bounded_extra_ddr_bytes": r["bounded_movement_bytes"]["added_copy_bytes"], "overload_extra_ddr_bytes": r["extra_ddr_bytes"],
         "bounded_spill_bytes": r["bounded_movement_bytes"]["spill_added_copy_bytes"], "overload_spill_bytes": r["spill_bytes"],
         "solver_wall_seconds": r["solver_wall_seconds"], "evaluation_wall_seconds": r["evaluation_wall_seconds"],
         "bounded_source_commit": r["bounded_source"]["commit"], "bounded_attempt_id": r["bounded_source"]["attempt_id"],
         "overload_evidence": {"commit": prior_commit, "path": prior_path} if r["case"] in {"050", "054"}
         else {"run_id": meta["run_id"], "path": str(batch.relative_to(ROOT))}}
        for r in combined])
    columns = ["case", "cores", "status", "bounded_makespan_cycles", "makespan_cycles", "bounded_over_new", "extra_ddr_bytes", "ddr_bytes", "spill_bytes", "solver_wall_seconds", "evaluation_wall_seconds"]
    with (batch / "comparison.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader(); writer.writerows({key: r[key] for key in columns} for r in rows)
    summary = {"scope": "16 new attempts plus 2 referenced original attempts from the same solver form the 18 predeclared activation set, not all 100 cases",
               "new16": quality(rows), "activation18": quality(combined),
               "prior_pair": {"commit": prior_commit, "path": prior_path, "policy": "Original attempts reused only; new feed has exactly 16 records"},
               "actual_new_calls": meta["actual_calls"], "activation_set_total_calls": {"solver": meta["actual_calls"]["solver"] + 2, "E0": meta["actual_calls"]["E0"] + 2, "E1": 0, "E2": 0},
               "heavy5": {"improved": sum(r["overload_makespan"] < r["heavy_makespan"] for r in heavy_comparison),
                          "regressed": sum(r["overload_makespan"] > r["heavy_makespan"] for r in heavy_comparison)},
               "solver_seconds_new16": {"min": min(r["solver_wall_seconds"] for r in rows), "max": max(r["solver_wall_seconds"] for r in rows), "mean": statistics.mean(r["solver_wall_seconds"] for r in rows)},
               "e0_seconds_new16": {"min": min(r["evaluation_wall_seconds"] for r in rows), "max": max(r["evaluation_wall_seconds"] for r in rows), "sum": sum(r["evaluation_wall_seconds"] for r in rows)}}
    h.write(batch / "activation-summary.json", summary)
    (batch / "preparation").mkdir(exist_ok=True)
    gate_dir = ROOT / "output/q1-overload-activation-20260925/preparation"
    for name in ("state.json", "controller-check.json", "source-check.json"):
        (batch / "preparation" / name).write_bytes((gate_dir / name).read_bytes())
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    report(parser.parse_args().batch.resolve())
