"""Round-1 F-TASK probes: shared tensors, multi-consumer, COPY boundary, empty core.

Reads the frozen official code (read-only), writes observations only into the
task's own results directory. No E0 scoring, no quality claim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "data" / "raw" / "a" / "official" / "code"
OUT_DIR = ROOT / "results" / "a" / "form" / "r1-20260923-farmeruncle123"

sys.dont_write_bytecode = True
sys.path.insert(0, str(CODE))
import multicore_cut_evaluate_problem_1 as p1  # noqa: E402

BANDWIDTH = 60  # from data/config.txt [bandwidth] bandwidth 60
# from data/config.txt [capacity]; the official code treats capacity as a
# per-position mapping (step2 does `{T: {} for T in capacity}`), not a scalar.
CAPACITY = {"L1": 524288, "UB": 131072}

# op2 produces tensor 102; tensor 102 is shared by op3 and op5.
GRAPH = {
    "ops": [
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 4, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
        {"id": 5, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
    ],
    "tensors": [
        {"id": 100, "pos": "DDR", "size": 64},
        {"id": 101, "pos": "L1", "size": 64},
        {"id": 102, "pos": "UB", "size": 64},
        {"id": 103, "pos": "UB", "size": 64},
        {"id": 104, "pos": "DDR", "size": 64},
        {"id": 105, "pos": "UB", "size": 64},
    ],
    "edges": [
        {"source": 100, "target": 1}, {"source": 1, "target": 101},
        {"source": 101, "target": 2}, {"source": 2, "target": 102},
        {"source": 102, "target": 3}, {"source": 3, "target": 103},
        {"source": 103, "target": 4}, {"source": 4, "target": 104},
        {"source": 102, "target": 5}, {"source": 5, "target": 105},
    ],
}


def probe(name, plan, graph=None):
    graph = GRAPH if graph is None else graph
    try:
        tasks, cross_task_traffic, traffic, view = p1._build_scene_a_tasks(
            graph, plan, BANDWIDTH, CAPACITY)
        ddr_ids = {t["id"] for t in graph["tensors"] if t.get("pos") == "DDR"}
        per_task = {}
        for task_id in sorted(tasks):
            t = tasks[task_id]
            per_task[str(task_id)] = {
                "core_id": t.get("core_id"),
                "pred_tasks": sorted(t.get("pred_tasks", [])),
                "n_ops": len(t.get("op_by_id", {})),
                "generated_op_ids": sorted(
                    o for o in t.get("op_by_id", {}) if o > 5),
                "generated_tensor_ids": sorted(
                    x for x in t.get("tensor_by_id", {}) if x > 105),
                "pos_of_rewritten": {
                    str(x): t["tensor_by_id"][x].get("pos")
                    for x in sorted(t.get("tensor_by_id", {}))
                    if x in ddr_ids
                },
                "pipe_ops": {k: list(v) for k, v in sorted(t.get("pipe_ops", {}).items())},
                "generated_op_types": {
                    t["op_by_id"][o].get("op"): t["op_by_id"][o].get("op")
                    for o in sorted(t.get("op_by_id", {})) if o > 5
                },
                "n_generated_copy_out": sum(
                    1 for o in t.get("op_by_id", {})
                    if o > 5 and t["op_by_id"][o].get("op") == "COPY_OUT"),
                "n_generated_copy_in": sum(
                    1 for o in t.get("op_by_id", {})
                    if o > 5 and t["op_by_id"][o].get("op") == "COPY_IN"),
            }
        return {"probe": name, "outcome": "built", "error": None,
                "num_cores": view["num_cores"],
                "cross_task_traffic": cross_task_traffic,
                "traffic": traffic, "per_task": per_task}
    except Exception as exc:  # noqa: BLE001
        return {"probe": name, "outcome": "rejected",
                "error": "{}: {}".format(type(exc).__name__, exc),
                "num_cores": None, "cross_task_traffic": None,
                "traffic": None, "per_task": None}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    probes = [
        # shared tensor consumed by two ops in the SAME remote task
        ("shared-tensor, one remote consumer task",
         {"node_to_subgraph": {"2": 0, "3": 1, "5": 1}, "core_schedules": [[0], [1]]}),
        # shared tensor consumed by two ops in TWO DIFFERENT remote tasks
        ("shared-tensor, two remote consumer tasks",
         {"node_to_subgraph": {"2": 0, "3": 1, "5": 2}, "core_schedules": [[0], [1], [2]]}),
        # same as above but with an extra EMPTY core
        ("shared-tensor, two remote tasks + empty core",
         {"node_to_subgraph": {"2": 0, "3": 1, "5": 2},
          "core_schedules": [[0], [1], [2], []]}),
        # every non-COPY op on one core (no cross-task traffic expected)
        ("all ops in one subgraph",
         {"node_to_subgraph": {"2": 0, "3": 0, "5": 0}, "core_schedules": [[0]]}),
    ]
    records = [probe(n, p) for n, p in probes]

    # A tensor declared pos=DDR but produced by a non-COPY op: the Task-local
    # copy must be rewritten to UB (F-TASK-002).
    ddr_out = json.loads(json.dumps(GRAPH))
    for t in ddr_out["tensors"]:
        if t["id"] == 105:
            t["pos"] = "DDR"
    records.append(probe(
        "DDR-pos tensor produced by a non-COPY op (F-TASK-002)",
        {"node_to_subgraph": {"2": 0, "3": 0, "5": 0}, "core_schedules": [[0]]},
        graph=ddr_out))

    # F-TASK-003: all eligible consumers of tensor 102 live inside the same task,
    # but an ORIGINAL COPY_OUT op also consumes it. That alone must make 102 an
    # output boundary. Baseline (without the extra COPY_OUT) is the
    # "all ops in one subgraph" probe above, which has no extra COPY_OUT on 102.
    with_copy_out = json.loads(json.dumps(GRAPH))
    with_copy_out["ops"].append(
        {"id": 6, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0})
    with_copy_out["tensors"].append({"id": 106, "pos": "DDR", "size": 64})
    with_copy_out["edges"].extend([{"source": 102, "target": 6}, {"source": 6, "target": 106}])
    records.append(probe(
        "original COPY_OUT consumes the shared tensor (F-TASK-003)",
        {"node_to_subgraph": {"2": 0, "3": 0, "5": 0}, "core_schedules": [[0]]},
        graph=with_copy_out))
    report = {
        "run_id": "r1-20260923-farmeruncle123",
        "scope": "F-TASK probes on problem-1 _build_scene_a_tasks",
        "official_code_hash": "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0",
        "bandwidth": BANDWIDTH, "capacity": CAPACITY,
        "note": "Structure/boundary/traffic observations only. No E0, no makespan, no quality claim.",
        "probes": records,
    }
    out = OUT_DIR / "ftask-observations.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in records:
        if r["outcome"] == "built":
            print("{:<46} num_cores={} cross_task_traffic={}".format(
                r["probe"], r["num_cores"], r["cross_task_traffic"]))
            for tid, info in r["per_task"].items():
                print("    task {} core={} gen_ops={} gen_tensors={} rewritten_DDR={}".format(
                    tid, info["core_id"], info["generated_op_ids"],
                    info["generated_tensor_ids"], info["pos_of_rewritten"]))
            print("    traffic={}".format(json.dumps(r["traffic"], ensure_ascii=False)))
        else:
            print("{:<46} REJECTED {}".format(r["probe"], r["error"]))
    print("\nwritten:", out)


if __name__ == "__main__":
    main()
