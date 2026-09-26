"""Static Stage E-4 target upper bound: eight fixed plans, zero scoring calls.

Only the eight incomplete cases' existing plans are inspected. No candidate is
constructed, no official Task is compiled and no simulator is invoked.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "results/a/q1-yuanzhifang/stage-e-4-20260925"
EXPECTED_MISSING = {"014", "041", "058", "062", "072", "076", "079", "091"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def artifact(ref):
    path = ROOT / ref["path"]
    require(digest(path.read_bytes()) == ref["sha256"], f"Changed artifact: {path.name}")
    return read(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphs", type=Path, required=True)
    args = parser.parse_args()
    start = time.perf_counter()
    protocol = read(BASE / "run/protocol.json")
    index = read(BASE / "evidence-index.json")
    require(digest((BASE / "evidence-index.json").read_bytes()) == protocol["evidence_index"]["sha256"], "Changed index")
    for path, expected in protocol["source_sha256"].items():
        require(digest((ROOT / path).read_bytes()) == expected, "Changed solver source")
    for path, expected in protocol["official_source_sha256"].items():
        require(digest((ROOT / "data/raw/a/official" / path).read_bytes()) == expected, "Changed official source")
    config = args.graphs / "config.txt"
    require(digest(config.read_bytes()) == protocol["input_sha256"]["config.txt"], "Changed config")
    # Imports only expose read-only functions from the already checked source.
    from diagnose import lower_bounds, read_scene_a_config
    from portfolio import boundary_cost
    from evaluation_validation import read_bandwidth_config
    from schedule_step3 import PIPE_SLOTS
    require(PIPE_SLOTS == 1, "Pipe-work bound assumes one in-flight op per pipe")
    waits = read_scene_a_config(str(config))
    bandwidth = read_bandwidth_config(str(config))
    feed = read(BASE / "board-feed-stage-e-4.json")
    records = feed["records"]
    require(len(records) == 100 and len({r["case_id"] for r in records}) == 100, "Need all 100 cases")
    require({r["case_id"] for r in records if r["status"] != "ok"} == EXPECTED_MISSING, "Different incomplete cases")
    observed_sum, missing_upper_sum = Fraction(0), Fraction(0)
    missing, observed = [], []
    for record in records:
        case = record["case_id"]
        receipt = artifact(record["artifacts"]["run"])
        denominator = artifact(record["baseline"]["result"])
        baseline = index["singlecore"][case]
        require(record["baseline"]["result"]["sha256"] == baseline["result"]["sha256"], "Changed fixed denominator bytes")
        single = baseline["makespan_cycles"]
        require(denominator["makespan"] == single, "Different denominator cycles")
        require(record["identity"]["graph_sha256"] == protocol["input_sha256"][f"case_{case}.json"], "Different graph identity")
        require(record["identity"]["config_sha256"] == protocol["input_sha256"]["config.txt"], "Different config identity")
        require(record["identity"]["official_sha256"] == protocol["official_code_hash"], "Different official identity")
        if record["status"] == "ok":
            result = artifact(record["artifacts"]["result"])
            cycles = result["makespan"]
            require(cycles == receipt["makespan_cycles"] == record["metrics"]["makespan_cycles"], "Different observed cycles")
            observed_sum += Fraction(single, cycles)
            observed.append({"case_id": case, "singlecore_cycles": single, "observed_cycles": cycles,
                             "result_sha256": record["artifacts"]["result"]["sha256"]})
            continue
        require(receipt["status"] == "timeout" and receipt["failure"]["stage"] == "evaluation", "Unexpected failure")
        plan = artifact(record["artifacts"]["plan"])
        require(receipt["plan_sha256"] == record["artifacts"]["plan"]["sha256"], "Changed fixed plan")
        diagnostic_path = BASE / "run" / f"{case}-k4" / "diagnostics.json"
        diagnostic = read(diagnostic_path)
        require(receipt["selected"] == diagnostic["selected"] == "fork", "Different selected candidate")
        graph_raw = (args.graphs / f"case_{case}.json").read_bytes()
        require(digest(graph_raw) == record["identity"]["graph_sha256"], "Changed graph bytes")
        graph = json.loads(graph_raw)
        gate = lower_bounds(graph, plan, waits)
        boundary = boundary_cost(graph, plan, bandwidth)
        chosen = diagnostic["costs"][diagnostic["selected"]]
        # JSON serializes integer Task dictionary keys as strings. This is a
        # diagnostic value comparison, never a normalization of plan evidence.
        boundary_json = json.loads(json.dumps(boundary))
        require(gate == chosen["gate"] and boundary_json == chosen["boundary"], "Static bounds differ from the original diagnostics")
        require(gate["witness_compute_cycles"] + gate["witness_gate_cycles"] == gate["task_gate_lower_bound_cycles"], "Gate witness mismatch")
        bounds = {"task_gate": Fraction(gate["task_gate_lower_bound_cycles"]),
                  "mandatory_boundary_DDR": Fraction(boundary["boundary_ddr_service_cycles"]),
                  "global_pipe_work": Fraction(str(gate["global_pipe_work_lower_bound_cycles"]))}
        lower_bound = max(bounds.values())
        require(lower_bound > 0, "Non-positive bound")
        upper_ratio = Fraction(single) / lower_bound
        missing_upper_sum += upper_ratio
        missing.append({"case_id": case, "singlecore_cycles": single,
                        "makespan_lower_bounds_cycles": {k: float(v) for k, v in bounds.items()},
                        "combined_lower_bound_cycles": float(lower_bound),
                        "combination": "max, never sum", "speedup_upper_bound": float(upper_ratio),
                        "speedup_upper_bound_fraction": str(upper_ratio),
                        "plan_sha256": record["artifacts"]["plan"]["sha256"],
                        "diagnostics_sha256": digest(diagnostic_path.read_bytes()),
                        "graph_sha256": digest(graph_raw),
                        "singlecore_result_sha256": record["baseline"]["result"]["sha256"],
                        "static_recomputation_matches_diagnostics": True})
    upper = (observed_sum + missing_upper_sum) / 100
    targets = [{"target": float(t), "optimistic_upper_bound_below_target": upper < t,
                "target_minus_upper_bound": float(t - upper)} for t in (Fraction("3.14"), Fraction("3.42710"))]
    output = {"schema": "q1-stage-e4-static-target-upper-bound-v1",
              "solver_commit": protocol["solver_commit"], "runner_commit": protocol["runner_commit"],
              "verifier_sha256": digest(Path(__file__).read_bytes()),
              "verifier_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "protocol_sha256": digest((BASE / "run/protocol.json").read_bytes()),
              "formula": "(sum_92(singlecore / observed_E0_makespan) + sum_8(singlecore / max(gate_LB, boundary_DDR_LB, global_pipe_LB))) / 100",
              "condition": "All eight incomplete fixed plans eventually have a legal finite official E0 result under the same frozen graph/config/code identities.",
              "scope": "Bound on this fixed uniform algorithm's 100 outputs, not on arbitrary alternative partitions. It is not a measured score or imputation.",
              "official_full100_mean_speedup": None, "observed_success_count": 92, "incomplete_count": 8,
              "observed_speedup_sum": float(observed_sum), "missing_optimistic_speedup_sum": float(missing_upper_sum),
              "optimistic_full100_mean_speedup_upper_bound": float(upper),
              "optimistic_upper_bound_fraction": str(upper), "targets": targets,
              "missing_plans": missing, "observed_terms": observed,
              "source_reasoning": [
                  "diagnose.lower_bounds uses one-slot pipe compute work and within-Task compute critical paths. Original COPY bridges are not retained in local compute paths. The official contracted Task DAG and serial core orders supply required waits; longest-path addition yields a fixed-plan bound.",
                  "portfolio.boundary_cost matches the official scene-A input/output boundary predicates. Every counted COPY uses shared DDR; sum of their exclusive service is a capacity bound. Spill can add work. Gate and DDR overlap, so only their maximum is a general lower bound.",
                  "All eight combined bounds are dominated by task_gate; mandatory DDR is checked separately and not added. The global pipe-work bound uses one-slot work / 4 cores."
              ],
              "source_references": {"task_bound": "src/q1_yuanzhifang/diagnose.py:23", "boundary_bound": "src/q1_yuanzhifang/portfolio.py:23",
                                    "official_boundary_reconstruction": "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py:70",
                                    "official_task_release": "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py:316",
                                    "official_DDR_service": "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py:238",
                                    "official_pipe_slots_and_duration": "data/raw/a/official/code/schedule_step3.py:30"},
              "static_graphs_read": 8, "all_100_graph_scan": False,
              "new_calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
              "static_wall_seconds": time.perf_counter() - start}
    with (BASE / "target-upper-bound.json").open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"upper_bound": float(upper), "targets": targets, "static_seconds": output["static_wall_seconds"], "new_calls": output["new_calls"]}))


if __name__ == "__main__":
    main()
