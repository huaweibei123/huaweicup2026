"""Remaining declared overload activations; wait for root and P3 resource release."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import finite_probe as runner

MANIFEST = "src/q1_benchmarks/overload_activation_batch.json"
RESULT_ROOT = ROOT / "results/a/q1-overload-activation-20260925"
GATE = ROOT / "output/q1-overload-activation-20260925/preparation/state.json"
CASES = ["003", "009", "031", "032", "035", "040", "043", "049", "053", "056", "057", "066", "068", "077", "087", "088"]


def declaration():
    cfg = runner.h.read(ROOT / MANIFEST)
    assert cfg["solver_commit"] == "3c6e41b938c764d207de45584fb526c64f4eb845"
    assert cfg["cells"] == [[case, 5] for case in CASES]
    assert cfg["parameters"] == {"max_rounds": 64, "max_sinks": 64}
    assert cfg["solver_extra_argv"] == []
    assert cfg["workers"] == 1 and cfg["retries"] == 0
    assert cfg["maximum_calls"] == {"solver": 16, "E0": 16, "E1": 0, "E2": 0}
    assert cfg["timeouts_seconds"] == {"solver": 30, "E0": 90, "batch": 900}
    return cfg


def run(batch):
    gate = runner.h.read(GATE)
    if gate.get("status") != "authorized" or not gate.get("authorization_message"):
        raise RuntimeError("WAIT_ROOT_REVIEW_AND_P3_RELEASE: root EXECUTE required")
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
