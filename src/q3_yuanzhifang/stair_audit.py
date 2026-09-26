"""One static first-wave stair analysis; no submission builder, derive, Step or E0."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from .construct import SharingIndex
from .tail_stair_model import analyze
from evaluation_validation import read_capacity_config


def main():
    start = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--incumbent", type=int)
    args = parser.parse_args()
    if args.incumbent is not None and args.incumbent <= 0:
        parser.error("incumbent must be positive")
    raw = args.graph.read_bytes()
    sequences, result = analyze(SharingIndex(json.loads(raw)), args.cores,
                                read_capacity_config(args.config))
    root = Path(__file__).resolve().parents[2]
    sources = ["src/q3_yuanzhifang/" + name + ".py" for name in (
        "stair_audit", "tail_stair_model", "tail_phase_model", "tail_fifo_bound",
        "wave_tail", "wave_capacity", "active_stages", "construct", "baseline")]
    result.update(
        schema="q3-stair-static-audit-v1",
        graph_sha256=hashlib.sha256(raw).hexdigest(),
        config_sha256=hashlib.sha256(args.config.read_bytes()).hexdigest(),
        source_sha256={name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                       for name in sources},
        compute_order_lengths=[len(seq) for seq in sequences],
        started_at_utc=started_at,
        analyzed_at_utc=datetime.now(timezone.utc).isoformat(),
        analysis_body_wall_seconds=time.perf_counter() - start,
        timing_scope="Body excludes interpreter/imports/serialization. Report external process wall separately.",
        costs="Case-specific static analysis, not a cold submission solver. A future cold run must recompute everything.",
        limitations="Fixed-order necessary compute/FIFO bound only; no COPY, spill, Cache or actual transfer lag. Not an achievable Makespan.",
        calls=dict(candidate_compute_order_analysis=1, submission_constructor=0,
                   submission_write=0, derive=0, step=0, E0=0, E1=0, E2=0))
    if args.incumbent is not None:
        result.update(incumbent_cycles=args.incumbent,
                      remaining_bound_slack_cycles=args.incumbent - result["lower_bound_cycles"],
                      fixed_layout_cannot_beat_incumbent=result["lower_bound_cycles"] >= args.incumbent,
                      incumbent_note="Comparison only; the incumbent is not used to construct the compute order.")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
