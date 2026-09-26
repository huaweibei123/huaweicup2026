"""Guarded first-wave capacity stair; one direct canonical-singleton plan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .construct import SharingIndex, derive_multicore_plan
from .tail_stair_model import analyze
from evaluation_validation import read_bandwidth_config, read_capacity_config


def build(index, cores, bandwidth, capacity):
    """Construct exactly one plan; an inapplicable guard raises, with no fallback."""
    del bandwidth  # Official external E0 uses bandwidth; the compute-order model does not.
    sequences, detail = analyze(index, cores, capacity)
    mapping = {str(u): i for i, u in enumerate(index.order)}
    plan = dict(node_to_subgraph=mapping,
                core_schedules=[[mapping[str(u)] for u in seq] for seq in sequences])
    derive_multicore_plan(index.graph, plan)
    return plan, dict(guard=True, selected="wave_stair", variant="wave_stair",
                      requested_cores=cores, active_cores=sum(bool(seq) for seq in sequences),
                      jobs=detail["jobs"], full_jobs_per_core=detail["full_jobs_per_core"],
                      tail_job_id=detail["jobs"] - 1, cuts=detail["cuts"],
                      per_core_compute_work_cycles=detail["per_core_work_cycles"],
                      minimax_compute_work_cycles=detail["workload_peak_cycles"],
                      beta=detail["beta"], U=detail["U"], h=detail["h"],
                      first_wave_sizes=detail["first_wave_sizes"], phase=detail["phase"],
                      zero_lag_fifo_lower_bound_cycles=detail["lower_bound_cycles"],
                      stair_model=detail, internal_step_calls=0, internal_E0_calls=0,
                      plan_built=True, derive_checked=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--config", type=Path,
                        default=Path(__file__).resolve().parents[2] / "data/raw/a/official/data/config.txt")
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    index = SharingIndex(graph)
    plan, meta = build(index, args.cores, read_bandwidth_config(args.config),
                       read_capacity_config(args.config))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(meta, sort_keys=True))


if __name__ == "__main__":
    main()
