"""Frozen Stage E-4: 100 cold portfolio solvers and at most 100 external E0s.

Default is preflight only. Execution additionally needs an explicitly recorded
measurement-window token. Existing run directories are never resumed/overwritten.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import shutil
import sys
import time

from benchmark import (ROOT, utc, sha, dump, git, relative, verify_source,
                       official_check, environment, call, compress)
from reuse_e import SOLVER, CAPTAIN, CASES, SOURCES, GitBlobs, require, verify_record, exact_match

SESSION = "yuanzhifang30-sudo/s-0e4f42cad8a647f18ea653130e34c5a9"
BASE = "results/a/q1-yuanzhifang/stage-e-4-20260925"
OUTPUT = BASE + "/run"
INDEX = BASE + "/evidence-index.json"
SCRIPT = "src/q1_yuanzhifang/portfolio.py"
ALGORITHM = "q1-two-structure-ddr-selector"
VARIANT = "bounded-or-fork-gate-plus-ddr-v1"
BUDGET = {"solver": 100, "E0": 100, "E1": 0, "E2": 0, "workers": 1,
          "wall_seconds": 1800, "solver_timeout_seconds": 30,
          "evaluation_timeout_seconds": 90, "retries": 0}
SOLVER_FILES = [SCRIPT, "src/q1_yuanzhifang/construct.py", "src/q1_yuanzhifang/diagnose.py",
                "src/q1_yuanzhifang/fork_frontier.py", "src/q1_yuanzhifang/upstream_bounded/__init__.py",
                "src/q1_yuanzhifang/upstream_bounded/bounded_tasks.py",
                "src/q1_yuanzhifang/upstream_bounded/component_pack.py",
                "src/q1_yuanzhifang/upstream_bounded/tree_frontier.py"]
RUNNER_FILES = ["src/q1_yuanzhifang/benchmark_e.py", "src/q1_yuanzhifang/reuse_e.py",
                "src/q1_yuanzhifang/benchmark.py", "src/q1_yuanzhifang/export_e.py"]


def artifact(path):
    return {"path": relative(path), "sha256": sha(path.read_bytes())}


def preflight(args):
    t0 = time.perf_counter()
    runner = git("rev-parse", "HEAD").decode().strip()
    require(not git("status", "--porcelain", "--untracked-files=no"), "Tracked runner worktree must be clean")
    require(not (ROOT / OUTPUT).exists(), "Stage E-4 already has a run directory; no overwrite or retry")
    manifest = json.loads((ROOT / "docs/a/source-manifest.json").read_bytes())
    official = official_check(ROOT, manifest)
    expected = {x["path"]: x["sha256"] for x in manifest["files"]}
    inputs = {}
    for name in ("config.txt", *(f"case_{c}.json" for c in CASES)):
        inputs[name] = sha((args.graphs / name).read_bytes())
        require(inputs[name] == expected["data/" + name], "Frozen input mismatch: " + name)
    sources = verify_source(ROOT, SOLVER, SOLVER_FILES)
    provenance_path = "src/q1_yuanzhifang/upstream_bounded/provenance.json"
    fixed_provenance = git("show", f"{SOLVER}:{provenance_path}")
    materialized_provenance = (ROOT / provenance_path).read_bytes()
    require(json.loads(fixed_provenance) == json.loads(materialized_provenance), "Upstream attribution metadata mismatch")
    for item in json.loads(fixed_provenance)["files"]:
        require(sha(git("show", f"{CAPTAIN}:" + item["source_path"])) == item["upstream_sha256"], "Upstream original source hash mismatch")
        require(sources[item["destination_path"]] == item["adapted_sha256"], "Adapted source hash mismatch")
    runner_sources = verify_source(ROOT, runner, RUNNER_FILES + [INDEX])
    index = json.loads((ROOT / INDEX).read_bytes())
    require(index["schema"] == "q1-stage-e-exact-byte-evidence-v1" and index["solver_commit"] == SOLVER, "Wrong evidence index")
    require(index["official_code_hash"] == manifest["official_code_hash"], "Evidence index official mismatch")
    require([(f["commit"], f["path"], f["candidate"]) for f in index["feeds"]] == list(SOURCES), "Unexpected evidence source")
    require(len(index["entries"]) == 109 and len(index["singlecore"]) == 100, "Incomplete historical coverage")
    if args.execute:
        require(bool(args.window_token), "Execution requires the actual granted measurement-window token")
    return {"runner_commit": runner, "solver_commit": SOLVER, "source_sha256": sources,
            "runner_source_sha256": runner_sources, "official_source_sha256": official,
            "upstream_provenance": {"path": provenance_path, "fixed_git_sha256": sha(fixed_provenance),
                                    "materialized_sha256": sha(materialized_provenance),
                                    "note": "Non-executable JSON metadata may have checkout CRLF; parsed content and every original/adapted source hash verified. Executable Python bytes match the solver commit exactly."},
            "official_code_hash": manifest["official_code_hash"], "input_sha256": inputs,
            "evidence_index": artifact(ROOT / INDEX), "preflight_wall_seconds": time.perf_counter() - t0}, index, manifest


def command(args, case, folder):
    return [sys.executable, "-X", "utf8", "-B", SCRIPT,
            relative(args.graphs / f"case_{case}.json"), relative(folder / f"case_{case}_multicore_res.json"),
            "--cores", "4", "--config", relative(args.graphs / "config.txt"),
            "--diagnostics", relative(folder / "diagnostics.json")]


def domain_failure(stderr):
    text = stderr.lower()
    if any(x in text for x in ("filenotfounderror", "no such file", "permission", "disk", "memoryerror", "modulenotfounderror", "importerror", "syntaxerror", "keyerror", "typeerror")):
        return False
    return any(x in text for x in ("cyclic", "cycle", "capacity", "deadlock", "invalid plan", "task dependency", "joint order", "step3schedulingerror", "step2schedulingerror", "no feasible"))


def reuse_quality(entry, plan_bytes, folder, manifest):
    with GitBlobs() as blobs:
        data, checked = verify_record(blobs, entry["commit"], entry["record"], manifest)
    require(data["plan"] == plan_bytes, "Exact SHA matched but historical plan bytes differ")
    require(checked == entry["checked"], "Historical evidence facts differ from frozen index")
    destination = folder / "reused_e0"
    destination.mkdir()
    copied = {}
    for kind in ("plan", "result", "trace", "run"):
        suffix = ".json.gz" if entry["record"]["artifacts"][kind]["path"].endswith(".gz") else ".json"
        path = destination / ("original-" + kind + suffix)
        path.write_bytes(data[kind])
        copied[kind] = artifact(path)
    source = {"commit": entry["commit"], "feed_path": entry["feed_path"], "feed_sha256": entry["feed_sha256"],
              "attempt_id": entry["record"]["attempt_id"], "record": entry["record"],
              "checked": checked, "copied_originals": copied,
              "scope": "Exact plan bytes and frozen graph/config/official identity; old quality reused after new solver exited. Zero new E0 calls. Historical wall is not this attempt's evaluation wall."}
    dump(destination / "reuse.json", source)
    result = json.loads(gzip.decompress(data["result"]) if copied["result"]["path"].endswith(".gz") else data["result"])
    return source, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphs", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--window-token")
    args = parser.parse_args()
    args.graphs = args.graphs.resolve()
    protocol, index, manifest = preflight(args)
    if not args.execute:
        print(json.dumps({"preflight": "ok", "budget": BUDGET, "cases": len(CASES), "cores": 4,
                          "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}, **protocol}))
        return
    hardware = environment()
    hardware["threads"] = None
    protocol.update(producer_session=SESSION, task_url="https://github.com/huaweibei123/huaweicup2026/issues/98",
                    cases=CASES, cores=4, algorithm_id=ALGORITHM, variant=VARIANT, budget=BUDGET,
                    environment=hardware, window_token=args.window_token,
                    parameters={"bounded": {"packet_factor": 4, "trigger_ops": 4096, "chunk_ops": 1024},
                                "fork": {"grain": 4, "frontier_tasks": "core"},
                                "selection": "strictly smaller fixed-plan compute/gate lower bound plus mandatory boundary DDR service; tie=bounded", "candidate_limit": 2},
                    preparation="Reuse existing Python 3.12 uv sync --locked environment; no new training/compilation. Both graph constructions are rebuilt in every cold solver. Read-only historical evidence/index audit and input hashing occur outside solver, are separately timed, and are never visible to the solver. OS caches not flushed.",
                    solver_scope="Outer subprocess.run perf_counter from fresh interpreter launch through imports, read graph/config, both constructions, proxy computation, selection, structural validation, final plan/diagnostics write and process exit; no online E0/E1/E2 or Task compilation.",
                    evaluation_scope="For new E0: separate unmodified official P1 CLI launch through result/trace/log write and exit. For exact-byte reuse: no E0 process or new evaluation wall; historical receipt remains under reused_e0 and is excluded from current timings.",
                    argv_note="Interpreter path normalized to python; version and lock identity recorded. Remaining relative arguments are those actually executed from the worktree root.")
    out = ROOT / OUTPUT
    out.mkdir(parents=True, exist_ok=False)
    dump(out / "protocol.json", protocol)
    rows, calls = [], {"solver": 0, "E0": 0, "E1": 0, "E2": 0}
    t0, started, stop = time.perf_counter(), utc(), "complete"
    events = (out / "events.jsonl").open("x", encoding="utf-8", newline="\n")
    unrun = list(CASES)

    def event(value):
        events.write(json.dumps({"utc": utc(), **value}) + "\n")
        events.flush()

    try:
        for case in CASES:
            if time.perf_counter() - t0 > BUDGET["wall_seconds"] - 125:
                stop = "batch_budget_reserve"; break
            if shutil.disk_usage(out).free < 512 * 1024 * 1024:
                stop = "insufficient_disk_headroom"; break
            folder = out / f"{case}-k4"
            folder.mkdir()
            run = {"case_id": case, "cores": 4, "variant": VARIANT, "solver_commit": SOLVER,
                   "runner_commit": protocol["runner_commit"], "started_at": utc(), "status": "running",
                   "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}, "artifacts": {}, "failure": None}
            stage = "solver"
            try:
                calls["solver"] += 1; run["calls"]["solver"] = 1; unrun.remove(case)
                event({"event": "launch", "stage": "solver", "case_id": case, "calls": dict(calls)})
                run["solver"] = call(command(args, case, folder), folder, "solver", 30)
                event({"event": "finished", "stage": "solver", "case_id": case, "process": run["solver"]})
                result = None
                if run["solver"]["status"] == "ok":
                    plan = folder / f"case_{case}_multicore_res.json"
                    plan_bytes = plan.read_bytes()
                    obj = json.loads(plan_bytes)
                    require(set(obj) == {"node_to_subgraph", "core_schedules"} and len(obj["core_schedules"]) == 4, "Solver contract mismatch")
                    run["plan_sha256"] = sha(plan_bytes)
                    diagnostic = json.loads((folder / "diagnostics.json").read_bytes())
                    require(diagnostic["candidate_count"] == 2 and diagnostic["selected"] in ("bounded", "fork"), "Portfolio candidate contract mismatch")
                    run["selected"] = diagnostic["selected"]
                    run["candidate_proxy_cycles"] = {k: v["serialized_resource_proxy_cycles"] for k, v in diagnostic["costs"].items()}
                    match = exact_match(index, case, 4, run["selected"], plan_bytes)
                    stage = "evaluation"
                    if match:
                        tr = time.perf_counter()
                        run["reuse"], result = reuse_quality(match, plan_bytes, folder, manifest)
                        run["evaluation"] = {"status": "reused", "new_call": False, "wall_seconds": None,
                                             "evidence_verification_wall_seconds": time.perf_counter() - tr}
                        run["quality_source"] = "historical_exact_plan_bytes"
                        event({"event": "reuse", "case_id": case, "source_attempt": match["record"]["attempt_id"], "new_E0_calls": 0})
                    else:
                        argv = [sys.executable, "-X", "utf8", "-B", "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py",
                                relative(args.graphs / f"case_{case}.json"), relative(plan), "--config", relative(args.graphs / "config.txt"),
                                "--output", relative(folder / "result.json"), "--trace-output", relative(folder / "trace.json"), "--log-output", relative(folder / "result.txt")]
                        calls["E0"] += 1; run["calls"]["E0"] = 1
                        event({"event": "launch", "stage": "E0", "case_id": case, "calls": dict(calls)})
                        run["evaluation"] = call(argv, folder, "evaluation", 90)
                        event({"event": "finished", "stage": "E0", "case_id": case, "process": run["evaluation"]})
                        run["quality_source"] = "new_external_E0"
                        if run["evaluation"]["status"] == "ok":
                            result = json.loads((folder / "result.json").read_bytes())
                process = run[stage]
                run["status"] = "ok" if process["status"] == "reused" else process["status"]
                if run["status"] != "ok":
                    errors = (folder / f"{stage}.stderr.txt").read_text(encoding="utf-8")
                    run["failure"] = {"stage": stage, "reason": errors or process.get("error") or process["status"],
                                      "exit_code": process["returncode"], "elapsed_seconds": process["wall_seconds"]}
                    if process["status"] == "infrastructure_failure" or (process["status"] == "failed" and not domain_failure(errors)):
                        stop = "unexpected_supervision_or_process_failure"
                    if run["status"] == "infrastructure_failure":
                        run["status"] = "failed"
                else:
                    require(result["scene"] == "A" and result["num_cores"] == 4, "E0 scenario mismatch")
                    run.update(makespan_cycles=result["makespan"], data_movement_bytes=result["data_movement_bytes"], task_count=len(result["step3_by_task"]))
                for name in ("result.json", "trace.json"):
                    if (folder / name).exists():
                        run["artifacts"][name] = compress(folder / name)
            except Exception as error:
                stop = "supervision_exception"
                run["status"] = "failed"
                run["failure"] = {"stage": "supervision-after-" + stage, "reason": f"{type(error).__name__}: {error}", "exit_code": None, "elapsed_seconds": None}
                run.pop("makespan_cycles", None)
            finally:
                run["finished_at"] = utc()
                dump(folder / "run.json", run)
                rows.append(run)
                event({"event": "attempt_saved", "case_id": case, "status": run["status"], "calls": dict(calls)})
            print(json.dumps({"case_id": case, "status": run["status"], "selected": run.get("selected"), "quality_source": run.get("quality_source"),
                              "makespan_cycles": run.get("makespan_cycles"), "solver_s": run.get("solver", {}).get("wall_seconds"), "new_E0_s": run.get("evaluation", {}).get("wall_seconds")}), flush=True)
            if stop != "complete":
                break
    finally:
        events.close()
        dump(out / "rows.json", rows)
        metadata = [relative(p) for p in out.rglob("*") if p.name.startswith("._") or p.name in (".DS_Store", "__MACOSX")]
        dump(out / "completion.json", {"status": stop, "started_at": started, "finished_at": utc(), "wall_seconds": time.perf_counter() - t0,
                                      "calls": calls, "records": len(rows), "unrun": unrun, "reused_E0_results": sum("reuse" in r for r in rows),
                                      "metadata_scan": metadata, "dot_clean": "unavailable on Windows"})
    if stop != "complete":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
