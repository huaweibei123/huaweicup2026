"""Bounded official P2 pilot, fixed Fang seeds; run from repository root."""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import platform
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from .joint import FixedAssignment, ROOT

SEED_COMMIT = "0b58c123cccf02fc993b741d79dcd8511e4dd38f"
SEED_DIR = "results/a/q2-yuanzhifang/stage-b-20260924-042906/plans"
EXPECTED = {"002-M1": 72415, "044-M1": 74530, "044-M2": 69113}
POLICIES = ("id", "critical32", "critical", "earliest_start")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    # Persist each reservation before launching its worker.
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    preparation = time.monotonic()
    inputs = out / "inputs"
    inputs.mkdir()
    with zipfile.ZipFile(ROOT / "data/raw/a/official-cases.zip") as archive:
        for case in ("002", "044"):
            (inputs / f"case_{case}.json").write_bytes(archive.read(f"data/case_{case}.json"))
    (inputs / "config.txt").write_bytes((ROOT / "data/raw/a/official/data/config.txt").read_bytes())
    for label in EXPECTED:
        data = subprocess.check_output(["git", "show", f"{SEED_COMMIT}:{SEED_DIR}/{label}.json"], cwd=ROOT)
        (inputs / f"{label}.json").write_bytes(data)
    source_files = sorted((ROOT / "data/raw/a/official/code").glob("*.py"))
    source_files += sorted((ROOT / "src/q2_nikolastarx").glob("*.py"))
    protocol = {
        "as_run_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "seed_commit": SEED_COMMIT, "problem": 2, "cores": 4,
        "python": sys.version, "platform": platform.platform(),
        "policies": POLICIES, "expected_baselines": EXPECTED,
        "max_calls": 13, "workers": 1, "per_call_timeout_seconds": 30,
        "batch_seconds": 180, "stop_launch_seconds": 120,
        "input_sha256": {p.name: sha(p.read_bytes()) for p in inputs.iterdir()},
        "source_sha256": {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in source_files},
        "uv_lock_sha256": sha((ROOT / "uv.lock").read_bytes()),
        "preparation_seconds": time.monotonic() - preparation,
        "timing_scope": "T0: after fixed-byte extraction; includes graph parsing, construction, E0, compression and machine summary. Not a from-graph solver benchmark; seed search is historical.",
    }
    dump(out / "protocol.json", protocol)
    t0 = time.monotonic()
    ledger = {"T0_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "calls": []}
    rows = []
    dump(out / "ledger.json", ledger)

    def evaluate(case, label, plan_bytes, generation_seconds=0.0):
        elapsed = time.monotonic() - t0
        if len(ledger["calls"]) >= 13 or elapsed > 120:
            raise RuntimeError("no call allowance or launch window left")
        run = out / label
        run.mkdir()
        (run / "plan.json").write_bytes(plan_bytes)
        argv = [sys.executable, "data/raw/a/official/code/multicore_cut_evaluate_problem_2.py",
                str((inputs / f"case_{case}.json").relative_to(ROOT)),
                str((run / "plan.json").relative_to(ROOT)), "--config",
                str((inputs / "config.txt").relative_to(ROOT)), "-o",
                str((run / "result.json").relative_to(ROOT)), "--trace-output",
                str((run / "trace.json").relative_to(ROOT)), "--log-output",
                str((run / "evaluation.txt").relative_to(ROOT))]
        entry = {"candidate_id": label, "reserved_at_seconds": elapsed,
                 "plan_sha256": sha(plan_bytes), "state": "reserved",
                 "argv": ["PYTHON", *argv[1:]]}
        ledger["calls"].append(entry)
        dump(out / "ledger.json", ledger)
        start = time.monotonic()
        try:
            with (run / "stdout.txt").open("w") as stdout, (run / "stderr.txt").open("w") as stderr:
                process = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=30)
            entry.update(returncode=process.returncode, cli_seconds=time.monotonic() - start,
                         state="success" if process.returncode == 0 else "failed")
            dump(out / "ledger.json", ledger)
            if process.returncode:
                raise RuntimeError(f"official CLI failed: {label}; stop without retry")
        except subprocess.TimeoutExpired:
            entry.update(state="timeout", cli_seconds=time.monotonic() - start)
            dump(out / "ledger.json", ledger)
            raise
        raw = (run / "result.json").read_bytes()
        result = json.loads(raw)
        for name in ("result.json", "trace.json"):
            path = run / name
            original = path.read_bytes()
            compressed = gzip.compress(original, mtime=0)
            assert gzip.decompress(compressed) == original
            path.with_suffix(path.suffix + ".gz").write_bytes(compressed)
            path.unlink()
        row = {"candidate_id": label, "case": case, "cycles": result["makespan"],
               "generation_seconds": generation_seconds, "cli_seconds": entry["cli_seconds"],
               "result_sha256": sha(raw), "plan_sha256": sha(plan_bytes),
               "data_movement_bytes": result["data_movement_bytes"]}
        rows.append(row)
        dump(out / "rows.json", rows)
        return row

    try:
        baseline = {}
        for label, expected in EXPECTED.items():
            baseline[label] = evaluate(label[:3], label, (inputs / f"{label}.json").read_bytes())
            if baseline[label]["cycles"] != expected:
                raise RuntimeError(f"baseline mismatch for {label}")
        winners = {}
        for case in ("002", "044"):
            start = time.monotonic()
            graph = json.loads((inputs / f"case_{case}.json").read_bytes())
            parent = json.loads((inputs / f"{case}-M1.json").read_bytes())
            index = FixedAssignment(graph, parent)
            initialization_seconds = time.monotonic() - start
            incumbent = min((r for r in rows if r["case"] == case), key=lambda r: r["cycles"])
            for policy in POLICIES:
                start = time.monotonic()
                plan = index.build(policy)
                encoded = (json.dumps(plan, indent=2) + "\n").encode()
                generation = time.monotonic() - start
                row = evaluate(case, f"{case}-{policy}", encoded, generation)
                row["index_seconds"] = initialization_seconds
                if row["cycles"] < incumbent["cycles"]:
                    incumbent = row
            winners[case] = incumbent
        for case, winner in winners.items():
            repeat = evaluate(case, f"{case}-confirm", (out / winner["candidate_id"] / "plan.json").read_bytes())
            if repeat["result_sha256"] != winner["result_sha256"]:
                raise RuntimeError(f"complete result repeat mismatch: {case}")
        dump(out / "summary.json", {"status": "complete", "winners": winners,
                                    "calls": len(ledger["calls"]), "elapsed_seconds": time.monotonic() - t0,
                                    "within_180_seconds": time.monotonic() - t0 <= 180})
    except Exception as error:
        dump(out / "failure.json", {"type": type(error).__name__, "message": str(error),
                                    "elapsed_seconds": time.monotonic() - t0})
        raise
    finally:
        dump(out / "rows.json", rows)
        manifest = {str(p.relative_to(out)): {"bytes": p.stat().st_size, "sha256": sha(p.read_bytes())}
                    for p in sorted(out.rglob("*")) if p.is_file()}
        dump(out / "manifest.json", manifest)
        dump(out / "completion.json", {"elapsed_seconds": time.monotonic() - t0,
                                       "within_180_seconds": time.monotonic() - t0 <= 180})


if __name__ == "__main__":
    main()
