"""Minimal platform counterexamples, no direct E0 or formal-case calls."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from research.a.e2_search import E2BatchEvaluator
from research.a.e2_search.tests.test_search import simple_graph, PLAN
from src.eval_exact import read_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cfg = read_config(ROOT / "data/raw/a/official/data/config.txt")
    with E2BatchEvaluator(simple_graph(), workers=1, recycle_peak_rss_bytes=1) as pool:
        rss = list(pool.evaluate_batch([PLAN, PLAN], **cfg))
    trials = []
    with E2BatchEvaluator(simple_graph(), workers=1, timeout_seconds=1e-12) as pool:
        for _ in range(8):
            start = time.perf_counter()
            rows = list(pool.evaluate_batch([PLAN], **cfg))
            trials.append(dict(wall_including_possible_spawn=time.perf_counter()-start, record=rows[0]))
    receipt = dict(graph=simple_graph(), plan=PLAN, config=cfg, direct_e0_calls=0,
                   completed_pool_records=10, rss_rows=rss, timeout_trials=trials,
                   monotonic=vars(time.get_clock_info("monotonic")),
                   perf_counter=vars(time.get_clock_info("perf_counter")),
                   no_live_slots=all(s is None for s in pool._slots))
    args.output.write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(rss_values=[r["worker_peak_rss_bytes"] for r in rss],
                         rss_same_pid=rss[0]["worker_pid"] == rss[1]["worker_pid"],
                         timeout_statuses=[r["record"]["status"] for r in trials],
                         monotonic=receipt["monotonic"], no_live_slots=receipt["no_live_slots"])))


if __name__ == "__main__":
    main()
