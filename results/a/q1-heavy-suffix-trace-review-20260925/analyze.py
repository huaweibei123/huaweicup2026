"""Read sealed artifacts; reconstruct boundary metadata only, never Task compilation.

Run from a checkout containing the source commit. No solver/evaluator imports.
"""
from collections import Counter, defaultdict
import gzip
import hashlib
import heapq
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCE = "fe67740a90857e127c5d3996d1c444a083efcebc"
PREFIX = "results/a/q1-heavy-suffix-20260924/20260924T1556Z-heavy2/"


def digest(b):
    return hashlib.sha256(b).hexdigest()


def source(path):
    b = subprocess.check_output(["git", "show", SOURCE + ":" + PREFIX + path], cwd=ROOT)
    return json.loads(gzip.decompress(b) if path.endswith(".gz") else b), digest(b)


def longest(weights, edges):
    pred = {u: {} for u in weights}
    succ = {u: set() for u in weights}
    for a, b, lag in edges:
        pred[b][a] = max(pred[b].get(a, 0), lag)
        succ[a].add(b)
    degree = {u: len(pred[u]) for u in weights}
    ready = [u for u in weights if not degree[u]]
    heapq.heapify(ready)
    starts, ends, previous = {}, {}, {}
    while ready:
        u = heapq.heappop(ready)
        best = max(((ends[v] + lag, v) for v, lag in pred[u].items()), default=(0, None))
        starts[u], previous[u] = best
        ends[u] = starts[u] + weights[u]
        for v in sorted(succ[u]):
            degree[v] -= 1
            if not degree[v]:
                heapq.heappush(ready, v)
    assert len(ends) == len(weights), "DAG certificate failed"
    final = max(ends, key=lambda u: (ends[u], u))
    path = []
    u = final
    while u is not None:
        v = previous[u]
        path.append({"node": u, "weight": weights[u], "incoming_lag": pred[u][v] if v is not None else 0})
        u = v
    return {"value": ends[final], "path": list(reversed(path)), "starts": starts, "ends": ends}


def busy(intervals):
    merged = []
    for a, b in sorted(intervals):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return sum(b - a for a, b in merged)


