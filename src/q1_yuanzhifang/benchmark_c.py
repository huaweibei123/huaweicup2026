"""Stage C: frozen fork-stage-frontier versus bounded component Tasks.

Default mode only checks inputs/source. --execute is required to consume the
separate Stage C budget, after a fixed solver SHA and scheduling window exist.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import time

from benchmark import (ROOT, SESSION, utc, sha, dump, git, relative, verify_source,
                       official_check, environment, call, compress)

BASELINE = "05f8fa0f7e52f5914f14815f6bdbcb851b631556"
NEW_SCRIPT = "src/q1_yuanzhifang/fork_frontier.py"
BASELINE_SCRIPT = "src/q1/bounded_tasks.py"
OUTPUT = "results/a/q1-yuanzhifang/stage-c-20260924"
SCENARIOS = tuple(("051", k) for k in (2, 3, 4, 5)) + tuple(
    (case, 4) for case in ("002", "008", "016", "024", "044", "048", "071", "080"))
VARIANTS = ("frontier-then-independent-chunks", "chain-atomic-grain4")
BUDGET = {"solver": 24, "E0": 24, "E1": 0, "E2": 0, "workers": 1,
          "wall_seconds": 1200, "solver_timeout_seconds": 30,
          "evaluation_timeout_seconds": 90, "retries": 0}
BASELINE_FILES = [BASELINE_SCRIPT, "src/q1/tree_frontier.py", "src/q1/component_pack.py"]
NEW_FILES = [NEW_SCRIPT, "src/q1_yuanzhifang/construct.py"]


def preflight(args):
    manifest = json.loads((ROOT / "docs/a/source-manifest.json").read_bytes())
    runner = git("rev-parse", "HEAD").decode().strip()
    if git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Tracked runner worktree must be clean")
    if git("rev-parse", "HEAD", root=args.baseline_root).decode().strip() != BASELINE:
        raise ValueError("Baseline checkout changed HEAD")
    baseline_sources = verify_source(args.baseline_root, BASELINE, BASELINE_FILES)
    frozen = official_check(ROOT, manifest)
    assert official_check(args.baseline_root, manifest) == frozen
    expected = {i["path"]: i["sha256"] for i in manifest["files"]}
    inputs = {}
    for name in ["config.txt", *(f"case_{c}.json" for c in sorted({c for c, _ in SCENARIOS}))]:
        inputs[name] = sha((args.graphs / name).read_bytes())
        if inputs[name] != expected["data/" + name]:
            raise ValueError("Frozen input mismatch: " + name)
    code = verify_source(ROOT, runner, ["src/q1_yuanzhifang/benchmark_c.py", "src/q1_yuanzhifang/benchmark.py"])
    new_sources = None
    if args.solver_commit:
        if not re.fullmatch("[0-9a-f]{40}", args.solver_commit):
            raise ValueError("New solver commit must be a full lowercase SHA")
        new_sources = verify_source(ROOT, args.solver_commit, NEW_FILES)
    if args.execute and new_sources is None:
        raise ValueError("Execution requires a frozen new solver commit")
    return {"runner_commit": runner, "solver_commit": args.solver_commit,
            "baseline_commit": BASELINE, "source_sha256": code,
            "new_solver_source_sha256": new_sources, "baseline_source_sha256": baseline_sources,
            "official_source_sha256": frozen, "official_code_hash": manifest["official_code_hash"],
            "input_sha256": inputs}


def command(args, variant, case, cores, folder):
    graph = relative(args.graphs / f"case_{case}.json")
    plan = relative(folder / f"case_{case}_multicore_res.json")
    diagnostics = relative(folder / "diagnostics.json")
    python = [sys.executable, "-X", "utf8", "-B"]
    if variant == VARIANTS[0]:
        return [*python, relative(args.baseline_root / BASELINE_SCRIPT), graph,
                "--output", plan, "--cores", str(cores), "--packet-factor", "4",
                "--trigger-ops", "4096", "--chunk-ops", "1024", "--diagnostics", diagnostics]
    return [*python, NEW_SCRIPT, graph, plan, "--cores", str(cores), "--grain", "4",
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
    p.add_argument("--baseline-root", type=Path, required=True)
    p.add_argument("--graphs", type=Path, required=True)
    p.add_argument("--solver-commit")
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    args.baseline_root, args.graphs = args.baseline_root.resolve(), args.graphs.resolve()
    protocol = preflight(args)
    if not args.execute:
        print(json.dumps({"preflight": "ok", "new_solver_frozen": protocol["new_solver_source_sha256"] is not None,
                          "scenarios": SCENARIOS, "budget": BUDGET, "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
                          **protocol}, ensure_ascii=False))
        return
    protocol.update(producer_session=SESSION, task_url="https://github.com/huaweibei123/huaweicup2026/issues/98",
                    scenarios=SCENARIOS, variants=VARIANTS, budget=BUDGET, environment=environment(),
                    parameters={VARIANTS[0]: {"packet_factor": 4, "trigger_ops": 4096, "chunk_ops": 1024},
                                VARIANTS[1]: {"grain": 4}},
                    preparation="Reuse Stage A/B uv sync --locked environment. Initial 14-package install reported 43.79s before A. Author reports 14 tests and seven graph-specific in-memory construction checks on 002/008/016/024/048/051/071 before freeze (0 E0/E1/E2; their complete wall cost not recorded here), disclosed in docs/a/q1-yuanzhifang/FORK_FRONTIER.md at solver_commit. Public development panel. No training, compilation or precomputed graph products reused by these cold processes.",
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
                if time.perf_counter() - t0 > 1075:
                    stop = "batch_budget_reserve"; break
                if shutil.disk_usage(out).free < 200 * 1024 * 1024:
                    stop = "insufficient_disk_headroom"; break
                folder = out / f"{case}-k{cores}-{variant}"
                folder.mkdir()
                run = {"case_id": case, "cores": cores, "variant": variant,
                       "solver_commit": BASELINE if variant == VARIANTS[0] else args.solver_commit,
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
