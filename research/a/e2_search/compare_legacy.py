"""Run old E2 at its fixed checkout against the SAME new, fully E0-labeled pools.

Execute by file path, not -m (so the legacy src package is imported first).
Nothing is written in the old checkout. Rust availability is recorded elsewhere.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

LEGACY = "d83d5f32a1c23f6450aa9c15fa85891c4ebddd7f"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    legacy = args.legacy_root.resolve()
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=legacy, text=True).strip() == LEGACY
    assert not subprocess.check_output(["git", "diff", "HEAD", "--", "src/eval_proxy", "src/eval_exact/_official.py"], cwd=legacy)
    sys.path.insert(0, str(legacy))
    from src.eval_proxy import prepare_graph, evaluate, evaluate_event
    root = Path(__file__).resolve().parents[3]
    config = json.loads((args.inputs / "run.json").read_text())["config"]
    results = []
    for label in ("004-fixed", "005-fixed", "011-fixed", "004-mixed8"):
        graph = json.loads((root / f"data/raw/a/official/data/case_{label[:3]}.json").read_text())
        with gzip.open(args.inputs / f"{label}.plans.json.gz", "rt") as f:
            plans = json.load(f)
        truth = json.loads((args.inputs / f"{label}.truth.json").read_text())
        for route, fn in (("rank", evaluate), ("event", evaluate_event)):
            start, cpu = time.perf_counter(), time.process_time()
            context = prepare_graph(graph, problem=1, **config)
            scores = [fn(context, plan) for plan in plans]
            elapsed, cpu_elapsed = time.perf_counter() - start, time.process_time() - cpu
            values = [s["metrics"]["makespan"] if route == "event" else s["rank_score"] for s in scores]
            best = min(t["makespan"] for t in truth)
            top = sorted(range(64), key=lambda i: values[i])[:8]
            regret = (min(truth[i]["makespan"] for i in top) - best) / max(1, best)
            errors = [abs(v - t["makespan"]) / max(1, t["makespan"]) for v, t in zip(values, truth)] if route == "event" else None
            results.append(dict(pool=label, route=route, wall=elapsed, cpu=cpu_elapsed,
                                shortlist=top, shortlist_regret=regret, values=values,
                                absolute_relative_error=None if errors is None else dict(
                                    median=float(np.median(errors)), p95=float(np.quantile(errors, .95)), maximum=max(errors))))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as f:
        json.dump(dict(legacy_head=LEGACY, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                       timing="parsed inputs; graph preparation plus 64 candidate scores; same pools as new E2; different returned diagnostics per legacy route", results=results), f, indent=2)
    print(json.dumps([{k: r[k] for k in ("pool", "route", "wall", "shortlist_regret", "absolute_relative_error")} for r in results], indent=2))


if __name__ == "__main__":
    main()
