"""Compare the two E2 directions on a frozen development pool.

The command reuses saved plans and compressed E0 truth.  It verifies every
saved hash before scoring, so route changes can be measured without rerunning
the expensive official evaluator or silently changing the candidate pool.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import platform
import statistics
import time
from pathlib import Path

from ..eval_exact._official import OFFICIAL_CODE_HASH, load_problem1_bundle
from .dev_pool import _average_ranks, _pearson
from .event_model import evaluate_event
from .model import evaluate, prepare_graph


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _delivery_lf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(probability * len(ordered)) - 1)
    return ordered[index]


def _shortlist_metrics(scores, truths, candidate_ids, shortlist_size):
    selected = sorted(range(len(scores)), key=lambda index: scores[index])[
        :shortlist_size
    ]
    best_all = min(truths)
    best_selected = min(truths[index] for index in selected)
    threshold = best_all * 1.01
    return {
        "shortlist_size": shortlist_size,
        "shortlist_candidate_ids": [candidate_ids[index] for index in selected],
        "best_e0_makespan_all": best_all,
        "best_e0_makespan_shortlist": best_selected,
        "shortlist_regret": (best_selected - best_all) / max(1, best_all),
        "retained_within_one_percent": any(
            truths[index] <= threshold for index in selected
        ),
        "spearman_same_pool": _pearson(_average_ranks(scores), _average_ranks(truths)),
    }


def _load_pool(
    pool_dir: Path,
    *,
    graph_sha256: str,
    config_sha256: str,
    official_code_hash: str,
):
    try:
        run = json.loads((pool_dir / "run.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read pool run.json: {error}") from error
    expected_identity = {
        "graph_sha256": graph_sha256,
        "config_sha256": config_sha256,
        "official_code_hash": official_code_hash,
    }
    for field, expected in expected_identity.items():
        observed = run.get(field) if isinstance(run, dict) else None
        if observed != expected:
            raise ValueError(
                f"pool run.json {field} mismatch: expected {expected}, got {observed}"
            )
    run_summary = run.get("summary") if isinstance(run, dict) else None
    recorded_candidate_count = (
        run_summary.get("candidate_count") if isinstance(run_summary, dict) else None
    )
    if type(recorded_candidate_count) is not int or recorded_candidate_count < 1:
        raise ValueError("pool run.json summary.candidate_count must be positive")
    provenance = run.get("candidate_implementation")
    delivery_hashes = (
        provenance.get("delivery_lf_sha256") if isinstance(provenance, dict) else None
    )
    if not isinstance(delivery_hashes, dict):
        raise ValueError(
            "pool run.json candidate_implementation.delivery_lf_sha256 is required"
        )
    repo_root = Path(__file__).resolve().parents[2]
    required_sources = ("src/eval_proxy/dev_pool.py", "src/eval_proxy/model.py")
    for relative in required_sources:
        expected = delivery_hashes.get(relative)
        observed = _delivery_lf_sha256(repo_root / relative)
        if expected != observed:
            raise ValueError(
                f"pool source delivery_lf_sha256 mismatch for {relative}: "
                f"expected {expected}, got {observed}"
            )

    with (pool_dir / "candidates.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("candidate pool is empty")
    if len(rows) != recorded_candidate_count:
        raise ValueError(
            "pool run.json candidate_count mismatch: "
            f"expected {recorded_candidate_count}, got {len(rows)} rows"
        )
    candidate_id_values = [row.get("candidate_id") for row in rows]
    if any(not value for value in candidate_id_values) or len(
        set(candidate_id_values)
    ) != len(candidate_id_values):
        raise ValueError("candidate pool ids must be non-empty and unique")

    plans = []
    truths = []
    candidate_ids = []
    recorded_e0_seconds = 0.0
    for row in rows:
        candidate_id = row["candidate_id"]
        if row["e0_status"] != "ok" or row["e0_encoding"] != "gzip":
            raise ValueError(f"unexpected E0 status/encoding for {candidate_id}")
        plan_path = pool_dir / row["plan_path"]
        proxy_path = pool_dir / row["proxy_output_path"]
        e0_path = pool_dir / row["e0_output_path"]
        if _sha256(plan_path) != row["plan_sha256"]:
            raise ValueError(f"plan hash mismatch for {candidate_id}")
        if _sha256(proxy_path) != row["proxy_output_sha256"]:
            raise ValueError(f"proxy hash mismatch for {candidate_id}")
        if _sha256(e0_path) != row["e0_output_sha256"]:
            raise ValueError(f"compressed E0 hash mismatch for {candidate_id}")
        raw_e0 = gzip.decompress(e0_path.read_bytes())
        if _sha256_bytes(raw_e0) != row["e0_json_sha256"]:
            raise ValueError(f"decompressed E0 hash mismatch for {candidate_id}")

        plans.append(json.loads(plan_path.read_text(encoding="utf-8")))
        makespan = json.loads(raw_e0)["makespan"]
        if makespan != int(row["e0_makespan"]):
            raise ValueError(f"E0 makespan mismatch for {candidate_id}")
        truths.append(makespan)
        candidate_ids.append(candidate_id)
        recorded_e0_seconds += float(row["e0_seconds"])
    return rows, plans, truths, candidate_ids, recorded_e0_seconds


def _time_route(function, context, plans, *, warmup, repeats):
    for _ in range(warmup):
        for plan in plans:
            function(context, plan)
    totals = []
    responses = None
    for _ in range(repeats):
        started = time.perf_counter()
        current = [function(context, plan) for plan in plans]
        totals.append(time.perf_counter() - started)
        if responses is None:
            responses = current
        elif current != responses:
            raise AssertionError("route response changed across timing repeats")
    return responses, totals


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--pool-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args(argv)
    if args.warmup < 0 or args.repeats < 1:
        parser.error("--warmup must be non-negative and --repeats positive")

    graph_path = Path(args.graph)
    config_path = Path(args.config)
    pool_dir = Path(args.pool_dir)
    output_path = Path(args.output)
    if output_path.exists():
        parser.error("--output must not already exist")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    _, support = load_problem1_bundle("_huaweicup_eval_proxy_route_comparison")
    contest_io = support["contest_io"]
    validation = support["evaluation_validation"]
    graph = contest_io._read_json(graph_path)
    settings = validation.read_evaluation_config(str(config_path))
    scene = validation.read_required_settings(
        str(config_path),
        "multicore_scene_a",
        ("task_cross_core_wait_cycles", "task_same_core_wait_cycles"),
    )
    graph_sha256 = _sha256(graph_path)
    config_sha256 = _sha256(config_path)
    context = prepare_graph(
        graph,
        problem=1,
        bandwidth=settings["bandwidth"],
        capacity=settings["capacity"],
        cross_core_wait=scene["task_cross_core_wait_cycles"],
        same_core_wait=scene["task_same_core_wait_cycles"],
        graph_hash=graph_sha256,
        config_hash=config_sha256,
    )
    rows, plans, truths, candidate_ids, recorded_e0_seconds = _load_pool(
        pool_dir,
        graph_sha256=graph_sha256,
        config_sha256=config_sha256,
        official_code_hash=OFFICIAL_CODE_HASH,
    )
    pool_summary = json.loads((pool_dir / "summary.json").read_text(encoding="utf-8"))
    if pool_summary.get("candidate_count") != len(rows):
        raise ValueError(
            "pool summary.json candidate_count does not match candidates.csv"
        )
    shortlist_size = int(pool_summary["shortlist_size"])

    rank_responses, rank_totals = _time_route(
        evaluate,
        context,
        plans,
        warmup=args.warmup,
        repeats=args.repeats,
    )
    event_responses, event_totals = _time_route(
        evaluate_event,
        context,
        plans,
        warmup=args.warmup,
        repeats=args.repeats,
    )
    rank_scores = [response["rank_score"] for response in rank_responses]
    event_scores = [response["metrics"]["makespan"] for response in event_responses]
    relative_errors = [
        abs(estimate - truth) / max(1, truth)
        for estimate, truth in zip(event_scores, truths)
    ]

    def timing(values):
        median = statistics.median(values)
        return {
            "warmup": args.warmup,
            "repeats": args.repeats,
            "pool_seconds": values,
            "median_pool_seconds": median,
            "p95_pool_seconds": _percentile(values, 0.95),
            "recorded_e0_seconds_over_route_median": (recorded_e0_seconds / median),
        }

    report = {
        "scope": (
            "same frozen 64-candidate development pool; in-memory route "
            "scoring with verified saved plans and E0 truth"
        ),
        "development_pool": True,
        "quality_gate_passed": False,
        "quality_gate_note": (
            "The pool is not held out, E1 timing is not measured here, and "
            "the event route misses the 1%/3% numeric error thresholds."
        ),
        "problem": 1,
        "candidate_count": len(rows),
        "all_saved_hashes_verified": True,
        "graph": graph_path.as_posix(),
        "graph_sha256": graph_sha256,
        "config": config_path.as_posix(),
        "config_sha256": config_sha256,
        "pool_dir": pool_dir.as_posix(),
        "official_code_hash": OFFICIAL_CODE_HASH,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
        },
        "source_sha256": {
            "compare_routes.py": _sha256(Path(__file__)),
            "model.py": _sha256(Path(__file__).with_name("model.py")),
            "event_model.py": _sha256(Path(__file__).with_name("event_model.py")),
        },
        "source_delivery_lf_sha256": {
            relative: _delivery_lf_sha256(
                Path(__file__).resolve().parents[2] / relative
            )
            for relative in ("src/eval_proxy/dev_pool.py", "src/eval_proxy/model.py")
        },
        "recorded_e0_total_seconds": recorded_e0_seconds,
        "routes": {
            "proxy-rank-v0": {
                "algorithm_direction": "aggregate_bounds_and_transfer_score",
                "numeric_kind": "none",
                "timing": timing(rank_totals),
                **_shortlist_metrics(
                    rank_scores, truths, candidate_ids, shortlist_size
                ),
            },
            "proxy-task-event-v0": {
                "algorithm_direction": "coarse_task_event_list_schedule",
                "numeric_kind": "estimate",
                "timing": timing(event_totals),
                **_shortlist_metrics(
                    event_scores, truths, candidate_ids, shortlist_size
                ),
                "relative_error": {
                    "median": statistics.median(relative_errors),
                    "p95": _percentile(relative_errors, 0.95),
                    "maximum": max(relative_errors),
                    "fraction_over_three_percent": sum(
                        value > 0.03 for value in relative_errors
                    )
                    / len(relative_errors),
                    "numeric_gate_passed": (
                        statistics.median(relative_errors) <= 0.01
                        and _percentile(relative_errors, 0.95) <= 0.03
                    ),
                },
            },
        },
    }
    output_path.write_bytes(
        (
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        ).encode("utf-8")
    )
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
