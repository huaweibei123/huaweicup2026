"""Preregistered Q3 pilot: three public graphs, <=21 normal E0 calls, no retries.

This is a research comparison, not an online best-plan solver. Separate direct
constructor wall time from paired P2/P3 external evaluation and oracle selection.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
import time

from .construct import ROOT, Index, UnsupportedStructure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    start = time.perf_counter()
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    records, attempts, skips = [], [], []
    state = {"started_utc": datetime.now(timezone.utc).isoformat(), "status": "running",
             "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
             "python": sys.version, "platform": platform.platform(), "seed": None,
             "cores": 4, "workers": 1, "timeout_seconds": 30, "batch_limit_seconds": 300,
             "formal_call_limit": 24, "records": records, "attempts": attempts, "skips": skips,
             "selection": "retrospective official P3 minimum; not an online solver",
             "command": ["python", "-m", "src.q3.experiment", str(a.output)]}
    sources = sorted((ROOT / "src/q3").glob("*.py"))
    sources += sorted((ROOT / "data/raw/a/official/code").glob("*.py"))
    sources += [ROOT / "uv.lock", ROOT / "data/raw/a/official/data/config.txt"]
    sources += [ROOT / f"data/raw/a/official/data/case_{c}.json" for c in ("008", "044", "080")]
    state["sha256"] = {str(path.relative_to(ROOT)): sha(path) for path in sources}

    def save():
        state["elapsed_seconds"] = time.perf_counter() - start
        (out / "run.json").write_text(json.dumps(state, indent=2) + "\n")

    def process(cmd, logname):
        remaining = 300 - (time.perf_counter() - start)
        if remaining <= 0:
            raise TimeoutError("batch budget exhausted")
        t = time.perf_counter()
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           timeout=min(30, remaining))
        wall = time.perf_counter() - t
        (out / f"{logname}.stdout.txt").write_text(r.stdout)
        (out / f"{logname}.stderr.txt").write_text(r.stderr)
        if r.returncode:
            raise RuntimeError(f"{logname}: child exit {r.returncode}; inspect saved stderr")
        return json.loads(r.stdout), wall

    def evaluate(case, strategy, problem, plan, repeat=False):
        if len(attempts) >= 24:
            raise RuntimeError("formal E0 call budget exhausted")
        prefix = f"case_{case}-{strategy}-p{problem}" + ("-repeat" if repeat else "")
        result_path = out / f"{prefix}.json.gz"
        attempt = {"case": case, "strategy": strategy, "problem": problem,
                   "repeat": repeat, "status": "started"}
        attempts.append(attempt)
        save()
        summary, wall = process([sys.executable, "-m", "src.q3.oracle",
                                 str(ROOT / f"data/raw/a/official/data/case_{case}.json"),
                                 str(plan), str(problem), str(result_path)], prefix)
        attempt["status"] = "ok"
        record = {**attempt, **summary, "child_wall_seconds": wall,
                  "plan": plan.name, "plan_sha256": sha(plan),
                  "result": result_path.name, "result_sha256": sha(result_path)}
        records.append(record)
        save()
        return record

    save()
    try:
        for case in ("008", "044", "080"):
            graph = ROOT / f"data/raw/a/official/data/case_{case}.json"
            idx = Index(json.loads(graph.read_text()))
            seen = set()
            for strategy in ("component", "affine_eighth", "resource_word"):
                if strategy == "resource_word":
                    try:
                        idx.word_descriptor()
                    except UnsupportedStructure as e:
                        skips.append({"case": case, "strategy": strategy, "reason": str(e)})
                        save()
                        continue
                plan = out / f"case_{case}-{strategy}_multicore_res.json"
                meta, wall = process([sys.executable, "-m", "src.q3.construct", str(graph),
                                      "--cores", "4", "--strategy", strategy, "-o", str(plan)],
                                     f"case_{case}-{strategy}-construct")
                state.setdefault("constructors", []).append({"case": case, **meta,
                                                             "process_wall_seconds": wall,
                                                             "plan_sha256": sha(plan)})
                if sha(plan) in seen:
                    skips.append({"case": case, "strategy": strategy, "reason": "duplicate plan bytes"})
                    continue
                seen.add(sha(plan))
                for problem in (2, 3):
                    evaluate(case, strategy, problem, plan)
            eligible = [r for r in records if r["case"] == case and r["problem"] == 3]
            winner = min(eligible, key=lambda r: (r["makespan"], r["strategy"]))
            repeat = evaluate(case, winner["strategy"], 3, out / winner["plan"], repeat=True)
            if repeat["result_sha256"] != winner["result_sha256"]:
                raise AssertionError("independent P3 full-result byte mismatch")
        state["status"] = "complete"
    except Exception as e:
        state["status"] = "stopped_on_failure"
        state["error"] = f"{type(e).__name__}: {e}"
        if attempts and attempts[-1]["status"] == "started":
            attempts[-1]["status"] = "failed_or_timed_out"
        save()
        raise
    save()
    print(json.dumps({"status": state["status"], "formal_calls": len(attempts),
                      "elapsed_seconds": state["elapsed_seconds"]}))


if __name__ == "__main__":
    main()
