"""Stage G: guarded intact-chain prefetch; only one new 051/k5 candidate attempt.

Default mode only checks inputs/source. --execute is required to consume the
separate Stage G budget, after a fixed solver SHA and scheduling window exist.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import re
import shutil
import sys
import time

from benchmark import (ROOT, SESSION, utc, sha, dump, git, relative, verify_source,
                       official_check, environment, call, compress)

SOLVER = "e29685da0268420f2d881246603763d6bf8baf5b"
NEW_SCRIPT = "src/q1_yuanzhifang/prefetch_frontier.py"
OUTPUT = "results/a/q1-yuanzhifang/stage-g-20260925/run"
SCENARIOS = (("051", 5),)
VARIANTS = ("fixed-root-four-two-v1",)
BUDGET = {"solver": 1, "E0": 1, "E1": 0, "E2": 0, "workers": 1,
          "wall_seconds": 180, "solver_timeout_seconds": 30,
          "evaluation_timeout_seconds": 90, "retries": 0}
NEW_FILES = [NEW_SCRIPT, "src/q1_yuanzhifang/star_frontier.py", "src/q1_yuanzhifang/construct.py",
             "src/q1_yuanzhifang/fork_frontier.py", "src/q1_yuanzhifang/diagnose.py"]
OLD_COMMIT = "88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a"
OLD_FEED = "results/a/q1-yuanzhifang/stage-c-20260924/board-feed-20260924T153000Z-stage-c.json"


def preflight(args):
    if not re.fullmatch("[0-9a-f]{40}", SOLVER or ""):
        raise ValueError("Stage G is preparation-only until parent freezes the solver SHA")
    manifest_raw = git("show", SOLVER + ":docs/a/source-manifest.json")
    assert (ROOT / "docs/a/source-manifest.json").read_bytes().replace(b"\r\n", b"\n") == manifest_raw
    manifest = json.loads(manifest_raw)
    runner = git("rev-parse", "HEAD").decode().strip()
    if git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Tracked runner worktree must be clean")
    if args.solver_commit != SOLVER:
        raise ValueError("Stage G solver identity differs from frozen task card")
    if (ROOT / OUTPUT).exists():
        raise ValueError("Stage G output directory already exists; no overwrite/retry")
    frozen = official_check(ROOT, manifest)
    verify_source(ROOT, SOLVER, ["data/raw/a/official/" + p for p in frozen])
    expected = {i["path"]: i["sha256"] for i in manifest["files"]}
    inputs = {}
    for name in ["config.txt", *(f"case_{c}.json" for c in sorted({c for c, _ in SCENARIOS}))]:
        inputs[name] = sha((args.graphs / name).read_bytes())
        if inputs[name] != expected["data/" + name]:
            raise ValueError("Frozen input mismatch: " + name)
    code = verify_source(ROOT, runner, ["src/q1_yuanzhifang/benchmark_g.py", "src/q1_yuanzhifang/benchmark.py",
                                       "src/q1_yuanzhifang/export_g.py", "src/q1_yuanzhifang/trace_c.py"])
    new_sources = None
    if args.solver_commit:
        if not re.fullmatch("[0-9a-f]{40}", args.solver_commit):
            raise ValueError("New solver commit must be a full lowercase SHA")
        new_sources = verify_source(ROOT, args.solver_commit, NEW_FILES)
    if args.execute and new_sources is None:
        raise ValueError("Execution requires a frozen new solver commit")
    if args.execute and not args.window_token:
        raise ValueError("Execution requires the parent's explicit START window token")
    old_raw = git("show", OLD_COMMIT + ":" + OLD_FEED)
    assert old_raw == (ROOT / OLD_FEED).read_bytes()
    old = next(r for r in json.loads(old_raw)["records"] if
               (r["case_id"], r["cores"], r["variant"]) == ("051", 5, "chain-atomic-grain4"))
    assert old["status"] == "ok" and old["metrics"]["makespan_cycles"] == 253856
    assert old["identity"]["graph_sha256"] == inputs["case_051.json"]
    assert old["identity"]["config_sha256"] == inputs["config.txt"]
    assert old["identity"]["official_sha256"] == manifest["official_code_hash"]
    for item in old["artifacts"].values():
        raw = (ROOT / item["path"]).read_bytes()
        assert raw == git("show", OLD_COMMIT + ":" + item["path"])
        assert sha(raw) == item["sha256"]
    old_result = json.loads(gzip.decompress((ROOT / old["artifacts"]["result"]["path"]).read_bytes()))
    assert old_result["makespan"] == 253856 and old_result["num_cores"] == 5 and old_result["scene"] == "A"
    return {"runner_commit": runner, "solver_commit": args.solver_commit,
            "source_sha256": code, "new_solver_source_sha256": new_sources,
            "official_source_sha256": frozen, "official_code_hash": manifest["official_code_hash"],
            "input_sha256": inputs, "manifest_git_sha256": sha(manifest_raw),
            "reused_stage_c": {"commit": OLD_COMMIT, "feed": OLD_FEED, "feed_sha256": sha(old_raw),
                               "attempt_id": old["attempt_id"], "artifacts": old["artifacts"], "makespan_cycles": 253856}}


def command(args, variant, case, cores, folder):
    graph = relative(args.graphs / f"case_{case}.json")
    plan = relative(folder / f"case_{case}_multicore_res.json")
    diagnostics = relative(folder / "diagnostics.json")
    python = [sys.executable, "-X", "utf8", "-B"]
    return [*python, NEW_SCRIPT, graph, plan, "--cores", str(cores),
            "--config", relative(args.graphs / "config.txt"), "--diagnostics", diagnostics]



def is_domain_failure(stderr):
    text = stderr.lower()
    # File/config/IO/programming faults must not be silently treated as an
    # invalid candidate and followed by more launches.
    infrastructure = ("filenotfounderror", "no such file", "permission", "disk", "memoryerror",
                      "modulenotfounderror", "importerror", "syntaxerror", "keyerror", "typeerror")
    if any(t in text for t in infrastructure):
        return False
    return any(t in text for t in ("cyclic", "cycle", "capacity", "deadlock", "invalid plan",
                                   "task dependency", "joint order", "step3schedulingerror",
                                   "step2schedulingerror", "no feasible"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graphs", type=Path, required=True)
    p.add_argument("--solver-commit", default=SOLVER)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--window-token", help="Literal parent START reference; required only for --execute")
    args = p.parse_args()
    args.graphs = args.graphs.resolve()
    protocol = preflight(args)
    if not args.execute:
        print(json.dumps({"preflight": "ok", "new_solver_frozen": protocol["new_solver_source_sha256"] is not None,
                          "scenarios": SCENARIOS, "budget": BUDGET, "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
                          **protocol}, ensure_ascii=False))
        return
    protocol.update(producer_session=SESSION, task_url="https://github.com/huaweibei123/huaweicup2026/issues/98",
                    measurement_window=args.window_token,
                    scenarios=SCENARIOS, variants=VARIANTS, budget=BUDGET, environment=environment(),
                    parameters={VARIANTS[0]: {"guard": "12 chains x 4 PIPE_V nodes, 11 binary reductions per round", "tail_core": 0, "first_round_chain_counts": [3, 3, 2, 2, 2], "later_round_chain_counts": [4, 2, 2, 2, 2], "fallback": "fork-frontier grain4 core tasks"}},
                    preparation="Reuse Stage A/B/C uv sync --locked environment; initial 14-package installation reported 43.79s before A. Parent reports 2 synthetic structural/model tests passing in 0.273s before source freeze, with no real-graph solver/E0; full development wall not recorded here. Stage F negative result and exposed Stage C evidence informed this intact-chain candidate; no held-out claim. No training or precomputed graph products reused by cold solver processes. Existing Stage C successful results are reused only for post-run comparison, with 0 baseline solver/E0 calls.",
                    solver_scope="Outer subprocess.run from new process launch, imports, graph/config input, all graph analysis/construction/validation, final plan and diagnostics writing to process exit. No online E0/E1/E2 calls. OS caches not flushed.",
                    evaluation_scope="Separate unmodified official E0 CLI process launch through full result, trace, text log creation and exit; outside solver wall.",
                    source_control="Both solver and runner sources checked against fixed Git objects before launch; output directory and files exclusive-create.",
                    argv_note="Executable normalized to python; actual interpreter version in environment. All following relative argv paths are exactly those used from runner root.")
    out = ROOT / OUTPUT
    out.mkdir(parents=True, exist_ok=False)
    dump(out / "protocol.json", protocol)
    events = (out / "events.jsonl").open("x", encoding="utf-8", newline="\n")
    rows, calls = [], {"solver": 0, "E0": 0, "E1": 0, "E2": 0}
    started, t0, stop = utc(), time.perf_counter(), "complete"
    unrun = [(v, c, k) for v in VARIANTS for c, k in SCENARIOS]

    def event(record):
        events.write(json.dumps({"utc": utc(), **record}, ensure_ascii=False) + "\n")
        events.flush()

    try:
        for variant in VARIANTS:
            for case, cores in SCENARIOS:
                if time.perf_counter() - t0 > 55:
                    stop = "batch_budget_reserve"; break
                if shutil.disk_usage(out).free < 200 * 1024 * 1024:
                    stop = "insufficient_disk_headroom"; break
                folder = out / f"{case}-k{cores}-{variant}"
                folder.mkdir()
                run = {"case_id": case, "cores": cores, "variant": variant,
                       "solver_commit": args.solver_commit,
                       "runner_commit": protocol["runner_commit"], "started_at": utc(),
                       "status": "running", "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
                       "artifacts": {}, "failure": None}
                stage_name = "solver"
                try:
                    calls["solver"] += 1; run["calls"]["solver"] += 1
                    unrun.remove((variant, case, cores))
                    event({"event": "launch", "stage": "solver", "case": case, "cores": cores, "variant": variant, "calls": calls})
                    run["solver"] = call(command(args, variant, case, cores, folder), folder, "solver", 30)
                    event({"event": "finished", "stage": "solver", "case": case, "cores": cores, "variant": variant, "process": run["solver"]})
                    if run["solver"]["status"] == "ok":
                        plan = folder / f"case_{case}_multicore_res.json"
                        obj = json.loads(plan.read_bytes())
                        if set(obj) != {"node_to_subgraph", "core_schedules"} or len(obj["core_schedules"]) != cores:
                            raise ValueError("Unexpected solver output contract")
                        run["plan_sha256"] = sha(plan.read_bytes())
                        run["diagnostics"] = json.loads((folder / "diagnostics.json").read_bytes())
                        if (run["diagnostics"].get("selected"), run["diagnostics"].get("model_r_cycles"),
                            run["diagnostics"].get("task_count")) != ("intact-prefetch-frontier", 208152, 144):
                            raise ValueError("Frozen 051 intact-prefetch identity/model differs; no E0 launch")
                        stage_name = "evaluation"
                        argv = [sys.executable, "-X", "utf8", "-B", "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py",
                                relative(args.graphs / f"case_{case}.json"), relative(plan), "--config", relative(args.graphs / "config.txt"),
                                "--output", relative(folder / "result.json"), "--trace-output", relative(folder / "trace.json"), "--log-output", relative(folder / "result.txt")]
                        calls["E0"] += 1; run["calls"]["E0"] += 1
                        event({"event": "launch", "stage": "E0", "case": case, "cores": cores, "variant": variant, "calls": calls})
                        run["evaluation"] = call(argv, folder, "evaluation", 90)
                        event({"event": "finished", "stage": "E0", "case": case, "cores": cores, "variant": variant, "process": run["evaluation"]})
                    stage = run[stage_name]
                    run["status"] = "failed" if stage["status"] == "infrastructure_failure" else stage["status"]
                    if stage["status"] != "ok":
                        errors = (folder / f"{stage_name}.stderr.txt").read_text(encoding="utf-8")
                        run["failure"] = {"stage": stage_name, "reason": errors or stage.get("error") or stage["status"],
                                          "exit_code": stage["returncode"], "elapsed_seconds": stage["wall_seconds"]}
                        if stage["status"] == "infrastructure_failure" or (stage["status"] == "failed" and not is_domain_failure(errors)):
                            stop = "unexpected_supervision_or_process_failure"
                    else:
                        result = json.loads((folder / "result.json").read_bytes())
                        assert result["scene"] == "A" and result["num_cores"] == cores
                        run.update(makespan_cycles=result["makespan"], data_movement_bytes=result["data_movement_bytes"], task_count=len(result["step3_by_task"]))
                    for name in ("result.json", "trace.json"):
                        if (folder / name).exists():
                            run["artifacts"][name] = compress(folder / name)
                except Exception as error:
                    stop = "supervision_exception"
                    run["status"] = "failed"
                    run["failure"] = {"stage": "supervision-after-" + stage_name, "reason": f"{type(error).__name__}: {error}", "exit_code": None, "elapsed_seconds": None}
                    run.pop("makespan_cycles", None)
                finally:
                    run["finished_at"] = utc()
                    dump(folder / "run.json", run)
                    rows.append(run)
                    event({"event": "attempt_saved", "case": case, "cores": cores, "variant": variant, "status": run["status"]})
                print(json.dumps({"case": case, "cores": cores, "variant": variant, "status": run["status"], "cycles": run.get("makespan_cycles"),
                                  "solver_s": run.get("solver", {}).get("wall_seconds"), "e0_s": run.get("evaluation", {}).get("wall_seconds")}), flush=True)
                if stop != "complete":
                    break
            if stop != "complete":
                break
    finally:
        events.close()
        dump(out / "rows.json", rows)
        metadata = [relative(f) for f in out.rglob("*") if f.name.startswith("._") or f.name in (".DS_Store", "__MACOSX")]
        dump(out / "completion.json", {"status": stop, "started_at": started, "finished_at": utc(), "wall_seconds": time.perf_counter() - t0,
                                      "calls": calls, "records": len(rows), "unrun": unrun, "metadata_scan": metadata, "dot_clean": "unavailable on Windows"})
    if stop != "complete":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
