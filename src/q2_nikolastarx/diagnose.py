"""Read saved P2 outputs; report observed tails, never infer causal wait types."""
import gzip
import json
import sys
from pathlib import Path


def main():
    root = Path(sys.argv[1])
    labels = ("002-M1", "002-critical", "002-earliest_start",
              "044-M1", "044-earliest_start", "044-M2")
    results = {name: json.loads(gzip.decompress((root / name / "result.json.gz").read_bytes()))
               for name in labels}
    observed = {}
    for name, result in results.items():
        core_rows = []
        for core in result["per_core_timeline"]:
            pipes = {}
            for op in core["ops"]:
                record = pipes.setdefault(op["pipe"], {"duration_sum": 0, "last_end": 0, "count": 0})
                record["duration_sum"] += op["duration"]
                record["last_end"] = max(record["last_end"], op["end"])
                record["count"] += 1
            end = max(record["last_end"] for record in pipes.values())
            core_rows.append({"core": core["core_id"], "pipes": pipes,
                              "tail_after_last_M": end - pipes["PIPE_M"]["last_end"]})
        observed[name] = {"makespan": result["makespan"], "cores": core_rows}
    sameness = []
    for a, b in zip(results["002-critical"]["per_core_timeline"],
                    results["002-earliest_start"]["per_core_timeline"]):
        def m_events(core):
            return [(o["op_id"], o["start"], o["end"]) for o in core["ops"] if o["pipe"] == "PIPE_M"]
        sameness.append({"core": a["core_id"], "M_events_equal": m_events(a) == m_events(b)})
    output = {"new_evaluator_calls": 0, "observed": observed,
              "002_critical_vs_earliest_start_M_exact": sameness,
              "limits": "duration sums are observed elapsed occupancy, including shared-bandwidth effects; tails are intervals, not a causal decomposition or counterfactual."}
    (root / "diagnostics.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
