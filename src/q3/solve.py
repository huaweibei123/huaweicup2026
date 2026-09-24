"""Online Q3 baseline: choose one construction from structure, verify, publish.

There is exactly one official P3 call per successful invocation. No retrospective
comparison, case-id dispatch or score-based search is performed. Failures are
reported without publishing a candidate as a valid final plan.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from .construct import ROOT, Index, UnsupportedStructure


def select(index):
    try:
        a, b, h = index.word_descriptor()
    except UnsupportedStructure as e:
        return "affine_eighth", {"rule": "general_affine", "word_declined": str(e)}
    return "resource_word", {"rule": "homogeneous_serial_MVM", "a": a, "b": b, "h": h}


def prepare(graph, cores):
    index = Index(graph)
    strategy, selection = select(index)
    plan, metadata = index.build(cores, strategy)
    return plan, {**metadata, "selection": selection}


def publish_new(path, payload):
    """Publish a complete file atomically; never replace an existing result."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".q3-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
        # Hard-link creation is atomic and refuses overwrite, unlike replace().
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def main():
    start = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True,
                        help="new directory for full official result and receipt")
    args = parser.parse_args()
    if args.output.exists() or args.evidence.exists():
        raise FileExistsError("output and evidence must be new paths")
    raw = args.graph.read_bytes()
    graph = json.loads(raw)
    plan, metadata = prepare(graph, args.cores)
    constructed = time.perf_counter()

    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_3 import (
        evaluate_problem_3, read_cache_config, read_scene_b_config,
    )
    config = ROOT / "data/raw/a/official/data/config.txt"
    settings = read_evaluation_config(config)
    settings["cross_core_copy_delay"] = read_scene_b_config(config)["cross_core_copy_delay_cycles"]
    settings.update(read_cache_config(config))
    result = evaluate_problem_3(graph, plan, **settings)
    verified = time.perf_counter()
    payload = (json.dumps(plan, separators=(",", ":")) + "\n").encode()
    full_result = gzip.compress(json.dumps(result, separators=(",", ":")).encode(), mtime=0)
    receipt = {**metadata, "official_e0_calls": 1, "makespan": result["makespan"],
               "data_movement_bytes": result["data_movement_bytes"],
               "cache_stats": result["cache_stats"],
               "graph_sha256": hashlib.sha256(raw).hexdigest(),
               "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
               "plan_sha256": hashlib.sha256(payload).hexdigest(),
               "result_sha256": hashlib.sha256(full_result).hexdigest(),
               "construct_main_seconds": constructed - start,
               "official_import_config_evaluate_seconds": verified - constructed,
               "timing_note": "These component timers exclude interpreter/import before main. Use an external process timer for end-to-end solver wall."}
    args.evidence.mkdir(parents=True, exist_ok=False)
    (args.evidence / "result.json.gz").write_bytes(full_result)
    (args.evidence / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    publish_new(args.output, payload)
    receipt["main_until_plan_published_seconds"] = time.perf_counter() - start
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
