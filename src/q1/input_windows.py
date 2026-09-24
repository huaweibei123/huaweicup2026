"""Direct P1 candidate: separate depth windows with large external input sets.

The input-byte budget is a proposal proxy, never a Step2 capacity certificate.
Whole independent components retain their core assignment; Task order follows
strictly increasing DAG depth windows. No evaluator is called by construction.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1.bounded_tasks import construct as bounded_construct
from stub_multicore_cut_and_schedule import (
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)
from evaluation_validation import validate_task_order


def construct(graph, cores, *, input_budget_bytes=262144,
              activation_bytes=524288, max_phases=32):
    for value in (input_budget_bytes, activation_bytes, max_phases):
        if type(value) is not int or value < 1:
            raise ValueError("Require positive integer construction budgets")
    fallback, base = bounded_construct(graph, cores)
    info = {"algorithm_id": "q1-external-input-windows", "variant": "component-core-depth-windows",
            "input_budget_bytes": input_budget_bytes, "activation_bytes": activation_bytes,
            "max_phases": max_phases, "selected": "bounded04", "base": base,
            "scope": "External input union is a pressure proxy, not a spill or performance certificate"}
    if cores == 1 or base["base"]["base"]["components"] < cores:
        info["reason"] = "retain existing route without enough whole components"
        return fallback, info
    ops = {o["id"]: o for o in graph["ops"] if o["op"] not in {"COPY_IN", "COPY_OUT"}}
    tensors = {t["id"]: t for t in graph["tensors"]}
    producers, reads = defaultdict(set), defaultdict(set)
    for e in graph["edges"]:
        u, v = e["source"], e["target"]
        if u in ops and v in tensors:
            producers[v].add(u)
        if u in tensors and v in ops:
            reads[v].add(u)
    external = {t for ts in reads.values() for t in ts if not producers[t]}
    external_bytes = sum(tensors[t]["size"] for t in external)
    info["external_input_bytes"] = external_bytes
    if external_bytes <= activation_bytes:
        info["reason"] = "external input union below activation threshold"
        return fallback, info
    _, full = _build_op_adjacency(graph)
    pred, succ = _contract_excluded_copy_nodes(sorted(ops), full)
    degree = {u: len(pred[u]) for u in ops}
    ready = deque(sorted(u for u in ops if not degree[u]))
    depth = dict.fromkeys(ops, 0)
    seen = 0
    while ready:
        u = ready.popleft()
        seen += 1
        for v in sorted(succ[u]):
            depth[v] = max(depth[v], depth[u] + 1)
            degree[v] -= 1
            if not degree[v]:
                ready.append(v)
    if seen != len(ops):
        raise ValueError("Cyclic compute graph")
    levels = defaultdict(list)
    for u in ops:
        levels[depth[u]].append(u)
    phases, nodes, inputs = [], [], set()
    for _, level_nodes in sorted(levels.items()):
        required = {t for u in level_nodes for t in reads[u] if t in external}
        combined = inputs | required
        if nodes and inputs and required - inputs and sum(tensors[t]["size"] for t in combined) > input_budget_bytes:
            phases.append((nodes, inputs))
            nodes, inputs = [], set()
        nodes.extend(level_nodes)
        inputs.update(required)
    if nodes:
        phases.append((nodes, inputs))
    if len(phases) <= 1 or len(phases) > max_phases:
        info["reason"] = "no useful window or phase budget exceeded"
        return fallback, info
    task_core = {t: c for c, order in enumerate(fallback["core_schedules"]) for t in order}
    old_mapping = {int(u): t for u, t in fallback["node_to_subgraph"].items()}
    mapping, schedules, details, next_task = {}, [[] for _ in range(cores)], [], 0
    for phase_nodes, phase_inputs in phases:
        bins = [[] for _ in range(cores)]
        for u in phase_nodes:
            bins[task_core[old_mapping[u]]].append(u)
        for c, members in enumerate(bins):
            if members:
                schedules[c].append(next_task)
                for u in members:
                    mapping[u] = next_task
                next_task += 1
        details.append({"depth_begin": min(depth[u] for u in phase_nodes),
                        "depth_end": max(depth[u] for u in phase_nodes),
                        "external_input_bytes": sum(tensors[t]["size"] for t in phase_inputs),
                        "core_compute_ops": list(map(len, bins))})
    plan = {"node_to_subgraph": {u: mapping[u] for u in ops}, "core_schedules": schedules}
    validate_task_order(derive_multicore_plan(graph, plan))
    info.update(selected="input-windows", phase_count=len(phases), phases=details, tasks=next_task)
    return plan, info


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("graph", type=Path)
    p.add_argument("--cores", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--diagnostics", type=Path)
    p.add_argument("--input-budget-bytes", type=int, default=262144)
    p.add_argument("--activation-bytes", type=int, default=524288)
    p.add_argument("--max-phases", type=int, default=32)
    a = p.parse_args()
    if a.output.exists() or (a.diagnostics and a.diagnostics.exists()):
        raise FileExistsError("Refuse to replace existing experiment artifacts")
    plan, info = construct(json.loads(a.graph.read_text()), a.cores,
                           input_budget_bytes=a.input_budget_bytes,
                           activation_bytes=a.activation_bytes, max_phases=a.max_phases)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x") as f:
        json.dump(plan, f, separators=(",", ":"))
        f.write("\n")
    if a.diagnostics:
        a.diagnostics.parent.mkdir(parents=True, exist_ok=True)
        with a.diagnostics.open("x") as f:
            json.dump(info, f, indent=2)
            f.write("\n")
    print(json.dumps(info))


if __name__ == "__main__":
    main()
