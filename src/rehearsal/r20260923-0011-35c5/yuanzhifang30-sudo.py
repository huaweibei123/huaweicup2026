"""Deterministic OLS baseline for the rehearsal's synthetic distance data."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN_ID = "r20260923-0011-35c5"
ACTOR = "yuanzhifang30-sudo"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fit(rows: list[dict[str, str]]) -> dict:
    if len(rows) < 2:
        raise ValueError("At least two observations are required")
    x = [float(row["time_s"]) for row in rows]
    y = [float(row["distance_m"]) for row in rows]
    if not all(math.isfinite(v) for v in x + y):
        raise ValueError("Observations must be finite")
    n = len(rows)
    mx, my = math.fsum(x) / n, math.fsum(y) / n
    sxx = math.fsum((v - mx) ** 2 for v in x)
    if sxx == 0:
        raise ValueError("Slope is not identifiable when time is constant")
    slope = math.fsum((a - mx) * (b - my) for a, b in zip(x, y)) / sxx
    intercept = my - slope * mx
    predictions = [slope * a + intercept for a in x]
    residuals = [b - pred for b, pred in zip(y, predictions)]
    return {
        "n": n,
        "slope_m_per_s": slope,
        "intercept_m": intercept,
        "mse_m2": math.fsum(r * r for r in residuals) / n,
        "max_abs_residual_m": max(abs(r) for r in residuals),
        "rows": [
            {"sample_id": row["sample_id"], "time_s": a, "distance_m": b,
             "prediction_m": pred, "residual_m": residual}
            for row, a, b, pred, residual in zip(rows, x, y, predictions, residuals)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="tests/rehearsal/observations.csv")
    parser.add_argument("--output", default=f"results/rehearsal/{RUN_ID}/{ACTOR}/result.json")
    args = parser.parse_args()
    source = ROOT / args.input
    output = ROOT / args.output
    with source.open(encoding="utf-8", newline="") as stream:
        metrics = fit(list(csv.DictReader(stream)))
    script = Path(__file__).resolve()
    script_relative = script.relative_to(ROOT).as_posix()
    code_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()
    script_changes = subprocess.check_output(
        ["git", "status", "--porcelain", "--", script_relative],
        cwd=ROOT, text=True, encoding="utf-8"
    ).strip()
    if script_changes:
        raise RuntimeError("Commit the script before generating published results")
    result = {
        "run_id": RUN_ID, "actor": ACTOR,
        "data_kind": "synthetic, noiseless rehearsal data; not competition observations",
        "algorithm": "ordinary least squares with intercept; centered sums",
        "parameters": {"fit_intercept": True}, "seed": None,
        "input": {"path": source.relative_to(ROOT).as_posix(), "sha256": sha256(source),
                  "units": {"time_s": "s", "distance_m": "m"},
                  "source": "repository rehearsal fixture, manually constructed",
                  "split": "all five rows fitted; in-sample recovery check, no holdout"},
        "code": {"commit": code_commit, "script": script_relative,
                 "script_sha256": sha256(script), "script_clean": True},
        "environment": {"python": platform.python_version(),
                        "implementation": platform.python_implementation(),
                        "os": platform.system(), "os_version": platform.version(),
                        "dependencies_used": "Python standard library only",
                        "uv_lock_sha256": sha256(ROOT / "uv.lock")},
        "command": f"uv run python {script_relative} --input {args.input} --output {args.output}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **metrics,
        "limitations": ["Noiseless, in-sample recovery only; no claim of generalization",
                        "Does not validate Atlas signatures, task state, or browser consistency"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: metrics[key] for key in
                      ("n", "slope_m_per_s", "intercept_m", "mse_m2", "max_abs_residual_m")}))


if __name__ == "__main__":
    main()
