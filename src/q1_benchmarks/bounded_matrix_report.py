"""Read-only v1 export and fixed-method 500-cell report; never invokes a solver.

Common schema fields come from the frozen same-algorithm k4 delivery. Every
per-attempt field is rebuilt from the new receipt; k4 retains original attempts
in the aggregate only. Feed sharding obeys the 8 MiB submission limit.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime
import gzip
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import bounded_matrix_e0 as m

h = m.h
K4 = "results/a/q1-bounded-full4-20260924/20260924T1439Z-boundedfull4-99"


def frozen_json(commit, path):
    return json.loads(h.git("show", f"{commit}:{path}"))


def stat(values):
    values = [x for x in values if x is not None]
    return {"n": len(values), "sum": sum(values), "min": min(values),
            "median": statistics.median(values), "max": max(values)} if values else {"n": 0}


def write_feeds(batch, records):
    def payload(items):
        return json.dumps({"schema_version": 1, "submission_version": 1, "records": items},
                          ensure_ascii=False, indent=2, allow_nan=False).encode() + b"\n"
    shards, current = [], []
    for record in records:
        if len(payload(current + [record])) > 8 * 1024**2:
            if not current:
                raise RuntimeError("One record exceeds feed limit")
            shards.append(current)
            current = []
        current.append(record)
    if current:
        shards.append(current)
    paths = []
    for i, items in enumerate(shards, 1):
        path = batch / ("board-feed.json" if len(shards) == 1 else f"board-feed-{i:03d}.json")
        path.write_bytes(payload(items))
        paths.append(dict(h.artifact(path), records=len(items)))
    return paths


def export(batch):
    meta = h.read(batch / "batch.json")
    if meta["status"] == "running":
        raise RuntimeError("Final export requires a stopped/completed batch")
    cfg = meta["manifest"]
    assert meta["solver_commit"] == h.SOLVER
    old = frozen_json(h.OLD, h.OLD_FEED)
    old_index = {(r["case_id"], r["cores"]): r for r in old["records"]}
    template = frozen_json(m.SUPPORT_COMMIT, K4 + "/board-feed.json")["records"][0]
    assert template["solver_commit"] == meta["solver_commit"]
    references = batch / "references"
    references.mkdir(exist_ok=True)
    base_cache, records, comparisons, previous_rows = {}, [], [], []
    for case, cores in meta["cells"]:
        folder = batch / "cells" / case / f"k{cores}"
        run = h.read(folder / "run.json")
        previous = old_index[case, cores]
        raw = h.git("show", f"{h.OLD}:{previous['artifacts']['result']['path']}")
        assert h.digest(raw) == previous["artifacts"]["result"]["sha256"]
        assert json.loads(gzip.decompress(raw))["makespan"] == previous["metrics"]["makespan_cycles"]
        previous_rows.append(previous)
        if case not in base_cache:
            b = previous["baseline"]
            raw = h.git("show", f"{h.OLD}:{b['result']['path']}")
            assert h.digest(raw) == b["result"]["sha256"]
            path = references / f"singlecore-{case}.json.gz"
            path.write_bytes(raw)
            base_cache[case] = dict(b, result=h.artifact(path)), json.loads(gzip.decompress(raw))["makespan"]
        baseline, baseline_cycles = base_cache[case]
        diag = run.get("diagnostics", {})
        movement = run.get("data_movement_bytes", {})
        metrics = {"makespan_cycles": run["makespan_cycles"],
                   "solver_wall_seconds": run.get("solver", {}).get("wall_seconds"),
                   "evaluation_wall_seconds": run.get("evaluation", {}).get("wall_seconds"),
                   "ddr_bytes": movement.get("scheduled_copy_bytes"),
                   "extra_ddr_bytes": movement.get("added_copy_bytes"), "spill_bytes": movement.get("spill_added_copy_bytes")}
        record = deepcopy(template)
        record.update(attempt_id=f"nikolastarx-{batch.name}-P1-{case}-k{cores}-r0", revision=1,
                      run_id=batch.name, case_id=case, cores=cores, status=run["status"], metrics=metrics,
                      observed_at=run["finished_at"], baseline=baseline)
        record["parameters"].update(cores=cores, base_selected=diag.get("base", {}).get("selected"),
                                    batch_timeout_seconds=cfg["batch_timeout_seconds"], workers=cfg["workers"], stop_policy=cfg["stop_policy"])
        record["identity"] = {"graph_sha256": run["graph_sha256"], "config_sha256": meta["config_sha256"],
                              "official_sha256": meta["official_code_hash"], "plan_sha256": run.get("plan_sha256")}
        record["artifacts"] = {k: v for k, v in run["artifacts"].items() if k != "diagnostics"}
        record["artifacts"]["run"] = h.artifact(folder / "run.json")
        prov = record["provenance"]
        prov["runner"] = {"source": h.source(meta["runner_commit"], meta["runner_path"], "run"),
                          "argv": meta["runner_argv"], "working_directory": "."}
        prov["environment"] = meta["environment"]
        prov["measurement"].update(started_at=run["started_at"], finished_at=run["finished_at"], calls=run["calls"], failure=run["failure"],
            budget={"wall_seconds": cfg["solver_timeout_seconds"], "candidate_limit": 1,
                    "stop_reason": "direct candidate complete" if run["status"] == "ok" else run.get("not_run_reason", run.get("failure_class", "failure"))},
            offline_costs=f"uv sync --locked; exact ZIP-byte materialization before cells ({meta['input_preparation_wall_seconds']} seconds); no training/search/case-specific precompute. Compression/export excluded from child walls. Batch controller limits two active cells; resources are shared.")
        missing = {"provenance.environment.threads": "Thread count not sampled; each child's OMP/BLAS/MKL environment set to 1",
                   "provenance.environment.peak_rss_bytes": "Peak RSS not sampled; dispatch guard samples host free+inactive+speculative page estimate",
                   "provenance.measurement.seed": "Deterministic construction has no RNG or seed"}
        for key in ("started_at", "finished_at"):
            if run[key] is None:
                missing[f"provenance.measurement.{key}"] = run.get("not_run_reason", "not started")
        if run["failure"]:
            for key in ("exit_code", "elapsed_seconds"):
                if run["failure"].get(key) is None:
                    run["failure"][key] = None
                    missing[f"provenance.measurement.failure.{key}"] = "Supervisor failure prevented a completed child receipt"
        prov["missing_reasons"] = missing
        record["notes"] = ["Fixed method, 400 new cells k1/k2/k3/k5; previous 100 k4 attempts occur only in the aggregate and are not rescored or repeated in this feed.",
                           cfg["resource_agreement"], "Fresh process timings with OS cache not flushed; non-exclusive host. No controlled speedup claim against prior single-worker or fixed64 timing.",
                           "Candidate nonzero/timeout after cleanup retained and continued, no retry. Supervision/source/resource failure stops dispatch; failures do not enter success-only means.",
                           f"Official singlecore denominator and fixed64 originals reused from {h.OLD}; no baseline calls. Delegated validation, not blind independent scientific acceptance."]
        records.append(record)
        makespan = run["makespan_cycles"]
        frontier = diag.get("base", {})
        component = frontier.get("base", {})
        chunks = diag.get("chunks", {})
        comparisons.append({"case": case, "cores": cores, "status": run["status"], **metrics,
            "baseline_cycles": baseline_cycles, "fixed64_cycles": previous["metrics"]["makespan_cycles"],
            "singlecore_speedup": baseline_cycles / makespan if makespan else None,
            "fixed64_speedup": previous["metrics"]["makespan_cycles"] / makespan if makespan else None,
            "attempt_id": record["attempt_id"], "run_id": batch.name, "reused": False,
            "base_selected": frontier.get("selected"), "actual_tasks": chunks.get("tasks_after"),
            "compute_ops": component.get("compute_ops"), "components": component.get("components"),
            "largest_component_ops": component.get("largest_component_ops"),
            "selection_reason": frontier.get("reason"), "frontier_packets": frontier.get("frontier_packet_count"),
            "tail_ops": frontier.get("tail_ops"), "oversized_tasks_processed": len(chunks.get("split_tasks", [])),
            "oversized_task_splits": sum(len(t["new_tasks"]) > 1 for t in chunks.get("split_tasks", [])),
            "indivisible_oversize_count": len(chunks.get("oversize_indivisible_components", [])),
            "failure": run["failure"], "source_run": h.artifact(folder / "run.json")})
    h.write(references / "fixed64-records.json", {"source_commit": h.OLD, "source_path": h.OLD_FEED, "records": previous_rows})
    h.write(batch / "comparison.json", comparisons)
    feeds = write_feeds(batch, records)
    h.write(batch / "feed-manifest.json", {"schema": "board-submission-v1-shards", "run_id": batch.name, "feeds": feeds, "new_attempts": len(records)})
    k4 = frozen_json(m.SUPPORT_COMMIT, cfg["reused_k4"]["comparison"])
    k4_summary = frozen_json(m.SUPPORT_COMMIT, cfg["reused_k4"]["summary"])
    assert len(k4) == 100 and k4_summary["solver_commit"] == h.SOLVER
    for row in k4:
        row.update(reused=True, aggregate_source_commit=m.SUPPORT_COMMIT, aggregate_source_path=cfg["reused_k4"]["comparison"])
    full = sorted(comparisons + k4, key=lambda r: (r["case"], r["cores"]))
    assert len(full) == 500 and len({(r["case"], r["cores"]) for r in full}) == 500
    h.write(batch / "full500-comparison.json", full)
    columns = ["case", "cores", "status", "makespan_cycles", "baseline_cycles", "fixed64_cycles", "singlecore_speedup", "fixed64_speedup",
               "solver_wall_seconds", "evaluation_wall_seconds", "extra_ddr_bytes", "spill_bytes", "base_selected", "attempt_id", "run_id", "reused"]
    with (batch / "full500-comparison.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(full)
    by_core = {}
    for k in range(1, 6):
        rows = [r for r in full if r["cores"] == k]
        ok = [r for r in rows if r["status"] == "ok"]
        by_core[str(k)] = {"requested": len(rows), "successful": len(ok), "status_counts": dict(Counter(r["status"] for r in rows)),
            "mean_baseline_speedup": statistics.mean(r["singlecore_speedup"] for r in ok) if ok else None,
            "mean_fixed64_baseline_speedup_same_success_subset": statistics.mean(r["baseline_cycles"] / r["fixed64_cycles"] for r in ok) if ok else None,
            "versus_fixed64": {label: sum(sign(r["makespan_cycles"], r["fixed64_cycles"]) for r in ok) for label, sign in
                               (("better", lambda a,b:a<b), ("equal", lambda a,b:a==b), ("worse", lambda a,b:a>b))},
            "versus_singlecore": {label: sum(sign(r["makespan_cycles"], r["baseline_cycles"]) for r in ok) for label, sign in
                               (("better", lambda a,b:a<b), ("equal", lambda a,b:a==b), ("worse", lambda a,b:a>b))},
            "solver_wall_seconds": stat([r["solver_wall_seconds"] for r in rows]),
            "external_E0_wall_seconds": stat([r["evaluation_wall_seconds"] for r in rows]),
            "unsuccessful": [{"case": r["case"], "status": r["status"]} for r in rows if r["status"] != "ok"]}
    summary = {"algorithm_id": cfg["algorithm_id"], "variant": template["variant"], "solver_commit": h.SOLVER,
               "parameters": {k: cfg[k] for k in ("packet_factor", "trigger_ops", "chunk_ops")},
               "scope": "Fixed-method public development matrix. 400 new attempts plus 100 preserved k4 attempts; k4 timing uses earlier one-worker runs. No mixed-method best-of selection.",
               "requested": 500, "new_attempts": 400, "new_actual_calls": meta["actual_calls"], "new_batch_status": meta["status"],
               "new_batch_started_at": meta["started_at"], "new_batch_finished_at": meta["finished_at"], "new_batch_wall_seconds": meta["batch_wall_seconds"],
               "reused_k4": cfg["reused_k4"], "reused_014_original": k4_summary["reused_case014"],
               "by_core": by_core, "status_counts": dict(Counter(r["status"] for r in full)),
               "limits": "Means use only successful pairs and always report n/100; failures are not zero. Fresh processes, OS cache not flushed, non-exclusive host, cross-case descriptive times only. No controlled speedup or optimality claim."}
    grid = {(r["case"], r["cores"]): r for r in full}
    summary["adjacent_core_regressions"] = [
        {"case": case, "from_cores": k, "to_cores": k+1, "from_makespan": a["makespan_cycles"], "to_makespan": b["makespan_cycles"]}
        for case in sorted({r["case"] for r in full}) for k in range(1, 5)
        if (a := grid[case, k])["status"] == "ok" and (b := grid[case, k+1])["status"] == "ok" and b["makespan_cycles"] > a["makespan_cycles"]]
    summary["regression_interpretation"] = "These are fixed-constructor outputs at different core counts, not proofs that the best feasible core-budget optimum worsens. No online selection among these outputs was performed."
    events = []
    for r in records:
        mm = r["provenance"]["measurement"]
        if mm["started_at"] and mm["finished_at"]:
            events += [(datetime.fromisoformat(mm["started_at"].replace("Z", "+00:00")), 1),
                       (datetime.fromisoformat(mm["finished_at"].replace("Z", "+00:00")), -1)]
    active = peak = 0
    for _, delta in sorted(events):
        active += delta
        peak = max(peak, active)
    samples = meta["resource_samples"]
    summary["resource_observations"] = {"configured_worker_cap": cfg["workers"], "cell_interval_peak_overlap": peak,
        "dispatch_samples": len(samples), "minimum_available_memory_estimate_bytes": min((s["available_memory_estimate_bytes"] for s in samples), default=None),
        "maximum_other_busy_project_processes_sampled": max((s["other_busy_project_processes"] for s in samples), default=None),
        "memory_definition": "vm_stat (free + inactive + speculative) pages; approximate host availability, not per-child peak RSS",
        "load_definition": "ps CPU >=25 percent project processes excluding controller and this batch's children; dispatch-time samples, not continuous profiling"}
    h.write(batch / "full500-summary.json", summary)
    failed = []
    for record in records:
        if record["status"] == "ok":
            continue
        folder = batch / "cells" / record["case_id"] / f"k{record['cores']}"
        receipt = h.read(folder / "run.json")
        failed.append({"case": record["case_id"], "cores": record["cores"], "status": record["status"],
                       "failure": receipt["failure"], "calls": receipt["calls"],
                       "cleanup_confirmed": receipt.get("evaluation", receipt.get("solver", {})).get("cleanup_confirmed"),
                       "files": [dict(h.artifact(p), bytes=p.stat().st_size) for p in sorted(folder.iterdir()) if p.is_file()]})
    h.write(batch / "failed-cells.json", failed)
    lines = ["# P1 bounded-task matrix: 400 new attempts, preserved 100 k4 attempts", "",
        f"Algorithm `{cfg['algorithm_id']}` / `{template['variant']}` at `{h.SOLVER}`; packet_factor=4, trigger_ops=4096, chunk_ops=1024.", "",
        f"Frozen runner `{meta['runner_commit']}`, `{meta['runner_path']}` and manifest `{m.MANIFEST}`. Read-only exporter `{Path(__file__).relative_to(ROOT)}` reuses schema constants from same-method fixed commit `{m.SUPPORT_COMMIT}`.", "",
        f"New batch UTC {meta['started_at']} to {meta['finished_at']}; {meta['batch_wall_seconds']:.3f} seconds controller wall (including preparation, source/resource checks, compression). Actual calls: `{meta['actual_calls']}`. Status: `{meta['status']}`. No retry, E1, E2, cloud or GPU.", "",
        "Budget: 400 constructors + 400 external E0 maximum, at most 2 active cells, 30 seconds per constructor, 60 seconds per E0, 1800 seconds whole batch. Candidate child failures/timeouts continue only after cleanup; source/hash/cleanup/disk/runner/resource failures stop dispatch. Four synthetic controller jobs validated a peak of two workers and candidate-failure continuation before freeze; a resource-failure fixture dispatched zero jobs. No solver/E0 was used for controller checks.", "",
        "## Coverage and official quality", "",
        f"All 500 matrix slots are represented, with statuses `{summary['status_counts']}`. A missing/failed score is not zero and is excluded from means; partial-core means do not claim a 100-case score. The 100 k4 records preserve their actual earlier attempts and do not appear in this batch's feed or new call count.", "",
        "| Cores | Successful / requested | Mean official singlecore / Makespan | Fixed64 mean on same successful cases | Better / equal / worse vs fixed64 |",
        "| --- | --- | --- | --- | --- |"]
    for k, value in by_core.items():
        v = value["versus_fixed64"]
        mean = value["mean_baseline_speedup"]
        fixed = value["mean_fixed64_baseline_speedup_same_success_subset"]
        lines.append(f"| {k} | {value['successful']}/{value['requested']} | {mean:.9f} | {fixed:.9f} | {v['better']} / {v['equal']} / {v['worse']} |" if mean is not None else f"| {k} | 0/{value['requested']} | NA | NA | 0 / 0 / 0 |")
    lines += ["", "Makespan is simulated cycles; solver and external E0 durations are seconds. Mean speedup is the arithmetic mean of per-case ratios. Complete original E0 movement fields, plan, result, run and optional diagnostics/trace/log are retained.", "",
        "## Observed program time and resources", "",
        "| Cores | Solver median / maximum seconds | External E0 total / maximum seconds |",
        "| --- | --- | --- |"]
    for k, value in by_core.items():
        s, e = value["solver_wall_seconds"], value["external_E0_wall_seconds"]
        lines.append(f"| {k} | {s.get('median', 0):.6f} / {s.get('max', 0):.6f} | {e.get('sum', 0):.3f} / {e.get('max', 0):.3f} |")
    lines += ["", "Fresh interpreter per cell, OS cache not flushed. Solver wall includes input read, construction, plan/diagnostic publication and process completion; external E0 wall includes official result/trace/log output and exit. Compression/export is outside both child timers. k4 used earlier one-worker runs; new cores use two shared workers. These are descriptive cross-case observations, not controlled timing speedups or repeated latency percentiles.", "",
        f"Host `{meta['environment']['cpu']}`, `{meta['environment']['os']}`, Python 3.12.13, locked dependencies. Resource observations: `{summary['resource_observations']}`. No per-process peak RSS or phase sampling; no inference of evaluator bottleneck from a timeout.", "",
        cfg["resource_agreement"], "", "## Failures and research feedback", "",
        f"New unsuccessful cells: `{[{'case': f['case'], 'cores': f['cores'], 'status': f['status']} for f in failed]}`. See `failed-cells.json` for exact costs, cleanup and retained file hashes. No retry or raised timeout.", "",
        f"There are {len(summary['adjacent_core_regressions'])} adjacent-core regressions among successful pairs for this fixed constructor. `full500-summary.json` lists them. They concern this constructor's outputs, not the optimum of the feasible core-budget problem. No online best-of selection was performed.", "",
        "This is the public development set used for feedback, not blind independent acceptance or an optimality claim. The unbounded full4 batch's stop remains unchanged; this is a distinct bounded-task algorithm and separately authorized batch.", "",
        "## Evidence and reproduction", "",
        f"- `board-feed.json` (or automatically numbered shards if >8 MiB) contains only these 400 attempts; `feed-manifest.json` lists exact hashes.",
        "- `full500-comparison.json`/CSV and `full500-summary.json` combine the fixed method across actual runs, without changing earlier attempts.",
        f"- k4 source `{m.SUPPORT_COMMIT}`: `{cfg['reused_k4']['comparison']}`; original 014 source `{k4_summary['reused_case014']['source_commit']}` is already preserved under the k4 source directory.",
        f"- Frozen official singlecore/fixed64 source `{h.OLD}` reused without calls. `references/` holds baseline original bytes and historical records.",
        f"- Read-only export: `python -B src/q1_benchmarks/bounded_matrix_report.py {batch.name}`.",
        "- `PRECHECK.json` stores the board-submission-v1 working-tree precheck. Fixed-commit precheck and every recursively referenced feed/run artifact are separately verified after commit; no central ledger writes.",
        "- `PRECHECK_EARLY.json` preserves a read-only precheck attempted before export finished (feed did not yet exist); after export completed, the actual precheck was rerun without solver/E0 calls.",
        "- The controller refuses existing run directories. Do not rerun this batch to repair export or metadata; export only reads preserved evidence.", ""]
    (batch / "README.md").write_text("\n".join(lines))
    print(json.dumps({"new_records": len(records), "feeds": feeds, "by_core": {k: {f: v[f] for f in ("successful", "mean_baseline_speedup")} for k,v in by_core.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_id")
    args = p.parse_args()
    if not args.run_id or Path(args.run_id).name != args.run_id:
        p.error("run_id must be a single path component")
    export(m.RESULT_ROOT / args.run_id)
