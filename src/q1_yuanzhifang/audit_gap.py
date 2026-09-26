"""Read fixed P1 k5 evidence and at most ten graphs; never construct or score.

Comparisons retain the uniform overload method's missing cases. Historical
bounded results are a separate comparator, not substituted into its scores.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import UTC, datetime
from fractions import Fraction
import csv
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time

from reuse_e import GitBlobs, raw_json, require, verify_official

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "results/a/q1-yuanzhifang/gap-audit-20260925"
NEW = "3c6e41b938c764d207de45584fb526c64f4eb845"
OLD = "05f8fa0f7e52f5914f14815f6bdbcb851b631556"
OLD_DATA = "f0dde725a047f1fb3bce03a30a3850d49b708463"
E4 = "e44ee4b55227e50d5e06ea725b1a3bae6c78cea2"
PROTOCOL = "5e626d869709578fbe4385e30709d7a2337e9aa9"
FEEDS = [
    ("overload-probe2", "new", "8f0009ac4a934c2161943b70530e418eb55f9366", "results/a/q1-overload-probe-20260925/20260924T1629Z-overload2/board-feed.json"),
    ("overload-activation16", "new", "8f0009ac4a934c2161943b70530e418eb55f9366", "results/a/q1-overload-activation-20260925/20260924T1636Z-overload16/board-feed.json"),
    ("overload-gapfill82", "new", "70036d6c1c098df2d61846473be137b3a294cdfb", "results/a/local-q1-overload-gapfill-20260925/20260924T1712Z-s59ee/board-feed-82.json"),
    ("bounded-matrix", "old", OLD_DATA, "results/a/q1-bounded-matrix-20260924/20260924T1459Z-bounded400/board-feed.json"),
    ("bounded-timeout-fill", "old", OLD_DATA, "results/a/q1-bounded-timeout-20260924/20260924T1524Z-timeout4/board-feed.json"),
]
# Frozen after the first read-only comparison: four regressions plus the six
# lowest-speedup unchanged successful cases. These are research diagnostics.
GRAPH_CASES = ("031", "032", "057", "077", "016", "024", "051", "044", "046", "090")
SUPPLEMENTS = (
    ("shared-input", "084168563b8d3f860a355a872e5dd336500bf4f0", "results/a/q1-shared-input-probe-20260925/20260924T1618Z-input3/board-feed.json", "288dd520caa5c7baaa1413e4021eb2d4221b6e66", "src/q1/shared_input_budget.py"),
    ("fork-C", "88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a", "results/a/q1-yuanzhifang/stage-c-20260924/board-feed-20260924T153000Z-stage-c.json", "0bf12cfe3164b155b02cc85896dabdfee72f9d37", "src/q1_yuanzhifang/fork_frontier.py"),
    ("guarded-G", "45fde88569b4ce877bda397ae32bc9a1b4abf082", "results/a/q1-yuanzhifang/stage-g-20260925/board-feed-20260924T175725Z-stage-g.json", "e29685da0268420f2d881246603763d6bf8baf5b", "src/q1_yuanzhifang/prefetch_frontier.py"),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def diagnostic_chain(value):
    chain = []
    keys = ("algorithm_id", "selected", "reason", "components", "compute_ops", "largest_component_ops", "tasks")
    while isinstance(value, dict):
        chain.append({k: value[k] for k in keys if k in value and not isinstance(value[k], (dict, list))})
        value = value.get("base")
    return chain


def check_record(blobs, commit, record, manifest, solver):
    expected = {f["path"]: f["sha256"] for f in manifest["files"]}
    case = record["case_id"]
    require(record["problem"] == "P1" and record["cores"] == 5 and record["solver_commit"] == solver, "Wrong algorithm/scenario")
    identity = record["identity"]
    for name, value in (("graph_sha256", expected[f"data/case_{case}.json"]),
                        ("config_sha256", expected["data/config.txt"]), ("official_sha256", manifest["official_code_hash"])):
        require(identity[name] == value, "Frozen identity mismatch")
        if record.get("baseline"):
            require(record["baseline"][name] == value, "Frozen denominator identity mismatch")
    require(record["evaluator"]["route"] == "E0", "Non-E0 evidence")
    cached, evidence, missing = {}, {}, set()

    def artifact(ref, parse=True, allow_missing=False):
        path = ref["path"]
        if path in missing:
            require(allow_missing, "Missing required artifact: " + path)
            return None
        if path not in cached:
            try:
                packed = blobs.read(commit, path)
            except ValueError as error:
                if not allow_missing or not str(error).startswith("Missing fixed blob"):
                    raise
                missing.add(path)
                evidence[path] = {"available": False, "expected_sha256": ref["sha256"],
                                  "reason": "Referenced auxiliary text log absent from fixed Git tree; not reconstructed or replaced"}
                return None
            require(sha(packed) == ref["sha256"], "Artifact hash mismatch: " + path)
            raw, value = raw_json(packed, path) if parse else (packed, None)
            cached[path] = (packed, raw, value)
            evidence[path] = {"available": True, "sha256": sha(packed), "raw_sha256": sha(raw), "stored_bytes": len(packed)}
        packed, raw, value = cached[path]
        require(sha(packed) == ref["sha256"], "Conflicting artifact hashes")
        if "raw_sha256" in ref:
            require(sha(raw) == ref["raw_sha256"], "Raw artifact hash mismatch")
        return value

    run = artifact(record["artifacts"]["run"])
    require(run["case_id"] == case and run["cores"] == 5 and run["status"] == record["status"], "Run identity/status mismatch")
    for name, value in (("graph_sha256", identity["graph_sha256"]), ("config_sha256", identity["config_sha256"]),
                        ("official_code_hash", identity["official_sha256"])):
        if name in run:
            require(run[name] == value, "Run frozen identity mismatch")
    for key, ref in record["artifacts"].items():
        artifact(ref, ref["path"].endswith((".json", ".json.gz")), allow_missing=key == "log")
    for key, ref in run.get("artifacts", {}).items():
        if isinstance(ref, dict) and "path" in ref and "sha256" in ref:
            artifact(ref, ref["path"].endswith((".json", ".json.gz")), allow_missing=key == "log")
    single = None
    if record.get("baseline"):
        single = artifact(record["baseline"]["result"])
        require(record["baseline"]["route"] == "E0" and record["baseline"]["entrypoint"] == "singlecore_evaluate.evaluate_singlecore", "Not official denominator")
        require(single["scene"] == "A" and single["num_cores"] == 1, "Wrong denominator scene")
    else:
        require(record["status"] != "ok", "Successful result without denominator")
    plan = artifact(record["artifacts"]["plan"]) if "plan" in record["artifacts"] else None
    if plan is not None:
        plan_hash = record["artifacts"]["plan"]["sha256"]
        require(set(plan) == {"node_to_subgraph", "core_schedules"} and len(plan["core_schedules"]) == 5, "Wrong plan schema")
        require(plan_hash == identity["plan_sha256"], "Plan identity mismatch")
        if "plan_sha256" in run:
            require(plan_hash == run["plan_sha256"], "Run plan mismatch")
    else:
        require(record["status"] == "not_run", "Attempt without plan")
    result = None
    if record["status"] == "ok":
        result = artifact(record["artifacts"]["result"])
        trace = artifact(record["artifacts"]["trace"])
        require(result["scene"] == "A" and result["num_cores"] == 5, "Wrong result scene")
        require(result["makespan"] == run["makespan_cycles"] == record["metrics"]["makespan_cycles"] > 0, "Makespan mismatch")
        require(result["data_movement_bytes"] == run["data_movement_bytes"], "Movement mismatch")
        for metric, field in (("ddr_bytes", "scheduled_copy_bytes"), ("extra_ddr_bytes", "added_copy_bytes"), ("spill_bytes", "spill_added_copy_bytes")):
            require(record["metrics"][metric] == result["data_movement_bytes"][field], "Feed movement mismatch")
        require(max(x["ts"] + x["dur"] for x in trace["traceEvents"] if x.get("ph") == "X") == result["makespan"], "Trace endpoint mismatch")
        require(max(t["end"] for c in result["per_core_timeline"] for t in c["tasks"]) == result["makespan"], "Timeline endpoint mismatch")
        evaluation = run["evaluation"]
        require(evaluation["status"] == "ok" and evaluation.get("returncode", evaluation.get("exit_code")) == 0, "E0 receipt not successful")
        require(run["calls"] == {"solver": 1, "E0": 1, "E1": 0, "E2": 0}, "Unexpected historical calls")
    else:
        require(record["metrics"]["makespan_cycles"] is None, "Failed result filled")
    for stage, metric in (("solver", "solver_wall_seconds"), ("evaluation", "evaluation_wall_seconds")):
        require(record["metrics"][metric] == run.get(stage, {}).get("wall_seconds"), "Historical wall mismatch")
    diagnostic_ref = run.get("artifacts", {}).get("diagnostics")
    diagnostic = artifact(diagnostic_ref) if diagnostic_ref else run.get("diagnostics", {})
    return {"case_id": case, "commit": commit, "attempt_id": record["attempt_id"], "status": record["status"],
            "identity": identity, "artifacts": record["artifacts"], "artifact_checks": evidence,
            "missing_auxiliary_logs": sorted(missing),
            "singlecore_cycles": single["makespan"] if single else None, "makespan_cycles": result["makespan"] if result else None,
            "movement": result["data_movement_bytes"] if result else None,
            "tasks_per_core": list(map(len, plan["core_schedules"])) if plan else None,
            "diagnostic_chain": diagnostic_chain(diagnostic),
            "split_components": diagnostic.get("split_components", []),
            "diagnostic_placement": diagnostic.get("placement"),
            "model_r_cycles": diagnostic.get("model_r_cycles"),
            "selected_active_cores": diagnostic.get("active_cores"),
            "evaluator_commit": record["evaluator"]["commit"],
            "historical_calls": run["calls"], "historical_solver_wall_seconds": record["metrics"]["solver_wall_seconds"],
            "historical_E0_wall_seconds": record["metrics"]["evaluation_wall_seconds"],
            "failure": record["provenance"]["measurement"]["failure"],
            "runtime_id": record["runtime_id"], "parameters": record["parameters"],
            "environment": record["provenance"]["environment"]}


def graph_stats(graph, plans):
    """Pure incidence/component statistics; no plan construction or Task compile."""
    all_ops = {o["id"]: o for o in graph["ops"]}
    ops = {u: o for u, o in all_ops.items() if o["op"] not in {"COPY_IN", "COPY_OUT"}}
    producers, consumers = defaultdict(set), defaultdict(set)
    full = {u: set() for u in all_ops}
    for e in graph["edges"]:
        u, v = e["source"], e["target"]
        if u in all_ops and v in all_ops:
            full[u].add(v)
        elif u in all_ops:
            producers[v].add(u)
        elif v in all_ops:
            consumers[u].add(v)
    for t, ps in producers.items():
        for p in ps:
            full[p].update(consumers[t] - {p})
    succ, pred = {u: set() for u in ops}, {u: set() for u in ops}
    for u in ops:
        stack, seen = list(full[u]), set()
        while stack:
            v = stack.pop()
            if v in seen:
                continue
            seen.add(v)
            if v in ops:
                succ[u].add(v); pred[v].add(u)
            else:
                stack.extend(full[v])
    unseen, components, owner = set(ops), [], {}
    while unseen:
        root = min(unseen); unseen.remove(root); stack, nodes = [root], []
        while stack:
            u = stack.pop(); nodes.append(u); owner[u] = root
            for v in (pred[u] | succ[u]) & unseen:
                unseen.remove(v); stack.append(v)
        work = Counter()
        for u in nodes:
            work[ops[u]["pipe"]] += max(1, ops[u]["cycles"])
        components.append({"anchor": root, "compute_ops": len(nodes), "pipe_work": dict(work),
                           "fork_nodes": sum(len(succ[u]) > 1 for u in nodes), "join_nodes": sum(len(pred[u]) > 1 for u in nodes),
                           "sinks": sum(not succ[u] for u in nodes)})
    external = [t for t in graph["tensors"] if not (producers[t["id"]] & ops.keys()) and (consumers[t["id"]] & ops.keys())]
    statistics_by_plan = {}
    for label, plan in plans.items():
        mapping = {int(u): t for u, t in plan["node_to_subgraph"].items()}
        core = {t: c for c, tasks in enumerate(plan["core_schedules"]) for t in tasks}
        dependencies = {(mapping[u], mapping[v]) for u in ops for v in succ[u] if mapping[u] != mapping[v]}
        copies = [(t["size"], len({mapping[u] for u in consumers[t["id"]] if u in mapping})) for t in external]
        statistics_by_plan[label] = {"tasks_per_core": list(map(len, plan["core_schedules"])),
                                     "cross_core_dependency_pairs": sum(core[a] != core[b] for a, b in dependencies),
                                     "task_dependency_pairs": len(dependencies),
                                     "same_core_sequence_edges": sum(max(0, len(q) - 1) for q in plan["core_schedules"]),
                                     "external_input_task_copy_bytes": sum(size * n for size, n in copies),
                                     "external_input_task_copies": sum(n for _, n in copies)}
    total_work = sum((Counter(c["pipe_work"]) for c in components), Counter())
    return {"compute_ops": len(ops), "tensors": len(graph["tensors"]), "edges": len(graph["edges"]),
            "contracted_compute_edges": sum(map(len, succ.values())), "components": components,
            "total_pipe_work": dict(total_work), "global_pipe_capacity_lower_bound_k5": max((v + 4) // 5 for v in total_work.values()),
            "weak_component_count": len(components), "fork_nodes": sum(len(v) > 1 for v in succ.values()),
            "join_nodes": sum(len(v) > 1 for v in pred.values()), "sinks": sum(not v for v in succ.values()),
            "external_input_unique_bytes": sum(t["size"] for t in external),
            "shared_external_input_tensors_across_components": sum(len({owner[u] for u in consumers[t["id"]] if u in owner}) > 1 for t in external),
            "plans": statistics_by_plan,
            "scope": "COPY-contracted adjacency used only for incidence/component/fork/sink statistics; no claimed compute critical-path lower bound through COPY bridges."}


def boundary_signature(graph, plan):
    """Count boundary COPY incidence; no reconstruction of Tasks or schedules."""
    mapping = {int(u): t for u, t in plan["node_to_subgraph"].items()}
    ops = {o["id"]: o for o in graph["ops"]}
    producers, consumers = defaultdict(set), defaultdict(set)
    for edge in graph["edges"]:
        u, v = edge["source"], edge["target"]
        if u in ops and v not in ops:
            producers[v].add(u)
        elif u not in ops and v in ops:
            consumers[u].add(v)
    signature = Counter()
    for tensor in graph["tensors"]:
        tid, size = tensor["id"], tensor["size"]
        ps = {mapping[u] for u in producers[tid] if u in mapping}
        cs = {mapping[u] for u in consumers[tid] if u in mapping}
        original_out = any(ops[u]["op"] == "COPY_OUT" for u in consumers[tid])
        if cs - ps:
            signature[(tid, "in", size)] += len(cs - ps)
        copies_out = sum(original_out or not cs or bool(cs - {p}) for p in ps)
        if copies_out:
            signature[(tid, "out", size)] += copies_out
    return signature


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphs", type=Path, required=True)
    args = parser.parse_args()
    begin, started = time.perf_counter(), datetime.now(UTC).isoformat().replace("+00:00", "Z")
    manifest_raw = (ROOT / "docs/a/source-manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    config_raw = (args.graphs / "config.txt").read_bytes()
    require(sha(config_raw) == next(f["sha256"] for f in manifest["files"] if f["path"] == "data/config.txt"), "Fixed configuration hash mismatch")
    source_facts, feeds, old, new, prior_failures = {}, [], {}, {}, []
    supplements, supplement_feeds, official_checked = {}, [], set()
    with GitBlobs() as blobs:
        for commit in (OLD, NEW):
            verify_official(blobs, commit, manifest)
            official_checked.add(commit)
        for name in ("component_overload", "heavy_suffix", "sink_peel", "bounded_tasks", "tree_frontier", "component_pack"):
            path = f"src/q1/{name}.py"
            source_facts[path] = {"commit": NEW, "sha256": sha(blobs.read(NEW, path))}
        source_facts["baseline_bounded_tasks"] = {"commit": OLD, "path": "src/q1/bounded_tasks.py", "sha256": sha(blobs.read(OLD, "src/q1/bounded_tasks.py"))}
        index_path = "results/a/q1-yuanzhifang/stage-e-4-20260925/evidence-index.json"
        index_raw = blobs.read(E4, index_path)
        require(sha(index_raw) == "b685923cb63ca3d20a3eb5929df17dc731f619fa027beab67b5e45afd9ef782d", "Changed sealed denominator index")
        singles = json.loads(index_raw)["singlecore"]
        for label, group, commit, path in FEEDS:
            raw = blobs.read(commit, path)
            rows = [r for r in json.loads(raw)["records"] if r["problem"] == "P1" and r["cores"] == 5]
            feeds.append({"label": label, "group": group, "commit": commit, "path": path, "sha256": sha(raw), "k5_status_counts": dict(Counter(r["status"] for r in rows))})
            for record in rows:
                facts = check_record(blobs, commit, record, manifest, NEW if group == "new" else OLD)
                facts["source_feed"] = label
                case = record["case_id"]
                canonical = singles[case]
                require(facts["singlecore_cycles"] in (None, canonical["makespan_cycles"]), "Official denominator changed")
                facts["singlecore_cycles"] = canonical["makespan_cycles"]
                facts["canonical_singlecore"] = canonical
                if group == "old" and facts["status"] != "ok":
                    prior_failures.append(facts)
                    continue
                target = new if group == "new" else old
                require(case not in target, "Duplicate successful/comparable cell")
                target[case] = facts
            print(json.dumps({"checked_feed": label, "k5_records": len(rows), "new_scoring_calls": 0}), flush=True)
        require(set(new) == set(old) == {f"{i:03d}" for i in range(1, 101)}, "Incomplete fixed source coverage")
        for case, entry in singles.items():
            run_raw = blobs.read(entry["commit"], entry["run"]["path"])
            require(sha(run_raw) == entry["run"]["sha256"], "Canonical denominator receipt changed")
            run = json.loads(run_raw)
            packed = blobs.read(entry["commit"], entry["result"]["path"])
            raw, result = raw_json(packed, entry["result"]["path"])
            require(sha(packed) == entry["result"]["sha256"] and sha(raw) == entry["result"]["raw_sha256"], "Canonical denominator bytes changed")
            require(run["status"] == "ok" and run["returncode"] == 0 and run["makespan_cycles"] == result["makespan"] == entry["makespan_cycles"], "Canonical denominator not successful")
        for label, commit, path, solver, source_path in SUPPLEMENTS:
            raw = blobs.read(commit, path)
            records = [r for r in json.loads(raw)["records"] if r["cores"] == 5 and
                       (label != "fork-C" or (r["case_id"] == "051" and r["variant"] == "chain-atomic-grain4"))]
            require(len(records) == (3 if label == "shared-input" else 1), "Supplement scope changed")
            supplement_feeds.append({"label": label, "commit": commit, "path": path, "sha256": sha(raw)})
            source_facts[label] = {"commit": solver, "path": source_path, "sha256": sha(blobs.read(solver, source_path))}
            supplements[label] = {}
            for record in records:
                facts = check_record(blobs, commit, record, manifest, solver)
                case = record["case_id"]
                require(case in GRAPH_CASES and facts["status"] == "ok" and facts["singlecore_cycles"] == singles[case]["makespan_cycles"], "Supplement identity/scope mismatch")
                reference = new[case]
                require(reference["status"] == "ok", "No paired overload reference")
                facts["overload_reference_cycles"] = reference["makespan_cycles"]
                facts["delta_speedup_vs_overload"] = float(Fraction(facts["singlecore_cycles"], facts["makespan_cycles"]) - Fraction(facts["singlecore_cycles"], reference["makespan_cycles"]))
                facts["uniform_algorithm_score_claim"] = False
                supplements[label][case] = facts
        for facts in [*old.values(), *new.values(), *prior_failures, *(f for group in supplements.values() for f in group.values())]:
            if facts["evaluator_commit"] not in official_checked:
                verify_official(blobs, facts["evaluator_commit"], manifest)
                official_checked.add(facts["evaluator_commit"])
        signature_path = "results/a/q1-yuanzhifang/stage-g-20260925/run/copy-signature-comparison.json"
        signature_raw = blobs.read(SUPPLEMENTS[-1][1], signature_path)
        signature_report = {"commit": SUPPLEMENTS[-1][1], "path": signature_path, "sha256": sha(signature_raw), "reported": json.loads(signature_raw)}
        comparisons, ratios, baseline_ratios = [], [], []
        for case in sorted(new):
            a, b = new[case], old[case]
            s = a["singlecore_cycles"]
            before, after = Fraction(s, b["makespan_cycles"]), Fraction(s, a["makespan_cycles"]) if a["status"] == "ok" else None
            delta = after - before if after is not None else None
            if delta is not None:
                ratios.append(after); baseline_ratios.append(before)
            plan_equal = None
            if "plan" in a["artifacts"]:
                plan_equal = blobs.read(a["commit"], a["artifacts"]["plan"]["path"]) == blobs.read(b["commit"], b["artifacts"]["plan"]["path"])
            comparisons.append({"case_id": case, "status": a["status"], "singlecore_cycles": s,
                                "bounded_cycles": b["makespan_cycles"], "overload_cycles": a["makespan_cycles"],
                                "bounded_speedup": float(before), "overload_speedup": float(after) if after is not None else None,
                                "delta_speedup": float(delta) if delta is not None else None,
                                "comparison": "unavailable" if delta is None else "win" if delta > 0 else "loss" if delta < 0 else "tie",
                                "bounded_extra_ddr_bytes": b["movement"]["added_copy_bytes"],
                                "overload_extra_ddr_bytes": a["movement"]["added_copy_bytes"] if a["movement"] else None,
                                "bounded_spill_bytes": b["movement"]["spill_added_copy_bytes"],
                                "overload_spill_bytes": a["movement"]["spill_added_copy_bytes"] if a["movement"] else None,
                                "bounded_task_count": sum(b["tasks_per_core"]), "overload_task_count": sum(a["tasks_per_core"]) if a["tasks_per_core"] else None,
                                "plan_bytes_equal": plan_equal, "selected": a["diagnostic_chain"][0].get("selected") if a["diagnostic_chain"] else None,
                                "bounded_solver_wall_seconds": b["historical_solver_wall_seconds"], "overload_solver_wall_seconds": a["historical_solver_wall_seconds"],
                                "bounded_attempt_id": b["attempt_id"], "overload_attempt_id": a["attempt_id"]})
        n = len(ratios)
        require(n == 94, "Unexpected evidence coverage")
        for row in comparisons:
            row["delta_common94_mean"] = row["delta_speedup"] / n if row["delta_speedup"] is not None else None
            row["delta_full100_known_contribution"] = row["delta_speedup"] / 100 if row["delta_speedup"] is not None else None
        completed = [r for r in comparisons if r["status"] == "ok"]
        top = sorted(completed, key=lambda r: (-abs(r["delta_speedup"]), r["case_id"]))[:10]
        structures = {}
        require(len(GRAPH_CASES) <= 10, "Graph-read cap")
        expected = {f["path"]: f["sha256"] for f in manifest["files"]}
        for case in GRAPH_CASES:
            raw = (args.graphs / f"case_{case}.json").read_bytes()
            require(sha(raw) == expected[f"data/case_{case}.json"], "Graph hash mismatch")
            plans = {label: json.loads(blobs.read(facts[case]["commit"], facts[case]["artifacts"]["plan"]["path"])) for label, facts in (("old", old), ("new", new))}
            for label, group in supplements.items():
                if case in group:
                    facts = group[case]
                    plans[label] = json.loads(blobs.read(facts["commit"], facts["artifacts"]["plan"]["path"]))
            graph = json.loads(raw)
            structures[case] = {"graph_sha256": sha(raw), **graph_stats(graph, plans)}
            if case == "051":
                signatures = {label: boundary_signature(graph, plans[label]) for label in ("fork-C", "guarded-G")}
                require(signatures["fork-C"] == signatures["guarded-G"], "C/G boundary multisets differ")
                sig = signatures["fork-C"]
                require(sum(sig.values()) == 1003 and sum(k[2] * n for k, n in sig.items()) == 9438614, "C/G COPY counts/bytes drifted")
                signature_report["independent_incidence_check"] = {"equal": True, "count_each": sum(sig.values()),
                    "bytes_each": sum(k[2] * n for k, n in sig.items()),
                    "multiset_sha256": sha(json.dumps(sorted([*k, n] for k, n in sig.items()), separators=(",", ":")).encode()),
                    "method": "Direct tensor producer/consumer Task-set incidence from this one graph read and fixed C/G plan bytes; no Task compiler; signature excludes Task id and time"}
                require(signature_report["reported"]["model_r_cycles"]["stage_g"] == supplements["guarded-G"]["051"]["model_r_cycles"], "G R receipt mismatch")
    summary = {"successful_common_cases": n, "expected_cases": 100, "new_status_counts": dict(Counter(r["status"] for r in comparisons)),
               "new_full100_mean": None, "new_common94_mean": float(sum(ratios) / n),
               "old_common94_mean": float(sum(baseline_ratios) / n), "difference_common94_mean": float((sum(ratios) - sum(baseline_ratios)) / n),
               "old_full100_mean": float(sum(Fraction(f["singlecore_cycles"], f["makespan_cycles"]) for f in old.values()) / 100),
               "comparison_counts": dict(Counter(r["comparison"] for r in comparisons)),
               "top10_absolute_contribution_cases": [r["case_id"] for r in top],
               "all_regressions": [r for r in completed if r["comparison"] == "loss"],
               "missing": [r for r in comparisons if r["status"] != "ok"],
               "negative_delta_sum": sum(r["delta_speedup"] for r in completed if r["delta_speedup"] < 0),
               "top10_delta_sum": sum(r["delta_speedup"] for r in top),
               "new_extra_ddr_common94_sum": sum(r["overload_extra_ddr_bytes"] for r in completed),
               "old_extra_ddr_common94_sum": sum(r["bounded_extra_ddr_bytes"] for r in completed),
               "source_call_totals_new": {k: sum(v["historical_calls"][k] for v in new.values()) for k in ("solver", "E0", "E1", "E2")},
               "missing_auxiliary_log_count_new": sum(len(v["missing_auxiliary_logs"]) for v in new.values()),
               "audit_calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0, "Task_compile": 0},
               "graph_cases_read": list(GRAPH_CASES), "historical_best_combination_mean": None,
               "scope": "Existing evidence for a fixed algorithm across three different external-evaluation budgets. Common-success-set diagnostic comparison, not full-matrix acceptance, historical winner assembly or controlled solver-speed experiment."}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, rows in (("comparison.csv", comparisons), ("top10-contributions.csv", top)):
        with (OUTPUT / filename).open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    dump(OUTPUT / "summary.json", summary)
    dump(OUTPUT / "evidence.json", {"feeds": feeds, "solver_sources": source_facts, "new": new, "old": old, "prior_bounded_failed_attempts": prior_failures})
    dump(OUTPUT / "structures.json", structures)
    dump(OUTPUT / "supplement.json", {"feeds": supplement_feeds, "facts": supplements, "C_G_copy_signature": signature_report,
                                     "scope": "Different algorithms on exposed development cases; individual diagnostic gaps only, no historical combination mean or uniform algorithm claim"})
    dump(OUTPUT / "metadata.json", {"started_at": started, "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                                    "wall_seconds": time.perf_counter() - begin, "audit_source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                                    "audit_source_sha256": sha(Path(__file__).read_bytes()), "protocol_commit_read": PROTOCOL,
                                    "manifest_sha256": sha(manifest_raw), "config_sha256": sha(config_raw),
                                    "dependency_lock_sha256": sha((ROOT / "uv.lock").read_bytes()),
                                    "command": "<reused-locked-python> -X utf8 -B src/q1_yuanzhifang/audit_gap.py --graphs <existing-official-data-directory>",
                                    "preflight": "AST parse and 11 evidence-schema checks across all feeds and all recorded statuses; 0 raw graph reads and 0 scoring calls",
                                    "official_code_commits_verified": sorted(official_checked),
                                    "os": platform.platform(), "python": platform.python_version(), "new_solver": NEW, "old_solver": OLD,
                                    "session": "yuanzhifang30-sudo/s-0e4f42cad8a647f18ea653130e34c5a9",
                                    "session_registration": "https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5818024851",
                                    "context": "continue; parent delegated zero-score gap audit after sealed E4; only audit_gap.py and this output directory are writable",
                                    "mailbox": {"fetch_complete": True, "topics_fetched": 6, "comments_fetched": 466, "issue98_read_through": 5819253048, "public_notice_read": 5819178999, "other_topic_histories_not_imported": [5, 15, 33, 51]},
                                    "graph_reads": len(GRAPH_CASES), "graph_choice": "Four regressions plus six lowest unchanged successful ratios from preliminary fixed-evidence readback; post hoc diagnostic sample, not a benchmark",
                                    "new_calls": summary["audit_calls"], "new_checkout_or_raw_graph_copy": False,
                                    "limits": "No solver, E0/E1/E2, Task compilation, plan generation, full raw-graph scan, score filling, production board mutation or algorithm changes."})
    print(json.dumps({k: summary[k] for k in ("successful_common_cases", "new_common94_mean", "old_common94_mean", "comparison_counts", "graph_cases_read", "audit_calls")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
