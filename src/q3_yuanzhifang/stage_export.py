"""Export the guarded-stage batch without launching any construction or E0."""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path

from benchmark import ROOT, artifact, utc, write_json
from export_feed import baseline, read_art, source, spec, TASK
from stage_benchmark import SOLVER_COMMIT, OUT

PILOT_FEED = Path("results/a/q3-yuanzhifang/pilot-20260924/board-feed-20260924T141108Z-unique-plans.json")


def export(folder):
    m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    old = json.loads((ROOT / PILOT_FEED).read_text(encoding="utf-8"))
    templates = {r["problem"]: r for r in old["records"]
                 if r["case_id"] == "044" and r["variant"] == "baseline"}
    calls = json.loads((folder / "call-ledger.json").read_text(encoding="utf-8"))
    c = m["constructions"][0] if m["constructions"] else None
    solver = next((call for call in calls if call["kind"] == "solver"), None)
    work = list(m["evaluations"])
    for call in calls:
        if call["status"] != "ok":
            work.append(dict(evaluation_id=call["call_id"], problem=call["call_id"].rsplit("-", 1)[1]
                             if call["kind"] == "E0" else "P3", call=call, artifacts={}))
    if m["status"] != "ok" and not any(call["status"] != "ok" for call in calls):
        work.append(dict(evaluation_id="044-shared_stages-preflight", problem="P3",
                         call=dict(call_id="044-shared_stages-preflight", kind="preflight", status="failed",
                                   wall_seconds=m["elapsed_seconds"], started_at=m["started_at"],
                                   finished_at=m["finished_at"], exit_code=None), artifacts={}))
    rows, summary = [], []
    for e in work:
        problem, call = e["problem"], e["call"]
        success = call["status"] == "ok"
        result = read_art(e["artifacts"]["result"]) if success else {}
        row = copy.deepcopy(templates[problem])
        row.update(attempt_id=m["run_id"] + "-" + e["evaluation_id"], revision=1,
                   run_id=m["run_id"], algorithm_id="q3-shared-stages", algorithm_name="共享权重同构链同层交错",
                   variant="shared_stages", solver_commit=SOLVER_COMMIT, status=call["status"],
                   observed_at=call["started_at"], source_url=TASK,
                   parameters=dict(cores=4, deterministic=True, candidate_policy="one guarded same-stage plan",
                                   guard="serial homogeneous jobs with identical shared-input stage signatures",
                                   fallback="baseline on guard rejection; pilot stops before E0 if 044 guard fails",
                                   batch_budget=m["budget"], internal_E0=0, internal_E1=0, internal_E2=0),
                   notes=["New independent 044/k4 stage batch; one actual cold construction and its actual P2/P3 pair.",
                          "Both records share the one construction; actual totals are in call-ledger.json.",
                          "Hardware inventory reused from the same host's first pilot, with acquisition times in manifest; "
                          "all process times and results here are newly measured. OS file cache was not flushed.",
                          "One public development graph, one observation, CPU host not proven exclusive. "
                          "No online selector, blind review or final independent acceptance."])
        identity = row["identity"]
        identity["plan_sha256"] = c["plan"]["sha256"] if c else None
        moved = result.get("data_movement_bytes", {})
        row["metrics"] = dict(makespan_cycles=result.get("makespan"),
                              solver_wall_seconds=solver["wall_seconds"] if solver else None,
                              evaluation_wall_seconds=call["wall_seconds"] if call["kind"] == "E0" else None,
                              ddr_bytes=moved.get("scheduled_copy_bytes"),
                              extra_ddr_bytes=moved.get("added_copy_bytes"),
                              spill_bytes=moved.get("spill_added_copy_bytes"),
                              cache_hit_rate=result.get("cache_stats", {}).get("hit_rate"))
        row["evaluator"]["commit"] = m["identity"]["runner_commit"]
        receipt = dict(schema="q3-stage-attempt-v1", solver_commit=SOLVER_COMMIT,
                       runner_commit=m["identity"]["runner_commit"], identity=identity,
                       construction=c, evaluation=e, environment=m["environment"],
                       environment_inventory_source=m["environment_inventory_source"],
                       note="Shared solver receipt for P2/P3; exactly one cold solver and two E0 calls in successful batch.")
        run_path = folder / "044/shared_stages" / problem / "run.json"
        write_json(run_path, receipt)
        row["artifacts"] = {name: spec(value) for name, value in e["artifacts"].items()}
        if c:
            row["artifacts"]["plan"] = spec(c["plan"])
        row["artifacts"].update(run=artifact(run_path), manifest=artifact(folder / "manifest.json"))
        p = row["provenance"]
        p["solver"].update(source=source(SOLVER_COMMIT, "src/q3_yuanzhifang/stages.py", "main"),
                           method="Strictly guard serial homogeneous jobs and their common-weight consumer signatures, "
                                  "retain baseline whole-job placement, then interleave one original operation per job per stage. "
                                  "No parameter sweep or online evaluation. Structural fallback exists; this batch only tests guarded 044.",
                           references=["https://github.com/huaweibei123/huaweicup2026/blob/" + SOLVER_COMMIT +
                                       "/docs/a/q3-yuanzhifang/STAGE_ALIGNMENT.md"],
                           upstream=[source("8f8bfce73b0b8e350de1dc40af21f3787c8ac8d6",
                                            "src/q3_yuanzhifang/construct.py", "SharingIndex"),
                                     source("a4e7ee13310d693ec4fb5cc236669ceb3b172d1f", "src/q3/construct.py", "Index")])
        p["runner"] = dict(source=source(m["identity"]["runner_commit"],
                                         "src/q3_yuanzhifang/stage_benchmark.py", "main"),
                           argv=m["argv"], working_directory=".")
        p["environment"] = m["environment"]
        p["measurement"].update(started_at=solver["started_at"] if solver else m["started_at"],
                                finished_at=call["finished_at"],
                                budget=dict(wall_seconds=120, candidate_limit=1, stop_reason=m["stop_reason"]),
                                calls=dict(solver=1 if solver else 0, E0=1 if call["kind"] == "E0" else 0, E1=0, E2=0),
                                offline_costs=m["offline_costs"], failure=None)
        if not success:
            p["measurement"]["failure"] = dict(stage=call["kind"], reason=m["stop_reason"],
                                                  exit_code=call.get("exit_code"), elapsed_seconds=call["wall_seconds"])
            if call.get("exit_code") is None:
                p["missing_reasons"]["provenance.measurement.failure.exit_code"] = "No child exit code for this preflight or spawn failure."
        row["baseline"] = baseline("044", identity) if success else None
        row["cache_pair"] = None
        if success and problem == "P3":
            paired = next(other for other in m["evaluations"] if other["problem"] == "P2")
            row["cache_pair"] = dict(**identity, cores=4, route="E0", result=spec(paired["artifacts"]["result"]))
        rows.append(row)
        summary.append(dict(problem=problem, case_id="044", cores=4, variant="shared_stages",
                            status=call["status"], **row["metrics"]))
    stamp = utc().replace("-", "").replace(":", "").split(".")[0] + "Z"
    feed = folder / f"board-feed-{stamp}-stages.json"
    if feed.exists():
        raise FileExistsError(feed)
    write_json(feed, dict(schema_version=1, submission_version=1, records=rows))
    with (folder / "summary.csv").open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    write_json(folder / "export-receipt.json", dict(exported_at=utc(), feed=artifact(feed),
               records=len(rows), calls=m["calls"], template_source=PILOT_FEED.as_posix(),
               note="Template structure and already verified singlecore denominator reused; all solver/result fields from stage receipts. Zero new calls."))
    print(json.dumps(dict(feed=feed.relative_to(ROOT).as_posix(), records=len(rows), calls=m["calls"])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", type=Path, default=Path(OUT))
    args = parser.parse_args()
    export((ROOT / args.folder).resolve())


if __name__ == "__main__":
    main()
