"""Export separate diagnostic attempts and an explicit timeout-fill quality view.

The original 500-slot table remains unchanged. Only successful predeclared
diagnostics whose plan hash equals their original plan fill an old missing slot.
No minimum-of-multiple-scores or mixed-algorithm selection is performed.
"""
from collections import Counter
from copy import deepcopy
import csv
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import bounded_timeout_e0 as runner
from src.q1_benchmarks.bounded_matrix_report import frozen_json, stat, write_feeds
h = runner.h


def main():
    batch = runner.RESULT_ROOT / sys.argv[1]
    meta = h.read(batch / "batch.json")
    if meta["status"] == "running":
        raise RuntimeError("Wait for diagnostic execution to finish")
    cfg = meta["manifest"]
    old = frozen_json(cfg["previous_commit"], cfg["previous_batch"] + "/board-feed.json")
    old_index = {(r["case_id"], r["cores"]):r for r in old["records"]}
    original = frozen_json(cfg["previous_commit"], cfg["previous_batch"] + "/full500-comparison.json")
    original_summary = frozen_json(cfg["previous_commit"], cfg["previous_batch"] + "/full500-summary.json")
    original_batch = frozen_json(cfg["previous_commit"], cfg["previous_batch"] + "/batch.json")
    records, comparisons = [], []
    for c in cfg["cells"]:
        case, cores = c["case_id"], c["cores"]
        folder = batch / "cells" / case / f"k{cores}"
        r = h.read(folder / "run.json")
        record = deepcopy(old_index[case, cores])
        assert record["status"] == "timeout" and record["attempt_id"] == c["old_attempt_id"]
        d = r.get("data_movement_bytes",{})
        metrics = {"makespan_cycles":r["makespan_cycles"],"solver_wall_seconds":r.get("solver",{}).get("wall_seconds"),
                   "evaluation_wall_seconds":r.get("evaluation",{}).get("wall_seconds"),"ddr_bytes":d.get("scheduled_copy_bytes"),
                   "extra_ddr_bytes":d.get("added_copy_bytes"),"spill_bytes":d.get("spill_added_copy_bytes")}
        record.update(attempt_id=f"nikolastarx-{batch.name}-P1-{case}-k{cores}-r0",revision=1,run_id=batch.name,status=r["status"],
                      metrics=metrics,observed_at=r["finished_at"])
        record["parameters"].update(workers=1,evaluation_timeout_seconds=180,batch_timeout_seconds=1200,stop_policy=cfg["stop_policy"],
                                    base_selected=r.get("diagnostics",{}).get("base",{}).get("selected"))
        record["identity"]["plan_sha256"] = r.get("plan_sha256")
        record["artifacts"] = {k:v for k,v in r["artifacts"].items() if k != "diagnostics"}
        record["artifacts"]["run"] = h.artifact(folder / "run.json")
        prov = record["provenance"]
        prov["runner"] = {"source":h.source(meta["runner_commit"],meta["runner_path"],"run"),"argv":meta["runner_argv"],"working_directory":"."}
        prov["environment"] = meta["environment"]
        prov["measurement"].update(started_at=r["started_at"],finished_at=r["finished_at"],calls=r["calls"],failure=r["failure"],
            budget={"wall_seconds":30,"candidate_limit":1,"stop_reason":"identical plan external E0 complete" if r["status"] == "ok" else r.get("not_run_reason",r.get("failure_class","failure"))},
            offline_costs=f"uv sync --locked and exact ZIP materialization ({meta['input_preparation_wall_seconds']} seconds); no search/training. Previous failed attempts remain recorded and are not hidden in the new wall. Plan SHA guard is controller validation outside constructor time. External E0 has new 180s limit; original limit was 60s.")
        missing = {"provenance.environment.threads":"Actual thread count not sampled; OMP/BLAS/MKL child environments set to 1",
                   "provenance.environment.peak_rss_bytes":"No per-child peak RSS sampling","provenance.measurement.seed":"Deterministic construction has no RNG"}
        for key in ("started_at","finished_at"):
            if r[key] is None:
                missing[f"provenance.measurement.{key}"] = r.get("not_run_reason","not started")
        if r["failure"]:
            for key in ("exit_code","elapsed_seconds"):
                if r["failure"].get(key) is None:
                    missing[f"provenance.measurement.failure.{key}"] = "No completed process receipt for this supervisory failure"
        prov["missing_reasons"] = missing
        record["notes"] = [cfg["interpretation"],cfg["resource_agreement"],cfg["stop_policy"],
            f"Independent diagnostic new attempt for prior timeout {c['old_attempt_id']} at {cfg['previous_commit']}; old attempt is permanently retained.",
            "Original official baseline bytes are inherited from the frozen prior batch in this Git commit; no new baseline evaluation."]
        if r["status"] == "ok":
            assert r["plan_bytes_equal"] is True and r["plan_sha256"] == c["old_plan_sha256"]
        records.append(record)
        old_row = next(x for x in original if (x["case"],x["cores"]) == (case,cores))
        row = deepcopy(old_row)
        row.update(metrics)
        makespan = r["makespan_cycles"]
        row.update(status=r["status"],attempt_id=record["attempt_id"],run_id=batch.name,reused=False,
            singlecore_speedup=row["baseline_cycles"] / makespan if makespan else None,
            fixed64_speedup=row["fixed64_cycles"] / makespan if makespan else None,
            failure=r["failure"],source_run=h.artifact(folder / "run.json"),plan_bytes_equal=r["plan_bytes_equal"],prior_attempt_id=c["old_attempt_id"])
        comparisons.append(row)
    feeds = write_feeds(batch,records)
    h.write(batch / "comparison.json",comparisons)
    h.write(batch / "feed-manifest.json",{"run_id":batch.name,"feeds":feeds,"new_attempts":len(records)})
    selected = {(r["case"],r["cores"]):dict(r,reused=True) for r in original}
    for r in comparisons:
        if r["status"] == "ok":
            selected[r["case"],r["cores"]] = r
    full = [selected[k] for k in sorted(selected)]
    by_core = {}
    for k in range(1,6):
        rows = [r for r in full if r["cores"] == k]
        ok = [r for r in rows if r["status"] == "ok"]
        by_core[str(k)] = {"requested":len(rows),"successful":len(ok),"status_counts":dict(Counter(r["status"] for r in rows)),
            "mean_baseline_speedup":statistics.mean(r["singlecore_speedup"] for r in ok) if ok else None,
            "mean_fixed64_baseline_speedup_same_success_subset":statistics.mean(r["baseline_cycles"]/r["fixed64_cycles"] for r in ok) if ok else None,
            "versus_fixed64":{label:sum(op(r["makespan_cycles"],r["fixed64_cycles"]) for r in ok) for label,op in
                               (("better",lambda a,b:a<b),("equal",lambda a,b:a==b),("worse",lambda a,b:a>b))}}
    summary = {"solver_commit":h.SOLVER,"algorithm_id":cfg["algorithm_id"],"parameters":{"packet_factor":4,"trigger_ops":4096,"chunk_ops":1024},
        "selection_rule":"Keep original 496 successes; fill only old E0-timeout slots using successful new attempts from the four-cell predeclared diagnostic with exactly equal plan SHA. No best-of scores. Old original 496/500 table and all four failed attempts remain unchanged.",
        "original_source":{"commit":cfg["previous_commit"],"path":cfg["previous_batch"] + "/full500-comparison.json"},
        "original_quality_status_counts":original_summary["status_counts"],
        "diagnostic_run_id":batch.name,"diagnostic_calls":meta["actual_calls"],"diagnostic_status":meta["status"],
        "diagnostic_started_at":meta["started_at"],"diagnostic_finished_at":meta["finished_at"],"diagnostic_batch_wall_seconds":meta["batch_wall_seconds"],
        "cumulative_fixed_method_calls":{"solver":100+original_batch["actual_calls"]["solver"]+meta["actual_calls"]["solver"],
                                         "E0":100+original_batch["actual_calls"]["E0"]+meta["actual_calls"]["E0"],"E1":0,"E2":0},
        "cost_accounting":"Includes original 100 k4 attempts, original 400 attempts (all four timeouts retained), and these new diagnostic attempts; no baseline calls. Earlier different algorithm batches are separate research costs.",
        "timing_clock_boundary":"batch_wall_seconds includes controller preflight validation before batch.json.started_at; child solver/E0 timers retain their exact per-process boundaries.",
        "by_core":by_core,"status_counts":dict(Counter(r["status"] for r in full)),"diagnostics":comparisons,
        "wall_time_limit":"Original k4 used one worker; original 400 used two; this diagnostic uses one with longer E0 cap. Keep times by actual run; do not infer a controlled speedup or cause of old timeout.",
        "scope":"Fixed-algorithm official quality table, including explicitly selected follow-up evidence. Public development dataset, not blind independent acceptance or an optimality claim."}
    summary["fixed64_regressions"] = [{k:r[k] for k in ("case","cores","makespan_cycles","fixed64_cycles","fixed64_speedup")}
                                       for r in full if r["status"] == "ok" and r["makespan_cycles"] > r["fixed64_cycles"]]
    summary["adjacent_core_regressions"] = []
    for case in sorted({r["case"] for r in full}):
        for k in range(1,5):
            a,b = selected[case,k], selected[case,k+1]
            if a["status"] == b["status"] == "ok" and b["makespan_cycles"] > a["makespan_cycles"]:
                summary["adjacent_core_regressions"].append({"case":case,"from_cores":k,"to_cores":k+1,
                    "from_makespan":a["makespan_cycles"],"to_makespan":b["makespan_cycles"],
                    "increase_cycles":b["makespan_cycles"]-a["makespan_cycles"],
                    "increase_ratio":b["makespan_cycles"]/a["makespan_cycles"]-1})
    summary["adjacent_core_interpretation"] = "Regressions of this fixed constructor at adjacent core counts, not of the optimum over feasible core-budget plans. No cross-core fallback was applied in this experiment."
    h.write(batch / "quality-regressions.json",{k:summary[k] for k in ("fixed64_regressions","adjacent_core_regressions","adjacent_core_interpretation")})
    h.write(batch / "full500-filled-comparison.json",full)
    h.write(batch / "full500-filled-summary.json",summary)
    with (batch / "full500-filled-comparison.csv").open("w",newline="") as f:
        columns=["case","cores","status","makespan_cycles","baseline_cycles","singlecore_speedup","fixed64_cycles","fixed64_speedup","solver_wall_seconds","evaluation_wall_seconds","extra_ddr_bytes","spill_bytes","run_id","attempt_id","reused"]
        w=csv.DictWriter(f,fieldnames=columns,extrasaction="ignore",lineterminator="\n");w.writeheader();w.writerows(full)
    lines=["# Separate diagnostic of four external E0 timeouts","",f"Solver `{h.SOLVER}`; runner `{meta['runner_commit']}`. Original matrix `{cfg['previous_commit']}` is unchanged.","",
        f"UTC {meta['started_at']} to {meta['finished_at']}, batch wall {meta['batch_wall_seconds']:.3f}s; calls `{meta['actual_calls']}`, status `{meta['status_counts']}`. Batch wall also includes preflight validation before the recorded batch started_at.","",
        "Budget: one worker, at most four new constructors and four new E0 calls, constructor30s/E0180s/batch1200s; stop at first new failure, no additional round. Reconstructed plan must exactly match old failed-plan SHA before E0.","",
        "| Case/core | Status | Same plan bytes | Makespan cycles | Constructor seconds | External E0 seconds |",
        "| --- | --- | --- | --- | --- | --- |"]
    for r in comparisons:
        lines.append(f"| {r['case']}/k{r['cores']} | {r['status']} | {r['plan_bytes_equal']} | {r['makespan_cycles']} | {r['solver_wall_seconds']} | {r['evaluation_wall_seconds']} |")
    lines += ["",summary["selection_rule"],"","| Cores | Valid / requested | Mean singlecore / Makespan |","| --- | --- | --- |"]
    for k,r in by_core.items():
        lines.append(f"| {k} | {r['successful']}/{r['requested']} | {r['mean_baseline_speedup']:.9f} |")
    lines += ["",cfg["interpretation"],"",cfg["resource_agreement"],"",summary["wall_time_limit"],"",
        f"Against same-core fixed64, k1 has {by_core['1']['versus_fixed64']['worse']} regressions; k2/k3/k4 have none; k5 has {by_core['5']['versus_fixed64']['worse']}. All negative cases and {len(summary['adjacent_core_regressions'])} adjacent-core regressions are retained in `quality-regressions.json` and the full comparison. Full coverage is not dominance over every comparator. No cross-core fallback was applied; adjacent regressions do not prove worse core-budget optima.","",
        f"`board-feed.json` contains only new diagnostic attempts. `full500-filled-*` is a declared follow-up evidence view; `full500-comparison.json` in the original matrix directory retains the first-pass missing scores. Fixed-method cumulative calls: `{summary['cumulative_fixed_method_calls']}`, including all original failures; no baseline rerun.","",
        "Original fixed64/singlecore evidence remains inherited in this commit. `PRECHECK.json` is the read-only v1 precheck; fixed Git artifact hashes are checked separately after commit with `src/q1_benchmarks/bounded_matrix_verify.py`. No central ledger write or publication by this agent.",""]
    (batch / "README.md").write_text("\n".join(lines))
    print(json.dumps({"records":len(records),"diagnostic_statuses":meta["status_counts"],"quality_statuses":summary["status_counts"],"by_core":by_core},ensure_ascii=False))


if __name__ == "__main__":
    main()
