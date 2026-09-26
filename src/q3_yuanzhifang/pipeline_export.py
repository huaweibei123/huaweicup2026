"""Export only preserved pipeline pilot bytes; never launch a solver or evaluator."""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path

from benchmark import ROOT, artifact, utc, write_json
from export_feed import baseline, read_art, source, spec, TASK
from pipeline_benchmark import SOLVER_COMMIT, OUT, VARIANT

PILOT_FEED = Path("results/a/q3-yuanzhifang/pilot-20260924/board-feed-20260924T141108Z-unique-plans.json")


def export(folder):
    m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    old = json.loads((ROOT / PILOT_FEED).read_text(encoding="utf-8"))
    templates = {r["problem"]: r for r in old["records"]
                 if r["case_id"] == "044" and r["variant"] == "baseline"}
    calls = json.loads((folder / "call-ledger.json").read_text(encoding="utf-8"))
    constructions = {c["case_id"]: c for c in m["constructions"]}
    work = list(m["evaluations"])
    for call in calls:
        if call["status"] != "ok":
            work.append(dict(evaluation_id=call["call_id"], case_id=call["call_id"][:3],
                             problem=call["call_id"].rsplit("-", 1)[1] if call["kind"] == "E0" else "P3",
                             call=call, artifacts={}))
    if m["status"] != "ok" and not any(call["status"] != "ok" for call in calls):
        case = m["constructions"][-1]["case_id"] if m["constructions"] else "044"
        work.append(dict(evaluation_id=case + "-pipeline-preflight", case_id=case, problem="P3",
                         call=dict(call_id=case + "-pipeline-preflight", kind="preflight", status="failed",
                                   wall_seconds=m["elapsed_seconds"], started_at=m["started_at"],
                                   finished_at=m["finished_at"], exit_code=None), artifacts={}))
    rows, summary = [], []
    for e in work:
        case, problem, call = e["case_id"], e["problem"], e["call"]
        c = constructions.get(case)
        solver = next((x for x in calls if x["kind"] == "solver" and x["call_id"].startswith(case + "-")), None)
        success = call["status"] == "ok"
        result = read_art(e["artifacts"]["result"]) if success else {}
        row = copy.deepcopy(templates[problem])
        row.update(attempt_id=m["run_id"] + "-" + e["evaluation_id"], revision=1,
                   run_id=m["run_id"], algorithm_id="q3-pipeline-stages", algorithm_name="同构共享链连续阶段流水构造",
                   variant=VARIANT, solver_commit=SOLVER_COMMIT, status=call["status"],
                   case_id=case, cores=4, observed_at=call["started_at"], source_url=TASK,
                   parameters=dict(cores=4, requested_cores=4, active_cores=c["active_cores"] if c else None,
                                   deterministic=True, candidate_policy="one exact minimax contiguous partition in a copy-free flowshop abstraction",
                                   guard="homogeneous serial jobs with identical common-input signature; jobs>=cores and chain length<=512",
                                   fallback="algorithm has structural fallback; this pilot stops before E0 on guard rejection",
                                   batch_budget=m["budget"], internal_E0=0, internal_E1=0, internal_E2=0),
                   notes=["Independent 044 k4 pipeline development pilot, one cold construction and two E0s at most.",
                          "Each P2/P3 pair shares its one actual construction; authoritative totals are in call-ledger.json.",
                          "Same-host static hardware inventory reused with acquisition time in manifest; all reported process "
                          "times and results are new. OS file cache not flushed; CPU host not proven exclusive.",
                          "One public development graph; this is not a full100 result, blind review or independent acceptance."])
        identity = row["identity"]
        graph_identity = next(x["sha256"] for x in m["identity"]["verified_files"]
                              if x["manifest_path"] == f"data/case_{case}.json")
        identity.update(graph_sha256=graph_identity, config_sha256=m["identity"]["config_sha256"],
                        official_sha256=m["identity"]["official_code_hash"],
                        plan_sha256=c["plan"]["sha256"] if c else None)
        moved = result.get("data_movement_bytes", {})
        row["metrics"] = dict(makespan_cycles=result.get("makespan"),
                              solver_wall_seconds=solver["wall_seconds"] if solver else None,
                              evaluation_wall_seconds=call["wall_seconds"] if call["kind"] == "E0" else None,
                              ddr_bytes=moved.get("scheduled_copy_bytes"), extra_ddr_bytes=moved.get("added_copy_bytes"),
                              spill_bytes=moved.get("spill_added_copy_bytes"),
                              cache_hit_rate=result.get("cache_stats", {}).get("hit_rate"))
        row["evaluator"]["commit"] = m["identity"]["runner_commit"]
        receipt = dict(schema="q3-pipeline-attempt-v1", solver_commit=SOLVER_COMMIT,
                       runner_commit=m["identity"]["runner_commit"], identity=identity,
                       construction=c, evaluation=e, environment=m["environment"],
                       environment_inventory_source=m["environment_inventory_source"],
                       note="P2/P3 share one construction per graph. Nonduplicated batch count is in call-ledger.json.")
        run_path = folder / case / VARIANT / problem / "run.json"
        write_json(run_path, receipt)
        row["artifacts"] = {name: spec(value) for name, value in e["artifacts"].items()}
        if c:
            row["artifacts"]["plan"] = spec(c["plan"])
        row["artifacts"].update(run=artifact(run_path), manifest=artifact(folder / "manifest.json"))
        p = row["provenance"]
        p["solver"].update(source=source(SOLVER_COMMIT, "src/q3_yuanzhifang/pipeline_stages.py", "main"),
                           method="Guard identical serial-chain jobs and common-input stage signatures. Solve exact "
                                  "minimum largest contiguous segment sum by O(k L^2) dynamic programming with L<=512. "
                                  "Assign one consecutive stage to each core, following the same job order. The copy-free "
                                  "single-server flowshop theorem motivates the split; actual pipe overlap, COPY, cache and "
                                  "capacity are not modeled. One plan and structural validation, no internal scoring/E0. "
                                  "This abstraction is not an official E0 optimum or bound.",
                           references=["https://github.com/huaweibei123/huaweicup2026/blob/" + SOLVER_COMMIT +
                                       "/docs/a/q3-yuanzhifang/PIPELINE_STAGES.md"],
                           upstream=[source("8f8bfce73b0b8e350de1dc40af21f3787c8ac8d6",
                                            "src/q3_yuanzhifang/construct.py", "SharingIndex"),
                                     source("bb7a7e8702b636a0a9dda33d070daad5f4d7c212",
                                            "src/q3_yuanzhifang/active_stages.py", "build"),
                                     source("a4e7ee13310d693ec4fb5cc236669ceb3b172d1f", "src/q3/construct.py", "Index")])
        p["runner"] = dict(source=source(m["identity"]["runner_commit"],
                                         "src/q3_yuanzhifang/pipeline_benchmark.py", "main"),
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
                p["missing_reasons"]["provenance.measurement.failure.exit_code"] = "No child exit code for preflight or spawn failure."
        row["baseline"] = baseline(case, identity) if success else None
        row["cache_pair"] = None
        if success and problem == "P3":
            paired = next(x for x in m["evaluations"] if x["case_id"] == case and x["problem"] == "P2")
            row["cache_pair"] = dict(**identity, cores=4, route="E0", result=spec(paired["artifacts"]["result"]))
        rows.append(row)
        summary.append(dict(problem=problem, case_id=case, cores=4, variant=VARIANT,
                            status=call["status"], **row["metrics"]))
    stamp = utc().replace("-", "").replace(":", "").split(".")[0] + "Z"
    feed = folder / f"board-feed-{stamp}-pipeline.json"
    if feed.exists():
        raise FileExistsError(feed)
    write_json(feed, dict(schema_version=1, submission_version=1, records=rows))
    with (folder / "summary.csv").open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    write_json(folder / "export-receipt.json", dict(exported_at=utc(), feed=artifact(feed), records=len(rows),
               calls=m["calls"], template_source=PILOT_FEED.as_posix(),
               note="Only template structure reused; all graph/plan/solver/result identities from pipeline receipts. Zero new calls."))
    print(json.dumps(dict(feed=feed.relative_to(ROOT).as_posix(), records=len(rows), calls=m["calls"])))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", nargs="?", type=Path, default=Path(OUT))
    args = ap.parse_args()
    export((ROOT / args.folder).resolve())


if __name__ == "__main__":
    main()
