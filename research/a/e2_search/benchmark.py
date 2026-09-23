"""Frozen development pools, E0 all-member labels and same-output E1/E2 timing.

Not a sealed or cross-platform release test. Fresh output directory required.
Main process truth work is outside timers. The separate resource child includes
graph/plans read, pool construction/startup, IPC, scoring, and teardown.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import threading
import time

import numpy as np

from src.eval_exact import P1Evaluator, P1BatchEvaluator, read_config
from src.eval_exact._official import REPO_ROOT as ROOT, OFFICIAL_CODE_HASH, load_problem1_bundle
from src.eval_exact.batch_benchmark import equal
from .engine import E2Evaluator, ENGINE_VERSION
from .pool import E2BatchEvaluator

HERE = Path(__file__).resolve().parent
FIELDS = ("makespan", "data_movement_bytes", "cross_task_traffic")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def measured(fn):
    start, cpu = time.perf_counter(), time.process_time()
    value = fn()
    return value, dict(wall=time.perf_counter() - start, cpu=time.process_time() - cpu)


def create_plans(graph, generate, case, mixed=False):
    plans = []
    for i in range(64):
        group = i // 8 if mixed else 0
        base = generate(graph, num_cores=4, seed=824000 + int(case) * 100 + group,
                        min_subgraph_size=50, max_subgraph_size=100)
        rng = random.Random(8240000 + int(case) * 100 + i)
        orders = [[] for _ in range(4)]
        for tid in sorted(set(base["node_to_subgraph"].values())):
            orders[rng.randrange(4)].append(tid)
        plans.append(dict(node_to_subgraph=base["node_to_subgraph"], core_schedules=orders))
    assert len({sha(json.dumps(p, sort_keys=True).encode()) for p in plans}) == 64
    return plans


def resource_child(args):
    """Clean parent process for parent+worker RSS; sampled sum, not PSS."""
    start = time.perf_counter()
    graph = json.loads((ROOT / f"data/raw/a/official/data/case_{args.case}.json").read_text())
    with gzip.open(args.plans, "rt") as f:
        plans = json.load(f)
    config = read_config(ROOT / "data/raw/a/official/data/config.txt")
    cls = E2BatchEvaluator if args.engine == "e2" else P1BatchEvaluator
    peak, samples = 0, 0
    stop = threading.Event()
    pool = cls(graph, workers=args.workers, cache_bytes=16 << 20, max_tasks_per_worker=256)
    def sample():
        nonlocal peak, samples
        while not stop.is_set():
            pids = [os.getpid()]
            for slot in pool._slots:
                try:
                    if slot is not None and slot[0].pid:
                        pids.append(slot[0].pid)
                except ValueError:
                    pass
            result = subprocess.run(["ps", "-o", "rss=", "-p", ",".join(map(str, pids))], capture_output=True, text=True)
            try:
                peak = max(peak, sum(int(x) * 1024 for x in result.stdout.split()))
                samples += 1
            except ValueError:
                pass
            stop.wait(.05)
    monitor = threading.Thread(target=sample, daemon=True)
    monitor.start()
    try:
        with pool:
            rows = list(pool.evaluate_batch(plans, **config))
    finally:
        stop.set()
        monitor.join(timeout=2)
    elapsed = time.perf_counter() - start
    expected = json.loads(args.truth.read_text())
    assert len(rows) == len(expected)
    for row, truth in zip(rows, expected):
        assert row["status"] == "ok", row
        assert all(equal(row[k], truth[k]) for k in FIELDS)
    save(args.output, dict(engine=args.engine, workers=args.workers, total_wall=elapsed,
                           parent_plus_workers_sampled_rss_bytes=peak, rss_samples=samples,
                           rss_method="ps RSS sum every 50ms, shared pages double counted; sampled lower bound on transient peak; excludes multiprocessing resource tracker",
                           timing="graph/plans/config read, pool construction, spawn, IPC, scoring, teardown, monitor; excludes Python interpreter imports/startup",
                           rows=rows))


def main(args):
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    config = read_config(ROOT / "data/raw/a/official/data/config.txt")
    oracle, support = load_problem1_bundle("_e2_search_benchmark_oracle")
    generate = support["stub_multicore_cut_and_schedule"].generate_multicore_plan
    protocol = [("004", False), ("005", False), ("011", False), ("004", True)]
    sources = [*HERE.glob("*.py"), *HERE.glob("native/*.cpp"), *HERE.glob("tests/*.py")]
    save(out / "run.json", dict(engine=ENGINE_VERSION, platform=platform.platform(), python=sys.version,
        git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        dirty=subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True),
        source_sha256={p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sources},
        native_binary_sha256=sha((HERE / "native/libreplay.so").read_bytes()),
        official_code_hash=OFFICIAL_CODE_HASH, config=config,
        e1_reference="5bfe53a29c1ba05167239f51ea937e602f7f85b4 unchanged src/eval_exact",
        protocol=protocol, candidates_per_pool=64, seed_formula="824000 + case*100 + partition; schedule 8240000 + case*100 + i",
        timing="parsed input -> graph snapshot + all 64 public search calls; cold partition compilation included, truth excluded; E1 returns same 3 score fields but internally constructs full diagnostics; not native-E1 comparison",
        acceptance="development pools only; all E0 labels, not sealed acceptance; no guaranteed >=10x"))
    summaries = []
    for case, mixed in protocol:
        label = case + ("-mixed8" if mixed else "-fixed")
        graph_path = ROOT / f"data/raw/a/official/data/case_{case}.json"
        graph = json.loads(graph_path.read_text())
        plans = create_plans(graph, generate, case, mixed)
        with gzip.open(out / f"{label}.plans.json.gz", "wt") as f:
            json.dump(plans, f)
        truth, truth_times = [], []
        for i, plan in enumerate(plans):
            value, timing = measured(lambda: oracle.evaluate_scene_a(graph, plan, **config))
            truth.append({k: value[k] for k in FIELDS})
            truth_times.append(timing)
            # Preserve full oracle outputs in bounded-size evidence chunks.
            with gzip.open(out / f"{label}.e0-{i // 16:02}.jsonl.gz", "at") as f:
                f.write(json.dumps(dict(index=i, result=value), separators=(",", ":")) + "\n")
        save(out / f"{label}.truth.json", truth)
        times, results = {}, {}
        order = ["e2", "e1"] if len(summaries) % 2 == 0 else ["e1", "e2"]
        for mode in order:
            cls = E2Evaluator if mode == "e2" else P1Evaluator
            evaluator, init = measured(lambda: cls(graph, cache_bytes=16 << 20))
            rows, batch = measured(lambda: list(evaluator.evaluate_batch(plans, **config)))
            assert all(r["status"] == "ok" for r in rows), rows
            for row, expected in zip(rows, truth):
                assert all(equal(row[k], expected[k]) for k in FIELDS), (label, mode, row)
            times[mode] = dict(initialization=init, batch=batch, total_wall=init["wall"] + batch["wall"],
                               total_cpu=init["cpu"] + batch["cpu"])
            results[mode] = rows
            del evaluator
        errors = [abs(r["makespan"] - t["makespan"]) / max(1, t["makespan"])
                  for r, t in zip(results["e2"], truth)]
        top = sorted(range(64), key=lambda i: results["e2"][i]["makespan"])[:8]
        best = min(x["makespan"] for x in truth)
        regret = (min(truth[i]["makespan"] for i in top) - best) / max(1, best)
        summary = dict(pool=label, graph_sha256=sha(graph_path.read_bytes()), candidates=64,
                       distinct_partitions=8 if mixed else 1, times=times, order=order,
                       speedup=times["e1"]["total_wall"] / times["e2"]["total_wall"],
                       cpu_speedup=times["e1"]["total_cpu"] / times["e2"]["total_cpu"],
                       absolute_relative_error=dict(median=float(np.median(errors)), p95=float(np.quantile(errors, .95)), maximum=max(errors)),
                       shortlist_regret=regret, retains_within_one_percent=regret <= .01,
                       routes=dict(Counter(r["route"] for r in results["e2"])),
                       e2_latency_p50=float(np.median([r["wall_seconds"] for r in results["e2"]])),
                       e2_latency_p95=float(np.quantile([r["wall_seconds"] for r in results["e2"]], .95)))
        save(out / f"{label}.timings.json", dict(rows=results, times=times, oracle_times=truth_times))
        summaries.append(summary)
        save(out / "summary.json", summaries)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    # One fixed and one changing-partition batch under identical worker budgets.
    for label in ("005-fixed", "004-mixed8"):
        for workers in (1, 2):
            for mode in ("e1", "e2"):
                command = [sys.executable, "-m", "research.a.e2_search.benchmark", "--resource-child",
                           "--case", label[:3], "--plans", str(out / f"{label}.plans.json.gz"),
                           "--truth", str(out / f"{label}.truth.json"), "--engine", mode,
                           "--workers", str(workers), "--output", str(out / f"{label}-{mode}-w{workers}.resources.json")]
                _, elapsed = measured(lambda: subprocess.run(command, cwd=ROOT, check=True))
                save(out / f"{label}-{mode}-w{workers}.process.json", elapsed)
                print(f"resource PASS {label} {mode} workers={workers} process wall={elapsed['wall']:.3f}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resource-child", action="store_true")
    parser.add_argument("--case")
    parser.add_argument("--plans", type=Path)
    parser.add_argument("--truth", type=Path)
    parser.add_argument("--engine", choices=("e1", "e2"))
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    resource_child(args) if args.resource_child else main(args)
