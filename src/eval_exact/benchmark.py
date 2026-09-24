"""Differential and paired timing harness for the first E1 rewrite."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import math
import os
import platform
import statistics
import time
from pathlib import Path

from ._official import (
    OFFICIAL_CODE_HASH,
    PROBLEM1_SHA256,
    load_problem1_bundle,
)
from .problem1 import evaluate_scene_a, read_scene_a_config

_CANDIDATE_SOURCE_FILES = (
    "src/eval_exact/_official.py",
    "src/eval_exact/problem1.py",
)


def _first_difference(left, right, path="$"):
    if type(left) is not type(right):
        return {"path": path, "oracle": repr(left), "exact": repr(right)}
    if isinstance(left, dict):
        if left.keys() != right.keys():
            return {
                "path": path,
                "oracle_keys": list(left),
                "exact_keys": list(right),
            }
        for key in left:
            difference = _first_difference(left[key], right[key], f"{path}.{key}")
            if difference:
                return difference
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return {"path": path, "oracle_len": len(left), "exact_len": len(right)}
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            difference = _first_difference(left_item, right_item, f"{path}[{index}]")
            if difference:
                return difference
        return None
    if left != right:
        return {"path": path, "oracle": repr(left), "exact": repr(right)}
    return None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _delivery_lf_sha256(path: Path) -> str:
    """Hash the LF bytes that Git delivers for repository text files."""
    content = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def _write_json_lf(path: Path, value) -> None:
    content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(content.encode("utf-8"))


def _percentile(values, probability):
    ordered = sorted(values)
    index = max(0, math.ceil(probability * len(ordered)) - 1)
    return ordered[index]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--min-subgraph-size", type=int, default=50)
    parser.add_argument("--max-subgraph-size", type=int, default=100)
    args = parser.parse_args(argv)
    if args.warmup < 0 or args.repeats < 1:
        parser.error("--warmup must be non-negative and --repeats positive")

    repo_root = Path(__file__).resolve().parents[2]
    official_root = repo_root / "data" / "raw" / "a" / "official"
    config_path = official_root / "data" / "config.txt"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    plans_dir = output_dir / "plans"
    plans_dir.mkdir()
    oracle_module, support = load_problem1_bundle(
        "_huaweicup_eval_oracle_problem1_benchmark"
    )
    _read_json = support["contest_io"]._read_json
    read_evaluation_config = support["evaluation_validation"].read_evaluation_config
    generate_multicore_plan = support[
        "stub_multicore_cut_and_schedule"
    ].generate_multicore_plan
    settings = read_evaluation_config(str(config_path))
    scene = read_scene_a_config(str(config_path))
    call_args = {
        "bandwidth": settings["bandwidth"],
        "capacity": settings["capacity"],
        "cross_core_wait": scene["task_cross_core_wait_cycles"],
        "same_core_wait": scene["task_same_core_wait_cycles"],
    }
    rows = []
    comparisons = []
    plan_hashes = {}

    for case_name in args.cases:
        graph_path = official_root / "data" / case_name
        graph = _read_json(graph_path)
        plan = generate_multicore_plan(
            graph,
            num_cores=args.cores,
            seed=args.seed,
            min_subgraph_size=args.min_subgraph_size,
            max_subgraph_size=args.max_subgraph_size,
        )
        plan_path = plans_dir / f"{Path(case_name).stem}.plan.json"
        _write_json_lf(plan_path, plan)
        plan_hashes[case_name] = _sha256(plan_path)
        oracle_result = oracle_module.evaluate_scene_a(graph, plan, **call_args)
        exact_result = evaluate_scene_a(graph, plan, **call_args)
        difference = _first_difference(oracle_result, exact_result)
        comparisons.append(
            {
                "case": case_name,
                "equal": difference is None,
                "first_difference": difference,
                "makespan": oracle_result.get("makespan"),
            }
        )
        if difference is not None:
            raise AssertionError(f"full result differs for {case_name}: {difference}")

        for _ in range(args.warmup):
            warm_oracle = oracle_module.evaluate_scene_a(graph, plan, **call_args)
            warm_exact = evaluate_scene_a(graph, plan, **call_args)
            for engine_name, result in (
                ("oracle", warm_oracle),
                ("exact", warm_exact),
            ):
                warm_difference = _first_difference(oracle_result, result)
                if warm_difference is not None:
                    raise AssertionError(
                        f"warm {engine_name} result differs for {case_name}: "
                        f"{warm_difference}"
                    )

        for repeat in range(args.repeats):
            engines = (
                (
                    ("oracle", oracle_module.evaluate_scene_a),
                    ("exact", evaluate_scene_a),
                )
                if repeat % 2 == 0
                else (
                    ("exact", evaluate_scene_a),
                    ("oracle", oracle_module.evaluate_scene_a),
                )
            )
            for engine_name, function in engines:
                gc.collect()
                started = time.perf_counter()
                result = function(graph, plan, **call_args)
                elapsed = time.perf_counter() - started
                repeat_difference = _first_difference(oracle_result, result)
                rows.append(
                    {
                        "case": case_name,
                        "engine": engine_name,
                        "repeat": repeat,
                        "seconds": f"{elapsed:.9f}",
                        "makespan": result["makespan"],
                        "full_equal": repeat_difference is None,
                    }
                )
                if repeat_difference is not None:
                    raise AssertionError(
                        f"timed {engine_name} result differs for {case_name} "
                        f"repeat {repeat}: {repeat_difference}"
                    )

    csv_path = output_dir / "paired-timings.csv"
    with csv_path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    summaries = []
    for case_name in args.cases:
        oracle_times = [
            float(row["seconds"])
            for row in rows
            if row["case"] == case_name and row["engine"] == "oracle"
        ]
        exact_times = [
            float(row["seconds"])
            for row in rows
            if row["case"] == case_name and row["engine"] == "exact"
        ]
        paired_speedups = [
            oracle_time / exact_time
            for oracle_time, exact_time in zip(oracle_times, exact_times)
        ]
        summaries.append(
            {
                "case": case_name,
                "oracle_median_seconds": statistics.median(oracle_times),
                "exact_median_seconds": statistics.median(exact_times),
                "oracle_p95_seconds": _percentile(oracle_times, 0.95),
                "exact_p95_seconds": _percentile(exact_times, 0.95),
                "speedup": statistics.median(oracle_times)
                / statistics.median(exact_times),
                "paired_speedup_geomean": math.exp(
                    statistics.fmean(math.log(value) for value in paired_speedups)
                ),
                "paired_fraction_at_least_0_8x": sum(
                    value >= 0.8 for value in paired_speedups
                )
                / len(paired_speedups),
            }
        )

    run = {
        "scope": "in-memory full result; excludes JSON/Trace serialization and process startup",
        "cases": args.cases,
        "seed": args.seed,
        "cores": args.cores,
        "warmup": args.warmup,
        "repeats": args.repeats,
        "subgraph_size": [args.min_subgraph_size, args.max_subgraph_size],
        "official_problem1_sha256": PROBLEM1_SHA256,
        "official_code_hash": OFFICIAL_CODE_HASH,
        "candidate_implementation": {
            "id": "eval-exact-indexed-boundary-schema-copy-v2",
            "delivery_lf_sha256": {
                relative: _delivery_lf_sha256(repo_root / relative)
                for relative in _CANDIDATE_SOURCE_FILES
            },
        },
        "benchmark_delivery_lf_sha256": _delivery_lf_sha256(Path(__file__)),
        "config_sha256": _sha256(config_path),
        "input_sha256": {
            case_name: _sha256(official_root / "data" / case_name)
            for case_name in args.cases
        },
        "plan_sha256": plan_hashes,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "summaries": summaries,
        "comparisons": comparisons,
    }
    _write_json_lf(output_dir / "run.json", run)
    print(json.dumps(run, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
