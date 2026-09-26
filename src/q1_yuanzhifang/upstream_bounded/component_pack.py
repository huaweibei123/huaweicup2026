"""Preserve compute components, balance them, and emit one Task per used core.

This is a direct Q1 proposal, not a makespan predictor. COPY-contracted weak
components have no compute edges between them. Unioning whole components on a
core therefore introduces no cross-Task compute dependency. Shared inputs,
local FIFO/memory behaviour and DDR contention still require official E0.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))
from stub_multicore_cut_and_schedule import (  # noqa: E402
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)
from evaluation_validation import validate_task_order  # noqa: E402


def construct(graph: dict, cores: int) -> tuple[dict, dict]:
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("cores must be an integer in 1..5")
    ops = [op for op in graph["ops"] if op["op"] not in {"COPY_IN", "COPY_OUT"}]
    if not ops or len({op["id"] for op in ops}) != len(ops):
        raise ValueError("Require nonempty compute operations with unique IDs")
    for op in ops:
        if type(op["cycles"]) is not int or op["cycles"] < 0:
            raise ValueError("Require nonnegative integer operation cycles")
    ids = sorted(op["id"] for op in ops)
    _, full = _build_op_adjacency(graph)
    _, successors = _contract_excluded_copy_nodes(ids, full)
    parent, size = {v: v for v in ids}, dict.fromkeys(ids, 1)

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for u in ids:
        for v in sorted(successors[u]):
            a, b = find(u), find(v)
            if a != b:
                if (size[a], -a) < (size[b], -b):
                    a, b = b, a
                parent[b] = a
                size[a] += size[b]
    groups: dict[int, list] = {}
    for op in ops:
        groups.setdefault(find(op["id"]), []).append(op)
    components = []
    for group in groups.values():
        work = Counter()
        for op in group:
            work[op["pipe"]] += op["cycles"]
        components.append((group, work, min(op["id"] for op in group)))
    components.sort(key=lambda x: (-max(x[1].values()), -sum(x[1].values()),
                                   -len(x[0]), x[2]))
    loads = [Counter() for _ in range(cores)]
    counts = [0] * cores
    assignments = {}
    for group, work, anchor in components:
        choices = []
        for core in range(cores):
            pipes = loads[core].keys() | work.keys()
            after = [loads[core][p] + work[p] for p in pipes]
            choices.append((max(after), sum(after), counts[core], core))
        core = min(choices)[-1]
        loads[core].update(work)
        counts[core] += len(group)
        assignments[find(anchor)] = core
    # Preserve original operation insertion order. Do not canonicalize IDs or
    # map order under an unproved evaluator-equivalence assumption.
    plan = {
        "node_to_subgraph": {op["id"]: assignments[find(op["id"])] for op in ops},
        "core_schedules": [[k] if counts[k] else [] for k in range(cores)],
    }
    view = derive_multicore_plan(graph, plan)
    validate_task_order(view)
    if view["dependency_pairs"]:
        raise AssertionError("Whole independent components must not cross Tasks")
    return plan, {
        "algorithm_id": "q1-component-pack", "variant": "pipe-lpt-one-task-per-core",
        "compute_ops": len(ops), "components": len(components),
        "largest_component_ops": max(len(x[0]) for x in components),
        "tasks": sum(bool(x) for x in counts), "core_compute_ops": counts,
        "compute_pipe_work_by_core": [dict(sorted(x.items())) for x in loads],
        "scope": "Structural Task-order check only; load is a proposal proxy, not E0 or a spill certificate",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--diagnostics", type=Path)
    args = parser.parse_args()
    if args.output.exists() or (args.diagnostics and args.diagnostics.exists()):
        raise FileExistsError("Refuse to overwrite an existing experiment artifact")
    plan, diagnostics = construct(json.loads(args.graph.read_text()), args.cores)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pending = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=args.output.parent, delete=False) as f:
            pending = Path(f.name)
            json.dump(plan, f, separators=(",", ":"))
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(pending, args.output)
    finally:
        if pending is not None and pending.exists():
            pending.unlink()
    if args.diagnostics:
        args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
        args.diagnostics.write_text(json.dumps(diagnostics, indent=2) + "\n")
    print(json.dumps(diagnostics))


if __name__ == "__main__":
    main()
