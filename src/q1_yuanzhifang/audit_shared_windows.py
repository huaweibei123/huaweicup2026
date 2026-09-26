"""Audit existing shared-input windows without constructing or evaluating a plan.

The hypothetical contractions below are metadata only. COPY monotonicity and a
resident-union certificate do not imply Makespan monotonicity: the official
compiler may change COPY IDs, FIFO order, memory dependencies and DDR overlap.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "9c5f87548cc7588465a638e032993969b5cac891"
CELL = "results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/cells/044/k4"


def frozen(name):
    raw = subprocess.check_output(["git", "show", f"{COMMIT}:{CELL}/{name}"], cwd=ROOT)
    decoded = gzip.decompress(raw) if name.endswith(".gz") else raw
    return json.loads(decoded), dict(commit=COMMIT, path=f"{CELL}/{name}",
        stored_sha256=hashlib.sha256(raw).hexdigest(),
        decoded_sha256=hashlib.sha256(decoded).hexdigest())


def analyze():
    plan, plan_src = frozen("plan.json")
    result, result_src = frozen("result.json.gz")
    run, run_src = frozen("run-derived.json")
    graph_raw = (ROOT / "data/raw/a/official/data/case_044.json").read_bytes()
    graph_sha = hashlib.sha256(graph_raw).hexdigest()
    if graph_sha != run["graph_sha256"]:
        raise ValueError("Original graph identity differs")
    if (plan_src["decoded_sha256"] != run["artifacts"]["plan.json"]["sha256"] or
            result_src["decoded_sha256"] != run["artifacts"]["result.json"]["sha256"]):
        raise ValueError("Archived artifact identity differs")
    graph = json.loads(graph_raw)
    tensors = {t["id"]: t for t in graph["tensors"]}
    all_ops = {o["id"]: o for o in graph["ops"]}
    compute = {u: o for u, o in all_ops.items() if o["op"] not in {"COPY_IN", "COPY_OUT"}}
    producers, consumers = defaultdict(set), defaultdict(set)
    for edge in graph["edges"]:
        u, v = edge["source"], edge["target"]
        if u in all_ops and v in tensors:
            producers[v].add(u)
        if u in tensors and v in all_ops:
            consumers[u].add(v)
    # Explicitly rule out an excluded COPY lying between two compute nodes.
    succ = {u: set() for u in all_ops}
    for edge in graph["edges"]:
        if edge["source"] in all_ops and edge["target"] in all_ops:
            succ[edge["source"]].add(edge["target"])
    for t in tensors:
        for u in producers[t]:
            succ[u].update(consumers[t])
    degree = dict.fromkeys(all_ops, 0)
    for targets in succ.values():
        for v in targets:
            degree[v] += 1
    ready = deque(u for u in all_ops if degree[u] == 0)
    before, after = (dict.fromkeys(all_ops, False) for _ in range(2))
    topological = []
    while ready:
        u = ready.popleft()
        topological.append(u)
        for v in succ[u]:
            before[v] |= before[u] or u in compute
            degree[v] -= 1
            if degree[v] == 0:
                ready.append(v)
    if len(topological) != len(all_ops):
        raise ValueError("Original operation graph contains a cycle")
    for u in reversed(topological):
        after[u] = any(after[v] or v in compute for v in succ[u])
    if any(before[u] and after[u] for u in all_ops if u not in compute):
        raise ValueError("Excluded COPY bridge is outside this audit's proof scope")
    mapping = {int(u): task for u, task in plan["node_to_subgraph"].items()}
    if set(mapping) != set(compute):
        raise ValueError("Plan must cover exactly the compute nodes")
    if any(len(producers[t]) > 1 for t in tensors):
        raise ValueError("This audit requires single-producer tensors")
    compute_touched = {t for t in tensors if (producers[t] | consumers[t]) & compute.keys()}
    if any(tensors[t]["pos"] not in result["capacity_bytes"] for t in compute_touched):
        raise ValueError("This audit is restricted to resident tensors incident to compute")
    members = defaultdict(set)
    for u, task in mapping.items():
        members[task].add(u)
    task_core = {task: c for c, order in enumerate(plan["core_schedules"]) for task in order}
    if len(task_core) != len(members):
        raise ValueError("Task schedules differ from the mapping")
    for dep in result["task_dependencies"]:
        a, b = dep["source"], dep["target"]
        c = task_core[a]
        if c != task_core[b] or plan["core_schedules"][c].index(a) >= plan["core_schedules"][c].index(b):
            raise ValueError("Expected forward local dependencies only")
    capacity = result["capacity_bytes"]
    bandwidth = result["bandwidth_bytes_per_cycle"]
    touched = {task: {t for t in tensors if (producers[t] | consumers[t]) & ns}
               for task, ns in members.items()}
    external = {t for t in tensors if consumers[t] & compute.keys() and not producers[t] & compute.keys()}
    original_out = {t for t in tensors if any(all_ops[u]["op"] == "COPY_OUT" for u in consumers[t])}

    def union_by_space(ids):
        return {space: sum(tensors[t]["size"] for t in ids if tensors[t]["pos"] == space)
                for space in capacity}

    if any(any(value > capacity[s] for s, value in union_by_space(ids).items())
           for ids in touched.values()):
        raise ValueError("The full no-spill certificate requires every remaining Task to fit too")

    def copy_cost(labels):
        total = service = 0
        for t, tensor in tensors.items():
            p = {labels[mapping[u]] for u in producers[t] if u in compute}
            c = {labels[mapping[u]] for u in consumers[t] if u in compute}
            copies = len(c - p) + sum(t in original_out or not c or bool(c - {a}) for a in p)
            total += copies * tensor["size"]
            service += copies * max(1, (tensor["size"] + bandwidth - 1) // bandwidth)
        return dict(bytes=total, isolated_service_cycles=service)

    identity = {t: t for t in members}
    original_copy = copy_cost(identity)
    if (result["data_movement_bytes"]["spill_added_copy_bytes"] != 0 or
            original_copy["bytes"] != result["data_movement_bytes"]["scheduled_copy_bytes"]):
        raise ValueError("No-spill boundary COPY reconstruction differs from E0")
    task_rows = []
    for core in result["per_core_timeline"]:
        for actual in core["tasks"]:
            task = actual["task_id"]
            work = Counter()
            for u in members[task]:
                work[compute[u]["pipe"]] += compute[u]["cycles"]
            busy = Counter()
            for op in core["ops"]:
                if op["task_id"] == task:
                    busy[op["pipe"]] += op["duration"]
            task_rows.append(dict(task=task, core=core["core_id"], timeline=actual,
                compute_ops=len(members[task]), compute_work_cycles=dict(work),
                observed_pipe_busy_cycles=dict(busy),
                external_input_bytes=sum(tensors[t]["size"] for t in touched[task] & external),
                resident_union_bytes=union_by_space(touched[task])))
    pairs = []
    for core, order in enumerate(plan["core_schedules"]):
        for a, b in zip(order, order[1:]):
            union = union_by_space(touched[a] | touched[b])
            labels = dict(identity)
            labels[b] = a
            after = copy_cost(labels)
            pairs.append(dict(core=core, adjacent_tasks=[a, b], resident_union_bytes=union,
                union_fits_capacity=all(union[s] <= capacity[s] for s in capacity),
                common_external_bytes=sum(tensors[t]["size"] for t in touched[a] & touched[b] & external),
                hypothetical_copy=after, removed_copy_bytes=original_copy["bytes"]-after["bytes"],
                removed_isolated_copy_service_cycles=original_copy["isolated_service_cycles"]-after["isolated_service_cycles"]))
    fitting = [p for p in pairs if p["union_fits_capacity"]]
    # For this fixed diagnostic the fitting pairs are disjoint. No submission
    # mapping is emitted, and no Task compiler is called for the contraction.
    used = set()
    labels = dict(identity)
    for pair in fitting:
        a, b = pair["adjacent_tasks"]
        if {a, b} & used:
            raise ValueError("The aggregate diagnostic assumes disjoint fitting pairs")
        used.update((a, b))
        labels[b] = a
    return dict(scope="Read-only audit of existing E0 and graph; contraction metadata is not a new plan or score",
        calls=dict(cold_solver=0, Task_compile=0, E0=0, E1=0, E2=0),
        checked_guards=dict(single_producer_tensors=True, compute_incident_tensors_resident=True,
            no_excluded_copy_bridge=True, all_task_dependencies_forward_on_same_core=True,
            all_original_task_resident_unions_fit_capacity=True),
        graph_sha256=graph_sha, sources=dict(plan=plan_src, result=result_src, run=run_src),
        baseline=dict(makespan_cycles=result["makespan"], core_schedules=plan["core_schedules"],
            capacity_bytes=capacity, memory_peak_by_core=result["memory_peak_by_core"],
            movement=result["data_movement_bytes"], reconstructed_copy=original_copy,
            same_core_wait_cycles=result["task_same_core_wait_cycles"]),
        tasks=task_rows, adjacent_pairs=pairs,
        disjoint_fitting_pairs=[p["adjacent_tasks"] for p in fitting],
        hypothetical_after_all_fitting_pairs=dict(copy=copy_cost(labels),
            task_count=len(members)-len(fitting), makespan_cycles=None,
            scope="Predicted no-spill COPY multiset only; no speed or compiler success claim"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    value = analyze()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(value, out, indent=2)
        out.write("\n")
    print(json.dumps({k: value[k] for k in ("disjoint_fitting_pairs", "hypothetical_after_all_fitting_pairs", "calls")}))


if __name__ == "__main__":
    main()
