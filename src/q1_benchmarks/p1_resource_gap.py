"""Optimistic P1 compute-resource bounds for a fixed full-500 checkpoint.

This is a mathematical ceiling, not a candidate plan or an evaluator result.
It uses the invariant that every original non-COPY op appears once and each
core has one executor slot per Pipe in the frozen scene-A evaluator.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[2]
RUN = "20260925T1525Z-s6607-branch-full500"
BUNDLE = ROOT / "results/a/p1-branch-refine-full500-20260925" / RUN
AUDIT = ROOT / "results/a/p1-branch-refine-full500-20260925/independent-audit.json"
ZIP = ROOT / "data/raw/a/official-cases.zip"
CENSUS = ROOT / "results/a/p1-compute-resource-gap-20260926/r7-strict-census.original.json"
STRICT_R7 = ("044", "046", "067", "073", "083", "092")


def compute_bound(graph: dict, cores: int) -> tuple[int, dict[str, int]]:
    if type(cores) is not int or cores < 1:
        raise ValueError("cores must be a positive integer")
    work: Counter[str] = Counter()
    for op in graph["ops"]:
        if op["op"] in {"COPY_IN", "COPY_OUT"}:
            continue
        cycles = op["cycles"]
        if type(cycles) is not int or cycles < 0:
            raise ValueError("invalid compute cycles")
        work[op["pipe"]] += max(1, cycles)
    if not work:
        raise ValueError("no compute work")
    return max((total + cores - 1) // cores for total in work.values()), dict(work)


def main() -> None:
    audit = json.loads(AUDIT.read_text())
    census = json.loads(CENSUS.read_text())
    recognized = {row["case"] for row in census["rows"] if row["recognized"]}
    if recognized != set(STRICT_R7):
        raise ValueError("strict R7 census differs from the frozen six-case set")
    rows = {row["case"]: row for row in audit["rows"] if row["cores"] == 5}
    if len(rows) != 100:
        raise ValueError("expected exactly 100 K5 checkpoint rows")
    out = []
    with zipfile.ZipFile(ZIP) as archive:
        case_names = {
            Path(name).stem.removeprefix("case_"): name
            for name in archive.namelist()
            if Path(name).name.startswith("case_") and name.endswith(".json")
            and not Path(name).name.startswith("._")
        }
        if set(case_names) != set(rows):
            raise ValueError("case ZIP and checkpoint do not cover the same 100 IDs")
        for case in sorted(rows):
            graph = json.loads(archive.read(case_names[case]))
            lower, work = compute_bound(graph, 5)
            with gzip.open(BUNDLE / "baselines" / f"{case}-singlecore.json.gz", "rt") as stream:
                baseline = json.load(stream)["makespan"]
            observed = rows[case]["makespan"]
            if lower > observed:
                raise AssertionError(f"resource lower bound exceeds E0: {case}")
            current = baseline / observed
            out.append({
                "case": case,
                "baseline_cycles": baseline,
                "checkpoint_makespan_cycles": observed,
                "pipe_work_cycles": work,
                "compute_resource_lower_bound_cycles": lower,
                "checkpoint_speedup": current,
                "optimistic_speedup_ceiling": baseline / lower,
                "optimistic_mean_headroom": (baseline / lower - current) / 100,
            })
    mean = sum(row["checkpoint_speedup"] for row in out) / 100
    strict_headroom = sum(row["optimistic_mean_headroom"] for row in out
                          if row["case"] in STRICT_R7)
    target = 4.025907473836023 * 1.05
    result = {
        "scope": "compute-resource lower bound only; assumes exactly one of each original non-COPY op, 5 cores, one slot per Pipe",
        "source_sha256": {
            "case_zip": hashlib.sha256(ZIP.read_bytes()).hexdigest(),
            "checkpoint_audit": hashlib.sha256(AUDIT.read_bytes()).hexdigest(),
            "strict_r7_census": hashlib.sha256(CENSUS.read_bytes()).hexdigest(),
        },
        "frozen_checkpoint": RUN,
        "official_evaluator_calls": 0,
        "case_count": 100,
        "observed_k5_mean_speedup": mean,
        "five_percent_target_relative_to_v4": target,
        "five_percent_target_relative_to_checkpoint": mean * 1.05,
        "strict_r7_six_cases": list(STRICT_R7),
        "strict_r7_only_optimistic_mean_ceiling": mean + strict_headroom,
        "strict_r7_only_target_shortfall": target - mean - strict_headroom,
        "strict_r7_only_checkpoint_target_shortfall": mean * 1.05 - mean - strict_headroom,
        "rows": out,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
