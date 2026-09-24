"""Static P3 lower bounds for guarded singleton M/V plans; never run E0.

COPY-contracted dependencies are not automatically official P3 dependencies.
This module rejects that ambiguity and never charges COPY service time. See
docs/a/q3/PIPE_BOUND.md for the proof, guards, and measured counterexample.
"""
from __future__ import annotations

import argparse
from collections import deque
import gzip
import hashlib
import json
from pathlib import Path

from .construct import Index, ROOT, derive_multicore_plan
from multicore_cut_evaluate_problem_1 import _original_tensor_views
from evaluation_validation import read_required_settings


class UnsupportedBound(ValueError):
    """The input is outside the proved lower-bound family."""


def _longest_path(ops, adjacency, owner, use_delay):
    indegree = dict.fromkeys(ops, 0)
    for targets in adjacency.values():
        for v in targets:
            indegree[v] += 1
    ready = deque(u for u, degree in indegree.items() if degree == 0)
    start = dict.fromkeys(ops, 0)
    previous = {}
    visited = 0
    while ready:
        u = ready.popleft()
        visited += 1
        for v, edge in adjacency[u].items():
            candidate = start[u] + max(1, ops[u]["cycles"])
            if use_delay:
                candidate += edge["delay"]
            if (candidate > start[v] or
                    (candidate == start[v] and u < previous.get(v, u + 1))):
                start[v], previous[v] = candidate, u
            indegree[v] -= 1
            if indegree[v] == 0:
                ready.append(v)
    if visited != len(ops):
        raise UnsupportedBound("compute dependencies plus pipe FIFO edges contain a cycle")
    if not ops:
        return {"lower_bound_cycles": 0, "path_ops": [], "segments": [],
                "cross_core_path_edges": [], "path_compute_cycles": 0,
                "path_delay_cycles": 0}
    last = max(ops, key=lambda u: (start[u] + max(1, ops[u]["cycles"]), -u))
    bound = start[last] + max(1, ops[last]["cycles"])
    path = [last]
    while path[-1] in previous:
        path.append(previous[path[-1]])
    path.reverse()
    segments = []
    for u in path:
        if not segments or segments[-1]["core"] != owner[u]:
            segments.append({"core": owner[u], "first_op": u, "last_op": u,
                             "compute_cycles": 0, "operations": 0})
        segments[-1]["last_op"] = u
        segments[-1]["compute_cycles"] += max(1, ops[u]["cycles"])
        segments[-1]["operations"] += 1
    cross = [{"source": u, "target": v, "source_core": owner[u],
              "target_core": owner[v],
              "delay_cycles": adjacency[u][v]["delay"] if use_delay else 0,
              "reasons": sorted(adjacency[u][v]["reasons"])}
             for u, v in zip(path, path[1:]) if owner[u] != owner[v]]
    compute = sum(max(1, ops[u]["cycles"]) for u in path)
    return {"lower_bound_cycles": bound, "path_ops": path, "segments": segments,
            "cross_core_path_edges": cross, "path_compute_cycles": compute,
            "path_delay_cycles": bound - compute}


