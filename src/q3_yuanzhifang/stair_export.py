"""Export sealed 067 first-wave stair artifacts; no constructor or evaluator calls."""
from __future__ import annotations

import argparse
import copy
import csv
import gzip
import json
from pathlib import Path

from benchmark import ROOT, artifact, digest, utc, write_json
from export_feed import baseline, read_art, source, spec, TASK
from stair_benchmark import SOLVER_COMMIT, OUT, CASES, TEMPLATE


def seal_snapshot(folder, name):
    raw = (folder / name).read_bytes()
    target = folder / (name + ".gz")
    if target.exists():
        raise FileExistsError(target)
    target.write_bytes(gzip.compress(raw, mtime=0))
    if gzip.decompress(target.read_bytes()) != raw:
        raise ValueError("snapshot gzip round trip failed: " + name)
    return dict(**artifact(target), raw_sha256=digest(raw), raw_bytes=len(raw),
                gzip_bytes=target.stat().st_size)


def verify_art(ref):
    path = ROOT / ref["path"]
    packed = path.read_bytes()
    if digest(packed) != ref["sha256"]:
        raise ValueError("artifact hash mismatch: " + ref["path"])
    if path.suffix == ".gz":
        raw = gzip.decompress(packed)
        if digest(raw) != ref["raw_sha256"] or len(raw) != ref["raw_bytes"]:
            raise ValueError("artifact raw-byte mismatch: " + ref["path"])


