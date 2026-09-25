"""Prepare or explicitly execute one frozen official E0 for 044/K5."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
import zipfile

from src.q1_benchmarks import bounded_probe_e0

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/a/p1-r7-construction-probe-20260926"
PLAN = OUT / "plan.json"
MANIFEST = ROOT / "docs/a/source-manifest.json"
ARCHIVE_REL = "data/raw/a/official-cases.zip"
CONFIG_REL = "data/raw/a/official/data/config.txt"
EVALUATOR_REL = "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"
GRAPH_SHA = "9abd4468a4be365e384de47431ac914ee44fd6e7b6221dffc584561f388cd57e"
PLAN_SHA = "8eecfa3411b660b7cbffc8951ee7129df2ebb49745128243bbd6e1a3f9b90716"
CONFIG_SHA = "dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9"
EVALUATOR_SHA = "2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f"
ARCHIVE_SHA = "e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528"
HELPER = ROOT / "src/q1_benchmarks/bounded_probe_e0.py"
HELPER_SHA = "08f86b1e95dbed9f0c3d82c4005cbf85d81e0164493fc4fc51542ced9035011c"
CASE, CORES, E0_TIMEOUT, BATCH_WALL = "044", 5, 120, 300


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha(path: Path) -> str:
    return digest(path.read_bytes())


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    tmp.replace(path)


def verify() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    files = {row["path"]: row for row in manifest["files"]}
    archive_path = ROOT / ARCHIVE_REL
    config = ROOT / CONFIG_REL
    evaluator = ROOT / EVALUATOR_REL
    if sha(PLAN) != PLAN_SHA or sha(config) != CONFIG_SHA or sha(evaluator) != EVALUATOR_SHA:
        raise RuntimeError("frozen plan/config/evaluator SHA mismatch")
    if sha(HELPER) != HELPER_SHA:
        raise RuntimeError("bounded E0 supervisor helper SHA mismatch")
    if sha(archive_path) != ARCHIVE_SHA or manifest["case_archive"]["sha256"] != ARCHIVE_SHA:
        raise RuntimeError("frozen official archive SHA mismatch")
    if manifest["official_code_hash"] != "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0":
        raise RuntimeError("official source aggregate differs from frozen manifest")
    official = ROOT / "data/raw/a/official"
    aggregate = hashlib.sha256()
    for path in sorted(p for p in files if p.startswith("code/")):
        row = files[path]
        raw = (official / path).read_bytes()
        if len(raw) != row["bytes"] or digest(raw) != row["sha256"]:
            raise RuntimeError(f"official source drift: {path}")
        aggregate.update(f"{path}\t{row['sha256']}\n".encode())
    if aggregate.hexdigest() != manifest["official_code_hash"]:
        raise RuntimeError("official source aggregate mismatch")
    with zipfile.ZipFile(archive_path) as zf:
        graph_raw = zf.read(f"data/case_{CASE}.json")
    if digest(graph_raw) != GRAPH_SHA or files[f"data/case_{CASE}.json"]["sha256"] != GRAPH_SHA:
        raise RuntimeError("frozen official graph SHA mismatch")
    if set(json.loads(PLAN.read_text())) != {"node_to_subgraph", "core_schedules"}:
        raise RuntimeError("candidate plan keys mismatch")
    return {"archive_sha256": ARCHIVE_SHA, "manifest_sha256": sha(MANIFEST),
            "config_sha256": CONFIG_SHA, "evaluator_sha256": EVALUATOR_SHA,
            "official_code_sha256": aggregate.hexdigest(), "graph_sha256": GRAPH_SHA,
            "plan_sha256": PLAN_SHA, "supervisor_helper_sha256": HELPER_SHA,
            "case": CASE, "cores": CORES}


def preflight() -> dict:
    ident = verify()
    return {"status": "preflight_ok", "scoring": False, "identity": ident,
            "workers": 1, "maximum_E0": 1, "solver_calls": 0,
            "standalone_Task_compile_calls": 0,
            "note": "E0 itself internally compiles Task; that is counted as part of E0",
            "E1_calls": 0, "E2_calls": 0, "E0_timeout_seconds": E0_TIMEOUT,
            "batch_wall_seconds": BATCH_WALL, "retries": 0,
            "stop_policy": "first failure, timeout, or source drift; no retry"}


def run(run_id: str) -> int:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", run_id):
        raise ValueError("run-id must be 1-64 safe ASCII characters")
    identity = verify()
    run_dir = OUT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    batch = {"run_id": run_id, "state": "running", "started_at": utc(),
             "case": CASE, "cores": CORES, "identity": identity,
             "budget": {"workers": 1, "E0_max": 1, "solver": 0,
                        "standalone_Task_compile": 0, "E1": 0, "E2": 0,
                        "retries": 0, "E0_timeout_seconds": E0_TIMEOUT,
                        "batch_wall_seconds": BATCH_WALL}, "result": None}
    write(run_dir / "batch.json", batch)
    folder = run_dir / "044-k5"
    folder.mkdir()
    graph = folder / "case_044.json"
    with zipfile.ZipFile(ROOT / ARCHIVE_REL) as zf:
        graph.write_bytes(zf.read(f"data/case_{CASE}.json"))
    plan = folder / "candidate-plan.json"
    plan.write_bytes(PLAN.read_bytes())
    result, trace, log = folder / "case_044_multicore_res.json", folder / "trace.json", folder / "official.log"
    row = {"case": CASE, "cores": CORES, "state": "failed",
           "calls": {"solver": 0, "standalone_Task_compile": 0, "E0": 0, "E1": 0, "E2": 0},
           "graph_sha256": sha(graph), "plan_sha256": sha(plan), "failure": None}
    try:
        if row["graph_sha256"] != GRAPH_SHA or row["plan_sha256"] != PLAN_SHA:
            raise RuntimeError("staged frozen input changed")
        if sha(ROOT / CONFIG_REL) != CONFIG_SHA or sha(ROOT / EVALUATOR_REL) != EVALUATOR_SHA or sha(HELPER) != HELPER_SHA:
            raise RuntimeError("frozen scorer or supervisor changed before dispatch")
        if time.monotonic() - started >= BATCH_WALL:
            raise TimeoutError("batch wall cap reached before E0 dispatch")
        argv = [sys.executable, "-B", str(ROOT / EVALUATOR_REL), str(graph), str(plan),
                "--config", str(ROOT / CONFIG_REL), "--output", str(result),
                "--trace-output", str(trace), "--log-output", str(log)]
        row["calls"]["E0"] = 1  # Conservative once dispatch is entered.
        row["process"] = bounded_probe_e0.process(
            argv, folder, "E0", min(E0_TIMEOUT, max(0.1, BATCH_WALL - (time.monotonic() - started))), folder)
        if row["process"]["status"] != "ok":
            raise RuntimeError(f"official E0 {row['process']['status']}")
        if not all(path.is_file() for path in (result, trace, log)):
            raise RuntimeError("official E0 omitted result, trace, or log")
        obj = json.loads(result.read_text())
        val = obj.get("makespan")
        if obj.get("scene") != "A" or obj.get("num_cores") != CORES or isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val <= 0:
            raise RuntimeError("official result identity/Makespan invalid")
        row.update(state="ok", makespan_cycles=val, data_movement_bytes=obj.get("data_movement_bytes"))
    except Exception as exc:
        row["failure"] = f"{type(exc).__name__}: {exc}"
    row["artifacts"] = {p.name: sha(p) for p in folder.iterdir() if p.is_file()}
    write(folder / "attempt.json", row)
    batch.update(state="complete" if row["state"] == "ok" else "stopped",
                 finished_at=utc(), elapsed_seconds=time.monotonic() - started,
                 actual_calls=row["calls"], result={k: row.get(k) for k in ("state", "makespan_cycles", "failure")})
    write(run_dir / "batch.json", batch)
    return 0 if row["state"] == "ok" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true", help="verify frozen bytes; performs zero scoring")
    modes.add_argument("--execute", action="store_true", help="explicitly invoke one official E0")
    parser.add_argument("--run-id", help="required for --execute; destination must not exist")
    args = parser.parse_args()
    if args.preflight:
        if args.run_id:
            parser.error("--run-id is only valid with --execute")
        print(json.dumps(preflight(), indent=2, ensure_ascii=False))
        return 0
    if not args.run_id:
        parser.error("--run-id is required with --execute")
    return run(args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
