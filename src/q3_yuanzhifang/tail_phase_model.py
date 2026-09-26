"""Direct staggered-tail compute order model; no plan or official evaluation."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from math import ceil
from pathlib import Path
import time

from .construct import SharingIndex
from .tail_fifo_bound import longest_path
from .wave_capacity import SPACES, model, structure
from .wave_tail import partition_tail
from evaluation_validation import read_capacity_config


def balanced_waves(count, width):
    if count == 0:
        return []
    waves = ceil(count / width)
    return [count // waves + (i < count % waves) for i in range(waves)]


def analyze(index, cores, capacity):
    data, reason = structure(index, cores)
    if reason:
        raise ValueError("structure guard failed: " + reason)
    jobs, length = data["jobs"], data["length"]
    if cores < 2 or len(jobs) % cores != 1 or length < cores:
        raise ValueError("single-tail shape guard failed")
    q = len(jobs) // cores
    if q < cores - 1:
        raise ValueError("staggered prefix requires q >= cores-1")
    bmax, footprint = model(data, capacity, q + 1)
    if bmax is None or bmax < 2:
        raise ValueError("capacity wave guard failed")
    m = [index.ops[u]["cycles"] if index.ops[u]["pipe"] == "PIPE_M" else 0 for u in jobs[0]]
    v = [index.ops[u]["cycles"] if index.ops[u]["pipe"] == "PIPE_V" else 0 for u in jobs[0]]
    boundary = [sum(footprint["frontier"][r][h] for r in range(len(SPACES)))
                for h in range(length + 1)]
    cuts, objective = partition_tail(m, v, cores, q, boundary)
    schedules, phase = [], []
    for c in range(cores):
        group = [jobs[j] for j in range(c, q * cores, cores)]
        prefix = balanced_waves(c, bmax)
        tail_full = min(bmax - 1, q - c)
        suffix = balanced_waves(q - c - tail_full, bmax)
        sizes = [*prefix, tail_full, *suffix]
        tail_wave = len(prefix)
        sequence, offset = [], 0
        for wave_no, size in enumerate(sizes):
            wave = group[offset:offset + size]
            offset += size
            for p in range(length):
                sequence.extend(job[p] for job in wave)
                if wave_no == tail_wave and cuts[c] <= p < cuts[c + 1]:
                    sequence.append(jobs[-1][p])
        if offset != q or not all(0 <= size <= bmax for size in sizes):
            raise ValueError("phase construction invariant failed")
        schedules.append(sequence)
        phase.append(dict(core=c, full_job_wave_sizes=sizes,
                          tail_wave_index=tail_wave, tail_wave_full_jobs=tail_full,
                          prefix_full_jobs=c, suffix_full_jobs=q-c-tail_full,
                          total_wave_count=len(sizes)))
    bound = longest_path(index.ops, index.succ, schedules)
    workloads = [dict(M=q * sum(m) + sum(m[cuts[c]:cuts[c + 1]]),
                      V=q * sum(v) + sum(v[cuts[c]:cuts[c + 1]]))
                 for c in range(cores)]
    if objective[0] != max(max(w.values()) for w in workloads):
        raise ValueError("fixed-tail DP/workload mismatch")
    shared_bytes = sum(map(sum, data["weights"]))
    bound.update(cuts=cuts, q=q, cores=cores, jobs=len(jobs), bmax=bmax,
                 phase=phase, per_core_work_cycles=workloads,
                 workload_peak_cycles=objective[0],
                 boundary_proxy_bytes=objective[1],
                 total_shared_wave_proxy_bytes=shared_bytes * sum(p["total_wave_count"] for p in phase),
                 shared_wave_proxy_note="Accounting proxy only; split tail has no guaranteed W*waves read bound",
                 no_plan=True, no_derive=True, internal_step_calls=0, internal_E0_calls=0,
                 method="Direct prefix(c)-tail-suffix waves; zero-lag original compute DAG and M/V FIFO lower bound")
    return schedules, bound


def main():
    started = datetime.now(timezone.utc).isoformat()
    clock = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[2] / "data/raw/a/official/data/config.txt")
    parser.add_argument("--incumbent", type=int)
    args = parser.parse_args()
    if args.incumbent is not None and args.incumbent <= 0:
        parser.error("incumbent must be positive")
    raw = args.graph.read_bytes()
    _, bound = analyze(SharingIndex(json.loads(raw)), args.cores, read_capacity_config(args.config))
    root = Path(__file__).resolve().parents[2]
    sources = ("tail_phase_model.py", "tail_fifo_bound.py", "wave_tail.py",
               "wave_capacity.py", "construct.py", "baseline.py")
    bound.update(graph_sha256=hashlib.sha256(raw).hexdigest(),
                 config_sha256=hashlib.sha256(args.config.read_bytes()).hexdigest(),
                 source_sha256={name: hashlib.sha256((root / "src/q3_yuanzhifang" / name).read_bytes()).hexdigest()
                                for name in sources},
                 started_at_utc=started, analyzed_at_utc=datetime.now(timezone.utc).isoformat(),
                 analysis_body_wall_seconds=time.perf_counter() - clock,
                 timing_scope="Body excludes interpreter startup/imports; report external process wall separately",
                 costs="One case-specific candidate-order analysis, not reusable outside future cold solver timing",
                 calls=dict(candidate_compute_order_analysis=1, submission_constructor=0,
                            submission_write=0, derive=0, Step=0, E0=0, E1=0, E2=0))
    if args.incumbent is not None:
        bound.update(incumbent_cycles=args.incumbent,
                     fixed_layout_cannot_beat_incumbent=bound["lower_bound_cycles"] >= args.incumbent)
    print(json.dumps(bound, sort_keys=True))


if __name__ == "__main__":
    main()
