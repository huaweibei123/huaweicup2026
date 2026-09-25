"""Stage J three-cell causal probe; explicit parent START required to execute."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os
import platform
import shutil
import subprocess
import sys
import time

from src.q1_yuanzhifang.job_j import managed_process

ROOT = Path(__file__).resolve().parents[2]
SOLVER_SHA = "aa3f18a71b117ebd0476c8d714c97d8d366d74d7"
SOLVER = ROOT / "src/q1_yuanzhifang/intact_pacing.py"
E0 = ROOT / "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"
CONFIG = ROOT / "data/raw/a/official/data/config.txt"
CELLS = (("control", 3), ("paced", 3), ("paced", 4))
OUTPUT = ROOT / "results/a/q1-yuanzhifang-stage-j/stage-j-20260925/run"
START_TOKEN = "STAGE-J-20260925-START"
DEPENDENCIES = ["src/q1_yuanzhifang/intact_pacing.py", "src/q1_yuanzhifang/star_frontier.py",
                "src/q1_yuanzhifang/fork_frontier.py", "src/q1_yuanzhifang/construct.py",
                "src/q1_yuanzhifang/diagnose.py", "data/raw/a/official/data/config.txt"]


def utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).strip()


def preflight(graphs, output):
    if os.name != "nt":
        raise RuntimeError("this runner requires Windows Job Objects")
    if output.exists():
        raise FileExistsError(output)
    source = json.loads(git("show", f"{SOLVER_SHA}:docs/a/source-manifest.json"))
    expected = {item["path"]: item["sha256"] for item in source["files"]}
    for relative in DEPENDENCIES:
        if git("hash-object", relative) != git("rev-parse", f"{SOLVER_SHA}:{relative}"):
            raise RuntimeError(f"frozen dependency differs: {relative}")
    for relative in ("src/q1_yuanzhifang/benchmark_j.py", "src/q1_yuanzhifang/job_j.py"):
        if git("hash-object", relative) != git("rev-parse", f"HEAD:{relative}"):
            raise RuntimeError(f"runner differs from committed HEAD: {relative}")
    for relative in ("src/q1_yuanzhifang/intact_pacing.py", "src/q1_yuanzhifang/star_frontier.py",
                     "src/q1_yuanzhifang/fork_frontier.py", "src/q1_yuanzhifang/construct.py",
                     "src/q1_yuanzhifang/diagnose.py"):
        if subprocess.run(["git", "diff", "--quiet", "--", relative], cwd=ROOT).returncode or \
           subprocess.run(["git", "diff", "--cached", "--quiet", "--", relative], cwd=ROOT).returncode:
            raise RuntimeError(f"uncommitted solver/dependency change: {relative}")
    code = ROOT / "data/raw/a/official/code"
    signature = "".join(f"code/{path.name}\t{sha(path)}\n" for path in sorted(code.iterdir()) if path.is_file())
    if hashlib.sha256(signature.encode()).hexdigest() != source["official_code_hash"]:
        raise RuntimeError("official source hash mismatch")
    graph = graphs / "case_051.json"
    if not graph.is_file() or sha(graph) != expected["data/case_051.json"]:
        raise RuntimeError("case_051 source identity mismatch")
    if sha(CONFIG) != expected["data/config.txt"]:
        raise RuntimeError("config source identity mismatch")
    if shutil.disk_usage(output.parent if output.parent.exists() else ROOT).free < 1_000_000_000:
        raise RuntimeError("less than 1 GB free near output")
    return dict(solver_commit=SOLVER_SHA, runner_head=git("rev-parse", "HEAD").decode(),
                graph_sha256=sha(graph), config_sha256=sha(CONFIG),
                official_code_hash=source["official_code_hash"],
                python=sys.version, platform=platform.platform(), cpu=platform.processor(),
                graph_dir=str(graphs), scenarios=[f"051/k{k}/{v}" for v, k in CELLS],
                budget=dict(solver=3, E0=3, E1=0, E2=0, retries=0,
                            workers=2, solver_timeout_seconds=30,
                            e0_timeout_seconds=60, batch_wall_seconds=180))


def run_cell(variant, cores, graph, output, deadline, expected_sha):
    cell = output / f"051-k{cores}-{variant}"
    cell.mkdir(exist_ok=False)
    plan = cell / "case_051_multicore_res.json"
    diagnostics = cell / "diagnostics.json"
    row = dict(case="051", cores=cores, variant=variant, graph_sha256=expected_sha,
               started_at=utc(), status="started", calls=dict(solver=0, E0=0, E1=0, E2=0))
    try:
        if time.monotonic() >= deadline:
            row["status"] = "deadline-before-solver"
            return row
        row["calls"]["solver"] = 1
        row["solver"] = managed_process(SOLVER,
            [graph, "--cores", cores, "--variant", variant, "--output", plan,
             "--diagnostics", diagnostics], cell, "solver", min(30, deadline-time.monotonic()))
        if row["solver"]["timeout"] or row["solver"]["returncode"] != 0 or not plan.is_file() or not diagnostics.is_file():
            row["status"] = "solver-failed"
            return row
        candidate = json.loads(plan.read_text(encoding="utf-8"))
        detail = json.loads(diagnostics.read_text(encoding="utf-8"))
        if set(candidate) != {"node_to_subgraph", "core_schedules"} or detail["variant"] != variant or detail["cores"] != cores:
            row["status"] = "identity-failed"
            return row
        row["plan_sha256"] = sha(plan)
        if time.monotonic() >= deadline:
            row["status"] = "deadline-before-e0"
            return row
        row["calls"]["E0"] = 1
        row["e0"] = managed_process(E0,
            [graph, plan, "--config", CONFIG, "--output", cell / "e0_result.json",
             "--trace-output", cell / "e0_trace.json", "--log-output", cell / "e0_log.txt"],
            cell, "e0", min(60, deadline-time.monotonic()))
        if row["e0"]["timeout"] or row["e0"]["returncode"] != 0:
            row["status"] = "e0-failed"
            return row
        result = json.loads((cell / "e0_result.json").read_text(encoding="utf-8"))
        if result["scene"] != "A" or result["num_cores"] != cores or type(result["makespan"]) is not int:
            row["status"] = "identity-failed"
            return row
        row.update(status="success", makespan_cycles=result["makespan"],
                   e0_result_sha256=sha(cell / "e0_result.json"),
                   e0_trace_sha256=sha(cell / "e0_trace.json"),
                   e0_log_sha256=sha(cell / "e0_log.txt"))
        return row
    except Exception as error:
        row.update(status="supervision-error", error_type=type(error).__name__, message=str(error))
        return row
    finally:
        row["finished_at"] = utc()
        (cell / "run.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")


def allocation(plan):
    task_core = {task: core for core, order in enumerate(plan["core_schedules"]) for task in order}
    return {node: task_core[task] for node, task in plan["node_to_subgraph"].items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphs", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--start-token")
    parser.add_argument("--producer-session")
    args = parser.parse_args()
    graphs, output = args.graphs.resolve(), args.output.resolve()
    facts = preflight(graphs, output)
    if args.preflight:
        print(json.dumps(facts, indent=2))
        return
    if args.start_token != START_TOKEN or not args.producer_session or "/s-" not in args.producer_session:
        raise ValueError("fixed parent START and actual producer session required")
    facts.update(started_at=utc(), producer_session=args.producer_session)
    output.mkdir(parents=True, exist_ok=False)
    (output / "batch_manifest.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    deadline, began = time.monotonic()+180, time.perf_counter()
    graph = graphs / "case_051.json"
    rows, pending, stop = [], iter(CELLS), False
    with ThreadPoolExecutor(max_workers=2) as pool:
        active = {}
        def submit():
            variant, cores = next(pending)
            active[pool.submit(run_cell, variant, cores, graph, output, deadline,
                               facts["graph_sha256"])] = (variant, cores)
        submit(); submit()
        while active:
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                variant, cores = active.pop(future)
                row = future.result()
                rows.append(row)
                print(json.dumps({"cell": f"051/k{cores}/{variant}", "status": row["status"]}), flush=True)
                if row["status"] in {"supervision-error", "identity-failed"}:
                    stop = True
            if not stop:
                for _ in range(2-len(active)):
                    try:
                        submit()
                    except StopIteration:
                        break
    for variant, cores in pending:
        cell = output / f"051-k{cores}-{variant}"
        cell.mkdir(exist_ok=False)
        row = dict(case="051", cores=cores, variant=variant, status="not-started-after-supervision-failure",
                   graph_sha256=facts["graph_sha256"], started_at=utc(), finished_at=utc(),
                   calls=dict(solver=0, E0=0, E1=0, E2=0))
        (cell / "run.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        rows.append(row)
    totals = {name: sum(row["calls"][name] for row in rows) for name in ("solver", "E0", "E1", "E2")}
    if totals["solver"] > 3 or totals["E0"] > 3 or totals["E1"] or totals["E2"]:
        raise AssertionError("Stage J call budget exceeded")
    pair = [row for row in rows if row["cores"] == 3 and row["status"] == "success"]
    pair_verified = None
    if len(pair) == 2:
        plans = [json.loads((output / f"051-k3-{row['variant']}" / "case_051_multicore_res.json").read_text()) for row in pair]
        pair_verified = (allocation(plans[0]) == allocation(plans[1]) and
                         pair[0]["graph_sha256"] == pair[1]["graph_sha256"])
    receipt = dict(finished_at=utc(), wall_seconds=time.perf_counter()-began,
                   calls=totals, stopped_after_supervision_failure=stop,
                   k3_control_paced_same_chain_to_core_allocation=pair_verified,
                   statuses={f"051/k{row['cores']}/{row['variant']}": row["status"] for row in rows})
    (output / "batch_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
