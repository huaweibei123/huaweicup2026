"""Finite shared-input probes; run only after parent releases the resource window."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import finite_probe as runner

MANIFEST = "src/q1_benchmarks/shared_input_probe_batch.json"
RESULT_ROOT = ROOT / "results/a/q1-shared-input-probe-20260925"
GATE = ROOT / "output/q1-shared-input-probe-20260925/preparation/state.json"


def declaration():
    cfg = runner.h.read(ROOT / MANIFEST)
    assert cfg["solver_commit"] == "288dd520caa5c7baaa1413e4021eb2d4221b6e66"
    assert cfg["cells"] == [["044", 5], ["046", 5], ["090", 5]]
    assert cfg["parameters"] == {"input_budget_bytes": 262144, "activation_bytes": 524288, "max_phases": 32}
    assert cfg["workers"] == 1 and cfg["retries"] == 0
    assert cfg["maximum_calls"] == {"solver": 3, "E0": 3, "E1": 0, "E2": 0}
    assert cfg["timeouts_seconds"] == {"solver": 30, "E0": 90, "batch": 420}
    return cfg


def run(batch):
    gate = runner.h.read(GATE)
    if gate.get("status") != "authorized" or not gate.get("authorization_message"):
        raise RuntimeError("wait-P2: root execute signal required before changing the execution gate")
    spec = declaration()
    assert gate["allowed_cells"] == spec["cells"]
    assert gate["solver_commit"] == spec["solver_commit"]
    spec["execution_authorization"] = gate
    return runner.run(batch, spec)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "export"))
    parser.add_argument("run_id")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.run_id):
        parser.error("valid run_id required")
    batch = RESULT_ROOT / args.run_id
    raise SystemExit(run(batch) if args.action == "run" else runner.export(batch))
