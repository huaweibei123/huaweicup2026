"""One isolated, unchanged official evaluation; output is lossless gzip JSON."""
import argparse
import gzip
import json
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import evaluate_scene_b, read_scene_b_config
from multicore_cut_evaluate_problem_3 import evaluate_problem_3, read_cache_config


def main():
    p = argparse.ArgumentParser()
    p.add_argument("graph", type=Path)
    p.add_argument("plan", type=Path)
    p.add_argument("problem", type=int, choices=(2, 3))
    p.add_argument("output", type=Path)
    a = p.parse_args()
    start = time.perf_counter()
    config = ROOT / "data/raw/a/official/data/config.txt"
    kwargs = read_evaluation_config(config)
    kwargs["cross_core_copy_delay"] = read_scene_b_config(config)["cross_core_copy_delay_cycles"]
    graph, plan = json.loads(a.graph.read_text()), json.loads(a.plan.read_text())
    if a.problem == 3:
        kwargs.update(read_cache_config(config))
        result = evaluate_problem_3(graph, plan, **kwargs)
    else:
        result = evaluate_scene_b(graph, plan, **kwargs)
    a.output.write_bytes(gzip.compress(json.dumps(result, separators=(",", ":")).encode(), mtime=0))
    r = resource.getrusage(resource.RUSAGE_SELF)
    print(json.dumps({"makespan": result["makespan"],
                      "data_movement_bytes": result["data_movement_bytes"],
                      "cache_stats": result.get("cache_stats"),
                      "read_evaluate_write_seconds": time.perf_counter() - start,
                      "cpu_seconds": r.ru_utime + r.ru_stime,
                      "max_rss_bytes": r.ru_maxrss * (1 if sys.platform == "darwin" else 1024)}))


if __name__ == "__main__":
    main()
