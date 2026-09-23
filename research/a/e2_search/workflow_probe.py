"""Actually run shortlist -> E1 recheck -> E0 confirmation and bounded long run."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import time

from src.eval_exact import P1Evaluator, read_config
from src.eval_exact._official import REPO_ROOT as ROOT, load_problem1_bundle
from .engine import E2Evaluator
from .pool import E2BatchEvaluator
from .benchmark import save, measured, FIELDS, equal


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    config = read_config(ROOT / "data/raw/a/official/data/config.txt")
    oracle, _ = load_problem1_bundle("_e2_workflow_oracle")
    save(args.output / "run.json", dict(code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                        input_run=args.inputs.as_posix(), config=config,
                                        git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                                        scope="actual local candidate loops, parsed inputs, one run each; no solver/generation/IO in timing"))
    rows = []
    for label in ("005-fixed", "004-mixed8"):
        graph = json.loads((ROOT / f"data/raw/a/official/data/case_{label[:3]}.json").read_text())
        with gzip.open(args.inputs / f"{label}.plans.json.gz", "rt") as f:
            plans = json.load(f)
        truth = json.loads((args.inputs / f"{label}.truth.json").read_text())
        for mode in ("e2", "e1"):
            start, cpu = time.perf_counter(), time.process_time()
            cls = E2Evaluator if mode == "e2" else P1Evaluator
            scorer = cls(graph)
            scores = list(scorer.evaluate_batch(plans, **config))
            assert all(s["status"] == "ok" for s in scores)
            shortlist = sorted(range(len(plans)), key=lambda i: scores[i]["makespan"])[:8]
            rechecks = []
            if mode == "e2":
                checker = P1Evaluator(graph)
                for i in shortlist:
                    full = checker.evaluate(plans[i], **config)
                    assert all(equal(full[k], truth[i][k]) for k in FIELDS)
                    rechecks.append(dict(index=i, makespan=full["makespan"]))
                selected = min(rechecks, key=lambda r: r["makespan"])["index"]
            else:
                selected = shortlist[0]  # E1 already fully replayed all 64.
            final = oracle.evaluate_scene_a(graph, plans[selected], **config)
            elapsed = time.perf_counter() - start
            cpu_elapsed = time.process_time() - cpu
            assert final["makespan"] == min(t["makespan"] for t in truth)
            row = dict(pool=label, engine=mode, wall=elapsed, cpu=cpu_elapsed,
                       shortlist=shortlist, rechecks=rechecks, selected=selected,
                       final_makespan=final["makespan"], all_scores=[r["makespan"] for r in scores])
            rows.append(row)
            save(args.output / "pipelines.json", rows)
            with gzip.open(args.output / f"{label}-{mode}-final-e0.json.gz", "wt") as f:
                json.dump(final, f)
            print(json.dumps({k: row[k] for k in ("pool", "engine", "wall", "cpu", "final_makespan")}), flush=True)
    # 1024 requests cycle these 64 plans. This is a bounded-retention/recycling
    # probe, explicitly NOT 1024 independent new candidates or a quality test.
    label = "005-fixed"
    graph = json.loads((ROOT / "data/raw/a/official/data/case_005.json").read_text())
    with gzip.open(args.inputs / f"{label}.plans.json.gz", "rt") as f:
        plans = json.load(f)
    truth = json.loads((args.inputs / f"{label}.truth.json").read_text())
    with E2BatchEvaluator(graph, workers=2, max_tasks_per_worker=256) as pool:
        start = time.perf_counter()
        receipt = []
        for row in pool.evaluate_batch(itertools.islice(itertools.cycle(plans), 1024), **config):
            assert row["status"] == "ok", row
            assert all(equal(row[k], truth[row["index"] % 64][k]) for k in FIELDS)
            receipt.append({k: row[k] for k in ("index", "worker_pid", "worker_peak_rss_bytes", "cache", "route", "wall_seconds", "cpu_seconds")})
        elapsed = time.perf_counter() - start
    assert all(s is None for s in pool._slots)
    save(args.output / "long-run.json", dict(requests=1024, distinct_plans=64, workers=2,
         max_tasks_per_worker=256, wall=elapsed, pids=sorted({r["worker_pid"] for r in receipt}),
         all_scores_equal=True, workers_closed=True, receipts=receipt))
    print(f"long run PASS 1024 calls; {len({r['worker_pid'] for r in receipt})} worker lifetimes", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
