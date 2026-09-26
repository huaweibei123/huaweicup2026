"""Direct first-wave capacity stair; compute-order model only, no plan/E0."""
from __future__ import annotations

from .tail_fifo_bound import longest_path
from .tail_phase_model import balanced_waves
from .wave_capacity import SPACES, model, structure
from .wave_tail import partition_tail


def position_widths(data, footprint, capacity, max_width):
    """Largest proxy width beta[p] satisfying Phi_r(p,b) in every space."""
    widths = []
    for p in range(data["length"]):
        width = max_width
        for r, space in enumerate(SPACES):
            headroom = capacity[space] - data["weights"][r][p] - footprint["active"][r][p]
            if headroom < 0:
                raise ValueError("single-job footprint exceeds capacity proxy")
            demand = max(footprint["frontier"][r][p], footprint["frontier"][r][p+1])
            if demand:
                width = min(width, 1 + headroom // demand)
        widths.append(width)
    return widths


def analyze(index, cores, capacity):
    data, reason = structure(index, cores)
    if reason:
        raise ValueError("structure guard failed: " + reason)
    jobs, length = data["jobs"], data["length"]
    if cores < 2 or len(jobs) % cores != 1 or length < cores:
        raise ValueError("single-tail shape guard failed")
    q = len(jobs) // cores
    bmax, footprint = model(data, capacity, q + 1)
    if bmax is None:
        raise ValueError("single-job capacity proxy guard failed")
    beta = position_widths(data, footprint, capacity, q + 1)
    if min(beta) != bmax:
        raise ValueError("position widths disagree with fixed capacity model")
    m = [index.ops[u]["cycles"] if index.ops[u]["pipe"] == "PIPE_M" else 0 for u in jobs[0]]
    v = [index.ops[u]["cycles"] if index.ops[u]["pipe"] == "PIPE_V" else 0 for u in jobs[0]]
    boundary = [sum(footprint["frontier"][r][h] for r in range(len(SPACES)))
                for h in range(length + 1)]
    cuts, objective = partition_tail(m, v, cores, q, boundary)
    upper = [min(q, min(beta[p] - int(cuts[c] <= p < cuts[c+1])
                        for p in range(length))) for c in range(cores)]
    h = min(upper[c] - c for c in range(cores))
    if h < 1:
        raise ValueError("capacity stair guard failed: h < 1")
    first_sizes = [h + c for c in range(cores)]
    schedules, phase = [], []
    for c, first_size in enumerate(first_sizes):
        group = [jobs[j] for j in range(c, q * cores, cores)]
        first = group[:first_size]
        rest = group[first_size:]
        later_sizes = balanced_waves(len(rest), bmax)
        seq = []
        for p in range(length):
            if cuts[c] <= p < cuts[c+1]:
                seq.append(jobs[-1][p])  # tail first at its own positions
            seq.extend(job[p] for job in first)
        offset = 0
        for size in later_sizes:
            wave = rest[offset:offset+size]
            offset += size
            for p in range(length):
                seq.extend(job[p] for job in wave)
        if offset != len(rest) or any(first_size + 1 > beta[p]
                                      for p in range(cuts[c], cuts[c+1])):
            raise ValueError("first-wave proxy width invariant failed")
        schedules.append(seq)
        phase.append(dict(core=c, full_job_wave_sizes=[first_size, *later_sizes],
                          first_wave_full_jobs=first_size, first_wave_has_tail=True,
                          later_wave_count=len(later_sizes)))
    owner = {u: c for c, seq in enumerate(schedules) for u in seq}
    position = {u: i for seq in schedules for i, u in enumerate(seq)}
    if len(owner) != len(index.ops):
        raise ValueError("eligible compute coverage mismatch")
    for u, targets in index.succ.items():
        for vtx in targets:
            if owner[u] == owner[vtx]:
                if position[u] >= position[vtx]:
                    raise ValueError("local compute order is not topological")
            elif owner[u] >= owner[vtx]:
                raise ValueError("cross-core tail dependency runs backward")
    result = longest_path(index.ops, index.succ, schedules)
    workloads = [dict(M=q * sum(m) + sum(m[cuts[c]:cuts[c+1]]),
                      V=q * sum(v) + sum(v[cuts[c]:cuts[c+1]])) for c in range(cores)]
    if objective[0] != max(max(w.values()) for w in workloads):
        raise ValueError("fixed-cut workload mismatch")
    result.update(cuts=cuts, beta=beta, global_width=bmax, U=upper, h=h,
                  first_wave_sizes=first_sizes, phase=phase, jobs=len(jobs),
                  cores=cores, full_jobs_per_core=q,
                  workload_peak_cycles=objective[0], per_core_work_cycles=workloads,
                  boundary_proxy_bytes=objective[1],
                  capacity_proxy_note="W/A/F position widths are proxies, not Step2 zero-spill certificates",
                  no_plan=True, no_derive=True, internal_step_calls=0, internal_E0_calls=0,
                  method="Direct beta -> U -> h+c first-wave stair; tail first at its own positions; zero-lag compute FIFO bound")
    return schedules, result
