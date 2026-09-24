"""Two frozen overload probes; require explicit root review and resource release."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import finite_probe as runner

MANIFEST = "src/q1_benchmarks/overload_probe_batch.json"
RESULT_ROOT = ROOT / "results/a/q1-overload-probe-20260925"
GATE = ROOT / "output/q1-overload-probe-20260925/preparation/state.json"


def declaration():
    cfg = runner.h.read(ROOT / MANIFEST)
    assert cfg["solver_commit"] == "3c6e41b938c764d207de45584fb526c64f4eb845"
    assert cfg["cells"] == [["054", 5], ["050", 5]]
    assert cfg["parameters"] == {"max_rounds": 64, "max_sinks": 64}
    assert cfg["solver_extra_argv"] == []  # CLI uses the frozen 64/64 defaults.
    assert cfg["workers"] == 1 and cfg["retries"] == 0
    assert cfg["maximum_calls"] == {"solver": 2, "E0": 2, "E1": 0, "E2": 0}
    assert cfg["timeouts_seconds"] == {"solver": 30, "E0": 90, "batch": 300}
    return cfg


def run(batch):
    gate = runner.h.read(GATE)
    if gate.get("status") != "authorized" or not gate.get("authorization_message"):
        raise RuntimeError("WAIT_ROOT_REVIEW_AND_P2_RELEASE: root EXECUTE required")
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
