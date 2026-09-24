"""Split a dominant weak component into coarse sink-exclusive waves for P1.

Component count is not parallel work. This candidate activates when a single
component owns >=80% of the dominant compute pipe's work despite having enough
components for every core. Minor components remain whole in the final wave.
No scorer is called, and neither the trigger nor peeling is a quality bound.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1.sink_peel import construct as sink_construct, peel_packets, PeelBudgetExceeded
from stub_multicore_cut_and_schedule import (
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)
from evaluation_validation import validate_task_order


def construct(graph, cores, *, dominant_percent=80, max_rounds=64, max_sinks=64):
    if type(dominant_percent) is not int or not 1 <= dominant_percent <= 100:
        raise ValueError("dominant_percent must be an integer in 1..100")
    fallback, base = sink_construct(graph, cores, max_rounds=max_rounds, max_sinks=max_sinks)
    info = {"algorithm_id": "q1-heavy-component-suffix", "variant": "dominant-pipe-suffix-waves",
            "selected": "sink-or-bounded", "dominant_percent": dominant_percent,
            "max_rounds": max_rounds, "max_sinks": max_sinks, "base": base,
            "scope": "Structural candidate; neither dominance nor zero spill proves quality"}
    if cores == 1 or base["base"]["base"]["base"]["components"] < cores:
        info["reason"] = "retain earlier single-core or component-scarce route"
        return fallback, info
    ops = {op["id"]: op for op in graph["ops"] if op["op"] not in {"COPY_IN", "COPY_OUT"}}
    _, full = _build_op_adjacency(graph)
    pred, succ = _contract_excluded_copy_nodes(sorted(ops), full)
    unseen, components = set(ops), []
    for root in sorted(ops):
        if root not in unseen:
            continue
        unseen.remove(root)
        stack, members = [root], []
        while stack:
            u = stack.pop()
            members.append(u)
            for v in pred[u] | succ[u]:
                if v in unseen:
                    unseen.remove(v)
                    stack.append(v)
        components.append(sorted(members))
    work = []
    total = Counter()
    for members in components:
        counts = Counter()
        for u in members:
            counts[ops[u]["pipe"]] += max(1, ops[u]["cycles"])
        work.append(counts)
        total.update(counts)
    dominant_pipe = min(total, key=lambda pipe: (-total[pipe], pipe))
    index = min(range(len(components)),
                key=lambda i: (-work[i][dominant_pipe], components[i][0]))
    info.update(components=len(components), dominant_pipe=dominant_pipe,
                total_pipe_work=dict(total), heavy_pipe_work=dict(work[index]),
                heavy_anchor=components[index][0], heavy_ops=len(components[index]))
    if 100 * work[index][dominant_pipe] < dominant_percent * total[dominant_pipe]:
        info["reason"] = "no dominant component"
        return fallback, info
    heavy = set(components[index])
    heavy_pred = {u: pred[u] & heavy for u in heavy}
    heavy_succ = {u: succ[u] & heavy for u in heavy}
    try:
        waves = peel_packets(heavy, heavy_pred, heavy_succ,
                             max_rounds=max_rounds, max_sinks=max_sinks)
    except PeelBudgetExceeded as exc:
        info["reason"] = str(exc)
        return fallback, info
    if not any(len(wave) > 1 for wave in waves):
        info["reason"] = "dominant component has no independent suffix packets"
        return fallback, info
    # Minor components have no compute edges to the heavy component or to
    # one another. Adding whole packets to the final wave cannot create a
    # backward edge. It can still delay completion or increase local pressure.
    waves[-1] = waves[-1] + [c for i, c in enumerate(components) if i != index]
    mapping, phase_of, schedules, details = {}, {}, [[] for _ in range(cores)], []
    next_task = 0
    for phase, wave in enumerate(waves):
        packets = []
        for nodes in wave:
            w = Counter()
            for u in nodes:
                w[ops[u]["pipe"]] += max(1, ops[u]["cycles"])
            packets.append((nodes, w))
        packets.sort(key=lambda x: (-max(x[1].values()), -sum(x[1].values()), x[0][0]))
        loads, bins = [Counter() for _ in range(cores)], [[] for _ in range(cores)]
        for nodes, w in packets:
            def choice(c):
                after = [loads[c][p] + w[p] for p in loads[c].keys() | w.keys()]
                return max(after), sum(after), len(bins[c]), c
            core = min(range(cores), key=choice)
            loads[core].update(w)
            bins[core].extend(nodes)
        for core, nodes in enumerate(bins):
            if nodes:
                schedules[core].append(next_task)
                for u in nodes:
                    mapping[u], phase_of[u] = next_task, phase
                next_task += 1
        details.append({"packets": len(wave), "packet_ops": sorted(map(len, wave)),
                        "core_ops": list(map(len, bins)),
                        "pipe_work_by_core": [dict(sorted(x.items())) for x in loads]})
    for u in ops:
        for v in succ[u]:
            if mapping[u] != mapping[v] and phase_of[u] >= phase_of[v]:
                raise AssertionError("Every inter-Task edge must advance a wave")
    plan = {"node_to_subgraph": {u: mapping[u] for u in ops}, "core_schedules": schedules}
    validate_task_order(derive_multicore_plan(graph, plan))
    info.update(selected="heavy-suffix", reason="dominant multi-sink component",
                wave_count=len(waves), tasks=next_task, waves=details,
                minor_components=len(components)-1,
                minor_ops=len(ops)-len(heavy), minor_placement="whole packets in final wave")
    return plan, info


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("graph", type=Path)
    p.add_argument("--cores", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--diagnostics", type=Path)
    p.add_argument("--dominant-percent", type=int, default=80)
    p.add_argument("--max-rounds", type=int, default=64)
    p.add_argument("--max-sinks", type=int, default=64)
    a = p.parse_args()
    if a.output.exists() or (a.diagnostics and a.diagnostics.exists()):
        raise FileExistsError("Refuse to overwrite experiment artifacts")
    plan, d = construct(json.loads(a.graph.read_text()), a.cores,
                        dominant_percent=a.dominant_percent,
                        max_rounds=a.max_rounds, max_sinks=a.max_sinks)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x") as f:
        json.dump(plan, f, separators=(",", ":")); f.write("\n")
    if a.diagnostics:
        a.diagnostics.parent.mkdir(parents=True, exist_ok=True)
        with a.diagnostics.open("x") as f:
            json.dump(d, f, indent=2); f.write("\n")
    print(json.dumps(d))


if __name__ == "__main__":
    main()
