"""Q1 direct in-tree frontier packing with a separate reduction tail Task.

For a COPY-contracted DAG with outdegree <= 1, subtree sets never overlap
unless nested. Maximal subtrees below total compute work / K form an antichain.
Their unions are independent worker Tasks; all residual operations form one
tail Task. Every crossing edge points from a worker into the tail. Graphs not
matching this structure use the frozen component-pack construction mechanism.
No scoring, evaluation or search occurs online.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1.component_pack import construct as component_construct  # noqa: E402
from stub_multicore_cut_and_schedule import (  # noqa: E402
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)
from evaluation_validation import validate_task_order  # noqa: E402


def construct(graph: dict, cores: int, packet_factor: int = 1) -> tuple[dict, dict]:
    if type(packet_factor) is not int or not 1 <= packet_factor <= 64:
        raise ValueError("packet_factor must be an integer in 1..64")
    # Also validates the graph/domain; its plan is the deterministic fallback.
    fallback, base = component_construct(graph, cores)
    info = {"algorithm_id": "q1-tree-frontier-pack", "variant": "threshold-antichain-tail",
            "packet_factor": packet_factor, "base": base, "selected": "component-pack",
            "scope": "Structural proof only; E0 required"}
    if cores == 1 or base["components"] >= cores:
        info["reason"] = "enough independent components or one core"
        return fallback, info
    ops = {o["id"]: o for o in graph["ops"] if o["op"] not in {"COPY_IN", "COPY_OUT"}}
    _, full = _build_op_adjacency(graph)
    pred, succ = _contract_excluded_copy_nodes(sorted(ops), full)
    if any(len(succ[u]) > 1 for u in ops):
        info["reason"] = "not an in-tree forest"
        return fallback, info
    indegree = {u: len(pred[u]) for u in ops}
    ready = deque(sorted(u for u in ops if not indegree[u]))
    order = []
    mass = {u: ops[u]["cycles"] for u in ops}
    while ready:
        u = ready.popleft()
        order.append(u)
        for v in succ[u]:
            mass[v] += mass[u]
            indegree[v] -= 1
            if not indegree[v]:
                ready.append(v)
    if len(order) != len(ops):
        raise ValueError("Cyclic compute graph")
    total = sum(o["cycles"] for o in ops.values())
    if total == 0:
        info["reason"] = "zero work"
        return fallback, info
    # Integer comparisons avoid float rounding at the frontier boundary.
    divisor = cores * packet_factor
    # Finer antichains reduce indivisible bin sizes at the cost of more
    # boundary copies/tail work. Never demand a packet smaller than one op.
    threshold_numerator = max(total, max(o["cycles"] for o in ops.values()) * divisor)
    roots = [u for u in order if mass[u] * divisor <= threshold_numerator and
             (not succ[u] or mass[next(iter(succ[u]))] * divisor > threshold_numerator)]
    packets, covered = [], set()
    for root in roots:
        stack, members, loads = [root], [], Counter()
        while stack:
            u = stack.pop()
            if u in covered:
                raise AssertionError("Selected subtrees must be disjoint")
            covered.add(u)
            members.append(u)
            loads[ops[u]["pipe"]] += ops[u]["cycles"]
            stack.extend(sorted(pred[u], reverse=True))
        packets.append((members, loads, root))
    tail = set(ops) - covered
    # A single packet gives no independent work; leave such chains untouched.
    if len(packets) < 2 or not tail:
        info["reason"] = "no useful multi-branch frontier"
        return fallback, info
    packets.sort(key=lambda p: (-max(p[1].values()), -sum(p[1].values()), p[2]))
    loads, counts = [Counter() for _ in range(cores)], [0] * cores
    mapping, root_core = {}, {}
    for nodes, work, root in packets:
        def key(k):
            after = [loads[k][p] + work[p] for p in loads[k].keys() | work.keys()]
            return max(after), sum(after), counts[k], k
        core = min(range(cores), key=key)
        for u in nodes:
            mapping[u] = core
        root_core[root] = core
        loads[core].update(work)
        counts[core] += len(nodes)
    # Approximate the slowest worker's core to avoid its remote wait at the
    # final gate. This is an explicit heuristic, not an exact timing claim.
    tail_core = max(range(cores), key=lambda k: (max(loads[k].values(), default=0),
                                               sum(loads[k].values()), -k))
    for u in tail:
        mapping[u] = cores
    schedules = [[k] if counts[k] else [] for k in range(cores)]
    schedules[tail_core].append(cores)
    plan = {"node_to_subgraph": {u: mapping[u] for u in ops}, "core_schedules": schedules}
    view = derive_multicore_plan(graph, plan)
    validate_task_order(view)
    if any(v != cores or u == cores for u, v in view["dependency_pairs"]):
        raise AssertionError("All crossing edges must enter the tail Task")
    info.update(selected="tree-frontier", frontier_roots=sorted(roots),
                frontier_packet_count=len(packets), tail_ops=len(tail), tail_core=tail_core,
                tail_work_by_pipe=dict(Counter({p: sum(ops[u]["cycles"] for u in tail if ops[u]["pipe"] == p)
                                               for p in {ops[u]["pipe"] for u in tail}})),
                core_frontier_ops=counts, root_core=root_core, tasks=len(view["subgraph_ids"]))
    return plan, info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--packet-factor", type=int, default=1)
    parser.add_argument("--diagnostics", type=Path)
    args = parser.parse_args()
    if args.output.exists() or (args.diagnostics and args.diagnostics.exists()):
        raise FileExistsError("Refuse to overwrite experiment artifacts")
    plan, info = construct(json.loads(args.graph.read_text()), args.cores, args.packet_factor)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as f:
        json.dump(plan, f, separators=(",", ":"))
        f.write("\n")
    if args.diagnostics:
        args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
        with args.diagnostics.open("x") as f:
            json.dump(info, f, indent=2)
            f.write("\n")
    print(json.dumps(info))


if __name__ == "__main__":
    main()
