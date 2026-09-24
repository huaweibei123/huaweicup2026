"""Finite reproducible differential/performance evidence, not release acceptance."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
import zipfile

from . import P1Evaluator, P1BatchEvaluator, read_config
from ._official import REPO_ROOT, OFFICIAL_CODE_HASH, load_problem1_bundle


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def equal(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    if isinstance(a, float):
        return a.hex() == b.hex()
    return a == b


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", default=["002", "003"])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--candidates", type=int, default=12)
    parser.add_argument("--resource-count", type=int, default=64)
    args = parser.parse_args(argv)
    if min(args.repeats, args.candidates, args.resource_count) < 1:
        parser.error("counts must be positive")
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    oracle, support = load_problem1_bundle("_batch_benchmark_oracle")
    config_path = REPO_ROOT / "data/raw/a/official/data/config.txt"
    config = read_config(config_path)
    generate = support["stub_multicore_cut_and_schedule"].generate_multicore_plan
    records = []
    metadata = dict(python=sys.version, platform=platform.platform(), seed=2026,
                    git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip(),
                    official_code_hash=OFFICIAL_CODE_HASH, config=config,
                    config_sha256=digest(config_path.read_bytes()),
                    uv_lock_sha256=digest((REPO_ROOT / "uv.lock").read_bytes()),
                    source_sha256={p.relative_to(REPO_ROOT).as_posix(): digest(p.read_bytes())
                                   for p in sorted((REPO_ROOT / "src/eval_exact").glob("*.py"))},
                    protocol=dict(cases=args.cases, repeats=args.repeats, candidates=args.candidates,
                                  resource_count=args.resource_count, cache_bytes=16 << 20),
                    timing_scope="parsed graph/plan to full result; cold cache per repetition; setup measured separately",
                    limitation="self-test, public development graphs; no sealed acceptance or multi-platform claim")
    save(out / "run.json", metadata)
    with zipfile.ZipFile(REPO_ROOT / "data/raw/a/official-cases.zip") as archive:
        for case in args.cases:
            raw = archive.read(f"data/case_{case}.json")
            graph = json.loads(raw)
            base = generate(graph, num_cores=4, seed=2026, min_subgraph_size=50, max_subgraph_size=100)
            tids = sorted(set(base["node_to_subgraph"].values()))
            fixed = []
            for index in range(args.candidates):
                rng = random.Random(260924 + index)
                orders = [[] for _ in range(4)]
                for tid in tids:
                    orders[rng.randrange(4)].append(tid)
                fixed.append(dict(node_to_subgraph=base["node_to_subgraph"], core_schedules=orders))
            changed = [generate(graph, num_cores=4, seed=8000 + i,
                                min_subgraph_size=50, max_subgraph_size=100) for i in range(4)]
            workloads = dict(fixed=fixed, changed=changed,
                             mixed=[fixed[0], fixed[1], changed[0], changed[1], fixed[2], fixed[3]])
            save(out / f"case_{case}.plans.json", workloads)
            metrics = []
            for name, plans in workloads.items():
                # Fixed repeat count set before running, other workloads one round.
                for repeat in range(args.repeats if name == "fixed" else 1):
                    setup = time.perf_counter()
                    engine = P1Evaluator(graph)
                    setup_seconds = time.perf_counter() - setup
                    rows = []
                    for index, plan in enumerate(plans):
                        results, times = {}, {}
                        functions = [("e0", lambda: oracle.evaluate_scene_a(graph, plan, **config)),
                                     ("batch", lambda: engine.evaluate(plan, **config))]
                        if (repeat + index) % 2:
                            functions.reverse()
                        for label, function in functions:
                            gc.collect()
                            start = time.perf_counter()
                            results[label] = function()
                            times[label] = time.perf_counter() - start
                        if not equal(results["e0"], results["batch"]):
                            save(out / "FAILURE.json", dict(case=case, workload=name, index=index, results=results))
                            raise AssertionError("full result/type differential")
                        row = dict(index=index, seconds=times, makespan=results["e0"]["makespan"],
                                   data_movement_bytes=results["e0"]["data_movement_bytes"])
                        rows.append(row)
                        if name == "fixed" and repeat == 0:
                            metrics.append({k: row[k] for k in ("makespan", "data_movement_bytes")})
                        del results
                    record = dict(case=case, workload=name, repeat=repeat, full_equal=True, rows=rows,
                                  graph_sha256=digest(raw), setup_seconds=setup_seconds, cache=engine.cache_stats(),
                                  speedup=sum(r["seconds"]["e0"] for r in rows) / sum(r["seconds"]["batch"] for r in rows))
                    records.append(record)
                    save(out / "paired.json", records)
                    print(json.dumps({k: record[k] for k in ("case", "workload", "repeat", "speedup", "cache")}), flush=True)
            # Resource-only repetitions are identified as repeated requests, NOT
            # additional distinct search candidates. Recycle every 32 requests.
            resources = []
            for workers in (1, 2):
                start = time.perf_counter()
                with P1BatchEvaluator(graph, workers=workers, max_tasks_per_worker=32) as pool:
                    rows = []
                    for row in pool.evaluate_batch((fixed[i % len(fixed)] for i in range(args.resource_count)), **config):
                        expected = metrics[row["index"] % len(metrics)]
                        if row["status"] != "ok" or any(row[k] != v for k, v in expected.items()):
                            raise AssertionError(row)
                        rows.append(row)
                elapsed = time.perf_counter() - start
                resources.append(dict(workers=workers, seconds=elapsed, rows=rows,
                                      requests=args.resource_count, distinct_candidates=len(fixed)))
                save(out / f"case_{case}.resources.json", resources)
                print(json.dumps(dict(case=case, workers=workers, resource_seconds=elapsed)), flush=True)
    save(out / "summary.json", dict(full_equal=True, paired_batches=len(records),
         results=[{k:r[k] for k in ("case", "workload", "repeat", "speedup", "cache")} for r in records]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
