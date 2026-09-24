"""Execute only the separately authorized three-cell heavy-suffix declaration."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import heavy_suffix_e0 as runner

HERE = "src/q1_benchmarks/heavy_suffix_more_e0.py"
MANIFEST = "src/q1_benchmarks/heavy_suffix_more_batch.json"
RESULT_ROOT = ROOT / "results/a/q1-heavy-suffix-more-20260925"


def declaration():
    cfg = runner.h.read(ROOT / MANIFEST)
    assert cfg["solver_commit"] == runner.SOLVER
    assert cfg["entrypoint"] == runner.ENTRY
    assert cfg["cells"] == [["003", 5], ["056", 5], ["068", 5]]
    assert cfg["parameters"] == {"dominant_percent": 80, "max_rounds": 64, "max_sinks": 64}
    assert cfg["workers"] == 1 and cfg["retries"] == 0
    assert cfg["maximum_calls"] == {"solver": 3, "E0": 3, "E1": 0, "E2": 0}
    assert cfg["timeouts_seconds"] == {"solver": 30, "E0": 90, "batch": 420}
    return cfg


def run(batch):
    cfg = declaration()
    return runner.run(batch, cells=cfg["cells"], batch_seconds=cfg["timeouts_seconds"]["batch"],
                      run_source=HERE, extra_sources=(HERE, MANIFEST),
                      declaration={"path": MANIFEST, "sha256": runner.h.sha(ROOT / MANIFEST), "content": cfg},
                      coordination=cfg["coordination"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "export"))
    parser.add_argument("run_id")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.run_id):
        parser.error("valid run_id required")
    batch = RESULT_ROOT / args.run_id
    raise SystemExit(run(batch) if args.action == "run" else runner.export(batch))
