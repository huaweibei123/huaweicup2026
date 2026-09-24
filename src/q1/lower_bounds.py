"""Static P1 makespan lower bounds; no solver or evaluator calls.

See docs/a/Q1_LOWER_BOUNDS.md for the resource/precedence proofs and scope.
The public function requires both the core count and DDR bandwidth explicitly.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data/raw/a/official/code"
sys.path.insert(0, str(OFFICIAL))
from evaluation_validation import PIPES, read_bandwidth_config, validate_graph  # noqa: E402


def _ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def _resource_bounds(jobs: list[tuple[int, int, int]], capacity: int) -> dict:
    """Each job is (necessary release, minimum work, necessary tail)."""
    work = sum(d for _, d, _ in jobs)
    release = min((r for r, _, _ in jobs), default=0)
    tail = min((q for _, _, q in jobs), default=0)
    load_bound = _ceil_div(work, capacity)
    return {
        "job_count": len(jobs), "capacity": capacity, "work_cycles": work,
        "minimum_release_cycles": release, "minimum_tail_cycles": tail,
        "load_bound_cycles": load_bound,
        "release_load_tail_bound_cycles": release + load_bound + tail,
    }


def lower_bounds(graph: dict, cores: int, bandwidth: int) -> dict:
    """Return valid lower bounds for successful executions of frozen P1.

    COPY nodes are removed without contracting paths through them. Original
    compute-to-compute direct/tensor dependencies are retained. Additional
    nodes describe only boundary COPY instances unavoidable for every plan.
    No partition, per-core assignment, FIFO, spill or event replay is computed.
    """
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("cores must be an integer in 1..5")
    if type(bandwidth) is not int or bandwidth <= 0:
        raise ValueError("bandwidth must be an explicit positive integer")
    validate_graph(graph)
    ops = {op["id"]: op for op in graph["ops"]}
    eligible = {v for v, op in ops.items() if op["op"] not in {"COPY_IN", "COPY_OUT"}}
    tensors = {t["id"]: t for t in graph["tensors"]}
    producers, consumers = defaultdict(set), defaultdict(set)
    successors = {v: set() for v in eligible}
    for edge in graph["edges"]:
        a, b = edge["source"], edge["target"]
        if a in ops and b in ops:
            if a in eligible and b in eligible:
                successors[a].add(b)
        elif a in ops:
            producers[b].add(a)
        else:
            consumers[a].add(b)
    compute_producers, compute_consumers = {}, {}
    input_work, output_work = {}, {}
    for tid, tensor in tensors.items():
        pp = producers[tid] & eligible
        cc = consumers[tid] & eligible
        compute_producers[tid], compute_consumers[tid] = pp, cc
        for v in pp:
            successors[v].update(cc)
        work = max(1, _ceil_div(tensor["size"], bandwidth))
        if not pp and cc:
            input_work[tid] = work
        if pp and (not cc or any(ops[v]["op"] == "COPY_OUT" for v in consumers[tid])):
            output_work[tid] = work

    indegree = dict.fromkeys(eligible, 0)
    for following in successors.values():
        for v in following:
            indegree[v] += 1
    ready = deque(sorted(v for v, count in indegree.items() if not count))
    topo = []
    while ready:
        v = ready.popleft()
        topo.append(v)
        for w in successors[v]:
            indegree[w] -= 1
            if not indegree[w]:
                ready.append(w)
    if len(topo) != len(eligible):
        raise ValueError("The retained compute dependency graph must be acyclic")

    duration = {v: max(1, ops[v]["cycles"]) for v in eligible}
    release, tail = dict.fromkeys(eligible, 0), dict.fromkeys(eligible, 0)
    compute_release = dict.fromkeys(eligible, 0)
    for tid, work in input_work.items():
        for v in compute_consumers[tid]:
            release[v] = max(release[v], work)
    for tid, work in output_work.items():
        for v in compute_producers[tid]:
            tail[v] = max(tail[v], work)
    for v in topo:
        for w in successors[v]:
            release[w] = max(release[w], release[v] + duration[v])
            compute_release[w] = max(compute_release[w], compute_release[v] + duration[v])
    for v in reversed(topo):
        for w in successors[v]:
            tail[v] = max(tail[v], duration[w] + tail[w])

    pipe_jobs = {pipe: [] for pipe in PIPES}
    for v in eligible:
        pipe_jobs[ops[v]["pipe"]].append((release[v], duration[v], tail[v]))
    ddr_jobs = []
    for tid, work in input_work.items():
        # Choose an actual read serving a consumer with the largest necessary
        # tail. Its own completion must precede that consumer's execution.
        job = (0, work, max(duration[v] + tail[v] for v in compute_consumers[tid]))
        pipe_jobs["PIPE_MTE2"].append(job)
        ddr_jobs.append(job)
    for tid, work in output_work.items():
        # Choose an actual write for a producer with the largest necessary
        # release. At least one such write exists by the boundary predicate.
        job = (max(release[v] + duration[v] for v in compute_producers[tid]), work, 0)
        pipe_jobs["PIPE_MTE3"].append(job)
        ddr_jobs.append(job)
    pipe_resources = {pipe: _resource_bounds(jobs, cores) for pipe, jobs in pipe_jobs.items()}
    ddr_resource = _resource_bounds(ddr_jobs, 1)
    compute_cp = max((compute_release[v] + duration[v] for v in eligible), default=0)
    augmented_cp = max((release[v] + duration[v] + tail[v] for v in eligible), default=0)
    pipe_bound = max(x["load_bound_cycles"] for x in pipe_resources.values())
    base = max(pipe_bound, augmented_cp, ddr_resource["load_bound_cycles"])
    strengthened = max(base, ddr_resource["release_load_tail_bound_cycles"],
                       *(x["release_load_tail_bound_cycles"] for x in pipe_resources.values()))
    return {
        "cores": cores, "ddr_bandwidth_bytes_per_cycle": bandwidth,
        "pipe_slots_per_core": 1, "compute_ops": len(eligible),
        "retained_compute_edges": sum(map(len, successors.values())),
        "compute_critical_path_cycles": compute_cp,
        "relaxed_critical_path_cycles": augmented_cp,
        "pipe_load_bound_cycles": pipe_bound,
        "mandatory_ddr_service_bound_cycles": ddr_resource["load_bound_cycles"],
        "mandatory_input_tensors": len(input_work), "mandatory_output_tensors": len(output_work),
        "mandatory_input_bytes": sum(tensors[t]["size"] for t in input_work),
        "mandatory_output_bytes": sum(tensors[t]["size"] for t in output_work),
        "pipe_resources": pipe_resources, "ddr_resource": ddr_resource,
        "base_lower_bound_cycles": base, "lower_bound_cycles": strengthened,
        "proof_scope": {
            "target": "all successful plans under frozen P1 resource and boundary semantics",
            "copy_bridge_contraction": False,
            "relaxed": ["task waiting", "fixed FIFO", "capacity/spill", "extra partition COPY"],
            "is_achievable_or_performance_result": False,
            "reference": "docs/a/Q1_LOWER_BOUNDS.md",
        },
        "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
    }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identity(config: Path) -> dict:
    relevant = ("evaluation_validation.py", "stub_multicore_cut_and_schedule.py",
                "multicore_cut_evaluate_problem_1.py", "schedule_step3.py")
    return {
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "implementation_sha256": _sha(Path(__file__).read_bytes()),
        "uv_lock_sha256": _sha((ROOT / "uv.lock").read_bytes()),
        "config_sha256": _sha(config.read_bytes()),
        "official_source_sha256": {name: _sha((OFFICIAL / name).read_bytes()) for name in relevant},
        "python": platform.python_version(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--graph", type=Path)
    source.add_argument("--scan-zip", type=Path)
    parser.add_argument("--cores", nargs="+", type=int, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refuse to overwrite an existing static result")
    if len(set(args.cores)) != len(args.cores):
        raise ValueError("core counts must be distinct")
    bandwidth = read_bandwidth_config(args.config)
    cases = []

    def add_case(name: str, raw: bytes) -> None:
        graph = json.loads(raw)
        cases.append({"input_member": name, "input_sha256": _sha(raw),
                      "bounds": [lower_bounds(graph, k, bandwidth) for k in args.cores]})

    if args.scan_zip:
        with zipfile.ZipFile(args.scan_zip) as archive:
            members = sorted(n for n in archive.namelist()
                             if n.startswith("data/case_") and n.endswith(".json") and "/._" not in n)
            if not members:
                raise ValueError("No official case JSON members found")
            for name in members:
                add_case(name, archive.read(name))
        input_identity = {"type": "zip", "sha256": _sha(args.scan_zip.read_bytes())}
    else:
        add_case(args.graph.name, args.graph.read_bytes())
        input_identity = {"type": "graph", "sha256": _sha(args.graph.read_bytes())}
    report = {
        "kind": "static_makespan_lower_bounds_not_performance", "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": ["python", str(Path(__file__).relative_to(ROOT)), *sys.argv[1:]],
        "code_identity": _identity(args.config), "input_identity": input_identity,
        "core_counts": args.cores, "case_count": len(cases),
        "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}, "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(report, out, indent=2, ensure_ascii=False)
        out.write("\n")
    print(json.dumps({"case_count": len(cases), "cores": args.cores, "calls": report["calls"]}))


if __name__ == "__main__":
    main()
