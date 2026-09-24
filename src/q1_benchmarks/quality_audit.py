"""Compare saved E0 rows with static lower bounds without running a solver."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("comparison", type=Path)
    p.add_argument("bounds", type=Path)
    p.add_argument("--feed", type=Path, action="append", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    sources = {}

    def read(path):
        raw = path.read_bytes()
        sources[path.as_posix()] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    rows = read(args.comparison)
    bounds = {Path(x["input_member"]).stem.removeprefix("case_"): x
              for x in read(args.bounds)["cases"]}
    attempts = {}
    for path in args.feed:
        for item in read(path)["records"]:
            key = item["attempt_id"]
            if key in attempts:
                raise ValueError("Repeated attempt; supply only its selected revision")
            attempts[key] = item
    result = []
    for row in rows:
        if row["status"] != "ok":
            continue
        record = attempts[row["attempt_id"]]
        bound_case = bounds[row["case"]]
        assert record["identity"]["graph_sha256"] == bound_case["input_sha256"]
        assert record["metrics"]["makespan_cycles"] == row["makespan_cycles"]
        assert record["case_id"] == row["case"] and record["cores"] == row["cores"]
        lower = next(x["lower_bound_cycles"] for x in bound_case["bounds"]
                     if x["cores"] == row["cores"])
        upper = row["makespan_cycles"]
        if not 0 < lower <= upper:
            raise ValueError(f"Bound contradiction: {row['case']}, {lower}, {upper}")
        result.append({"case": row["case"], "cores": row["cores"],
                       "attempt_id": row["attempt_id"], "makespan_cycles": upper,
                       "lower_bound_cycles": lower,
                       "relative_optimality_gap_upper_bound": upper / lower - 1})
    walls = sorted(r["solver_wall_seconds"] for r in rows if r["status"] == "ok")
    report = {
        "scope": "Derived evidence, not a new evaluation or proof-system certification. "
                 "U/L-1 bounds the unknown relative gap only under the static-bound assumptions; "
                 "a large value does not prove achievable improvement.",
        "sources_sha256": sources, "new_solver_or_evaluator_calls": 0,
        "successful_cases": len(result), "bound_violations": 0,
        "gap_threshold_counts": {str(t): sum(r["relative_optimality_gap_upper_bound"] <= t
                                            for r in result) for t in [.01, .02, .05, .1, .2]},
        "observed_solver_wall_seconds": {"median": statistics.median(walls),
                                         "p95_nearest_rank": walls[(95 * len(walls) + 99) // 100 - 1],
                                         "max": max(walls)},
        "timing_scope": "Observed per-case process wall; shared machine, OS cache not flushed; "
                        "not repeat-latency distribution or a controlled speedup comparison.",
        "cases": sorted(result, key=lambda r: (-r["relative_optimality_gap_upper_bound"], r["case"]))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
