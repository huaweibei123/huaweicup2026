"""Build a frozen 64-candidate development pool with E0 truth for every member."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import platform
import statistics
import time
from pathlib import Path

from ..eval_exact._official import OFFICIAL_CODE_HASH, load_problem1_bundle
from .model import evaluate, prepare_graph


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _delivery_lf_sha256(path: Path) -> str:
    """Hash the LF bytes delivered by Git for a tracked source file."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _source_delivery_lf_sha256() -> dict[str, str]:
    repo_root = Path(__file__).resolve().parents[2]
    relative_paths = ("src/eval_proxy/dev_pool.py", "src/eval_proxy/model.py")
    return {
        relative: _delivery_lf_sha256(repo_root / relative)
        for relative in relative_paths
    }


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _text_bytes(value: str) -> bytes:
    """Encode generated evidence with repository-canonical LF newlines."""
    return value.replace("\r\n", "\n").encode("utf-8")


def _plan_bytes(plan) -> bytes:
    return (
        json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _official_json_bytes(value) -> bytes:
    """Match ``contest_io._write_json`` without materializing a large file."""
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _deterministic_gzip(value: bytes) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=buffer, compresslevel=9, mtime=0
    ) as archive:
        archive.write(value)
    return buffer.getvalue()


def _average_ranks(values):
    ordered = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[cursor]]:
            end += 1
        rank = (cursor + end - 1) / 2 + 1
        for position in range(cursor, end):
            ranks[ordered[position]] = rank
        cursor = end
    return ranks


