"""Compare existing v4 E0 records across core counts; never run a solver."""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from recompute_snapshot import ARCHIVE, FEED, FEED_SHA256, SOLVER, read_blob


def derive(repo: Path) -> dict:
    raw = read_blob(repo, ARCHIVE, FEED)
    if hashlib.sha256(raw).hexdigest() != FEED_SHA256:
        raise ValueError("fixed feed hash mismatch")
    records = json.loads(raw)["records"]
    cases = [f"{i:03d}" for i in range(1, 101)]
    expected = {(case, cores) for case in cases for cores in range(1, 6)}
    lookup = {(row["case_id"], row["cores"]): row for row in records}
    if len(records) != 500 or set(lookup) != expected:
        raise ValueError("incomplete or duplicate 100 by 5 matrix")
    for row in records:
        if row["status"] != "ok" or row["solver_commit"] != SOLVER:
            raise ValueError("unexpected source or failed observation")
        value = row["metrics"]["makespan_cycles"]
        if type(value) is not int or value <= 0:
            raise ValueError("positive integer makespan required")

    pairs, summaries = [], []
    for cores in (2, 3, 4):
        group = []
        for case in cases:
            before, after = lookup[case, cores], lookup[case, cores + 1]
            for field in ("graph_sha256", "config_sha256", "official_sha256"):
                if before["identity"][field] != after["identity"][field]:
                    raise ValueError(f"incompatible paired identity: {case}/{field}")
            a = before["metrics"]["makespan_cycles"]
            b = after["metrics"]["makespan_cycles"]
            change = Fraction(b - a, a)
            group.append({
                "case_id": case,
                "from_cores": cores,
                "to_cores": cores + 1,
                "before_makespan_cycles": a,
                "after_makespan_cycles": b,
                "delta_cycles": b - a,
                "change_fraction": str(change),
                "change_percent": float(100 * change),
                "outcome": "improved" if b < a else "worsened" if b > a else "unchanged",
            })
        counts = {name: sum(p["outcome"] == name for p in group)
                  for name in ("improved", "unchanged", "worsened")}
        worsened = [p for p in group if p["outcome"] == "worsened"]
        worst = max(worsened, key=lambda p: Fraction(p["change_fraction"]), default=None)
        if sum(counts.values()) != 100:
            raise AssertionError("paired classifications do not cover all cases")
        summaries.append({
            "from_cores": cores,
            "to_cores": cores + 1,
            "n": 100,
            **counts,
            "worst_worsened": worst,
            "worsened_cases": [p["case_id"] for p in worsened],
        })
        pairs.extend(group)

    return {
        "schema": "p1-v4-core-pairs-v1",
        "archive_commit": ARCHIVE,
        "solver_commit": SOLVER,
        "feed_path": FEED,
        "feed_sha256": FEED_SHA256,
        "definition": "Same-case v4 Makespan at K and K+1, K=2,3,4. Positive change means slower. Percentage denominator is the lower-core Makespan, not the single-core baseline.",
        "scope": "300 derived pairs from the existing 500-cell archive; not 300 additional experiments. No causal trace attribution or global-optimum claim.",
        "summaries": summaries,
        "pairs": pairs,
        "new_calls": {"solver": 0, "Task_compile": 0, "E0": 0, "E1": 0, "E2": 0},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("choose a new output path; do not overwrite archived results")
    result = derive(Path(__file__).resolve().parents[3])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"pairs": len(result["pairs"]), "summaries": result["summaries"],
                      "new_calls": result["new_calls"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
