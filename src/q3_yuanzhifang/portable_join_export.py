"""Export a real portable batch using its executing session and live environment."""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path

from benchmark import ROOT, artifact, utc, write_json
from export_feed import baseline, read_art, source, spec, TASK
from portable_join_benchmark import SOLVER_COMMIT, VARIANT

PILOT_FEED = Path("results/a/q3-yuanzhifang/pilot-20260924/board-feed-20260924T141108Z-unique-plans.json")


def export(folder):
    m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if m.get("schema") != "q3-portable-join-v1" or not m.get("producer_session") or not m.get("runtime_id"):
        raise ValueError("requires an actual portable-run manifest, not a legacy host receipt")
    if m["status"] == "running":
        raise ValueError("cannot export while calls are in flight")
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
        case = m["constructions"][-1]["case_id"] if m["constructions"] else "069"
        work.append(dict(evaluation_id=case + "-join-validation", case_id=case, problem="P3",
                         call=dict(call_id=case + "-join-validation", kind="validation", status="failed",
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
                   run_id=m["run_id"], algorithm_id="q3-dag-join-list", algorithm_name="对最后前驱与释放汇合节点联合分配",
                   variant=VARIANT, solver_commit=SOLVER_COMMIT, status=call["status"],
                   case_id=case, cores=5, observed_at=call["started_at"], source_url=TASK,
                   runtime_id=m["runtime_id"],
                   parameters=dict(cores=5, requested_cores=5, active_cores=c["active_cores"] if c else None,
                                   deterministic=True, candidate_policy="one chain-DAG list schedule with at most k^2 arithmetic pair placements per released join",
                                   guard="physical computation edges match official original tensor/direct edges; fork and join exist",
                                   fallback="algorithm has structural fallback; this pilot stops before E0 on guard rejection",
                                   batch_budget=m["budget"], internal_E0=0, internal_E1=0, internal_E2=0),
                   notes=["Portable candidate batch: 069/071 platform replication, 005/086 first larger-DAG generalization; four prescribed cases only.",
                          "Each P2/P3 pair shares one actual cold construction; authoritative counts are in call-ledger.json.",
                          "Environment acquired live on the executing host. Producer session and runtime ID come from this batch manifest.",
                          "One observation per graph. OS file cache not flushed; peak RSS unmeasured; CPU host not proven exclusive.",
                          "Cross-platform replication alone is not blind review, full100 coverage or final scientific acceptance."])

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
        receipt = dict(schema="q3-portable-join-attempt-v1", solver_commit=SOLVER_COMMIT,
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
        p["producer_session"] = m["producer_session"]
        p["task_url"] = TASK
        p["missing_reasons"] = dict(m["environment_missing_reasons"])

        p["solver"].update(source=source(SOLVER_COMMIT, "src/q3_yuanzhifang/join_list.py", "main"),
                           method="Guard physical dependency agreement and fork/join structure. Condense maximal serial "
                                  "chains and use remaining-path ready priority. When a chain releases its sole multi-input "
                                  "join, append that pair using the best of at most k^2 arithmetic core placements; otherwise "
                                  "use direct single-chain placement. Each chain is committed once in global topological "
                                  "order. Per-pipe clocks and static transfer estimates exclude shared COPY, cache and "
                                  "capacity; this local model guarantee is not global or official optimality. No internal E0.",
                           references=["https://github.com/huaweibei123/huaweicup2026/blob/" + SOLVER_COMMIT +
                                       "/docs/a/q3-yuanzhifang/JOIN_LIST.md"],
                           upstream=[source("20fbf33b310b6e9959e45d67361f580601f5959f",
                                            "src/q3_yuanzhifang/dag_list.py", "chain_dag"),
                                     source("8f8bfce73b0b8e350de1dc40af21f3787c8ac8d6",
                                            "src/q3_yuanzhifang/construct.py", "SharingIndex"),
                                     source("bb7a7e8702b636a0a9dda33d070daad5f4d7c212",
                                            "src/q3_yuanzhifang/active_stages.py", "build"),
                                     source("a4e7ee13310d693ec4fb5cc236669ceb3b172d1f", "src/q3/construct.py", "Index")])
        p["runner"] = dict(source=source(m["identity"]["runner_commit"],
                                         "src/q3_yuanzhifang/portable_join_benchmark.py", "main"),
                           argv=m["argv"], working_directory=".")
        p["environment"] = m["environment"]
        p["measurement"].update(started_at=solver["started_at"] if solver else m["started_at"],
                                finished_at=call["finished_at"],
                                budget=dict(wall_seconds=600, candidate_limit=4, stop_reason=m["stop_reason"]),
                                calls=dict(solver=1 if solver else 0, E0=1 if call["kind"] == "E0" else 0, E1=0, E2=0),
                                offline_costs=m["offline_costs"], failure=None)
        if not success:
            p["measurement"]["failure"] = dict(stage=call["kind"], reason=m["stop_reason"],
                                                  exit_code=call.get("exit_code"), elapsed_seconds=call["wall_seconds"])
            if call.get("exit_code") is None:
                p["missing_reasons"]["provenance.measurement.failure.exit_code"] = "No child exit code for validation or spawn failure."
        row["baseline"] = baseline(case, identity) if success else None
        row["cache_pair"] = None
        if success and problem == "P3":
            paired = next(x for x in m["evaluations"] if x["case_id"] == case and x["problem"] == "P2")
            row["cache_pair"] = dict(**identity, cores=5, route="E0", result=spec(paired["artifacts"]["result"]))
        rows.append(row)
        summary.append(dict(problem=problem, case_id=case, cores=5, variant=VARIANT,
                            status=call["status"], **row["metrics"]))
    stamp = utc().replace("-", "").replace(":", "").split(".")[0] + "Z"
    feed = folder / f"board-feed-{stamp}-portable-join.json"
    if feed.exists():
        raise FileExistsError(feed)
    write_json(feed, dict(schema_version=1, submission_version=1, records=rows))
    with (folder / "summary.csv").open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    write_json(folder / "export-receipt.json", dict(exported_at=utc(), feed=artifact(feed), records=len(rows),
               calls=m["calls"], template_source=PILOT_FEED.as_posix(),
               note="Only template structure reused; all graph/plan/solver/result identities from portable receipts and executing session. Zero new calls."))
    print(json.dumps(dict(feed=feed.relative_to(ROOT).as_posix(), records=len(rows), calls=m["calls"])))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", type=Path, help="Existing finished portable batch output directory")
    args = ap.parse_args()
    folder = (ROOT / args.folder).resolve()
    if not folder.is_relative_to(ROOT / "results"):
        ap.error("folder must remain inside this repository's results directory")
    export(folder)


if __name__ == "__main__":
    main()