def export(folder):
    manifest_path = folder / "manifest.json"
    m = json.loads(manifest_path.read_bytes())
    if m.get("schema") != "q3-wave-stair-v1" or m.get("status") not in ("ok", "stopped"):
        raise ValueError("requires an ended first-wave stair batch")
    if "identity" not in m or "environment" not in m:
        raise ValueError("no verified measured attempt to export")
    if (folder / "export-receipt.json").exists():
        raise FileExistsError("batch already exported")
    calls = json.loads((folder / "call-ledger.json").read_bytes())
    if m["calls"] != {kind: sum(c["kind"] == kind for c in calls)
                      for kind in ("solver", "E0", "E1", "E2")}:
        raise ValueError("manifest/ledger call count mismatch")
    for call in calls:
        if call["status"] == "running":
            raise ValueError("in-flight call cannot be archived")
        for name in ("stdout", "stderr"):
            if name in call:
                verify_art(call[name])
    for construction in m["constructions"]:
        verify_art(construction["plan"])
    for evaluation in m["evaluations"]:
        for ref in evaluation["artifacts"].values():
            verify_art(ref)
    old = json.loads((ROOT / TEMPLATE).read_bytes())
    templates = {problem: next(r for r in old["records"] if r["case_id"] == "044" and
                 r["variant"] == "baseline" and r["problem"] == problem) for problem in ("P2", "P3")}
    constructions = {c["construction_id"]: c for c in m["constructions"]}
    evals = {e["evaluation_id"]: e for e in m["evaluations"]}
    work = list(evals.values())
    for call in calls:
        if call["status"] == "ok" or call["call_id"] in evals:
            continue
        case = call["call_id"][:3]
        problem = call["call_id"].rsplit("-", 1)[1] if call["kind"] == "E0" else "P3"
        construction_id = call["call_id"].rsplit("-", 1)[0] if call["kind"] == "E0" else call["call_id"]
        work.append(dict(evaluation_id=call["call_id"], construction_id=construction_id,
                         case_id=case, problem=problem,
                         call=call, artifacts={}))
    # Validation can fail after a successful subprocess. Keep that failure visible
    # without rewriting or downgrading a successful E0 receipt.
    for failure_index, failure in enumerate(m.get("failures", []), 1):
        case = failure["case_id"]
        attempted = [x for x in calls if x["call_id"].startswith(f"{case}-wave_stair")]
        last = attempted[-1] if attempted else None
        problem = (last["call_id"].rsplit("-", 1)[1]
                   if last and last["kind"] == "E0" else "P2" if last else "P3")
        if (last and last["kind"] == "E0" and problem == "P2" and
                "official E0 result identity mismatch" not in failure["reason"]):
            problem = "P3"  # Failure after completed P2 concerns the next dispatch.
        if last is None or last["status"] == "ok":
            failure_id = f"{case}-failure-{failure_index}"
            construction_id = f"{case}-wave_stair"
            work.append(dict(evaluation_id=failure_id, construction_id=construction_id,
                case_id=case, problem=problem,
                call=dict(call_id=failure_id, kind="validation", status="failed",
                    wall_seconds=0, started_at=m["finished_at"], finished_at=m["finished_at"],
                    exit_code=None), artifacts={}, validation_failure=failure))
    # Seal immutable source records before any feed points at them.
    manifest_archive = seal_snapshot(folder, "manifest.json")
    ledger_archive = seal_snapshot(folder, "call-ledger.json")
    rows, summary = [], []
    for e in work:
        case, problem, call = e["case_id"], e["problem"], e["call"]
        if case not in CASES or problem not in ("P2", "P3"):
            raise ValueError("unexpected attempted case/problem")
        cid = e["construction_id"]
        if cid != f"{case}-wave_stair":
            raise ValueError("unexpected stair construction ID")
        c = constructions.get(cid)
        solver = next((x for x in calls if x["kind"] == "solver" and x["call_id"] == cid), None)
        success = call["status"] == "ok" and e["evaluation_id"] in evals
        result = read_art(e["artifacts"]["result"]) if success else {}
        audit_state = None
        if success and problem == "P3":
            audit_state = e.get("p3_audit")
            if (audit_state is None or not audit_state.get("passed")) and not any(f["case_id"] == case
                                                for f in m.get("failures", [])):
                raise ValueError("successful P3 lacks audit and matching failure receipt")
        audit_passed = bool(audit_state and audit_state.get("passed"))
        identity = dict(graph_sha256=next(x["sha256"] for x in m["identity"]["verified_files"]
            if x["manifest_path"] == f"data/case_{case}.json"),
            config_sha256=m["identity"]["config_sha256"],
            official_sha256=m["identity"]["official_code_hash"],
            plan_sha256=c["plan"]["sha256"] if c else None)
        row = copy.deepcopy(templates[problem])
        row.update(attempt_id=m["run_id"] + "-" + e["evaluation_id"], revision=1,
            run_id=m["run_id"], algorithm_id="q3-wave-stair", algorithm_name="首波容量阶梯与尾操作优先构造",
            variant="wave_stair", solver_commit=SOLVER_COMMIT, status="ok" if success else call["status"],
            case_id=case, cores=5, observed_at=call["started_at"], source_url=TASK,
            parameters=dict(cores=5, requested_cores=5,
                active_cores=c["active_cores"] if c else None, deterministic=True,
                candidate_policy="one direct first-wave capacity stair; no E0 selection",
                guard="strict homogeneous jobs and private tensor signatures; J=qk+1, beta/U/h stair, one split tail",
                fallback="runner stops before E0 when structural guard rejects candidate",
                batch_budget=m["budget"], resource_context=m["resource_context"],
                internal_E0=0, internal_E1=0, internal_E2=0),
            notes=["067 k5 research pilot: one cold first-wave stair plan and up to two external E0s.",
                   "P2/P3 share the same construction ID and plan; new calls counted once in sealed ledger.",
                   "One worker; only the final job is split across five cores; beta/U/h stair and tail-first order are direct rules.",
                   "Historical static bound and analysis wall are not reused in the measured cold call.",
                   "Historical pipeline 067 P2/P3=15686331 at c514edf0 is reference only, not rerun or included in new calls.",
                   "Whole-job lower bound 12446880 and same-identity captain result 12237901 are historical references, not candidate-selection inputs.",
                   "This is not a unified full500 result or independent acceptance."])
        if success and problem == "P3":
            row["parameters"]["post_E0_audit"] = "passed" if audit_passed else "failed"
            row["notes"].append("P3 post-E0 cache/workload audit " +
                                ("passed; details in run receipt." if audit_passed else
                                 "failed or interrupted; official E0 bytes preserved and separate failure receipt follows."))
        moved = result.get("data_movement_bytes", {})
        row["identity"] = identity
        row["metrics"] = dict(makespan_cycles=result.get("makespan"),
            solver_wall_seconds=solver["wall_seconds"] if solver else None,
            evaluation_wall_seconds=call["wall_seconds"] if call["kind"] == "E0" else None,
            ddr_bytes=moved.get("scheduled_copy_bytes"), extra_ddr_bytes=moved.get("added_copy_bytes"),
            spill_bytes=moved.get("spill_added_copy_bytes"),
            cache_hit_rate=result.get("cache_stats", {}).get("hit_rate"))
        row["evaluator"]["commit"] = m["identity"]["runner_commit"]
        receipt = dict(schema="q3-wave-stair-attempt-v1", run_id=m["run_id"],
            solver_commit=SOLVER_COMMIT, runner_commit=m["identity"]["runner_commit"],
            identity=identity, construction=c, evaluation=e, environment=m["environment"],
            resource_context=m["resource_context"], resource_checks=m["resource_checks"],
            sealed_manifest=manifest_archive, sealed_call_ledger=ledger_archive,
            post_E0_audit=(dict(status="passed", detail=audit_state) if audit_passed else
                           dict(status="failed", detail=audit_state, reason="see manifest failures") if success and problem == "P3" else None),
            note="P2/P3 share a single cold construction. Batch counts are in the sealed ledger.")
        destination = folder / case / "wave_stair" / (problem if success else "failed-" + call["call_id"])
        run_path = destination / "run.json"
        write_json(run_path, receipt)
        row["artifacts"] = {name: spec(ref) for name, ref in e["artifacts"].items()}
        if c:
            row["artifacts"]["plan"] = spec(c["plan"])
        row["artifacts"].update(run=artifact(run_path), manifest=spec(manifest_archive))
        p = row["provenance"]
        p["solver"].update(source=source(SOLVER_COMMIT,
            "src/q3_yuanzhifang/wave_stair.py", "main"),
            method="Strict homogeneous job guard; two-pass tail DP and per-position capacity proxy beta give U and h+c first-wave sizes. "
                   "The tail runs first at its positions; remaining full jobs use minimum balanced waves. "
                   "Cold call includes zero-lag FIFO bound and singleton derive; no internal E0 or official score prediction.",
            references=["https://github.com/huaweibei123/huaweicup2026/blob/" +
                        m["identity"]["runner_commit"] + "/docs/a/q3-yuanzhifang/STAIR_MEASUREMENT.md"],
            upstream=[source(x["commit"], x["path"], "dependency")
                      for x in m["identity"]["implementation"] if x["path"] !=
                      "src/q3_yuanzhifang/wave_stair.py"])
        p["runner"] = dict(source=source(m["identity"]["runner_commit"],
            m.get("runner_source_path", "src/q3_yuanzhifang/stair_benchmark.py"), "main"),
            argv=m["argv"], working_directory=".")
        p["environment"] = m["environment"]
        p["producer_session"] = m["producer_session"]
        p["missing_reasons"].update(m.get("environment_missing_reasons", {}))
        p["measurement"].update(started_at=solver["started_at"] if solver else m["started_at"],
            finished_at=call["finished_at"],
            budget=dict(wall_seconds=180, candidate_limit=1, stop_reason=m["stop_reason"]),
            calls=dict(solver=1 if solver else 0, E0=1 if call["kind"] == "E0" else 0, E1=0, E2=0),
            offline_costs=m["offline_costs"], failure=None)
        if not success:
            p["measurement"]["failure"] = dict(stage=call["kind"],
                reason=e.get("validation_failure", {}).get("reason", m["stop_reason"]),
                exit_code=call.get("exit_code"), elapsed_seconds=call["wall_seconds"])
            if call.get("exit_code") is None:
                p["missing_reasons"]["provenance.measurement.failure.exit_code"] = "No child exit code."
        row["baseline"] = baseline(case, identity) if success else None
        row["cache_pair"] = None
        if success and problem == "P3":
            paired = next((x for x in m["evaluations"] if x["construction_id"] == cid and x["problem"] == "P2"), None)
            if paired:
                row["cache_pair"] = dict(**identity, cores=5, route="E0",
                                         result=spec(paired["artifacts"]["result"]))
        rows.append(row)
        summary.append(dict(problem=problem, case_id=case, cores=5, variant="wave_stair",
                            status=row["status"], **row["metrics"]))
    stamp = utc().replace("-", "").replace(":", "").split(".")[0] + "Z"
    feed_path = folder / f"board-feed-{stamp}-stair.json"
    if feed_path.exists():
        raise FileExistsError(feed_path)
    write_json(feed_path, dict(schema_version=1, submission_version=1, records=rows))
    with (folder / "summary.csv").open("w", encoding="utf-8", newline="") as out:
        fields = ["problem", "case_id", "cores", "variant", "status", "makespan_cycles",
                  "solver_wall_seconds", "evaluation_wall_seconds", "ddr_bytes", "extra_ddr_bytes",
                  "spill_bytes", "cache_hit_rate"]
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)
    write_json(folder / "export-receipt.json", dict(exported_at=utc(), feed=artifact(feed_path),
        records=len(rows), calls=m["calls"], sealed_manifest=manifest_archive,
        sealed_call_ledger=ledger_archive, template_source=TEMPLATE,
        note="Export only; no solver or evaluator calls. Feed references immutable snapshots, not live ledger."))
    print(json.dumps(dict(feed=feed_path.relative_to(ROOT).as_posix(), records=len(rows), calls=m["calls"])))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", nargs="?", type=Path, default=Path(OUT))
    args = ap.parse_args()
    export((ROOT / args.folder).resolve())


if __name__ == "__main__":
    main()
