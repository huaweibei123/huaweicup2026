"""One new public P1 pool; 64 E0 calls, no author-result reuse or calibration."""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import platform
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from research.a.e2_search import E2Evaluator
from src.eval_exact import P1Evaluator, read_config
from src.eval_exact._official import load_problem1_bundle, OFFICIAL_CODE_HASH

FIELDS = ("makespan", "data_movement_bytes", "cross_task_traffic")
SEED = 9240600


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(equal(x, y) for x, y in zip(left, right))
    if isinstance(left, float):
        return left.hex() == right.hex()
    return left == right


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    graph_path = ROOT / "data/raw/a/official/data/case_006.json"
    config_path = ROOT / "data/raw/a/official/data/config.txt"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    config = read_config(config_path)
    oracle, support = load_problem1_bundle("_independent_windows_e0")
    generate = support["stub_multicore_cut_and_schedule"].generate_multicore_plan
    plans = []
    for group in range(8):
        base = generate(graph, num_cores=4, seed=SEED + group,
                        min_subgraph_size=40, max_subgraph_size=80)
        tids = sorted(set(base["node_to_subgraph"].values()))
        for variant in range(8):
            rng = random.Random(SEED + 100 + group * 8 + variant)
            orders = [[] for _ in range(4)]
            for tid in tids:
                orders[rng.randrange(4)].append(tid)
            plans.append(dict(node_to_subgraph=base["node_to_subgraph"], core_schedules=orders))
    plan_hashes = [sha(json.dumps(p, sort_keys=True).encode()) for p in plans]
    assert len(set(plan_hashes)) == 64
    save(out / "plans.json", plans)
    meta = dict(tested_head="f4ee4756fc15c65ddc4256f3c73ff4efc89accfc",
                case="006", seed=SEED, partitions=8, candidates=64, cores=4,
                workers=1, mode="sequential in-process", max_e0_calls=64,
                python=sys.version, platform=platform.platform(), config=config,
                graph_sha256=sha(graph_path.read_bytes()), config_sha256=sha(config_path.read_bytes()),
                official_code_hash=OFFICIAL_CODE_HASH, plan_sha256=plan_hashes,
                limitation="Public new-graph independent reproduction, not sealed acceptance. Generator is frozen official stub; E1 still constructs full diagnostics.")
    save(out / "protocol.json", meta)
    truth, truth_seconds = [], []
    for i, plan in enumerate(plans):
        t = time.perf_counter()
        result = oracle.evaluate_scene_a(graph, plan, **config)
        truth_seconds.append(time.perf_counter() - t)
        with gzip.open(out / f"e0-{i:02d}.json.gz", "wt", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False)
        truth.append({k: result[k] for k in FIELDS})
        if (i + 1) % 16 == 0:
            print(f"E0 {i+1}/64", flush=True)
    save(out / "truth.json", truth)
    timings, all_records, differences = {}, {}, []
    for label, cls in (("e1", P1Evaluator), ("e2", E2Evaluator)):
        t = time.perf_counter()
        engine = cls(graph, cache_bytes=16 << 20)
        records = [engine.evaluate_record(plan, **config) for plan in plans]
        timings[label] = time.perf_counter() - t
        for i, (record, expected) in enumerate(zip(records, truth)):
            if record["status"] != "ok" or any(not equal(record.get(k), expected[k]) for k in FIELDS):
                differences.append(dict(engine=label, index=i, record=record, expected=expected))
        all_records[label] = records
        save(out / f"{label}-records.json", records)
    e2 = all_records["e2"]
    errors = sorted(abs(r["makespan"] - t["makespan"]) / max(1, t["makespan"]) for r, t in zip(e2, truth))
    shortlist = sorted(range(64), key=lambda i: (e2[i]["makespan"], i))[:8]
    best = min(t["makespan"] for t in truth)
    best_selected = min(truth[i]["makespan"] for i in shortlist)
    summary = dict(e0_calls=64, distinct_plans=64, differences=differences,
                   e2_routes=dict(Counter(r.get("route", "unspecified") for r in e2)),
                   absolute_relative_error_median=(errors[31]+errors[32])/2,
                   absolute_relative_error_p95=errors[60], max_error=max(errors),
                   shortlist=shortlist, best_e0=best, best_shortlisted_e0=best_selected,
                   shortlist_regret=(best_selected-best)/max(1, best),
                   e0_seconds=sum(truth_seconds), search_api_seconds=timings,
                   observed_e1_over_e2=timings["e1"]/timings["e2"],
                   e2_cache=e2[-1]["cache"], total_wall_seconds=time.perf_counter()-start,
                   timing_scope="One sequential pass per engine, graph/plans parsed; includes engine setup, all plan compilation/scoring. Excludes generation, interpreter, file I/O. Not release speed acceptance.")
    save(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if differences or summary["e2_routes"] != {"native": 64}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
