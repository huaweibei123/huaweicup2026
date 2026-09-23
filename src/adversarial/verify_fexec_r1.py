"""Round-1 F-EXEC probes: exercise validate_task_order and validate_execution.

Two kinds of observations are recorded separately:
  (a) unit-level: crafted view/tasks passed straight to the validators, which is
      NOT the official input domain;
  (b) reachability: whether the official entry (_build_scene_a_tasks) can produce
      the same situation.
No E0 call, no scoring, no quality claim.
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
from evaluation_validation import validate_execution, validate_task_order  # noqa: E402

BANDWIDTH = 60
CAPACITY = {"L1": 524288, "UB": 131072}


def _graph_factory():
    return {
        "ops": [
            {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
            {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
            {"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
            {"id": 4, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
            {"id": 5, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        ],
        "tensors": [
            {"id": 100, "pos": "DDR", "size": 64}, {"id": 101, "pos": "L1", "size": 64},
            {"id": 102, "pos": "UB", "size": 64}, {"id": 103, "pos": "UB", "size": 64},
            {"id": 104, "pos": "DDR", "size": 64}, {"id": 105, "pos": "UB", "size": 64},
        ],
        "edges": [
            {"source": 100, "target": 1}, {"source": 1, "target": 101},
            {"source": 101, "target": 2}, {"source": 2, "target": 102},
            {"source": 102, "target": 3}, {"source": 3, "target": 103},
            {"source": 103, "target": 4}, {"source": 4, "target": 104},
            {"source": 102, "target": 5}, {"source": 5, "target": 105},
        ],
    }


def run_validator(name, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return {"probe": name, "outcome": "accepted", "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"probe": name, "outcome": "rejected",
                "error": "{}: {}".format(type(exc).__name__, exc)}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []

    # ---- (a) unit-level: validate_task_order on crafted views -----------------
    records.append(run_validator(
        "unit: all cores have <=1 subgraph -> early return",
        validate_task_order,
        {"core_orders": {0: [0], 1: [1]}, "dependency_pairs": [[0, 1]], "subgraph_ids": [0, 1]}))

    records.append(run_validator(
        "unit: dependency cycle only (no core-order edge involved)",
        validate_task_order,
        {"core_orders": {0: [0, 1], 1: [2]},
         "dependency_pairs": [[0, 1], [1, 2], [2, 0]], "subgraph_ids": [0, 1, 2]}))

    # Dependencies are acyclic here; the cycle can only come from the core-order
    # edge that validate_task_order itself adds (order [1,0] vs dependency 0->1).
    records.append(run_validator(
        "unit: core-order edge alone induces the cycle",
        validate_task_order,
        {"core_orders": {0: [1, 0]}, "dependency_pairs": [[0, 1]], "subgraph_ids": [0, 1]}))

    # ---- (b) real tasks from the official entry ------------------------------
    plan = {"node_to_subgraph": {"2": 0, "3": 1, "5": 2},
            "core_schedules": [[0], [1], [2]]}
    tasks, _cross, _traffic, view = p1._build_scene_a_tasks(
        _graph_factory(), plan, BANDWIDTH, CAPACITY)
    tasks_by_core = {t["core_id"]: t for t in tasks.values()}

    records.append(run_validator(
        "real tasks: cross_links empty -> early return",
        validate_execution, tasks_by_core, []))
    records.append(run_validator(
        "real tasks: validate_task_order on the real view",
        validate_task_order, view))

    # A plausible cross-core link: from a generated COPY_OUT op on one task to a
    # generated COPY_IN op on another. Op ids are read from the real output.
    gen = {}
    for core, t in tasks_by_core.items():
        gen[core] = {"ops": sorted(o for o in t["op_by_id"] if o > 5),
                     "pipe_ops": {k: list(v) for k, v in t["pipe_ops"].items()}}
    records.append({"probe": "real tasks: generated ids and pipes (context)",
                    "outcome": "observed", "error": None, "detail": gen})

    # Build one cross-core link between two tasks and check both directions.
    cores = sorted(tasks_by_core)
    if len(cores) >= 2:
        a, b = cores[0], cores[1]
        out_a = next((o for o in gen[a]["ops"]
                      if tasks_by_core[a]["op_by_id"][o].get("op") == "COPY_OUT"), None)
        in_b = next((o for o in gen[b]["ops"]
                     if tasks_by_core[b]["op_by_id"][o].get("op") == "COPY_IN"), None)
        if out_a is not None and in_b is not None:
            fwd = [{"source_core": a, "source_copy_out_id": out_a,
                    "target_core": b, "target_copy_in_id": in_b}]
            rev = [{"source_core": b, "source_copy_out_id": in_b,
                    "target_core": a, "target_copy_in_id": out_a}]
            records.append(dict(run_validator(
                "real tasks: forward cross-core COPY link", validate_execution,
                tasks_by_core, fwd), link=fwd))
            records.append(dict(run_validator(
                "real tasks: reversed link (intentional misuse of ids)",
                validate_execution, tasks_by_core, rev), link=rev))

            # Both directions at once: (a->b) and (b->a) must form a cycle in the
            # global (core, op) graph.
            out_b = next((o for o in gen[b]["ops"]
                          if tasks_by_core[b]["op_by_id"][o].get("op") == "COPY_OUT"), None)
            in_a = next((o for o in gen[a]["ops"]
                         if tasks_by_core[a]["op_by_id"][o].get("op") == "COPY_IN"), None)
            if out_b is not None and in_a is not None:
                both = fwd + [{"source_core": b, "source_copy_out_id": out_b,
                               "target_core": a, "target_copy_in_id": in_a}]
                records.append(dict(run_validator(
                    "real tasks: two opposite cross-core links (cycle)",
                    validate_execution, tasks_by_core, both), link=both))
            else:
                records.append({"probe": "real tasks: two opposite cross-core links",
                                "outcome": "skipped",
                                "error": "missing generated COPY_OUT on b or COPY_IN on a"})
        else:
            records.append({"probe": "real tasks: cross-core link", "outcome": "skipped",
                            "error": "no generated COPY_OUT/COPY_IN pair found",
                            "detail": gen})

    report = {
        "run_id": "r1-20260923-farmeruncle123",
        "scope": "F-EXEC validators; unit-level probes labelled as non-official input domain",
        "official_code_hash": "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0",
        "note": ("Unit-level probes feed crafted views straight to the validators. "
                 "Reachability from the official entry is reported separately and is "
                 "not claimed where not tested."),
        "records": records,
    }
    out = OUT_DIR / "fexec-observations.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in records:
        print("{:<62} {:<9} {}".format(r["probe"], r["outcome"], r["error"] or ""))
    print("\nwritten:", out)


if __name__ == "__main__":
    main()
