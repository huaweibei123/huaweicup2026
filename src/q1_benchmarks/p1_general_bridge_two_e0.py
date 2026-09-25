"""Prepared two-cell, saved-plan P1 E0 pilot. No constructor or E1/E2 path."""
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
RESULTS = ROOT / "results/a/p1-general-bridge-probe-20260926"
ARCHIVE = ROOT / "data/raw/a/official-cases.zip"
OFFICIAL = ROOT / "data/raw/a/official"
CONFIG = OFFICIAL / "data/config.txt"
EVALUATOR = OFFICIAL / "code/multicore_cut_evaluate_problem_1.py"
MANIFEST = ROOT / "docs/a/source-manifest.json"
HELPER = ROOT / "src/q1_benchmarks/bounded_probe_e0.py"
CELLS = (
    ("068", 5, RESULTS / "068-k5/candidate-plan.json",
     "0b4b64cba1e0000220337bcee60cd94e206526f949ec3ba04cad02fb4d8b2720",
     "dfd9a58ef9d26a8a4567026b50af8b4499d87eebb3d98f8208b909b11e963c6d"),
    ("085", 5, RESULTS / "085-k5/candidate-plan.json",
     "ba9be0e9bea3ea3f23c0eda28c7fa6ce1d5787fa52624da8e54a9c61120cc054",
     "b63169e9cd0f21dc2da6617e7138472e95937465c703b7e4bf4dbc80125ed4f6"),
)
EXPECTED_ARCHIVE = "e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528"
EXPECTED_CONFIG = "dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9"
EXPECTED_EVALUATOR = "2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f"
EXPECTED_HELPER = "08f86b1e95dbed9f0c3d82c4005cbf85d81e0164493fc4fc51542ced9035011c"
E0_TIMEOUT = 120
MAX_WALL = 300


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write(path: Path, obj: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    temp.replace(path)


def verify_inputs() -> dict:
    if sha(ARCHIVE) != EXPECTED_ARCHIVE:
        raise RuntimeError("frozen official case archive SHA mismatch")
    if sha(CONFIG) != EXPECTED_CONFIG or sha(EVALUATOR) != EXPECTED_EVALUATOR:
        raise RuntimeError("frozen official config/evaluator SHA mismatch")
    if sha(HELPER) != EXPECTED_HELPER:
        raise RuntimeError("bounded E0 process helper SHA mismatch")
    manifest = json.loads(MANIFEST.read_text())
    rows = {row["path"]: row for row in manifest["files"]}
    code_rows = sorted((row for row in rows.values() if row["path"].startswith("code/")),
                       key=lambda row: row["path"])
    aggregate = hashlib.sha256()
    for row in code_rows:
        source = OFFICIAL / row["path"]
        if sha(source) != row["sha256"] or source.stat().st_size != row["bytes"]:
            raise RuntimeError(f"official source SHA mismatch: {row['path']}")
        aggregate.update(f"{row['path']}\t{row['sha256']}\n".encode())
    if aggregate.hexdigest() != manifest["official_code_hash"]:
        raise RuntimeError("official source aggregate mismatch")
    if sha(ARCHIVE) != manifest["case_archive"]["sha256"]:
        raise RuntimeError("manifest archive SHA mismatch")
    identities = {}
    with zipfile.ZipFile(ARCHIVE) as archive:
        for case, cores, plan_path, plan_sha, graph_sha in CELLS:
            plan_raw = plan_path.read_bytes()
            graph_raw = archive.read(f"data/case_{case}.json")
            if sha_bytes(plan_raw) != plan_sha or sha_bytes(graph_raw) != graph_sha:
                raise RuntimeError(f"frozen candidate or graph SHA mismatch: {case}/k{cores}")
            if set(json.loads(plan_raw)) != {"node_to_subgraph", "core_schedules"}:
                raise RuntimeError(f"candidate plan keys mismatch: {case}/k{cores}")
            if rows[f"data/case_{case}.json"]["sha256"] != graph_sha:
                raise RuntimeError(f"manifest graph SHA mismatch: {case}/k{cores}")
            identities[case] = {"cores": cores, "plan_sha256": plan_sha,
                                "graph_sha256": graph_sha, "plan_bytes": len(plan_raw),
                                "graph_bytes": len(graph_raw)}
    return {"archive_sha256": sha(ARCHIVE), "config_sha256": sha(CONFIG),
            "evaluator_sha256": sha(EVALUATOR), "official_code_sha256": aggregate.hexdigest(),
            "source_manifest_sha256": sha(MANIFEST), "supervisor_helper_sha256": sha(HELPER),
            "cells": identities}


def preflight(selected_case: str) -> dict:
    identity = verify_inputs()
    return {"status": "preflight_ok", "selected_case": selected_case, "scoring": False,
            "calls": {"solver": 0, "standalone_Task_compile": 0, "E0": 0, "E1": 0, "E2": 0},
            "workers": 1, "maximum_E0": 1, "per_cell_timeout_seconds": E0_TIMEOUT,
            "stop_policy": "first failure/timeout/source drift; no retry", "identity": identity}


def run(run_id: str, selected_case: str) -> int:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", run_id):
        raise ValueError("run id must be 1-64 safe ASCII characters")
    identity = verify_inputs()
    selected_cells = tuple(row for row in CELLS if row[0] == selected_case)
    if len(selected_cells) != 1:
        raise ValueError(f"unknown case: {selected_case}")
    run_dir = RESULTS / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    batch = {"run_id": run_id, "state": "running", "started_at": utc(),
             "selected_case": selected_case,
             "cells": [f"{case}/k{cores}" for case, cores, *_ in selected_cells],
             "budgets": {"workers": 1, "E0_max": 1, "solver": 0, "standalone_Task_compile": 0,
                         "E1": 0, "E2": 0, "retries": 0,
                         "E0_timeout_seconds_per_cell": E0_TIMEOUT,
                         "batch_wall_seconds": MAX_WALL},
             "stop_policy": "stop on first failure, timeout, source drift, or batch wall cap; no retry",
             "identity": identity, "results": []}
    write(run_dir / "batch.json", batch)
    stopped = None
    with zipfile.ZipFile(ARCHIVE) as archive:
        for case, cores, plan_path, plan_sha, graph_sha in selected_cells:
            folder = run_dir / f"{case}-k{cores}"
            folder.mkdir()
            graph_raw = archive.read(f"data/case_{case}.json")
            graph = folder / f"case_{case}.json"
            plan_raw = plan_path.read_bytes()
            graph.write_bytes(graph_raw)
            plan = folder / "candidate-plan.json"
            plan.write_bytes(plan_raw)
            result = folder / f"case_{case}_multicore_res.json"
            trace = folder / "trace.json"
            official_log = folder / "official.log"
            row = {"case_id": case, "cores": cores, "state": "not_run",
                   "calls": {"solver": 0, "standalone_Task_compile": 0, "E0": 0, "E1": 0, "E2": 0},
                   "source_plan": plan_path.relative_to(ROOT).as_posix(),
                   "plan_sha256": sha_bytes(plan_raw), "graph_sha256": sha_bytes(graph_raw),
                   "failure": None}
            if stopped is not None:
                row["not_run_reason"] = stopped
            elif time.monotonic() - started >= MAX_WALL:
                stopped = "batch wall cap reached before dispatch"
                row["not_run_reason"] = stopped
            else:
                argv = [sys.executable, "-B", str(EVALUATOR), str(graph), str(plan),
                        "--config", str(CONFIG), "--output", str(result),
                        "--trace-output", str(trace), "--log-output", str(official_log)]
                try:
                    if sha(graph) != graph_sha or sha(plan) != plan_sha:
                        raise RuntimeError(f"frozen bytes changed before dispatch: {case}/k{cores}")
                    row.update(state="dispatching", dispatch_started_at=utc())
                    row["calls"]["E0"] = 1  # Count conservatively once dispatch is entered.
                    write(folder / "attempt.json", {**row, "state": "dispatching",
                          "timeout_seconds": E0_TIMEOUT, "workers": 1})
                    process = bounded_probe_e0.process(argv, folder, "E0", E0_TIMEOUT, folder)
                    row["process"] = process
                    if process["status"] != "ok":
                        raise RuntimeError(f"official E0 status {process['status']}")
                    obj = json.loads(result.read_text())
                    if obj.get("scene") != "A" or obj.get("num_cores") != cores:
                        raise RuntimeError("official result scene/core identity mismatch")
                    makespan = obj.get("makespan")
                    if isinstance(makespan, bool) or not isinstance(makespan, (int, float)) or not math.isfinite(makespan) or makespan <= 0:
                        raise RuntimeError("official result Makespan invalid")
                    row.update(state="ok", finished_at=utc(), makespan_cycles=makespan,
                               data_movement_bytes=obj.get("data_movement_bytes"),
                               artifacts={name: {"path": path.name, "sha256": sha(path)}
                                          for name, path in (("graph", graph), ("plan", plan),
                                                             ("result", result), ("trace", trace),
                                                             ("official_log", official_log),
                                                             ("stdout", folder / "E0.stdout.txt"),
                                                             ("stderr", folder / "E0.stderr.txt"))
                                          if path.is_file()})
                except Exception as exc:
                    row.update(state="failed", finished_at=utc(),
                               failure=f"{type(exc).__name__}: {exc}")
                    row["artifacts"] = {p.name: sha(p) for p in folder.iterdir() if p.is_file()}
                    stopped = f"stopped after {case}/k{cores}: {row['failure']}"
            write(folder / "attempt.json", row)
            batch["results"].append({"case_id": case, "cores": cores, "state": row["state"],
                                     "calls": row["calls"], "makespan_cycles": row.get("makespan_cycles"),
                                     "failure": row.get("failure"), "not_run_reason": row.get("not_run_reason")})
            write(run_dir / "batch.json", batch)
    batch.update(state="stopped" if stopped else "complete", finished_at=utc(),
                 elapsed_seconds=time.monotonic() - started,
                 actual_calls={key: sum(r["calls"][key] for r in batch["results"])
                               for key in ("solver", "standalone_Task_compile", "E0", "E1", "E2")},
                 stop_reason=stopped)
    write(run_dir / "batch.json", batch)
    return 1 if stopped else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true", help="verify frozen bytes; never scores")
    mode.add_argument("--execute", action="store_true", help="run one explicitly selected official E0")
    parser.add_argument("--case", choices=("068",), required=True,
                        help="first admission window is locked to 068/K5 only")
    parser.add_argument("--run-id", help="required with --execute; destination must be new")
    args = parser.parse_args()
    if args.preflight:
        if args.run_id:
            parser.error("--run-id is only valid with --execute")
        print(json.dumps(preflight(args.case), indent=2, ensure_ascii=False))
        return 0
    if not args.run_id:
        parser.error("--run-id is required with --execute")
    return run(args.run_id, args.case)


if __name__ == "__main__":
    raise SystemExit(main())
