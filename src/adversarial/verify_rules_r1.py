"""Round-1 first increment: exercise F-PLAN rules against the frozen official code.

Reads the official sources (read-only) and writes observations only into the
task's own results directory. Never evaluates "quality"; it records acceptance
and rejection behaviour of `derive_multicore_plan` on tiny synthetic graphs.

Usage:  python src/adversarial/verify_rules_r1.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "data/raw/a/official/code"
OUT_DIR = ROOT / "results/a/form/r1-20260923-farmeruncle123"

sys.path.insert(0, str(CODE))
import stub_multicore_cut_and_schedule as stub  # noqa: E402


def graph(ops, tensors, edges):
    return {"ops": ops, "tensors": tensors, "edges": [{"source": a, "target": b} for a, b in edges]}


# Minimal chain: t100(DDR) -> op1 COPY_IN -> t101(L1) -> op2 CONV -> t102(UB) -> op3 COPY_OUT -> t103(DDR)
CHAIN = graph(
    ops=[
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 3, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
    ],
    tensors=[
        {"id": 100, "pos": "DDR", "size": 64},
        {"id": 101, "pos": "L1", "size": 64},
        {"id": 102, "pos": "UB", "size": 64},
        {"id": 103, "pos": "DDR", "size": 64},
    ],
    edges=[(100, 1), (1, 101), (101, 2), (2, 102), (102, 3), (3, 103)],
)

# Straight DAG with two non-COPY ops in a chain: op2 -> op3 (via tensor 102).
DAG2 = graph(
    ops=[
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 4, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
    ],
    tensors=[
        {"id": 100, "pos": "DDR", "size": 8},
        {"id": 101, "pos": "L1", "size": 8},
        {"id": 102, "pos": "UB", "size": 8},
        {"id": 103, "pos": "UB", "size": 8},
        {"id": 104, "pos": "DDR", "size": 8},
    ],
    edges=[(100, 1), (1, 101), (101, 2), (2, 102), (102, 3), (3, 103), (103, 4), (4, 104)],
)

# Two non-COPY ops linked in both directions through contracted COPY nodes.
CYCLE = graph(
    ops=[
        {"id": 1, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 2, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 3, "op": "CONV", "pipe": "PIPE_M", "cycles": 4},
        {"id": 4, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
        {"id": 5, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
        {"id": 6, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 0},
        {"id": 7, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 0},
    ],
    tensors=[
        {"id": 100, "pos": "DDR", "size": 8},
        {"id": 101, "pos": "L1", "size": 8},
        {"id": 102, "pos": "UB", "size": 8},
        {"id": 103, "pos": "DDR", "size": 8},
        {"id": 104, "pos": "L1", "size": 8},
        {"id": 105, "pos": "DDR", "size": 8},
        {"id": 106, "pos": "L1", "size": 8},
    ],
    edges=[
        (100, 1), (1, 101), (101, 2), (2, 102),
        (102, 4), (4, 103), (103, 5), (5, 104), (104, 3),
        (3, 106), (106, 6), (6, 105), (105, 7), (7, 101),
    ],
)


def run(rule_id, note, g, plan):
    """Return an observation record for one probe."""
    try:
        view = stub.derive_multicore_plan(g, plan)
        return {"rule_id": rule_id, "note": note, "outcome": "accepted",
                "error": None,
                "observed": {"num_cores": view["num_cores"],
                             "subgraph_ids": view["subgraph_ids"],
                             "dependency_pairs": view["dependency_pairs"]}}
    except Exception as exc:  # official code raises its own error types
        return {"rule_id": rule_id, "note": note, "outcome": "rejected",
                "error": "{}: {}".format(type(exc).__name__, exc), "observed": None}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    probes = [
        ("F-PLAN-000", "baseline: single non-COPY op, one core",
         CHAIN, {"node_to_subgraph": {"2": 0}, "core_schedules": [[0]]}),
        ("F-PLAN-001", "plan carries an extra field",
         CHAIN, {"node_to_subgraph": {"2": 0}, "core_schedules": [[0]], "confidence": 0.9}),
        ("F-PLAN-001", "plan misses core_schedules",
         CHAIN, {"node_to_subgraph": {"2": 0}}),
        ("F-PLAN-002", "non-COPY op not covered",
         CHAIN, {"node_to_subgraph": {}, "core_schedules": [[]]}),
        ("F-PLAN-002", "COPY_IN/COPY_OUT must not be assigned",
         CHAIN, {"node_to_subgraph": {"1": 1, "2": 0, "3": 2}, "core_schedules": [[0], [1], [2]]}),
        ("F-PLAN-003", "negative subgraph id",
         CHAIN, {"node_to_subgraph": {"2": -1}, "core_schedules": [[-1]]}),
        ("F-PLAN-003", "duplicate integer keys via '2' and 2",
         CHAIN, {"node_to_subgraph": {"2": 0, "02": 0}, "core_schedules": [[0]]}),
        ("F-PLAN-004", "empty core_schedules",
         CHAIN, {"node_to_subgraph": {"2": 0}, "core_schedules": []}),
        ("F-PLAN-004", "a subgraph scheduled twice",
         DAG2, {"node_to_subgraph": {"2": 0, "3": 1}, "core_schedules": [[0, 1], [1]]}),
        ("F-PLAN-004", "a subgraph never scheduled",
         DAG2, {"node_to_subgraph": {"2": 0, "3": 1}, "core_schedules": [[0], []]}),
        ("F-PLAN-004", "empty core is allowed (core with no subgraph)",
         CHAIN, {"node_to_subgraph": {"2": 0}, "core_schedules": [[0], []]}),
        ("F-PLAN-005", "attempt contracted-subgraph cycle (raw graph already cyclic)",
         CYCLE, {"node_to_subgraph": {"2": 0, "3": 1}, "core_schedules": [[0], [1]]}),
        ("F-PLAN-006", "same-core dependency order violated (2->3 but 3 scheduled first)",
         DAG2, {"node_to_subgraph": {"2": 0, "3": 1}, "core_schedules": [[1, 0]]}),
        ("F-PLAN-006", "same-core dependency order satisfied (control)",
         DAG2, {"node_to_subgraph": {"2": 0, "3": 1}, "core_schedules": [[0, 1]]}),
    ]
    records = [run(rid, note, g, p) for rid, note, g, p in probes]
    report = {
        "run_id": "r1-20260923-farmeruncle123",
        "scope": "F-PLAN only; derive_multicore_plan acceptance/rejection probes",
        "official_code_hash": "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0",
        "code_file_sha256": {
            "code/stub_multicore_cut_and_schedule.py":
                "0a3a3b79b5173b466fc05fc8d33b72d11d90b4df78995435853d91c632a35892",
            "code/evaluation_validation.py":
                "103206b8c5c25e37de50cc3193de3989d7c1e01d4a11cc5f509dedd8f9be9a64",
        },
        "note": "E0 oracle not run; no quality claim. Observations are accept/reject only.",
        "probes": records,
    }
    out = OUT_DIR / "fplan-observations.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in records:
        print("{:<12} {:<12} {}".format(
            r["rule_id"], r["outcome"], (r["error"] or json.dumps(r["observed"], ensure_ascii=False))))
    print("\nwritten:", out)


if __name__ == "__main__":
    main()
