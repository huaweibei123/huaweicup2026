"""Two-cell guarded Stage L probe; a parent START token is required."""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

from src.q1_yuanzhifang.job_l import managed_process, JOB_MEMORY_BYTES

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "5c64b4057cb9b2f2af5426bd1efdd579b9df5559"
SOLVER = ROOT / "src/q1_yuanzhifang/shared_packet_model.py"
E0 = ROOT / "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"
CONFIG = ROOT / "data/raw/a/official/data/config.txt"
OUT = ROOT / "results/a/q1-yuanzhifang-stage-l/stage-l-mem512-20260925/run"
TOKEN = "STAGE-L-MEM512-20260925-START"
CELLS = (3, 4)
MIN_AVAILABLE_RAM_BYTES = 1 << 30


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).strip()


def utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def available_ram():
    class Memory(ctypes.Structure):
        _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD)] + [
            (n, ctypes.c_ulonglong) for n in ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile",
                                           "ullAvailPageFile", "ullTotalVirtual", "ullAvailVirtual",
                                           "ullAvailExtendedVirtual")]
    state = Memory()
    state.dwLength = ctypes.sizeof(state)
    if not ctypes.WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx(ctypes.byref(state)):
        raise ctypes.WinError(ctypes.get_last_error())
    return state.ullAvailPhys


def preflight(graph_dir, output):
    if os.name != "nt":
        raise RuntimeError("Stage L requires Windows Job Objects")
    if output.exists():
        raise FileExistsError(output)
    manifest = json.loads(git("show", f"{SOURCE}:docs/a/source-manifest.json"))
    expected = {item["path"]: item["sha256"] for item in manifest["files"]}
    source_files = ["src/q1_yuanzhifang/shared_packet_model.py",
                    "data/raw/a/official/data/config.txt"]
    for relative in source_files:
        if git("hash-object", relative) != git("rev-parse", f"{SOURCE}:{relative}"):
            raise RuntimeError(f"frozen source differs: {relative}")
        if subprocess.run(["git", "diff", "--quiet", "--", relative], cwd=ROOT).returncode or \
           subprocess.run(["git", "diff", "--cached", "--quiet", "--", relative], cwd=ROOT).returncode:
            raise RuntimeError(f"uncommitted frozen source: {relative}")
    for relative in ("src/q1_yuanzhifang/benchmark_l.py", "src/q1_yuanzhifang/job_l.py"):
        if git("hash-object", relative) != git("rev-parse", f"HEAD:{relative}"):
            raise RuntimeError(f"runner differs from HEAD: {relative}")
    code = ROOT / "data/raw/a/official/code"
    signature = "".join(f"code/{p.name}\t{sha(p)}\n" for p in sorted(code.iterdir()) if p.is_file())
    official_hash = hashlib.sha256(signature.encode()).hexdigest()
    if official_hash != manifest["official_code_hash"]:
        raise RuntimeError("full official source differs")
    graph = graph_dir / "case_044.json"
    if not graph.is_file() or sha(graph) != expected["data/case_044.json"]:
        raise RuntimeError("case_044 graph identity differs")
    if sha(CONFIG) != expected["data/config.txt"]:
        raise RuntimeError("official config identity differs")
    ram = available_ram()
    if ram < MIN_AVAILABLE_RAM_BYTES:
        raise RuntimeError("less than 1 GiB available RAM")
    if shutil.disk_usage(output.parent if output.parent.exists() else ROOT).free < 1_000_000_000:
        raise RuntimeError("less than 1 GB output space")
    return dict(solver_commit=SOURCE, runner_head=git("rev-parse", "HEAD").decode(),
                job_supervisor_upstream="f3e548f1915ce895e1f785219420fc747777ceb0:src/q1_yuanzhifang/job_j.py",
                graph_sha256=sha(graph), config_sha256=sha(CONFIG), official_code_hash=official_hash,
                official_e0_sha256=sha(E0), graph_dir=str(graph_dir),
                python=sys.version, platform=platform.platform(), cpu=platform.processor(),
                available_ram_bytes_at_preflight=ram,
                available_ram_min_bytes=MIN_AVAILABLE_RAM_BYTES,
                owned_job_memory_limit_bytes=JOB_MEMORY_BYTES,
                budget=dict(solver=2, E0=2, E1=0, E2=0, retries=0, workers=1,
                            available_ram_min_bytes=MIN_AVAILABLE_RAM_BYTES,
                            owned_job_memory_limit_bytes=JOB_MEMORY_BYTES,
                            solver_timeout_seconds=120, e0_timeout_seconds=90, batch_wall_seconds=300))


