"""Search-only JSONL streaming; each line is an unchanged official plan object."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time

from ._official_b import read_config
from .engine import ENGINE_VERSION
from .pool import E2BatchEvaluator


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("plans_jsonl", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--cache-mib", type=int, default=16)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--recycle-after", type=int, default=256)
    parser.add_argument("--problem", type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args(argv)
    start = time.perf_counter()
    graph = json.loads(args.graph.read_text())
    config = read_config(args.config, problem=args.problem)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    counts = {}
    # Exclusive creation prevents accidental replacement of previous evidence.
    with args.output.open("x") as output, args.plans_jsonl.open() as inputs:
        with E2BatchEvaluator(graph, workers=args.workers, cache_bytes=args.cache_mib << 20,
                              timeout_seconds=args.timeout,
                              max_tasks_per_worker=args.recycle_after, problem=args.problem) as pool:
            for record in pool.evaluate_batch((json.loads(line) for line in inputs), **config):
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                output.flush()
                key = record["status"] + ":" + record.get("route", "worker")
                counts[key] = counts.get(key, 0) + 1
    metadata = dict(engine=f'p{args.problem}-e2-native-search-v1', capability=f"p{args.problem}_search_records",
                    counts=counts, workers=args.workers, cache_mib_per_worker=args.cache_mib,
                    wall_seconds=time.perf_counter() - start,
                    timing="graph/config read, worker startup, JSONL read/write, IPC, scoring, teardown",
                    formal_score="E0 confirmation required; development candidate, no sealed acceptance")
    Path(str(args.output) + ".run.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return 0 if all(k.startswith("ok:") for k in counts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