def analyze(case, archive, bounds):
    base = f"cells/{case}/k5/"
    files = ["run.json", f"case_{case}_multicore_res.json", "diagnostics.json", "result.json.gz", "trace.json.gz"]
    docs = {f: source(base + f) for f in files}
    run, plan, diag, result, trace = [docs[f][0] for f in files]
    for key, filename in [("plan", files[1]), ("diagnostics", files[2]), ("result", files[3]), ("trace", files[4])]:
        assert docs[filename][1] == run["artifacts"][key]["sha256"]
    raw = archive.read(f"data/case_{case}.json")
    assert digest(raw) == run["graph_sha256"]
    graph = json.loads(raw)
    ops = {x["id"]: x for x in graph["ops"]}
    tensors = {x["id"]: x for x in graph["tensors"]}
    mapping = {int(u): t for u, t in plan["node_to_subgraph"].items()}
    compute = set(mapping)
    assert compute == {u for u, op in ops.items() if op["op"] not in {"COPY_IN", "COPY_OUT"}}
    producers, consumers = defaultdict(set), defaultdict(set)
    fullsucc, fullpred = defaultdict(set), defaultdict(set)
    direct = []
    for edge in graph["edges"]:
        a, b = edge["source"], edge["target"]
        if a in ops and b in tensors:
            producers[b].add(a)
        elif a in tensors and b in ops:
            consumers[a].add(b)
        elif a in ops and b in ops and a != b:
            direct.append((a, b))
    for a, b in direct + [(a, b) for t in tensors for a in producers[t] for b in consumers[t]]:
        fullsucc[a].add(b)
        fullpred[b].add(a)
    # Contract only COPY nodes to recover component membership, not operation CP.
    succ = {u: set() for u in compute}
    for u in compute:
        stack, seen = list(fullsucc[u]), set()
        while stack:
            v = stack.pop()
            if v in seen:
                continue
            seen.add(v)
            if v in compute:
                succ[u].add(v)
            else:
                stack.extend(fullsucc[v])
    adj = {u: set(succ[u]) for u in compute}
    for u in compute:
        for v in succ[u]:
            adj[v].add(u)
    heavy, stack = set(), [diag["heavy_anchor"]]
    while stack:
        u = stack.pop()
        if u not in heavy:
            heavy.add(u)
            stack.extend(adj[u] - heavy)
    assert len(heavy) == diag["heavy_ops"]
    remaining = compute - heavy
    task_ops = defaultdict(set)
    for u, t in mapping.items():
        task_ops[t].add(u)
    timeline = {t["task_id"]: {**t, "core": c["core_id"]} for c in result["per_core_timeline"] for t in c["tasks"]}
    phase_of = {}
    next_task = 0
    for phase, wave in enumerate(diag["waves"]):
        for core, count in enumerate(wave["core_ops"]):
            if count:
                assert timeline[next_task]["core"] == core
                phase_of[next_task] = phase
                next_task += 1
    assert len(phase_of) == len(timeline)
    events = [e for e in trace["traceEvents"] if e.get("ph") == "X" and e.get("cat", "").startswith("PIPE_")]
    bytask = defaultdict(list)
    for e in events:
        bytask[e["args"]["task_id"]].append(e)
    # Pure metadata reproduction of official _build_scene_a_tasks lines 86-164.
    next_op, next_tensor = max(ops) + 1, max(max(tensors), 10000) + 1
    used = set(ops) | set(tensors)
    copies, task_edges = {}, {}
    bw = result["bandwidth_bytes_per_cycle"]
    for task in sorted(task_ops):
        members = task_ops[task]
        edges = {(a, b, 0) for a, b in direct if a in members and b in members}
        for tid in sorted(tensors):
            lp, lc = producers[tid] & members, consumers[tid] & members
            if not (lp or lc):
                continue
            edges.update((a, b, 0) for a in lp for b in lc)
            eligible_consumers = consumers[tid] & compute
            copy_out = any(ops[u]["op"] == "COPY_OUT" for u in consumers[tid])
            kinds = []
            if lc and not lp:
                kinds.append("COPY_IN")
            if lp and (copy_out or not eligible_consumers or eligible_consumers - members):
                kinds.append("COPY_OUT")
            for kind in kinds:
                while next_tensor in used:
                    next_tensor += 1
                used.add(next_tensor)
                next_tensor += 1
                while next_op in used:
                    next_op += 1
                u = next_op
                used.add(u)
                next_op += 1
                n = tensors[tid]["size"]
                copies[u] = {"task": task, "kind": kind, "tensor": tid, "bytes": n,
                             "service": max(1, (n + bw - 1) // bw),
                             "pipe": "PIPE_MTE2" if kind == "COPY_IN" else "PIPE_MTE3"}
                if kind == "COPY_IN":
                    edges.update((u, b, 0) for b in lc)
                else:
                    edges.update((a, u, 0) for a in lp)
        task_edges[task] = edges
    trace_copies = {e["args"]["op_id"] for e in events if e["name"].startswith("COPY_")}
    assert trace_copies == set(copies)
    assert {x["issued"]["op_id"] for x in result["ddr_contention_log"]} == trace_copies
    assert sum(x["bytes"] for x in copies.values()) == result["data_movement_bytes"]["scheduled_copy_bytes"]
    assert result["data_movement_bytes"]["spill_added_copy_bytes"] == 0
    rows = []
    for task in sorted(task_ops):
        ev = bytask[task]
        actual_ids = {e["args"]["op_id"] for e in ev}
        own_copies = {u: x for u, x in copies.items() if x["task"] == task}
        assert actual_ids == task_ops[task] | set(own_copies)
        weights = {u: max(1, ops[u]["cycles"]) for u in task_ops[task]}
        weights.update({u: x["service"] for u, x in own_copies.items()})
        work, heavy_work, remaining_work = Counter(), Counter(), Counter()
        for u in task_ops[task]:
            work[ops[u]["pipe"]] += weights[u]
            (heavy_work if u in heavy else remaining_work)[ops[u]["pipe"]] += weights[u]
        ordinary_cp = longest(weights, task_edges[task])["value"]
        fifo = set(task_edges[task])
        for pipe in {e["cat"] for e in ev}:
            seq = sorted((e["ts"], e["args"]["op_id"]) for e in ev if e["cat"] == pipe)
            fifo.update((a[1], b[1], 0) for a, b in zip(seq, seq[1:]))
        fifo_cp = longest(weights, fifo)["value"]
        service = sum(x["service"] for x in own_copies.values())
        remaining_copies = [x for x in own_copies.values()
                            if (producers[x["tensor"]] | consumers[x["tensor"]]) & (task_ops[task] & remaining)]
        floor = max(max(work.values(), default=0), service, ordinary_cp)
        fifo_floor = max(floor, fifo_cp)
        span = timeline[task]
        assert floor <= fifo_floor <= span["duration"]
        for e in ev:
            u = e["args"]["op_id"]
            assert e["dur"] >= weights[u]
            if u in compute:
                assert e["dur"] == weights[u]
        local = result["step3_by_task"][str(task)]
        rows.append({"task": task, "phase": phase_of[task], "core": span["core"],
                     "start": span["start"], "end": span["end"], "actual_duration": span["duration"],
                     "local_makespan_not_bound": local["local_makespan"],
                     "actual_minus_local_not_contention": span["duration"] - local["local_makespan"],
                     "memory_dependency_count": local["memory_dependency_count"],
                     "compute_pipe_work": dict(work), "heavy_pipe_work": dict(heavy_work),
                     "remaining_pipe_work": dict(remaining_work),
                     "remaining_copy_bytes": sum(x["bytes"] for x in remaining_copies),
                     "remaining_copy_service": sum(x["service"] for x in remaining_copies),
                     "copy_count": len(own_copies), "copy_bytes": sum(x["bytes"] for x in own_copies.values()),
                     "copy_service": service, "original_local_cp": ordinary_cp,
                     "fixed_fifo_cp": fifo_cp, "partition_task_floor": floor, "fixed_fifo_task_floor": fifo_floor})
    macro = []
    for edge in result["task_dependencies"]:
        a, b = edge["source"], edge["target"]
        macro.append((a, b, result["task_cross_core_wait_cycles"] if timeline[a]["core"] != timeline[b]["core"] else 0))
    chain_edges = []
    for schedule in plan["core_schedules"]:
        chain_edges += list(zip(schedule, schedule[1:]))
    macro += [(a, b, result["task_same_core_wait_cycles"]) for a, b in chain_edges]
    models = {}
    for kind, key in [("partition_and_mapping", "partition_task_floor"), ("frozen_fifo_and_mapping", "fixed_fifo_task_floor"), ("observed_duration_descriptive_only", "actual_duration")]:
        model = longest({r["task"]: r[key] for r in rows}, macro)
        if key == "actual_duration":
            assert all(model["starts"][t] == timeline[t]["start"] for t in timeline)
            assert model["value"] == result["makespan"]
        models[kind] = {"value": model["value"], "path": model["path"],
                        "path_gate_sum": sum(x["incoming_lag"] for x in model["path"])}
    task_succ = defaultdict(set)
    for a, b, _ in macro:
        task_succ[a].add(b)
    merge_checks = []
    for a, b in chain_edges:
        seen, stack = set(), list(task_succ[a] - {b})
        while stack:
            u = stack.pop()
            if u not in seen:
                seen.add(u)
                stack.extend(task_succ[u] - seen)
        merge_checks.append({"a": a, "b": b, "individually_acyclic_contraction": b not in seen})
    holes = []
    for c in result["per_core_timeline"]:
        for a, b in zip(c["tasks"], c["tasks"][1:]):
            holes.append({"core": c["core_id"], "after": a["task_id"], "before": b["task_id"],
                          "start": a["end"], "end": b["start"], "idle": b["start"] - a["end"],
                          "beyond_same_core_wait": max(0, b["start"] - a["end"] - result["task_same_core_wait_cycles"])})
    last_heavy = max(e["ts"] + e["dur"] for e in events if e["args"]["op_id"] in heavy)
    last_compute = max((e for e in events if e["args"]["op_id"] in compute), key=lambda e: e["ts"] + e["dur"])
    copy_intervals = [(e["ts"], e["ts"] + e["dur"]) for e in events if e["args"]["op_id"] in copies]
    copy_service = sum(x["service"] for x in copies.values())
    phases = []
    for phase in range(diag["wave_count"]):
        rs = [r for r in rows if r["phase"] == phase]
        phases.append({"phase": phase, "tasks": [r["task"] for r in rs], "first_start": min(r["start"] for r in rs),
                       "last_end": max(r["end"] for r in rs), "copy_service": sum(r["copy_service"] for r in rs),
                       "max_task_floor": max(r["partition_task_floor"] for r in rs),
                       "max_fifo_floor": max(r["fixed_fifo_task_floor"] for r in rs),
                       "used_cores": [r["core"] for r in rs]})
    ext = lambda members: {t for t in tensors if consumers[t] & members and not producers[t] & compute}
    ext_heavy, ext_remaining = ext(heavy), ext(remaining)
    current_remaining_input_bytes = sum(x["bytes"] for x in copies.values()
                                        if x["kind"] == "COPY_IN" and x["tensor"] in ext_remaining)
    direct_compute = {(u, v) for u in compute for v in fullsucc[u] if v in compute}
    copy_bridge_edges = {(u, v) for u in compute for v in succ[u]} - direct_compute
    # All residual components are whole: discover their input sharing without repacking.
    residual_components = []
    unseen = set(remaining)
    while unseen:
        members, stack = set(), [min(unseen)]
        while stack:
            u = stack.pop()
            if u not in members:
                members.add(u)
                stack.extend(adj[u] - members)
        unseen -= members
        residual_components.append(members)
    residual_input_sum = sum(sum(tensors[t]["size"] for t in ext(c)) for c in residual_components)
    bound = next(c for c in bounds["cases"] if c["input_member"] == f"data/case_{case}.json")
    assert bound["input_sha256"] == digest(raw)
    return {"case": case, "cores": 5, "makespan": result["makespan"],
            "input_sha256": digest(raw), "artifact_hashes": {f: docs[f][1] for f in files},
            "global_static_bound": next(b for b in bound["bounds"] if b["cores"] == 5),
            "movement": result["data_movement_bytes"], "peak": result["memory_peak_by_core"],
            "memory_dependency_count": sum(r["memory_dependency_count"] for r in rows),
            "boundary_copy_service": copy_service, "trace_ddr_busy_union": busy(copy_intervals),
            "sum_copy_elapsed_not_service": sum(b - a for a, b in copy_intervals),
            "fixed_partition_floor": max(copy_service, models["partition_and_mapping"]["value"]),
            "frozen_fifo_floor": max(copy_service, models["frozen_fifo_and_mapping"]["value"]),
            "macro_models": models, "tasks": rows, "phases": phases,
            "last_heavy_compute_end": last_heavy,
            "post_heavy_tail_observed_not_savings": result["makespan"] - last_heavy,
            "last_compute": {"task": last_compute["args"]["task_id"], "op": last_compute["args"]["op_id"],
                             "end": last_compute["ts"] + last_compute["dur"],
                             "in_remaining_component": last_compute["args"]["op_id"] in remaining},
            "top_idle_holes": sorted(holes, key=lambda h: -h["idle"])[:12],
            "adjacent_merge_checks": merge_checks,
            "external_inputs": {"heavy_bytes": sum(tensors[t]["size"] for t in ext_heavy),
                                "remaining_union_bytes": sum(tensors[t]["size"] for t in ext_remaining),
                                "heavy_remaining_shared_bytes": sum(tensors[t]["size"] for t in ext_heavy & ext_remaining),
                                "sum_per_remaining_component_bytes": residual_input_sum,
                                "current_remaining_bundle_copy_in_bytes": current_remaining_input_bytes,
                                "extra_bytes_if_each_remaining_component_separate": residual_input_sum - current_remaining_input_bytes},
            "global_bound_applicability": {"copy_bridge_extra_compute_edges": len(copy_bridge_edges),
                                           "multiple_compute_producer_tensors": sum(len(producers[t] & compute) > 1 for t in tensors),
                                           "nonpositive_compute_cycles": sum(ops[u]["cycles"] <= 0 for u in compute),
                                           "pipe_slots": 1, "bandwidth": bw,
                                           "input_hash_matches_existing_bound": True},
            "checks": {"plan_covers_original_compute_once": True, "artifact_and_graph_hashes_match": True,
                       "boundary_copy_ids_match_trace_and_issued_ids": True, "boundary_bytes_match_result": True,
                       "all_task_starts_equal_exact_gate_release": True,
                       "all_task_floors_le_actual": True, "all_compute_durations_match_max1_cycles": True}}


def main():
    archive_path = ROOT / "data/raw/a/official-cases.zip"
    batch, batch_hash = source("batch.json")
    assert digest(archive_path.read_bytes()) == batch["input_archive_sha256"]
    bounds_path = ROOT / "results/a/q1-lower-bounds-20260924/static_bounds.json"
    bounds = json.loads(bounds_path.read_bytes())
    with zipfile.ZipFile(archive_path) as archive:
        cases = [analyze(c, archive, bounds) for c in ("049", "088")]
    output = {"kind": "sealed_trace_static_analysis_not_new_performance", "source_commit": SOURCE,
              "solver_commit": batch["solver_commit"], "runner_commit": batch["runner_commit"],
              "batch_sha256": batch_hash, "archive_sha256": batch["input_archive_sha256"],
              "bounds_sha256": digest(bounds_path.read_bytes()), "script_sha256": digest(Path(__file__).read_bytes()),
              "calls": {"solver": 0, "task_compiler": 0, "E0": 0, "E1": 0, "E2": 0},
              "scope": "Two sealed cells only. Trace FIFO bounds apply to their fixed compiler order; no counterfactual E0.",
              "cases": cases}
    output["official_source_sha256"] = {}
    for path in ["data/raw/a/official/code/multicore_cut_evaluate_problem_1.py",
                 "data/raw/a/official/code/schedule_step3.py",
                 "data/raw/a/official/data/config.txt"]:
        b = subprocess.check_output(["git", "show", SOURCE + ":" + path], cwd=ROOT)
        assert (ROOT / path).read_bytes() == b
        output["official_source_sha256"][path] = digest(b)
    (OUT / "analysis.json").write_text(json.dumps(output, indent=2) + "\n")
    for c in cases:
        print(c["case"], {k: c[k] for k in ["makespan", "boundary_copy_service", "trace_ddr_busy_union", "memory_dependency_count", "fixed_partition_floor", "frozen_fifo_floor", "post_heavy_tail_observed_not_savings"]})
        print("models", c["macro_models"])
        print("inputs", c["external_inputs"])


if __name__ == "__main__":
    main()
