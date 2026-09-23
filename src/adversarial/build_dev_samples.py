"""Build the development counterexample set (first batch) for a-r1-form-adversarial.

Each sample is an explicitly constructed, reproducible graph/plan pair with an
expected category and hash. Observations come from running the frozen official
code; nothing here is scored and no legality claim is made beyond what is
observed.

Writes:  tests/adversarial/dev-samples.jsonl
         results/a/form/r1-20260923-farmeruncle123/dev-samples-observations.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "data" / "raw" / "a" / "official" / "code"
FIX = ROOT / "tests" / "adversarial"
OUT = ROOT / "results" / "a" / "form" / "r1-20260923-farmeruncle123"

sys.dont_write_bytecode = True
sys.path.insert(0, str(CODE))
import multicore_cut_evaluate_problem_1 as p1  # noqa: E402
from stub_multicore_cut_and_schedule import derive_multicore_plan  # noqa: E402

BANDWIDTH = 60
CAPACITY = {"L1": 524288, "UB": 131072}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def h(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def chain_graph(shared_consumer_split="one_task", size=64):
    """COPY_IN -> CONV(2) -> shared tensor 102 -> CONV(3)/CONV(5); COPY_OUT 4."""
    return {
        "ops": [
            {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
            {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
            {"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
            {"id": 4, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
            {"id": 5, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        ],
        "tensors": [
            {"id": 100, "pos": "DDR", "size": size},
            {"id": 101, "pos": "L1", "size": size},
            {"id": 102, "pos": "UB", "size": size},
            {"id": 103, "pos": "UB", "size": size},
            {"id": 104, "pos": "DDR", "size": size},
            {"id": 105, "pos": "UB", "size": size},
        ],
        "edges": [
            {"source": 100, "target": 1}, {"source": 1, "target": 101},
            {"source": 101, "target": 2}, {"source": 2, "target": 102},
            {"source": 102, "target": 3}, {"source": 3, "target": 103},
            {"source": 103, "target": 4}, {"source": 4, "target": 104},
            {"source": 102, "target": 5}, {"source": 5, "target": 105},
        ],
    }


SAMPLES = [
    {
        "sample_id": "S-PLAN-QUOTIENT-CYCLE",
        "mechanism_group": "合法性/组合环",
        "category": "结构非法方案",
        "graph": {"ops": [{"id": i, "op": "VADD", "pipe": "PIPE_V", "cycles": 1} for i in (1, 2, 3)],
                  "tensors": [], "edges": [{"source": 1, "target": 2}, {"source": 2, "target": 3}]},
        "plan": {"node_to_subgraph": {"1": 0, "2": 1, "3": 0}, "core_schedules": [[0], [1]]},
        "expected": "derive_multicore_plan 拒绝：商图成环",
        "path": "derive",
    },
    {
        "sample_id": "S-PLAN-EMPTY-CORE",
        "mechanism_group": "合法性/组合环",
        "category": "边界：空核",
        "graph": chain_graph(),
        "plan": {"node_to_subgraph": {"2": 0, "3": 1, "5": 2}, "core_schedules": [[0], [1], [2], []]},
        "expected": "接受，num_cores=4（空核计入核数）",
        "path": "derive",
    },
    {
        "sample_id": "S-PLAN-ID-LEADING-ZERO",
        "mechanism_group": "合法性/组合环",
        "category": "对抗：ID 字面表示不唯一",
        "graph": chain_graph(),
        "plan": {"node_to_subgraph": {"2": 0, "02": 0}, "core_schedules": [[0]]},
        "expected": "拒绝：'02' 与 '2' 视为重复整数键",
        "path": "derive",
    },
    {
        "sample_id": "S-PLAN-COPY-IN-ASSIGNED",
        "mechanism_group": "合法性/组合环",
        "category": "对抗：把 COPY op 纳入划分",
        "graph": chain_graph(),
        "plan": {"node_to_subgraph": {"1": 1, "2": 0, "3": 2, "4": 3, "5": 3},
                 "core_schedules": [[0], [1], [2], [3]]},
        "expected": "拒绝：node_to_subgraph 必须恰好覆盖非 COPY op",
        "path": "derive",
    },
    {
        "sample_id": "S-TASK-SHARED-1REMOTE",
        "mechanism_group": "搬运统计",
        "category": "正例：共享 tensor / 多消费者",
        "graph": chain_graph(),
        "plan": {"node_to_subgraph": {"2": 0, "3": 1, "5": 1}, "core_schedules": [[0], [1]]},
        "expected": "cross_task_traffic=64（按远端消费 Task 数）",
        "path": "tasks",
    },
    {
        "sample_id": "S-TASK-SHARED-2REMOTE",
        "mechanism_group": "搬运统计",
        "category": "边界：同一 tensor 被两个远端 Task 消费",
        "graph": chain_graph(),
        "plan": {"node_to_subgraph": {"2": 0, "3": 1, "5": 2}, "core_schedules": [[0], [1], [2]]},
        "expected": "cross_task_traffic=128",
        "path": "tasks",
    },
    {
        "sample_id": "S-TASK-COPYOUT-BOUNDARY",
        "mechanism_group": "搬运统计",
        "category": "对抗：消费者全在本 Task 内但仍判输出边界",
        "graph": None,  # built below
        "plan": {"node_to_subgraph": {"2": 0, "3": 0, "5": 0}, "core_schedules": [[0]]},
        "expected": "因原图存在 COPY_OUT 消费者，插入额外的输出边界 COPY",
        "path": "tasks",
    },
    {
        "sample_id": "S-TASK-DDR-REWRITE",
        "mechanism_group": "搬运统计",
        "category": "对抗：声明 DDR 却由非 COPY op 产出",
        "graph": None,  # built below
        "plan": {"node_to_subgraph": {"2": 0, "3": 0, "5": 0}, "core_schedules": [[0]]},
        "expected": "Task 局部副本被封 pos 改写成 UB",
        "path": "tasks",
    },
    {
        "sample_id": "S-ROUND-SIZE-1",
        "mechanism_group": "取整/同刻事件",
        "category": "边界：极小 tensor，ceil 后不足 1 cycle",
        "graph": chain_graph(size=1),
        "plan": {"node_to_subgraph": {"2": 0, "3": 1, "5": 2}, "core_schedules": [[0], [1], [2]]},
        "expected": "边界 COPY cycles = max(1, ceil(1/60)) = 1",
        "path": "tasks",
    },
    {
        "sample_id": "S-ROUND-SIZE-0",
        "mechanism_group": "取整/同刻事件",
        "category": "边界：零尺寸 tensor（非正式输入域）",
        "graph": chain_graph(size=0),
        "plan": {"node_to_subgraph": {"2": 0, "3": 1, "5": 2}, "core_schedules": [[0], [1], [2]]},
        "expected": "边界 COPY cycles = max(1, 0) = 1；零尺寸属非正式输入域，单列",
        "path": "tasks",
    },
]


def build_special_graphs():
    with_copy_out = chain_graph()
    with_copy_out["ops"].append({"id": 6, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0})
    with_copy_out["tensors"].append({"id": 106, "pos": "DDR", "size": 64})
    with_copy_out["edges"].extend([{"source": 102, "target": 6}, {"source": 6, "target": 106}])
    ddr = chain_graph()
    for t in ddr["tensors"]:
        if t["id"] == 105:
            t["pos"] = "DDR"
    return with_copy_out, ddr


def boundary_copy_cycles(task):
    """Cycles of the COPY ops this Task generated (id > 5)."""
    out = {}
    for oid, op in sorted(task["op_by_id"].items()):
        if oid > 5 and op.get("op") in ("COPY_IN", "COPY_OUT"):
            out[str(oid)] = {"op": op["op"], "cycles": op.get("cycles")}
    return out


def main():
    FIX.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with_copy_out, ddr_graph = build_special_graphs()
    overrides = {"S-TASK-COPYOUT-BOUNDARY": with_copy_out, "S-TASK-DDR-REWRITE": ddr_graph}

    manifest, observations = [], []
    for s in SAMPLES:
        graph = overrides.get(s["sample_id"], s["graph"])
        rec = {"sample_id": s["sample_id"], "mechanism_group": s["mechanism_group"],
               "category": s["category"], "expected": s["expected"],
               "path": s["path"], "seed": None,
               "graph_sha256": h(graph), "plan_sha256": h(s["plan"])}
        try:
            if s["path"] == "derive":
                view = derive_multicore_plan(graph, s["plan"])
                rec["observed"] = {"outcome": "accepted", "num_cores": view["num_cores"],
                                   "subgraph_ids": view["subgraph_ids"],
                                   "dependency_pairs": view["dependency_pairs"]}
            else:
                tasks, cross, traffic, _v = p1._build_scene_a_tasks(
                    graph, s["plan"], BANDWIDTH, CAPACITY)
                rec["observed"] = {
                    "outcome": "accepted", "cross_task_traffic": cross,
                    "traffic": traffic,
                    "generated_copy_cycles": {str(tid): boundary_copy_cycles(t)
                                              for tid, t in sorted(tasks.items())},
                    "rewritten_pos": {
                        str(tid): {str(x): t["tensor_by_id"][x].get("pos")
                                   for x in sorted(t["tensor_by_id"])
                                   if x in {v["id"] for v in graph["tensors"] if v.get("pos") == "DDR"}}
                        for tid, t in sorted(tasks.items())},
                }
        except Exception as exc:  # noqa: BLE001
            rec["observed"] = {"outcome": "rejected",
                               "error": "{}: {}".format(type(exc).__name__, exc)}
        # full graph+plan kept in the obs record only when small, to stay reviewable
        rec["graph"] = graph
        rec["plan"] = s["plan"]
        manifest.append(rec)
        observations.append({"sample_id": s["sample_id"], **rec["observed"]})

    (FIX / "dev-samples.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in manifest) + "\n", encoding="utf-8")
    report = {
        "run_id": "r1-20260923-farmeruncle123",
        "bin": "first batch of development counterexamples",
        "official_code_hash": "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0",
        "bandwidth": BANDWIDTH, "capacity": CAPACITY, "seed": None,
        "covered_groups": ["合法性/组合环", "搬运统计", "取整/同刻事件（仅边界 COPY 取整）"],
        "not_covered_groups": ["Step3 固定 FIFO 与内存复用", "spill/容量临界",
                               "L2 同时 miss/FIFO"],
        "note": ("Not covered groups are listed as gaps, not as passes. "
                 "No E0 call, no makespan, no quality claim."),
        "observations": observations,
    }
    (OUT / "dev-samples-observations.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    for r in manifest:
        o = r["observed"]
        print("{:<28} {:<10} {}".format(r["sample_id"], o["outcome"],
                                        o.get("error") or ""))
    print("\nsamples:", len(manifest))
    print("manifest:", FIX / "dev-samples.jsonl")


if __name__ == "__main__":
    main()
