"""Two structural proposals, accepted only by complete official P3 results.

Preserve the original structural seed, then consider one guarded reduction-tree
proposal. No parameter or random search. Evaluation and all preparation are
online costs. The old entrypoint remains unchanged for historical comparisons.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from .construct import ROOT, Index, UnsupportedStructure
from .reduction_tree import construct as tree_construct
from .solve import publish_new, select


def encoded(value):
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


def evaluate_candidates(index, cores, evaluate, save):
    """Exact acceptance policy; injection permits policy tests without E0 calls."""
    strategy, selection = select(index)
    seed, meta = index.build(cores, strategy)
    result = evaluate(seed)
    seed_files = save("seed", seed, result) or {}
    winner = (seed, result, strategy)
    calls = 1
    records = [{"name": "seed", "strategy": strategy, "status": "ok",
                "makespan": result["makespan"], "metadata": meta, "artifacts": seed_files}]
    try:
        proposal, meta = tree_construct(index, cores)
    except UnsupportedStructure as error:
        records.append({"name": "tree", "strategy": "balanced_reduction_tree",
                        "status": "unsupported", "reason": str(error), "makespan": None})
        return winner, calls, records, selection
    if encoded(proposal) == encoded(seed):
        records.append({"name": "tree", "strategy": "balanced_reduction_tree",
                        "status": "duplicate", "metadata": meta, "makespan": None})
        return winner, calls, records, selection

    # Preserve the confirmed seed if this proposal is rejected. The failure is
    # evidence, never a fake low/high numeric score and never retried.
    from evaluation_validation import EvaluationValidationError
    calls += 1
    try:
        proposed_result = evaluate(proposal)
    except EvaluationValidationError as error:
        records.append({"name": "tree", "strategy": "balanced_reduction_tree",
                        "status": "rejected", "reason": str(error), "makespan": None,
                        "metadata": meta})
        return winner, calls, records, selection
    tree_files = save("tree", proposal, proposed_result) or {}
    records.append({"name": "tree", "strategy": meta["strategy"], "status": "ok",
                    "makespan": proposed_result["makespan"], "metadata": meta,
                    "artifacts": tree_files})
    if proposed_result["makespan"] < result["makespan"]:
        winner = (proposal, proposed_result, meta["strategy"])
    return winner, calls, records, selection


def main(policy=evaluate_candidates):
    start = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.evidence.exists():
        raise FileExistsError("output and evidence must be new paths")
    raw = args.graph.read_bytes()
    index = Index(json.loads(raw))
    args.evidence.mkdir(parents=True, exist_ok=False)

    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_3 import (
        evaluate_problem_3, read_cache_config, read_scene_b_config,
    )
    config = ROOT / "data/raw/a/official/data/config.txt"
    settings = read_evaluation_config(config)
    settings["cross_core_copy_delay"] = read_scene_b_config(config)["cross_core_copy_delay_cycles"]
    settings.update(read_cache_config(config))
    evaluations = []

    def evaluate(plan):
        # Charge before dispatch; an exception or process death cannot erase it.
        (args.evidence / f"evaluated-plan-{len(evaluations)}.json").write_bytes(encoded(plan))
        evaluations.append({"ordinal": len(evaluations), "status": "started",
                            "plan_sha256": hashlib.sha256(encoded(plan)).hexdigest()})
        (args.evidence / "evaluations.json").write_bytes(encoded(evaluations))
        t0 = time.perf_counter()
        try:
            result = evaluate_problem_3(index.graph, plan, **settings)
        except Exception as error:
            evaluations[-1].update(status="failed", error_type=type(error).__name__,
                                   reason=str(error), seconds=time.perf_counter() - t0)
            (args.evidence / "evaluations.json").write_bytes(encoded(evaluations))
            raise
        evaluations[-1].update(status="ok", seconds=time.perf_counter() - t0)
        (args.evidence / "evaluations.json").write_bytes(encoded(evaluations))
        return result

    def save(name, plan, result):
        folder = args.evidence / name
        folder.mkdir()
        files = {"plan": ("plan.json", encoded(plan)),
                 "result": ("result.json.gz", gzip.compress(encoded(result), mtime=0))}
        artifacts = {}
        for kind, (filename, data) in files.items():
            (folder / filename).write_bytes(data)
            artifacts[kind] = {"path": f"{name}/{filename}",
                               "sha256": hashlib.sha256(data).hexdigest()}
        return artifacts

    (plan, result, strategy), calls, candidates, selection = policy(
        index, args.cores, evaluate, save)
    payload = encoded(plan)
    full = gzip.compress(encoded(result), mtime=0)
    receipt = {"strategy": strategy, "selected_strategy": strategy,
               "official_e0_calls": calls, "candidate_limit": 2,
               "seed_selection": selection, "candidates": candidates,
               "makespan": result["makespan"],
               "data_movement_bytes": result["data_movement_bytes"],
               "cache_stats": result["cache_stats"],
               "graph_sha256": hashlib.sha256(raw).hexdigest(),
               "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
               "plan_sha256": hashlib.sha256(payload).hexdigest(),
               "result_sha256": hashlib.sha256(full).hexdigest(),
               "evaluation_seconds": sum(e["seconds"] for e in evaluations),
               "main_until_evidence_seconds": time.perf_counter() - start,
               "timing_note": "All E0 calls are online; use outer subprocess wall for full solver cost."}
    (args.evidence / "result.json.gz").write_bytes(full)
    (args.evidence / "receipt.json").write_bytes(encoded(receipt))
    publish_new(args.output, payload)
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
