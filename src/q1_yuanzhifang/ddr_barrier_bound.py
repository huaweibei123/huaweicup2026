"""Guarded universal cut-or-blocking certificate for repeated fork/join graphs.

This is a lower bound for arbitrary legal Task partitions of the checked graph,
not a candidate generator or simulator. See DDR_BARRIER_BOUND.md for the proof
and source assumptions. The original Pro lemma is tightened using actual leaf
to root reduction distances instead of a single ADD.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from math import ceil
from pathlib import Path

from construct import OFFICIAL, _build_op_adjacency, topo
from star_frontier import guarded_stages
from multicore_cut_evaluate_problem_1 import _original_tensor_views, read_scene_a_config
from evaluation_validation import read_bandwidth_config


def certificate(graph, bandwidth, waits):
    if bandwidth <= 0:
        raise ValueError("bandwidth must be positive")
    same = waits["task_same_core_wait_cycles"]
    cross = waits["task_cross_core_wait_cycles"]
    if same < 0 or cross < same:
        return {"supported": False, "reason": "require nonnegative same wait <= cross wait"}
    guarded, reason = guarded_stages(graph)
    if guarded is None:
        return {"supported": False, "reason": reason}
    ops = {o["id"]: o for o in graph["ops"]}
    sizes = {t["id"]: t["size"] for t in graph["tensors"]}
    producers, _, _ = _original_tensor_views(graph)
    inputs = defaultdict(set)
    for edge in graph["edges"]:
        if edge["source"] in sizes and edge["target"] in ops:
            inputs[edge["target"]].add(edge["source"])
    external = defaultdict(list)
    internal = []
    stage_inputs = []
    for entry in guarded["rounds"]:
        current = []
        for chain in entry["chains"]:
            candidates = [t for t in inputs[chain[0]] if sizes[t] > 0 and producers[t]
                          and all(ops[u]["op"] == "COPY_IN" for u in producers[t])]
            if len(candidates) != 1:
                return {"supported": False, "reason": "each chain needs exactly one distinct original COPY_IN tensor"}
            tensor = candidates[0]
            current.append(tensor)
            external[tensor].append(chain[0])
            for u, v in zip(chain, chain[1:]):
                matches = [t for t in inputs[v] if producers[t] == {u} and sizes[t] == sizes[tensor]]
                if len(matches) != 1:
                    return {"supported": False, "reason": "internal chain link must carry one equal-size private tensor"}
                internal.append({"tensor": matches[0], "producer": u, "consumer": v})
        if len(set(current)) != 12:
            return {"supported": False, "reason": "twelve chains must have distinct original inputs"}
        stage_inputs.append(set(current))
    if any(s != stage_inputs[0] for s in stage_inputs):
        return {"supported": False, "reason": "rounds must reuse the same twelve original inputs"}
    all_internal = {x["tensor"] for x in internal}
    if len(all_internal) != len(internal) or all_internal.intersection(external):
        return {"supported": False, "reason": "private chain tensor identities are not disjoint"}
    input_sizes = {sizes[t] for t in external}
    if len(input_sizes) != 1:
        return {"supported": False, "reason": "equal original input sizes required"}
    size = next(iter(input_sizes))
    work = max(1, ceil(size / bandwidth))
    p = guarded["heavy_cycles"]
    length, width = 4 * p, 12
    # These sufficient inequalities yield the coefficient p on every carried
    # full chain or nonempty prefix. Reject rather than extend the theorem.
    if not p <= work <= 2 * p:
        return {"supported": False, "reason": "joint coefficient requires p <= COPY work <= 2p"}
    _, full_succ = _build_op_adjacency(graph)
    stages = []
    for index, entry in enumerate(guarded["rounds"]):
        tail = set(entry["tail"])
        succ = {u: full_succ[u] & tail for u in tail}
        distance = {}
        for u in reversed(topo(tail, succ)):
            distance[u] = max(1, ops[u]["cycles"]) + max((distance[v] for v in succ[u]), default=0)
        depths = [distance[next(iter(full_succ[chain[-1]] & tail))] for chain in entry["chains"]]
        tail_min = min(depths)
        base = width * work + length + tail_min
        epoch = base + same
        if width * length < epoch + width * p:
            return {"supported": False, "reason": "all-carried case does not imply the joint coefficient"}
        stages.append({"stage": entry["stage"], "root": entry["root"],
                       "minimum_reduction_path_cycles": tail_min, "leaf_reduction_path_cycles": depths,
                       "root_interval_lower_bound_cycles": base if index == 0 else epoch})
    lower = sum(s["root_interval_lower_bound_cycles"] for s in stages)
    return {"supported": True, "reason": "all structural and numerical guards passed",
            "proof_status": "candidate theorem; independent proof audit pending",
            "rounds": len(stages), "chains_per_round": width, "chain_nodes": 4,
            "heavy_cycles": p, "chain_cycles": length, "input_bytes": size,
            "input_copy_service_cycles": work, "minimum_task_gate_cycles": same,
            "universal_makespan_lower_bound_cycles": lower,
            "original_input_task_pairs_max": width * len(stages),
            "joint_carried_coefficient_cycles": p,
            "joint_formula": "max(universal_LB + p * (12 * rounds - M), copy_service * (M + 2 * B))",
            "stages": stages,
            "original_inputs": [{"tensor": t, "first_ops": sorted(nodes)} for t, nodes in sorted(external.items())],
            "private_internal_links": internal,
            "scope": "Any legal Task partition/core assignment/order of this guarded graph, conditional on the audited frozen P1 boundary COPY, gate, compute-dependency and unit DDR-capacity semantics. No optimality or attainability claim."}


def plan_terms(cert, plan):
    if not cert["supported"]:
        raise ValueError("need a supported graph certificate")
    mapping = {int(u): task for u, task in plan["node_to_subgraph"].items()}
    pairs = sum(len({mapping[u] for u in x["first_ops"]}) for x in cert["original_inputs"])
    cuts = sum(mapping[x["producer"]] != mapping[x["consumer"]] for x in cert["private_internal_links"])
    blocking = cert["universal_makespan_lower_bound_cycles"] + cert["joint_carried_coefficient_cycles"] * (cert["original_input_task_pairs_max"] - pairs)
    ddr = cert["input_copy_service_cycles"] * (pairs + 2 * cuts)
    return {"M": pairs, "B": cuts, "blocking_lower_bound_cycles": blocking,
            "large_COPY_lower_bound_cycles": ddr, "joint_lower_bound_cycles": max(blocking, ddr),
            "plan_legality_checked": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--config", type=Path, default=OFFICIAL / "data/config.txt")
    parser.add_argument("--plan", type=Path)
    args = parser.parse_args()
    raw, config = args.graph.read_bytes(), args.config.read_bytes()
    result = certificate(json.loads(raw), read_bandwidth_config(str(args.config)), read_scene_a_config(str(args.config)))
    result["graph_sha256"] = hashlib.sha256(raw).hexdigest()
    result["config_sha256"] = hashlib.sha256(config).hexdigest()
    result["source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if args.plan and result["supported"]:
        plan = args.plan.read_bytes()
        result["fixed_plan_terms"] = plan_terms(result, json.loads(plan))
        result["plan_sha256"] = hashlib.sha256(plan).hexdigest()
    with args.output.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write("\n")
    print(json.dumps({k: result.get(k) for k in ("supported", "reason", "universal_makespan_lower_bound_cycles", "fixed_plan_terms")}))


if __name__ == "__main__":
    main()
