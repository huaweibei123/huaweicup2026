"""Export existing pilot bytes; never launch a solver or evaluator."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path
import sys

from benchmark import (ROOT, DEFAULT_OUTPUT, SOLVER_COMMIT, SESSION, artifact,
                       sha, utc, write_json)

REPO = "huaweibei123/huaweicup2026"
TASK = "https://github.com/" + REPO + "/issues/51"
UPSTREAM = "a4e7ee13310d693ec4fb5cc236669ceb3b172d1f"


def spec(value):
    return {key: value[key] for key in ("path", "sha256")}


def source(commit, path, entrypoint):
    return dict(repo=REPO, commit=commit, path=path, entrypoint=entrypoint)


def read_art(value):
    path = ROOT / value["path"]
    if sha(path) != value["sha256"]:
        raise ValueError("artifact SHA mismatch: " + value["path"])
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
        if "raw_sha256" in value:
            import hashlib
            if hashlib.sha256(raw).hexdigest() != value["raw_sha256"]:
                raise ValueError("unpacked SHA mismatch: " + value["path"])
    return json.loads(raw)


def baseline(case, identity):
    folder = ROOT / "results/benchmark-board/official-singlecore-20260924" / case
    run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    if any(run[a] != identity[b] for a, b in (
            ("graph_sha256", "graph_sha256"), ("config_sha256", "config_sha256"),
            ("official_code_hash", "official_sha256"))):
        raise ValueError("singlecore baseline identity mismatch: " + case)
    ref = spec(run["artifacts"]["result.json"])
    result = read_art(ref)
    if result.get("scene") != "A" or result.get("num_cores") != 1 or run["status"] != "ok":
        raise ValueError("invalid frozen singlecore baseline: " + case)
    return dict(**{key: identity[key] for key in (
        "graph_sha256", "config_sha256", "official_sha256")}, route="E0",
        entrypoint="singlecore_evaluate.evaluate_singlecore", result=ref)


def export(folder):
    manifest_path = folder / "manifest.json"
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    constructors = {c["construction_id"]: c for c in m["constructions"]}
    evaluations = {e["evaluation_id"]: e for e in m["evaluations"]}
    actual = list(evaluations.values())
    calls = json.loads((folder / "call-ledger.json").read_text(encoding="utf-8"))
    # Failed calls stay as separate failed attempts. They never acquire a best-plan result.
    for call in calls:
        if call["status"] == "ok":
            continue
        if call["kind"] == "E0":
            construct_id, problem = call["call_id"].rsplit("-", 1)
        else:
            construct_id, problem = call["call_id"], "P3"
        if construct_id not in constructors:
            case, variant = construct_id.split("-", 1)
            graph_hash = next(v["sha256"] for v in m["identity"]["verified_files"]
                              if v["manifest_path"] == f"data/case_{case}.json")
            constructors[construct_id] = dict(construction_id=construct_id, case_id=case,
                                              variant=variant, graph_sha256=graph_hash,
                                              plan=None, solver=call, detail={}, alias_of=None)
        actual.append(dict(evaluation_id=call["call_id"], construction_id=construct_id,
                           problem=problem, call=call, artifacts={}))
    rows = []
    for evaluation in actual:
        c = constructors[evaluation["construction_id"]]
        call = evaluation["call"]
        problem, case = evaluation["problem"], c["case_id"]
        success = call["status"] == "ok"
        result = read_art(evaluation["artifacts"]["result"]) if success else {}
        identity = dict(graph_sha256=c["graph_sha256"],
                        config_sha256=m["identity"]["config_sha256"],
                        official_sha256=m["identity"]["official_code_hash"],
                        plan_sha256=c["plan"]["sha256"] if c["plan"] else None)
        aliases = [other["construction_id"] for other in m["constructions"]
                   if other["alias_of"] == c["construction_id"]]
        receipt = dict(schema="q3-sharing-attempt-v1", run_id=m["run_id"],
                       solver_commit=SOLVER_COMMIT, runner_commit=m["identity"]["runner_commit"],
                       identity=identity, construction=c, evaluation=evaluation,
                       plan_aliases=aliases, environment=m["environment"],
                       note="One construction serves a P2/P3 pair; do not sum solver calls twice. "
                            "Alias constructions have zero new E0 calls and no separate feed record.")
        receipt_path = folder / case / c["variant"] / problem / "run.json"
        write_json(receipt_path, receipt)
        arts = {name: spec(value) for name, value in evaluation["artifacts"].items()}
        if c["plan"]:
            arts["plan"] = spec(c["plan"])
        arts.update(run=artifact(receipt_path), manifest=artifact(manifest_path))
        moved, cache = result.get("data_movement_bytes", {}), result.get("cache_stats", {})
        missing = {
            "provenance.environment.peak_rss_bytes": "Peak process RSS was not instrumented in this batch.",
            "provenance.measurement.seed": "Deterministic direct constructor; no random seed. PYTHONHASHSEED=0 is fixed."}
        if m["environment"]["ram_bytes"] is None:
            missing["provenance.environment.ram_bytes"] = "OS memory query returned no value."
        failure = None if success else dict(stage=call["kind"], reason=m["stop_reason"],
                                           exit_code=call.get("exit_code"), elapsed_seconds=call["wall_seconds"])
        if failure and failure["exit_code"] is None:
            missing["provenance.measurement.failure.exit_code"] = "Process did not produce an exit code."
        row = dict(
            attempt_id=f"{m['run_id']}-{evaluation['evaluation_id']}", revision=1,
            run_id=m["run_id"], algorithm_id="q3-input-sharing", algorithm_name="共享输入束直接构造",
            variant=c["variant"], solver_commit=SOLVER_COMMIT,
            parameters=dict(cores=4, deterministic=True, lag_policy="length_per_core//8 guarded by MVM resource_word",
                            plan_aliases=aliases, batch_budget=m["budget"], internal_E0=0, internal_E1=0,
                            internal_E2=0, selection="one prescribed direct construction; no online best selection"),
            problem=problem, case_id=case, cores=4, status=call["status"],
            metrics=dict(makespan_cycles=result.get("makespan"),
                         solver_wall_seconds=c["solver"]["wall_seconds"],
                         evaluation_wall_seconds=call["wall_seconds"] if call["kind"] == "E0" else None,
                         ddr_bytes=moved.get("scheduled_copy_bytes"),
                         extra_ddr_bytes=moved.get("added_copy_bytes"),
                         spill_bytes=moved.get("spill_added_copy_bytes"),
                         cache_hit_rate=cache.get("hit_rate") if problem == "P3" else None),
            evaluator=dict(route="E0", commit=m["identity"]["runner_commit"],
                           entrypoint="multicore_cut_evaluate_problem_" + problem[1:] + "." +
                           ("evaluate_problem_3" if problem == "P3" else "evaluate_scene_b")),
            identity=identity, artifacts=arts, runtime_id="yuanzhifang-windows-ryzen5600h-py31214-w1-20260924",
            observed_at=call["started_at"], timing=dict(solver_includes_evaluation=False,
                evaluation_precision="time.perf_counter outer process wall; seconds, no rounding", utc="UTC"),
            provenance=dict(producer_session=SESSION, task_url=TASK,
                solver=dict(source=source(SOLVER_COMMIT, "src/q3_yuanzhifang/construct.py", "main"),
                            authors=["yuanzhifang30-sudo", "NikolaStarx"],
                            method="Fixed resource_word/affine_eighth baseline; shared_order aligns input bundle order; "
                                   "shared_place greedily reduces added ingress under baseline per-Pipe load caps with full fallback. "
                                   "All variants retain the strict MVM guard. No online evaluator or search.",
                            references=[TASK + "#issuecomment-5815599293",
                                        "https://github.com/" + REPO + "/blob/" + SOLVER_COMMIT +
                                        "/docs/a/q3-yuanzhifang/METHOD.md"],
                            upstream=[source(UPSTREAM, "src/q3/construct.py", "Index.build")],
                            selected_algorithm_id=None, selected_solver_commit=None),
                runner=dict(source=source(m["identity"]["runner_commit"],
                                          "src/q3_yuanzhifang/benchmark.py", "main"),
                            argv=m["argv"], working_directory="."),
                environment=m["environment"],
                measurement=dict(started_at=c["solver"]["started_at"], finished_at=call["finished_at"],
                    seed=None, repeat_index=0, cold_start=True,
                    solver_scope="Outer fresh Python process startup through import, input read, analysis, construction, "
                                 "structural checks, final plan write and process exit. E0 is external, excluded. OS cache not flushed.",
                    evaluation_scope="Outer fresh official CLI process startup through config/graph/plan read, evaluation, "
                                     "complete result/trace/log writes and process exit; no source modification.",
                    budget=dict(wall_seconds=600, candidate_limit=12, stop_reason=m["stop_reason"]),
                    calls=dict(solver=1, E0=1 if call["kind"] == "E0" else 0, E1=0, E2=0),
                    offline_costs=m["offline_costs"], failure=failure), missing_reasons=missing),
            notes=["Actual unique-plan E0 call. Aliases are listed but are not additional E0 attempts.",
                   "P2/P3 records share construction_id=" + c["construction_id"] +
                   "; authoritative nonduplicated totals are in call-ledger.json.",
                   "Only 4 public development graphs at k=4; one observation per constructor, nonexclusive host; "
                   "not an online selector, full100 result, blind review or final independent acceptance."],
            source_url=TASK + "#issuecomment-5815599293", baseline=None, cache_pair=None)
        if success:
            row["baseline"] = baseline(case, identity)
            if problem == "P3":
                paired = evaluations[c["construction_id"] + "-P2"]
                row["cache_pair"] = dict(**identity, cores=4, route="E0",
                                         result=spec(paired["artifacts"]["result"]))
        rows.append(row)
    stamp = utc().replace("-", "").replace(":", "").split(".")[0] + "Z"
    feed = folder / f"board-feed-{stamp}-unique-plans.json"
    if feed.exists():
        raise FileExistsError(feed)
    write_json(feed, dict(schema_version=1, submission_version=1, records=rows))
    summary = []
    for c in m["constructions"]:
        owner = c["alias_of"] or c["construction_id"]
        for problem in ("P2", "P3"):
            e = evaluations.get(owner + "-" + problem)
            if not e:
                continue
            result = read_art(e["artifacts"]["result"])
            move = result["data_movement_bytes"]
            summary.append(dict(case_id=c["case_id"], variant=c["variant"], problem=problem,
                cores=4, makespan_cycles=result["makespan"],
                solver_wall_seconds=c["solver"]["wall_seconds"],
                evaluation_wall_seconds="" if c["alias_of"] else e["call"]["wall_seconds"],
                evaluation_reused_from=owner if c["alias_of"] else "",
                plan_sha256=c["plan"]["sha256"], extra_ddr_bytes=move["added_copy_bytes"],
                spill_bytes=move["spill_added_copy_bytes"],
                cache_hit_rate=result.get("cache_stats", {}).get("hit_rate", ""),
                ingress_proxy_bytes=c["detail"].get("ingress_proxy_bytes")))
    if summary:
        with (folder / "summary.csv").open("w", encoding="utf-8", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=list(summary[0]))
            writer.writeheader()
            writer.writerows(summary)
    write_json(folder / "export-receipt.json", dict(exported_at=utc(), feed=artifact(feed),
               records=len(rows), constructions=len(m["constructions"]), actual_calls=m["calls"],
               unique_plans=len({e["construction_id"] for e in m["evaluations"]}),
               aliases=[dict(construction_id=c["construction_id"], alias_of=c["alias_of"])
                        for c in m["constructions"] if c["alias_of"]],
               note="Export and baseline evidence reuse only: zero new solver/E0/E1/E2 calls."))
    print(json.dumps(dict(feed=feed.relative_to(ROOT).as_posix(), records=len(rows), calls=m["calls"])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", type=Path, default=Path(DEFAULT_OUTPUT))
    args = parser.parse_args()
    export((ROOT / args.folder).resolve())


if __name__ == "__main__":
    main()