def analyze(graph, plan, cross_core_delay_cycles=0):
    """Return zero-delay and configured-delay bounds, or raise on unsupported input.

    The caller must use the actual frozen P3 cross-core delay, or leave it zero.
    A result is a lower bound on any successful official execution, not proof
    that allocation, COPY dependencies, or the submitted plan can execute.
    """
    if type(cross_core_delay_cycles) is not int or cross_core_delay_cycles < 0:
        raise UnsupportedBound("cross_core_delay_cycles must be a nonnegative integer")
    index = Index(graph)
    view = derive_multicore_plan(graph, plan)
    if any(len(nodes) != 1 for nodes in view["nodes_by_subgraph"].values()):
        raise UnsupportedBound("requires exactly one original non-COPY operation per subgraph")
    if any(op["pipe"] not in {"PIPE_M", "PIPE_V"} for op in index.ops.values()):
        raise UnsupportedBound("only original non-COPY PIPE_M/PIPE_V operations are proved")
    # Durations in this frozen model are max(1, cycles). Integer inputs retain
    # exact integer arithmetic and avoid a rounding claim for custom graphs.
    if any(type(op.get("cycles")) is not int or op["cycles"] < 0
           for op in index.ops.values()):
        raise UnsupportedBound("requires nonnegative integer original compute cycles")
    owner = {u: view["core_by_subgraph"][sg] for u, sg in view["mapping"].items()}
    producers, consumers, direct = _original_tensor_views(graph)
    original_edges = set()
    for tensor in graph["tensors"]:
        tid = tensor["id"]
        original_edges.update((u, v) for u in producers.get(tid, ())
                              for v in consumers.get(tid, ())
                              if u in index.ops and v in index.ops and u != v)
    original_edges.update((edge["source"], edge["target"]) for edge in direct
                          if edge["source"] in index.ops and edge["target"] in index.ops)
    contracted = {(u, v) for u, targets in index.succ.items() for v in targets}
    ambiguous = contracted - original_edges
    if ambiguous:
        sample = sorted(ambiguous)[:8]
        raise UnsupportedBound(f"excluded-COPY contraction adds unproved P3 dependencies: {sample}")
    adjacency = {u: {} for u in index.ops}

    def add_edge(u, v, delay, reason):
        edge = adjacency[u].setdefault(v, {"delay": 0, "reasons": set()})
        # Multiple tensor/direct/FIFO constraints are a conjunction, not a
        # sequence of extra waits: use max, never sum duplicate-edge delays.
        edge["delay"] = max(edge["delay"], delay)
        edge["reasons"].add(reason)

    for u, v in sorted(original_edges):
        add_edge(u, v, cross_core_delay_cycles if owner[u] != owner[v] else 0,
                 "original_compute_dependency")
    per_core_pipe_work = []
    for core in range(view["num_cores"]):
        previous = {}
        work = {"PIPE_M": 0, "PIPE_V": 0}
        for sg in view["core_orders"][core]:
            u = view["nodes_by_subgraph"][sg][0]
            pipe = index.ops[u]["pipe"]
            work[pipe] += max(1, index.ops[u]["cycles"])
            if pipe in previous:
                add_edge(previous[pipe], u, 0, "same_core_pipe_fifo")
            previous[pipe] = u
        per_core_pipe_work.append({"core": core, **work})
    zero = _longest_path(index.ops, adjacency, owner, False)
    delayed = _longest_path(index.ops, adjacency, owner, True)
    return {"schema": "q3-singleton-pipe-bound-v1", "scope": "P3 singleton M/V",
            "execution_legality_proved": False, "official_evaluations": 0,
            "cross_core_delay_cycles": cross_core_delay_cycles,
            "operations": len(index.ops), "original_dependency_edges": len(original_edges),
            "cross_core_dependency_edges": sum(owner[u] != owner[v] for u, v in original_edges),
            "augmented_edges": sum(map(len, adjacency.values())),
            "per_core_pipe_work": per_core_pipe_work,
            "zero_delay": zero, "with_cross_core_delay": delayed}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_batch(batch_path, config_path):
    """Read saved plans/results only. Hash checks fail closed; no evaluator call."""
    batch_path, config_path = Path(batch_path), Path(config_path)
    batch = json.loads(batch_path.read_text())
    sources = [ROOT / "data/raw/a/official/code" / name for name in (
        "multicore_cut_evaluate_problem_1.py", "multicore_cut_evaluate_problem_3.py",
        "schedule_step2.py", "schedule_step3.py", "stub_multicore_cut_and_schedule.py")]
    for source in sources:
        relative = str(source.relative_to(ROOT))
        expected = {stage["source_input_sha256"].get(relative) for stage in batch["stages"]}
        if expected != {_sha(source)}:
            raise ValueError(f"official source differs from recorded batch: {relative}")
    delay = read_required_settings(config_path, "multicore_scene_b",
                                   ("cross_core_copy_delay_cycles",))["cross_core_copy_delay_cycles"]
    records = []
    for record in batch["records"]:
        if record["status"] != "ok":
            raise ValueError("audit requires successful existing records")
        artifacts = record["artifacts"]
        plan_path, result_path = (ROOT / artifacts[k]["path"] for k in ("plan", "result"))
        for name, path in (("plan", plan_path), ("result", result_path)):
            if _sha(path) != artifacts[name]["sha256"]:
                raise ValueError(f"{name} hash mismatch for {record['job_key']}")
        graph_path = ROOT / f"data/raw/a/official/data/case_{record['case_id']}.json"
        if _sha(graph_path) != record["identity"]["graph_sha256"]:
            raise ValueError("graph identity mismatch")
        if _sha(config_path) != record["identity"]["config_sha256"]:
            raise ValueError("config identity mismatch")
        graph, plan = json.loads(graph_path.read_text()), json.loads(plan_path.read_text())
        result = json.loads(gzip.decompress(result_path.read_bytes()))
        if result["problem"] != 3 or result["cross_core_copy_delay_cycles"] != delay:
            raise ValueError("saved official problem/delay mismatch")
        bound = analyze(graph, plan, delay)
        observed = result["makespan"]
        if bound["with_cross_core_delay"]["lower_bound_cycles"] > observed:
            raise AssertionError(f"bound exceeds official result for {record['job_key']}")
        mapping = {int(u): sg for u, sg in plan["node_to_subgraph"].items()}
        inverse = {sg: u for u, sg in mapping.items()}
        ops = {op["id"]: op for op in graph["ops"] if op["id"] in mapping}
        pipe_checks = []
        for core, schedule in enumerate(plan["core_schedules"]):
            for pipe in ("PIPE_M", "PIPE_V"):
                expected = [inverse[sg] for sg in schedule if ops[inverse[sg]]["pipe"] == pipe]
                actual = [op["op_id"] for op in sorted(result["per_core_timeline"][core]["ops"],
                                                       key=lambda op: op["start"])
                          if op["op_id"] in ops and op["pipe"] == pipe]
                if expected != actual:
                    raise AssertionError("official compute pipe projection mismatch")
                pipe_checks.append({"core": core, "pipe": pipe, "operations": len(actual), "match": True})
        records.append({"job_key": record["job_key"], "case_id": record["case_id"],
                        "cores": record["cores"], "variant": record["variant"],
                        "plan": artifacts["plan"], "result": artifacts["result"],
                        "graph_sha256": _sha(graph_path), "official_makespan": observed,
                        "lower_bound_le_official": True, "pipe_projection_checks": pipe_checks,
                        "bound": bound})
    return {"schema": "q3-pipe-bound-existing-results-audit-v1", "official_evaluations": 0,
            "batch": {"path": str(batch_path.relative_to(ROOT)), "sha256": _sha(batch_path)},
            "as_run_solver_commit": batch["solver_commit"],
            "config": {"path": str(config_path.relative_to(ROOT)), "sha256": _sha(config_path)},
            "audit_source_sha256": _sha(Path(__file__)),
            "official_source_sha256": {str(p.relative_to(ROOT)): _sha(p) for p in sources},
            "record_count": len(records), "all_bounds_le_official": True, "records": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path, nargs="?")
    parser.add_argument("plan", type=Path, nargs="?")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--audit-batch", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    if args.audit_batch:
        if not args.config:
            parser.error("--audit-batch requires the frozen --config")
        result = audit_batch(args.audit_batch.resolve(), args.config.resolve())
    else:
        if not args.graph or not args.plan:
            parser.error("graph and plan are required")
        delay = (read_required_settings(args.config, "multicore_scene_b",
                 ("cross_core_copy_delay_cycles",))["cross_core_copy_delay_cycles"]
                 if args.config else 0)
        result = analyze(json.loads(args.graph.read_text()), json.loads(args.plan.read_text()), delay)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as stream:
            stream.write(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
