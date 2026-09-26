"""Export only preserved cold-setup pipeline pilot bytes; never launch a solver or evaluator."""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path

from benchmark import ROOT, artifact, utc, write_json
from export_feed import baseline, read_art, source, spec, TASK
from pipeline_setup_followup_benchmark import SOLVER_COMMIT, OUT, VARIANT

PILOT_FEED = Path("results/a/q3-yuanzhifang/pilot-20260924/board-feed-20260924T141108Z-unique-plans.json")


def export(folder):
    m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if m.get("schema") != "q3-pipeline-setup-v1" or m.get("status") == "running":
        raise ValueError("requires an ended cold-setup pipeline batch")
    if "identity" not in m or "environment" not in m:
        raise ValueError("preflight failed before a measured attempt; preserve manifest without inventing a feed")
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
        case = m.get("active_case_id", "044")
        work.append(dict(evaluation_id=case + "-pipeline-setup-preflight", case_id=case, problem="P3",
                         call=dict(call_id=case + "-pipeline-setup-preflight", kind="preflight", status="failed",
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
                   run_id=m["run_id"], algorithm_id="q3-pipeline-cold-setup", algorithm_name="共同输入首次搬运的连续流水阶段DP",
                   variant=VARIANT, solver_commit=SOLVER_COMMIT, status=call["status"],
                   case_id=case, cores=4, observed_at=call["started_at"], source_url=TASK,
                   parameters=dict(cores=4, requested_cores=4, active_cores=c["active_cores"] if c else None,
                                   deterministic=True, candidate_policy="one O(k L^2) cold-setup contiguous partition with singleton mapping and job-major priorities",
                                   guard="homogeneous serial jobs; positive integer M/V cycles; each shared input consumed at one position; jobs>=cores and length<=512",
                                   fallback="algorithm has structural fallback; this pilot stops before E0 on guard rejection",
                                   batch_budget=m["budget"], internal_E0=0, internal_E1=0, internal_E2=0),
                   notes=["Independent 044 k4 cold-setup pipeline pilot: at most one cold construction and two E0s, no control rerun.",
                          "Each P2/P3 pair shares its one actual construction; authoritative totals are in call-ledger.json.",
                          "Live hardware inventory acquired in this batch; all reported process "
                          "times and results are new. OS file cache not flushed; CPU host not proven exclusive.",
                          "One public development graph; this is not a full100 result, blind review or independent acceptance."])
        row["parameters"]["resource_context"] = m["resource_context"]
        row["notes"].append("Actual concurrent work: " + m["resource_context"]["concurrent_work"] +
            "; available RAM checked before each child, >=1 GiB required. This is not an exclusive-host latency claim.")
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
        receipt = dict(schema="q3-pipeline-setup-attempt-v1", solver_commit=SOLVER_COMMIT,
                       runner_commit=m["identity"]["runner_commit"], identity=identity,
                       construction=c, evaluation=e, environment=m["environment"],
                       resource_context=m["resource_context"], memory_checks=m["memory_checks"],
                       environment_inventory_source=m["environment_inventory_source"],
                       note="P2/P3 share one construction per graph. Nonduplicated batch count is in call-ledger.json.")
        # Resource/validation failure after a successful P3 must never overwrite
        # that successful evaluation's receipt, or its feed hash would break.
        receipt_folder = problem if success else "failed-" + call["call_id"]
        run_path = folder / case / VARIANT / receipt_folder / "run.json"
        write_json(run_path, receipt)
        row["artifacts"] = {name: spec(value) for name, value in e["artifacts"].items()}
        if c:
            row["artifacts"]["plan"] = spec(c["plan"])
        row["artifacts"].update(run=artifact(run_path), manifest=artifact(folder / "manifest.json"))
        p = row["provenance"]
        p["solver"].update(source=source(SOLVER_COMMIT, "src/q3_yuanzhifang/pipeline_setup.py", "main"),
                           method="Guard homogeneous positive M/V serial chains with each shared input consumed "
                                  "at a unique job position. Price each shared tensor once as ceil(bytes/bandwidth). "
                                  "Solve an O(k L^2), O(k L) dynamic program exactly for a serial-stage first-job "
                                  "cold-setup abstraction, then submit one contiguous singleton pipeline plan. "
                                  "Core ownership may change from the compute-only control. Real M/V overlap, "
                                  "COPY contention, private inputs, cross-core delay and capacity are outside this "
                                  "model; model time is neither an official bound nor actual makespan. No internal E0.",
                           references=["https://github.com/huaweibei123/huaweicup2026/blob/" + SOLVER_COMMIT +
                                       "/docs/a/q3-yuanzhifang/PIPELINE_SETUP.md"],
                           upstream=[source("6bae8dfa317bc71226068344b59dd65d2612c32b",
                                            "src/q3_yuanzhifang/pipeline_stages.py", "build"),
                                     source("bb7a7e8702b636a0a9dda33d070daad5f4d7c212",
                                            "src/q3_yuanzhifang/active_stages.py", "stage_structure"),
                                     source("8f8bfce73b0b8e350de1dc40af21f3787c8ac8d6",
                                            "src/q3_yuanzhifang/construct.py", "SharingIndex"),
                                     source("a4e7ee13310d693ec4fb5cc236669ceb3b172d1f", "src/q3/construct.py", "Index")])
        p["runner"] = dict(source=source(m["identity"]["runner_commit"],
                                         "src/q3_yuanzhifang/pipeline_setup_followup_benchmark.py", "main"),
                           argv=m["argv"], working_directory=".")
        p["environment"] = m["environment"]
        p["producer_session"] = m["producer_session"]
        p["missing_reasons"].update(m.get("environment_missing_reasons", {}))
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
    feed = folder / f"board-feed-{stamp}-pipeline-setup.json"
    if feed.exists():
        raise FileExistsError(feed)
    write_json(feed, dict(schema_version=1, submission_version=1, records=rows))
    with (folder / "summary.csv").open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(summary[0]) if summary else [
            "problem", "case_id", "cores", "variant", "status", "makespan_cycles",
            "solver_wall_seconds", "evaluation_wall_seconds", "ddr_bytes", "extra_ddr_bytes",
            "spill_bytes", "cache_hit_rate"])
        writer.writeheader()
        writer.writerows(summary)
    aliases = [dict(case_id=c["case_id"], construction_id=c["construction_id"], plan=c["plan"],
                    solver_wall_seconds=c["solver"]["wall_seconds"], alias_of=c["alias_of"],
                    comparison=c["historical_control_comparison"], reused_evaluations=c["reused_evaluations"])
               for c in m["constructions"] if c.get("alias_of")]
    write_json(folder / "alias-reuse.json", dict(schema="q3-pipeline-setup-alias-v1", aliases=aliases,
               note="Byte-identical plans reference the existing P2/P3 attempts only. "
                    "Parsed JSON equality alone never permits reuse. "
                    "New cold wall retained; no separate feed record or new E0 claimed for an alias."))
    write_json(folder / "export-receipt.json", dict(exported_at=utc(), feed=artifact(feed), records=len(rows),
               calls=m["calls"], aliases=len(aliases), template_source=PILOT_FEED.as_posix(),
               note="Only template structure reused; all graph/plan/solver/result identities from pipeline-setup receipts. Zero new calls."))
    print(json.dumps(dict(feed=feed.relative_to(ROOT).as_posix(), records=len(rows), calls=m["calls"])))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", nargs="?", type=Path, default=Path(OUT))
    args = ap.parse_args()
    export((ROOT / args.folder).resolve())


if __name__ == "__main__":
    main()
