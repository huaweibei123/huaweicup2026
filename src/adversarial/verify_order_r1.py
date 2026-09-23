"""Round-1 F-TASK-004 probe: does the original graph's declaration order matter?

The contract warns that sort order and spill tie-breaking depend on insertion
order. This probe re-declares the same graph with permuted ops/tensors/edges and
compares the Task-local results of the official entry.

Permutations are explicit (no RNG), so `seed` is null and the run is deterministic.
No E0 call, no scoring.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "data" / "raw" / "a" / "official" / "code"
OUT_DIR = ROOT / "results" / "a" / "form" / "r1-20260923-farmeruncle123"

sys.dont_write_bytecode = True
sys.path.insert(0, str(CODE))
import multicore_cut_evaluate_problem_1 as p1  # noqa: E402

BANDWIDTH = 60
CAPACITY = {"L1": 524288, "UB": 131072}
PLAN = {"node_to_subgraph": {"2": 0, "3": 0, "4": 0, "5": 0}, "core_schedules": [[0]]}

# Two independent chains plus a shared tensor, so several ops are cost-tied and a
# tie-break has something to be sensitive to.
BASE = {
    "ops": [
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 4, "op": "RELU", "pipe": "PIPE_V", "cycles": 4},
        {"id": 5, "op": "RELU", "pipe": "PIPE_V", "cycles": 4},
    ],
    "tensors": [
        {"id": 100, "pos": "DDR", "size": 64},
        {"id": 101, "pos": "L1", "size": 64},
        {"id": 102, "pos": "UB", "size": 64},
        {"id": 103, "pos": "UB", "size": 64},
        {"id": 104, "pos": "UB", "size": 64},
        {"id": 105, "pos": "UB", "size": 64},
    ],
    "edges": [
        {"source": 100, "target": 1}, {"source": 1, "target": 101},
        {"source": 101, "target": 2}, {"source": 2, "target": 102},
        {"source": 102, "target": 3}, {"source": 102, "target": 4},
        {"source": 3, "target": 103}, {"source": 4, "target": 104},
        {"source": 103, "target": 5}, {"source": 5, "target": 105},
    ],
}


def digest_task(task):
    """Order-sensitive fingerprint of one prepared Task.

    Includes Step1's sequence (`seq`) and Step3's prepared output, because the
    contract warns that sort order and spill tie-breaking may depend on
    insertion order.
    """
    return json.dumps({
        "op_by_id": sorted(task["op_by_id"]),
        "tensor_ids": sorted(task["tensor_by_id"]),
        "pipe_ops": {k: list(v) for k, v in sorted(task["pipe_ops"].items())},
        "op_preds": {str(k): sorted(v) for k, v in sorted(task["op_preds"].items())},
        "op_succs": {str(k): sorted(v) for k, v in sorted(task["op_succs"].items())},
        "in_tids": {str(k): sorted(v) for k, v in sorted(task["in_tids"].items())},
        "out_tids": {str(k): sorted(v) for k, v in sorted(task["out_tids"].items())},
        "seq": list(task["seq"]),
        "seq_pos": {str(k): v for k, v in sorted(task["seq_pos"].items())},
        "step3": task["step3"],
    }, ensure_ascii=False, sort_keys=True, default=str)


def run(graph, label):
    try:
        tasks, cross, traffic, _view = p1._build_scene_a_tasks(
            graph, PLAN, BANDWIDTH, CAPACITY)
        t0 = tasks[0]
        return {"variant": label, "outcome": "built",
                "fingerprint": digest_task(t0),
                "pipe_ops": {k: list(v) for k, v in sorted(t0["pipe_ops"].items())},
                "cross_task_traffic": cross, "traffic": traffic}
    except Exception as exc:  # noqa: BLE001
        return {"variant": label, "outcome": "rejected",
                "error": "{}: {}".format(type(exc).__name__, exc)}


def permuted(seed):
    g = json.loads(json.dumps(BASE))
    rnd = random.Random(seed)
    rnd.shuffle(g["ops"])
    rnd.shuffle(g["tensors"])
    rnd.shuffle(g["edges"])
    return g


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = [run(BASE, "baseline declaration order")]
    for seed in (1, 2, 3):
        records.append(run(permuted(seed), "permutation seed={}".format(seed)))

    base_fp = records[0].get("fingerprint")
    for r in records:
        r["same_as_baseline"] = (r.get("fingerprint") == base_fp) if base_fp else None

    report = {
        "run_id": "r1-20260923-farmeruncle123",
        "scope": "F-TASK-004: sensitivity of Task-local results to input declaration order",
        "official_code_hash": "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0",
        "seed": None,
        "note": ("Permutations are explicit seeded shuffles of the ORIGINAL graph declaration "
                 "order only; tensor/op ids are unchanged. No E0, no makespan."),
        "all_same": all(r.get("same_as_baseline") for r in records[1:]),
        "records": records,
    }
    out = OUT_DIR / "ftask-order-observations.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in records:
        print("{:<34} {:<8} same_as_baseline={}".format(
            r["variant"], r["outcome"], r.get("same_as_baseline")))
    print("all_same:", report["all_same"])
    if not report["all_same"]:
        print("baseline pipe_ops:", json.dumps(records[0]["pipe_ops"], ensure_ascii=False))
        for r in records[1:]:
            print(r["variant"], "pipe_ops:", json.dumps(r.get("pipe_ops"), ensure_ascii=False))
    print("\nwritten:", out)


if __name__ == "__main__":
    main()
