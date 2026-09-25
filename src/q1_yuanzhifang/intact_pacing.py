"""Exact guarded whole-chain source-core pacing for P1, k3/k4 only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))
sys.path.insert(0, str(Path(__file__).parent))
from star_frontier import guarded_stages
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


class Unsupported(ValueError):
    pass


def assemble(rounds, cores, variant):
    """Return a plan and the structural rank witness, without graph scoring."""
    if cores not in (3, 4) or variant not in ("control", "paced"):
        raise ValueError("supported fixed cells are k3/k4 and control/paced")
    width = 12 // cores
    mapping, orders, tasks = {}, [[] for _ in range(cores)], []

    def add(core, nodes, stage, phase, chain_indices):
        task = len(tasks)
        if not nodes:
            raise AssertionError("empty Task")
        for node in nodes:
            if node in mapping:
                raise AssertionError("compute operation assigned twice")
            mapping[node] = task
        orders[core].append(task)
        tasks.append(dict(id=task, core=core, stage=stage, phase=phase,
                          chain_indices=chain_indices, ops=len(nodes)))

    for stage, entry in enumerate(rounds):
        chains = entry["chains"]
        if len(chains) != 12 or any(len(chain) != 4 for chain in chains) or len(entry["tail"]) != 11:
            raise Unsupported("not twelve intact four-op chains and eleven ADDs")
        for core in range(cores):
            indices = list(range(core * width, (core + 1) * width))
            if core == 0 and stage > 0 and variant == "paced":
                groups = [(indices[:1], 0), (indices[1:], 1)]
            else:
                groups = [(indices, 0)]
            for selected, phase in groups:
                add(core, [u for index in selected for u in chains[index]],
                    stage, phase, selected)
        add(0, entry["tail"], stage, 2, [])
    plan = {"node_to_subgraph": {u: mapping[u] for u in sorted(mapping)},
            "core_schedules": orders}
    return plan, tasks


def construct(graph, cores, variant):
    if type(cores) is not int or cores not in (3, 4):
        raise ValueError("cores must be 3 or 4")
    if variant not in ("control", "paced"):
        raise ValueError("variant must be control or paced")
    began = time.perf_counter()
    guarded, reason = guarded_stages(graph)
    if guarded is None or len(guarded["rounds"]) != 24:
        raise Unsupported(reason if guarded is None else "requires exactly 24 fork/join rounds")
    operations = {item["id"]: item for item in graph["ops"]}
    if any(operations[u]["op"] != "ADD" for entry in guarded["rounds"] for u in entry["tail"]):
        raise Unsupported("all eleven reductions must be ADD")
    plan, tasks = assemble(guarded["rounds"], cores, variant)
    view = derive_multicore_plan(graph, plan)
    validate_task_order(view)
    rank = {item["id"]: (item["stage"], item["phase"]) for item in tasks}
    edges = list(view["dependency_pairs"]) + [
        (a, b) for sequence in plan["core_schedules"] for a, b in zip(sequence, sequence[1:])]
    if any(rank[a] >= rank[b] for a, b in edges):
        raise AssertionError("joint Task and core order fails strict stage/phase progression")
    assigned = plan["node_to_subgraph"]
    for entry in guarded["rounds"]:
        for chain in entry["chains"]:
            if len({assigned[u] for u in chain}) != 1:
                raise AssertionError("whole chain was cut")
    return plan, dict(algorithm_id="q1-intact-source-pacing", variant=variant,
                      guard=reason, cores=cores, rounds=24, task_count=len(tasks),
                      chain_width=12 // cores, tail_core=0, tasks=tasks,
                      construction_validation_seconds=time.perf_counter() - began,
                      scope="Direct guarded construction; official E0 outcome unknown")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, choices=(3, 4), required=True)
    parser.add_argument("--variant", choices=("control", "paced"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    args = parser.parse_args()
    if args.output == args.diagnostics or args.output.exists() or args.diagnostics.exists():
        raise FileExistsError("refuse to overwrite solver artifacts")
    start = time.perf_counter()
    plan, info = construct(json.loads(args.graph.read_bytes()), args.cores, args.variant)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(plan, out, separators=(",", ":"))
        out.write("\n")
    info["cli_body_through_plan_wall_seconds"] = time.perf_counter() - start
    with args.diagnostics.open("x", encoding="utf-8") as out:
        json.dump(info, out, indent=2)
        out.write("\n")


if __name__ == "__main__":
    main()