def _pearson(left, right):
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right)
    )
    left_norm = math.sqrt(sum((value - left_mean) ** 2 for value in left))
    right_norm = math.sqrt(sum((value - right_mean) ** 2 for value in right))
    if left_norm == 0 or right_norm == 0:
        return None
    return numerator / (left_norm * right_norm)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--count", type=int, default=64)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--scales", nargs="+", type=int, default=[25, 50, 100, 200])
    parser.add_argument("--max-attempts", type=int)
    args = parser.parse_args(argv)
    if args.count < 8:
        parser.error("--count must be at least 8")
    if any(scale < 2 for scale in args.scales):
        parser.error("all --scales values must be at least 2")

    graph_path = Path(args.graph)
    config_path = Path(args.config)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    attempts_dir = output_dir / "attempts"
    plans_dir = output_dir / "plans"
    e0_dir = output_dir / "e0"
    proxy_dir = output_dir / "proxy"
    for directory in (attempts_dir, plans_dir, e0_dir, proxy_dir):
        directory.mkdir()
    max_attempts = args.max_attempts or args.count * 20
    if max_attempts < args.count:
        parser.error("--max-attempts must be at least --count")

    oracle_module, support = load_problem1_bundle(
        "_huaweicup_eval_proxy_dev_pool_oracle"
    )
    contest_io = support["contest_io"]
    validation = support["evaluation_validation"]
    generate_multicore_plan = support[
        "stub_multicore_cut_and_schedule"
    ].generate_multicore_plan
    _read_json = contest_io._read_json
    read_evaluation_config = validation.read_evaluation_config
    read_required_settings = validation.read_required_settings
    evaluate_scene_a = oracle_module.evaluate_scene_a
    graph = _read_json(graph_path)
    settings = read_evaluation_config(str(config_path))
    scene = read_required_settings(
        str(config_path),
        "multicore_scene_a",
        ("task_cross_core_wait_cycles", "task_same_core_wait_cycles"),
    )
    call_args = {
        "bandwidth": settings["bandwidth"],
        "capacity": settings["capacity"],
        "cross_core_wait": scene["task_cross_core_wait_cycles"],
        "same_core_wait": scene["task_same_core_wait_cycles"],
    }
    context = prepare_graph(
        graph,
        problem=1,
        **call_args,
        graph_hash=_sha256(graph_path),
        config_hash=_sha256(config_path),
    )

    candidates = []
    failures = []
    seen_hashes = set()
    attempts = 0
    plans_path = output_dir / "plans.jsonl"
    with plans_path.open("w", encoding="utf-8", newline="\n") as plan_stream:
        while len(candidates) < args.count and attempts < max_attempts:
            scale_index = attempts % len(args.scales)
            seed_index = attempts // len(args.scales)
            max_size = args.scales[scale_index]
            min_size = max(1, max_size // 2)
            seed = scale_index * 100_000 + seed_index
            attempts += 1
            plan = generate_multicore_plan(
                graph,
                num_cores=args.cores,
                seed=seed,
                min_subgraph_size=min_size,
                max_subgraph_size=max_size,
            )
            encoded_plan = _plan_bytes(plan)
            plan_hash = hashlib.sha256(encoded_plan).hexdigest()
            if plan_hash in seen_hashes:
                continue
            seen_hashes.add(plan_hash)

            attempt_id = f"attempt-{attempts:05d}"
            attempt_path = attempts_dir / f"{attempt_id}.plan.json"
            attempt_path.write_bytes(encoded_plan)
            frozen_plan = _read_json(attempt_path)

            try:
                proxy_started = time.perf_counter()
                proxy_result = evaluate(context, frozen_plan)
                proxy_seconds = time.perf_counter() - proxy_started
                oracle_started = time.perf_counter()
                oracle_result = evaluate_scene_a(graph, frozen_plan, **call_args)
                oracle_seconds = time.perf_counter() - oracle_started
            except Exception as error:
                failures.append(
                    {
                        "attempt_id": attempt_id,
                        "plan_sha256": plan_hash,
                        "status": "error",
                        "error_type": type(error).__name__,
                        "message": str(error),
                    }
                )
                continue

            candidate_id = f"candidate-{len(candidates):03d}"
            exact_plan_path = plans_dir / f"{candidate_id}.plan.json"
            exact_plan_path.write_bytes(encoded_plan)
            e0_path = e0_dir / f"{candidate_id}.result.json.gz"
            proxy_path = proxy_dir / f"{candidate_id}.result.json"
            e0_json_bytes = _official_json_bytes(oracle_result)
            e0_path.write_bytes(_deterministic_gzip(e0_json_bytes))
            proxy_path.write_bytes(
                _text_bytes(
                    json.dumps(
                        proxy_result, ensure_ascii=False, indent=2, allow_nan=False
                    )
                    + "\n"
                )
            )
            plan_stream.write(
                json.dumps(
                    {
                        "candidate_id": candidate_id,
                        "seed": seed,
                        "min_subgraph_size": min_size,
                        "max_subgraph_size": max_size,
                        "plan_sha256": plan_hash,
                        "plan_path": exact_plan_path.relative_to(output_dir).as_posix(),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "seed": seed,
                    "min_subgraph_size": min_size,
                    "max_subgraph_size": max_size,
                    "subgraph_count": len(set(plan["node_to_subgraph"].values())),
                    "plan_sha256": plan_hash,
                    "plan_path": exact_plan_path.relative_to(output_dir).as_posix(),
                    "proxy_rank_score": proxy_result["rank_score"],
                    "proxy_seconds": proxy_seconds,
                    "proxy_output_path": proxy_path.relative_to(output_dir).as_posix(),
                    "proxy_output_sha256": _sha256(proxy_path),
                    "e0_makespan": oracle_result["makespan"],
                    "e0_seconds": oracle_seconds,
                    "e0_status": "ok",
                    "e0_encoding": "gzip",
                    "e0_output_path": e0_path.relative_to(output_dir).as_posix(),
                    "e0_output_sha256": _sha256(e0_path),
                    "e0_json_sha256": _sha256_bytes(e0_json_bytes),
                    "proxy_risk_flags": "|".join(proxy_result["risk_flags"]),
                }
            )

    if failures:
        (output_dir / "failures.jsonl").write_bytes(
            _text_bytes(
                "".join(
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
                    for item in failures
                )
            )
        )
    if len(candidates) < args.count:
        raise RuntimeError(
            f"only {len(candidates)} successful unique candidates after "
            f"{attempts} attempts; see failures.jsonl"
        )

    shortlist_size = min(len(candidates), max(8, math.ceil(0.1 * len(candidates))))
    shortlist = sorted(candidates, key=lambda row: row["proxy_rank_score"])[
        :shortlist_size
    ]
    best_all = min(row["e0_makespan"] for row in candidates)
    best_shortlist = min(row["e0_makespan"] for row in shortlist)
    regret = (best_shortlist - best_all) / max(1, best_all)
    scores = [row["proxy_rank_score"] for row in candidates]
    truths = [row["e0_makespan"] for row in candidates]
    spearman = _pearson(_average_ranks(scores), _average_ranks(truths))
    threshold = best_all * 1.01
    retained_within_one_percent = any(
        row["e0_makespan"] <= threshold for row in shortlist
    )
    shortlist_ids = {row["candidate_id"] for row in shortlist}
    for row in candidates:
        row["shortlisted"] = row["candidate_id"] in shortlist_ids

    csv_path = output_dir / "candidates.csv"
    with csv_path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(candidates[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(candidates)
    summary = {
        "capability": "rank_only",
        "development_pool": True,
        "candidate_count": len(candidates),
        "all_candidates_have_e0_truth": all(
            row["e0_status"] == "ok" for row in candidates
        ),
        "shortlist_size": shortlist_size,
        "best_e0_makespan_all": best_all,
        "best_e0_makespan_shortlist": best_shortlist,
        "shortlist_regret": regret,
        "retained_within_one_percent": retained_within_one_percent,
        "spearman_same_pool": spearman,
        "proxy_total_seconds": sum(row["proxy_seconds"] for row in candidates),
        "e0_total_seconds": sum(row["e0_seconds"] for row in candidates),
        "observed_throughput_ratio": sum(row["e0_seconds"] for row in candidates)
        / max(1e-12, sum(row["proxy_seconds"] for row in candidates)),
        "quality_gate_passed": False,
        "quality_gate_note": (
            "This is the same development pool used to inspect v0; it is not a "
            "held-out release validation set."
        ),
    }
    (output_dir / "summary.json").write_bytes(
        _text_bytes(
            json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
    )
    run = {
        "command_scope": "in-memory E0 full result and internal E2 score",
        "graph": str(graph_path.as_posix()),
        "graph_sha256": _sha256(graph_path),
        "config": str(config_path.as_posix()),
        "config_sha256": _sha256(config_path),
        "problem": 1,
        "cores": args.cores,
        "requested_count": args.count,
        "attempts": attempts,
        "max_attempts": max_attempts,
        "failed_attempts": len(failures),
        "scales": args.scales,
        "official_code_hash": OFFICIAL_CODE_HASH,
        "candidate_implementation": {
            "id": "eval-proxy-v0",
            "delivery_lf_sha256": _source_delivery_lf_sha256(),
        },
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "summary": summary,
    }
    (output_dir / "run.json").write_bytes(
        _text_bytes(
            json.dumps(run, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
    )
    print(json.dumps(summary, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