def run_cell(cores, graph, output, deadline, graph_sha):
    cell = output / f"044-k{cores}"
    cell.mkdir(exist_ok=False)
    plan, diagnostics = cell / "case_044_multicore_res.json", cell / "diagnostics.json"
    row = dict(case="044", cores=cores, graph_sha256=graph_sha, status="started",
               started_at=utc(), calls=dict(solver=0, E0=0, E1=0, E2=0))
    try:
        row["available_ram_bytes_before_cell"] = available_ram()
        if row["available_ram_bytes_before_cell"] < MIN_AVAILABLE_RAM_BYTES:
            row["status"] = "ram-insufficient-before-cell"
            return row
        left = deadline-time.monotonic()
        if left <= 0:
            row["status"] = "deadline-before-solver"
            return row
        row["calls"]["solver"] = 1  # Conservative attempt charge on launch failure.
        row["solver"] = managed_process(SOLVER,
            [graph, "--cores", cores, "--output", diagnostics, "--plan", plan],
            cell, "solver", min(120, left), module="src.q1_yuanzhifang.shared_packet_model")
        if row["solver"]["timeout"] or row["solver"]["returncode"] or not plan.is_file() or not diagnostics.is_file():
            row["status"] = "solver-failed"
            return row
        candidate = json.loads(plan.read_bytes())
        detail = json.loads(diagnostics.read_bytes())
        if (set(candidate) != {"node_to_subgraph", "core_schedules"}
                or detail.get("algorithm_id") != "q1-shared-packet-pipeline"
                or detail.get("graph_sha256") != graph_sha
                or len(candidate["core_schedules"]) != cores):
            row["status"] = "identity-failed"
            return row
        row["plan_sha256"] = sha(plan)
        left = deadline-time.monotonic()
        if left <= 0:
            row["status"] = "deadline-before-e0"
            return row
        row["calls"]["E0"] = 1
        row["e0"] = managed_process(E0,
            [graph, plan, "--config", CONFIG, "--output", cell / "e0_result.json",
             "--trace-output", cell / "e0_trace.json", "--log-output", cell / "e0_log.txt"],
            cell, "e0", min(90, left))
        if row["e0"]["timeout"] or row["e0"]["returncode"]:
            row["status"] = "e0-failed"
            return row
        result = json.loads((cell / "e0_result.json").read_bytes())
        if (result.get("scene") != "A" or result.get("num_cores") != cores
                or type(result.get("makespan")) is not int
                or not (cell / "e0_trace.json").is_file() or not (cell / "e0_log.txt").is_file()):
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graphs", type=Path, required=True)
    p.add_argument("--output", type=Path, default=OUT)
    p.add_argument("--preflight", action="store_true")
    p.add_argument("--start-token")
    p.add_argument("--producer-session")
    a = p.parse_args()
    graphs, output = a.graphs.resolve(), a.output.resolve()
    facts = preflight(graphs, output)
    if a.preflight:
        print(json.dumps(facts, indent=2))
        return
    if a.start_token != TOKEN or not a.producer_session or "/s-" not in a.producer_session:
        raise ValueError("parent START token and actual producer session required")
    facts.update(started_at=utc(), producer_session=a.producer_session)
    output.mkdir(parents=True, exist_ok=False)
    (output / "batch_manifest.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    deadline, began = time.monotonic()+300, time.perf_counter()
    rows, hard_failure = [], False
    for cores in CELLS:
        if hard_failure:
            cell = output / f"044-k{cores}"
            cell.mkdir(exist_ok=False)
            row = dict(case="044", cores=cores, graph_sha256=facts["graph_sha256"],
                       status="not-started-after-supervision-failure", started_at=utc(), finished_at=utc(),
                       calls=dict(solver=0, E0=0, E1=0, E2=0))
            (cell / "run.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        else:
            row = run_cell(cores, graphs / "case_044.json", output, deadline, facts["graph_sha256"])
        rows.append(row)
        print(json.dumps({"cell": f"044/k{cores}", "status": row["status"]}), flush=True)
        hard_failure |= row["status"] in {"supervision-error", "identity-failed",
                                          "ram-insufficient-before-cell"}
    totals = {name: sum(r["calls"][name] for r in rows) for name in ("solver", "E0", "E1", "E2")}
    if totals["solver"] > 2 or totals["E0"] > 2 or totals["E1"] or totals["E2"]:
        raise AssertionError("Stage L budget exceeded")
    receipt = dict(finished_at=utc(), wall_seconds=time.perf_counter()-began,
                   calls=totals, stopped_after_supervision_failure=hard_failure,
                   statuses={f"044/k{r['cores']}": r["status"] for r in rows}, retries=0)
    (output / "batch_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
