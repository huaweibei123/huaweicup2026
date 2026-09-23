"""Add the F-PLAN-005 quotient-cycle counterexample as a structural-invalid fixture.

Source of the construction: captain UNBLOCK-001 (Issue #14). Re-verified locally
against the frozen official code; nothing here modifies the official sources.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "adversarial"
OUT = ROOT / "results" / "a" / "form" / "r1-20260923-farmeruncle123"

FIXTURES.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "data" / "raw" / "a" / "official" / "code"))
from evaluation_validation import validate_graph  # noqa: E402
from stub_multicore_cut_and_schedule import derive_multicore_plan  # noqa: E402

# Original graph 1 -> 2 -> 3 is a DAG; ops 1 and 3 share subgraph 0, op 2 alone in 1.
GRAPH = {
    "ops": [{"id": i, "op": "VADD", "pipe": "PIPE_V", "cycles": 1} for i in (1, 2, 3)],
    "tensors": [],
    "edges": [{"source": 1, "target": 2}, {"source": 2, "target": 3}],
}
PLAN = {"node_to_subgraph": {"1": 0, "2": 1, "3": 0}, "core_schedules": [[0], [1]]}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main():
    observations = {}
    try:
        validate_graph(GRAPH)
        observations["validate_graph"] = "pass"
    except Exception as exc:  # noqa: BLE001
        observations["validate_graph"] = "{}: {}".format(type(exc).__name__, exc)
    try:
        derive_multicore_plan(GRAPH, PLAN)
        observations["derive_multicore_plan"] = "accepted"
    except Exception as exc:  # noqa: BLE001
        observations["derive_multicore_plan"] = "{}: {}".format(type(exc).__name__, exc)

    fixture = {
        "fixture_id": "fplan-005-quotient-cycle",
        "rule_id": "F-PLAN-005",
        "category": "structurally invalid plan (rejected at plan level, never evaluated)",
        "seed": None,
        "deterministic": True,
        "graph": GRAPH,
        "plan": PLAN,
        "expected": {
            "validate_graph": "pass (original graph is a DAG)",
            "derive_multicore_plan": "reject: contracted subgraph graph contains a cycle",
        },
        "observed": observations,
        "why_it_matters": (
            "Contraction of COPY nodes preserves the DAG; the cycle comes from the second "
            "step - grouping ops into subgraphs by node_to_subgraph. Merging non-contiguous "
            "ops (1 and 3) can make the quotient graph cyclic even when the input is acyclic."
        ),
        "graph_sha256": hashlib.sha256(canonical(GRAPH).encode("utf-8")).hexdigest(),
        "plan_sha256": hashlib.sha256(canonical(PLAN).encode("utf-8")).hexdigest(),
    }
    path = FIXTURES / "fplan-005-quotient-cycle.json"
    path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "run_id": "r1-20260923-farmeruncle123",
        "fixture": str(path.relative_to(ROOT)),
        "official_code_hash": "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0",
        "note": "Rejection sample only. No E0 call, no score, no legality claim beyond the observed reject.",
        **observations,
    }
    (OUT / "fplan-005-observation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
