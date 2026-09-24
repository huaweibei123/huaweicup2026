"""One direct structural proposal, one online official P3 validation.

Each method is an independent solver. Comparing their results afterwards does
not create an online winner-selection algorithm or a non-regression guarantee.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from .construct import Index, ROOT, UnsupportedStructure
from .capacity_tree import construct as capacity_construct
from .reduction_tree import construct as balanced_construct
from .fragment_tree import construct as fragment_construct
from .release_tree import construct as release_construct
from .stage_fork_join import construct as stage_construct
from .safe_solve import encoded
from .solve import publish_new, select


def prepare(index, cores, method):
    if method in ("stage-single-cut", "stage-two-cut"):
        from .stage_migration import construct as migration_construct
        mode = "single_cut" if method == "stage-single-cut" else "two_cut"
        return _prepare(index, cores, method,
                        lambda i, k: migration_construct(i, k, mode=mode))
    # Keep the research attention route separate from the adaptive production router.
    if method in ("attention", "attention-ffn"):
        from .attention_rows import construct as attention_construct
        builder = lambda i, k: attention_construct(i, k, pack_ffn=method == "attention-ffn")
        return _prepare(index, cores, method, builder)
    builder = {"balanced": balanced_construct, "capacity": capacity_construct,
               "fragment": fragment_construct, "stage": stage_construct,
               "stage-rotate": lambda i, k: stage_construct(i, k, collector_policy="rotate_heavy"),
               "release-order": release_construct,
               "release-place": lambda i, k: release_construct(i, k, place=True)}[method]
    return _prepare(index, cores, method, builder)


def _prepare(index, cores, method, builder):
    try:
        plan, metadata = builder(index, cores)
        return plan, metadata, {"rule": "guarded_direct_tree", "method": method}
    except UnsupportedStructure as error:
        strategy, selection = select(index)
        plan, metadata = index.build(cores, strategy)
        return plan, metadata, {**selection, "tree_declined": str(error)}


def main():
    start = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--tree-method", choices=("balanced", "capacity", "fragment",
                                                "release-order", "release-place", "stage", "stage-rotate",
                                                "stage-single-cut", "stage-two-cut", "attention", "attention-ffn"), required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.evidence.exists():
        raise FileExistsError("output and evidence must be new paths")
    raw = args.graph.read_bytes()
    index = Index(json.loads(raw))
    indexed = time.perf_counter()
    plan, metadata, selection = prepare(index, args.cores, args.tree_method)
    constructed = time.perf_counter()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3, read_cache_config, read_scene_b_config
    config = ROOT / "data/raw/a/official/data/config.txt"
    settings = read_evaluation_config(config)
    settings["cross_core_copy_delay"] = read_scene_b_config(config)["cross_core_copy_delay_cycles"]
    settings.update(read_cache_config(config))
    args.evidence.mkdir(parents=True, exist_ok=False)
    payload = encoded(plan)
    (args.evidence / "evaluated-plan-0.json").write_bytes(payload)
    ledger = [{"ordinal": 0, "status": "started", "plan_sha256": hashlib.sha256(payload).hexdigest()}]
    (args.evidence / "evaluations.json").write_bytes(encoded(ledger))
    evaluating = time.perf_counter()
    try:
        result = evaluate_problem_3(index.graph, plan, **settings)
    except Exception as error:
        ledger[0].update(status="failed", error_type=type(error).__name__, reason=str(error),
                         seconds=time.perf_counter() - evaluating)
        (args.evidence / "evaluations.json").write_bytes(encoded(ledger))
        raise
    evaluated = time.perf_counter()
    ledger[0].update(status="ok", seconds=evaluated - evaluating)
    (args.evidence / "evaluations.json").write_bytes(encoded(ledger))
    full = gzip.compress(encoded(result), mtime=0)
    candidate_dir = args.evidence / "seed"
    candidate_dir.mkdir()
    (candidate_dir / "plan.json").write_bytes(payload)
    (candidate_dir / "result.json.gz").write_bytes(full)
    (args.evidence / "result.json.gz").write_bytes(full)
    refs = {"plan": {"path": "seed/plan.json", "sha256": hashlib.sha256(payload).hexdigest()},
            "result": {"path": "seed/result.json.gz", "sha256": hashlib.sha256(full).hexdigest()}}
    saved = time.perf_counter()
    strategy = metadata["strategy"]
    receipt = {"strategy": strategy, "selected_strategy": strategy,
               "official_e0_calls": 1, "candidate_limit": 1, "seed_selection": selection,
               "candidates": [{"name": "seed", "strategy": strategy, "status": "ok",
                               "makespan": result["makespan"], "metadata": metadata, "artifacts": refs}],
               "makespan": result["makespan"], "data_movement_bytes": result["data_movement_bytes"],
               "cache_stats": result["cache_stats"], "graph_sha256": hashlib.sha256(raw).hexdigest(),
               "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
               "plan_sha256": refs["plan"]["sha256"], "result_sha256": refs["result"]["sha256"],
               "read_index_seconds": indexed - start, "construct_seconds": constructed - indexed,
               "config_prepare_ledger_seconds": evaluating - constructed,
               "evaluation_seconds": evaluated - evaluating, "result_write_seconds": saved - evaluated,
               "main_until_evidence_seconds": saved - start,
               "timing_note": "Disjoint main-phase timers exclude startup and final receipt/publication; outer process wall is authoritative. One candidate only; no online comparison or non-regression guarantee."}
    (args.evidence / "receipt.json").write_bytes(encoded(receipt))
    publish_new(args.output, payload)
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
