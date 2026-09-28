#!/usr/bin/env python3
"""Fit the rehearsal's synthetic straight line and record reproducible evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
import sys
from pathlib import Path


RUN_ID = "r20260923-0011-35c5"
ACTOR = "lyx0217"
SCRIPT_RELATIVE_PATH = Path("src/rehearsal") / RUN_ID / f"{ACTOR}.py"
INPUT_RELATIVE_PATH = Path("tests/rehearsal/observations.csv")
OUTPUT_RELATIVE_PATH = Path("results/rehearsal") / RUN_ID / ACTOR / "result.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def load_observations(path: Path) -> list[dict[str, float | str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        expected = ["sample_id", "time_s", "distance_m"]
        if reader.fieldnames != expected:
            raise ValueError(f"expected columns {expected}, found {reader.fieldnames}")
        rows = [
            {
                "sample_id": row["sample_id"],
                "time_s": float(row["time_s"]),
                "distance_m": float(row["distance_m"]),
            }
            for row in reader
        ]
    if len(rows) < 2:
        raise ValueError("at least two observations are required")
    return rows


def fit_line(rows: list[dict[str, float | str]]) -> tuple[float, float]:
    times = [float(row["time_s"]) for row in rows]
    distances = [float(row["distance_m"]) for row in rows]
    mean_time = sum(times) / len(times)
    mean_distance = sum(distances) / len(distances)
    denominator = sum((time_s - mean_time) ** 2 for time_s in times)
    if denominator == 0:
        raise ValueError("time_s must contain at least two distinct values")
    numerator = sum(
        (time_s - mean_time) * (distance_m - mean_distance)
        for time_s, distance_m in zip(times, distances, strict=True)
    )
    slope = numerator / denominator
    intercept = mean_distance - slope * mean_time
    return slope, intercept


def build_result(repo_root: Path, input_path: Path) -> dict[str, object]:
    rows = load_observations(input_path)
    slope, intercept = fit_line(rows)
    predictions = []
    squared_error = 0.0
    max_abs_residual = 0.0

    for row in rows:
        time_s = float(row["time_s"])
        distance_m = float(row["distance_m"])
        prediction_m = slope * time_s + intercept
        residual_m = distance_m - prediction_m
        squared_error += residual_m**2
        max_abs_residual = max(max_abs_residual, abs(residual_m))
        predictions.append(
            {
                "sample_id": row["sample_id"],
                "time_s": time_s,
                "distance_m": distance_m,
                "prediction_m": prediction_m,
                "residual_m": residual_m,
            }
        )

    mse_m2 = squared_error / len(rows)
    values = [slope, intercept, mse_m2, max_abs_residual]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("fit produced a non-finite result")

    script_path = repo_root / SCRIPT_RELATIVE_PATH
    lock_path = repo_root / "uv.lock"
    return {
        "schema_version": 1,
        "run_id": RUN_ID,
        "actor": ACTOR,
        "scope": "Synthetic noiseless rehearsal data; not a contest result.",
        "algorithm": {
            "name": "ordinary_least_squares_closed_form",
            "deterministic": True,
            "seed": None,
            "description": "Fits distance_m = slope * time_s + intercept from the CSV values.",
        },
        "input": {
            "path": INPUT_RELATIVE_PATH.as_posix(),
            "sha256": sha256_file(input_path),
            "n": len(rows),
            "columns": {
                "time_s": "seconds",
                "distance_m": "metres",
            },
        },
        "code": {
            "path": SCRIPT_RELATIVE_PATH.as_posix(),
            "sha256": sha256_file(script_path),
            "commit": git_head(repo_root),
        },
        "execution": {
            "command": f"uv run python {SCRIPT_RELATIVE_PATH.as_posix()}",
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "standard_library_only": True,
            "uv_lock_sha256": sha256_file(lock_path),
        },
        "fit": {
            "slope_m_per_s": slope,
            "intercept_m": intercept,
            "mse_m2": mse_m2,
            "max_abs_residual_m": max_abs_residual,
        },
        "predictions": predictions,
    }


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=repo_root / INPUT_RELATIVE_PATH)
    parser.add_argument("--output", type=Path, default=repo_root / OUTPUT_RELATIVE_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[3]
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    result = build_result(repo_root, input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output_path), "fit": result["fit"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
