"""Read-only structural diagnostic; never constructs a plan or calls E0/E1/E2.

Usage from the repository root:
  python results/a/q2-nikolastarx/component-bottleneck-20260925/analyze_graph.py \
    data/raw/a/official/data/case_056.json --output <new-summary.json>

Input selection is a diagnostic argument, not a solver case-ID branch.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import heapq
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[4]
PIPES = ("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3")
POOLS = ("L1", "UB", "DDR")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def longest_path(ops, pred, succ):
    degree = {u: len(pred[u]) for u in ops}
    ready = [u for u in ops if not degree[u]]
    heapq.heapify(ready)
    order, finish = [], {}
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        finish[u] = max((finish[v] for v in pred[u]), default=0) + max(1, ops[u]["cycles"])
        for v in succ[u]:
            degree[v] -= 1
            if not degree[v]:
                heapq.heappush(ready, v)
    if len(order) != len(ops):
        raise ValueError("eligible dependency graph is cyclic")
    return order, finish


def analyze(graph):
    ops = {o["id"]: o for o in graph["ops"] if o["op"] not in ("COPY_IN", "COPY_OUT")}
    tensors = {t["id"]: t for t in graph["tensors"]}
    producers, consumers, inputs, outputs = (defaultdict(set) for _ in range(4))
    pred, succ = {u: set() for u in ops}, {u: set() for u in ops}
    for edge in graph["edges"]:
        a, b = edge["source"], edge["target"]
        if a in ops and b in tensors:
            producers[b].add(a)
            outputs[a].add(b)
        elif a in tensors and b in ops:
            consumers[a].add(b)
            inputs[b].add(a)
        elif a in ops and b in ops:
            succ[a].add(b)
            pred[b].add(a)
    for t in tensors:
        for a in producers[t]:
            for b in consumers[t]:
                succ[a].add(b)
                pred[b].add(a)
    order, finish = longest_path(ops, pred, succ)
    components, owner = [], {}
    for root in order:
        if root in owner:
            continue
        cid, stack = len(components), [root]
        owner[root] = cid
        components.append([])
        while stack:
            u = stack.pop()
            for v in succ[u] | pred[u]:
                if v not in owner:
                    owner[v] = cid
                    stack.append(v)
    for u in order:
        components[owner[u]].append(u)
    external = {t for t in tensors if consumers[t] and not producers[t]}
    terminal = {t for t in tensors if producers[t] and not consumers[t]}
    work = {p: sum(max(1, o["cycles"]) for o in ops.values() if o["pipe"] == p) for p in PIPES}
    details = []
    for cid, nodes in enumerate(components):
        first, last = {}, {}
        for i, u in enumerate(nodes):
            for t in inputs[u] | outputs[u]:
                first.setdefault(t, i)
                last[t] = i
        events = defaultdict(Counter)
        for t in first:
            events[first[t]][tensors[t]["pos"]] += tensors[t]["size"]
            events[last[t] + 1][tensors[t]["pos"]] -= tensors[t]["size"]
        live, peak, peak_op = Counter(), Counter(), {}
        for i, u in enumerate(nodes):
            live.update(events[i])
            for p in POOLS:
                if live[p] > peak[p]:
                    peak[p], peak_op[p] = live[p], u
        ts = set(first)
        ins, outs = ts & external, ts & terminal
        details.append({
            "component_id": cid, "op_count": len(nodes), "min_op_id": min(nodes),
            "max_op_id": max(nodes), "natural_order_is_increasing_id": nodes == sorted(nodes),
            "pipe_work_cycles": {p: sum(max(1, ops[u]["cycles"]) for u in nodes
                                         if ops[u]["pipe"] == p) for p in PIPES},
            "original_compute_critical_path_cycles": max(finish[u] for u in nodes),
            "external_input_count": len(ins), "external_input_bytes": sum(tensors[t]["size"] for t in ins),
            "terminal_output_count": len(outs), "terminal_output_bytes": sum(tensors[t]["size"] for t in outs),
            "all_distinct_touched_tensor_bytes": {p: sum(tensors[t]["size"] for t in ts
                                                         if tensors[t]["pos"] == p) for p in POOLS},
            "original_touch_peak_bytes": {p: peak[p] for p in POOLS},
            "original_touch_peak_op_ids": peak_op,
        })
    largest = max(range(len(components)), key=lambda j: len(components[j]), default=None)
    fifo_bound = None
    if largest is not None:
        nodes = components[largest]
        local_ops = {u: ops[u] for u in nodes}
        local_pred = {u: set(pred[u]) for u in nodes}
        local_succ = {u: set(succ[u]) for u in nodes}
        for p in PIPES:
            sequence = [u for u in nodes if ops[u]["pipe"] == p]
            for a, b in zip(sequence, sequence[1:]):
                local_succ[a].add(b)
                local_pred[b].add(a)
        _, fifo_finish = longest_path(local_ops, local_pred, local_succ)
        fifo_bound = max(fifo_finish.values(), default=0)
    multi = sorted(t for t in tensors if len(producers[t]) > 1)
    boundary = external | terminal
    return {
        "original_counts": {k: len(graph[k]) for k in ("ops", "tensors", "edges")},
        "eligible_ops": len(ops), "component_count": len(components), "pipe_work_cycles": work,
        "original_compute_critical_path_cycles": max(finish.values(), default=0),
        "multiple_eligible_producer_tensor_ids": multi,
        "external_input_count": len(external), "external_input_bytes": sum(tensors[t]["size"] for t in external),
        "external_input_component_fanout_histogram": dict(Counter(len({owner[u] for u in consumers[t]}) for t in external)),
        "external_input_op_fanout_histogram": dict(Counter(len(consumers[t]) for t in external)),
        "terminal_output_count": len(terminal), "terminal_output_bytes": sum(tensors[t]["size"] for t in terminal),
        "boundary_bytes": sum(tensors[t]["size"] for t in boundary),
        "boundary_rounded_work_at_frozen_bw60": sum(max(1, (tensors[t]["size"] + 59) // 60) for t in boundary),
        "largest_component_id": largest,
        "largest_component_natural_compute_fifo_relaxation_cycles": fifo_bound,
        "components": details,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    start = time.perf_counter()
    raw = args.graph.read_bytes()
    report = analyze(json.loads(raw))
    sources = ["src/q2_nikolastarx/component_envelope.py", "src/q2_nikolastarx/dag_direct.py",
               "src/q2_nikolastarx/direct.py", "data/raw/a/official/code/multicore_cut_evaluate_problem_2.py",
               "data/raw/a/official/code/schedule_step2.py", "data/raw/a/official/code/schedule_step3.py",
               "data/raw/a/official/data/config.txt"]
    report.update({
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": args.graph.as_posix(), "input_sha256": hashlib.sha256(raw).hexdigest(),
        "source_identity_kind": "actual working-tree file SHA-256; no Git commands or commit equivalence assertion",
        "source_file_sha256": {name: digest(ROOT / name) for name in sources},
        "diagnostic_script_sha256": digest(Path(__file__)),
        "benchmark_reference_only": "b7c05cf2205bd42ec23680e618a10796b37562f6",
        "scope": "static eligible graph and natural-priority diagnostics, no candidate constructed",
        "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
        "runtime_memory_certificate": False, "zero_spill_claim": False,
        "timing_caveat": "COPY work is an ideal service diagnostic, not a validated floating-event makespan bound",
        "static_wall_seconds": time.perf_counter() - start,
    })
    with args.output.open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({k: report[k] for k in ("eligible_ops", "component_count", "input_sha256", "calls")}))


if __name__ == "__main__":
    main()
