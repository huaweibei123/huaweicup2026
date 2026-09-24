"""Static analysis of sealed plans/results only. Does not import any solver."""
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import heapq
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SHA = "8f0009ac4a934c2161943b70530e418eb55f9366"
BASE = "results/a/q1-overload-activation-20260925/20260924T1636Z-overload16/"
PRIORITY = {"031", "032", "057", "077", "068"}
RECEIPTS = {}


def read(path, sha=SHA):
    b = read_bytes(path, sha)
    return json.loads(gzip.decompress(b) if path.endswith(".gz") else b)


def read_bytes(path, sha=SHA):
    b = subprocess.check_output(["git", "show", sha + ":" + path], cwd=ROOT)
    RECEIPTS[sha + ":" + path] = hashlib.sha256(b).hexdigest()
    return b


def longest(weights, edges):
    pred, succ = {u: {} for u in weights}, {u: set() for u in weights}
    for a, b, lag in edges:
        pred[b][a] = max(pred[b].get(a, 0), lag)
        succ[a].add(b)
    indegree = {u: len(pred[u]) for u in weights}
    ready = [u for u in weights if not indegree[u]]
    heapq.heapify(ready)
    starts, ends, previous = {}, {}, {}
    while ready:
        u = heapq.heappop(ready)
        starts[u], previous[u] = max(((ends[v] + lag, v) for v, lag in pred[u].items()), default=(0, None))
        ends[u] = starts[u] + weights[u]
        for v in sorted(succ[u]):
            indegree[v] -= 1
            if not indegree[v]:
                heapq.heappush(ready, v)
    assert len(ends) == len(weights)
    final = max(ends, key=lambda u: (ends[u], u))
    path, u = [], final
    while u is not None:
        p = previous[u]
        path.append({"task": u, "weight": weights[u], "incoming_lag": pred[u][p] if p is not None else 0})
        u = p
    return {"value": ends[final], "starts": starts, "path": list(reversed(path))}


def graph_view(g):
    ops = {o["id"]: o for o in g["ops"]}
    compute = {u for u in ops if ops[u]["op"] not in {"COPY_IN", "COPY_OUT"}}
    tensors = {t["id"]: t for t in g["tensors"]}
    prod, cons = defaultdict(set), defaultdict(set)
    full, direct = defaultdict(set), set()
    for e in g["edges"]:
        a, b = e["source"], e["target"]
        if a in ops and b in tensors:
            prod[b].add(a)
        elif a in tensors and b in ops:
            cons[a].add(b)
        elif a in ops and b in ops and a != b:
            direct.add((a, b))
    for a, b in direct | {(a, b) for t in tensors for a in prod[t] for b in cons[t] if a != b}:
        full[a].add(b)
    succ = {u: set() for u in compute}
    for u in compute:
        stack, seen = list(full[u]), set()
        while stack:
            v = stack.pop()
            if v in seen:
                continue
            seen.add(v)
            if v in compute:
                succ[u].add(v)
            else:
                stack.extend(full[v])
    original_edges = {(u, v) for u in compute for v in full[u] if v in compute}
    adj = {u: set(succ[u]) for u in compute}
    for u in compute:
        for v in succ[u]:
            adj[v].add(u)
    components, component_of = [], {}
    remaining = set(compute)
    while remaining:
        root = min(remaining)
        stack, members = [root], set()
        while stack:
            u = stack.pop()
            if u not in members:
                members.add(u)
                stack.extend(adj[u] - members)
        remaining -= members
        work = Counter()
        for u in sorted(members):
            work[ops[u]["pipe"]] += max(1, ops[u]["cycles"])
            component_of[u] = root
        components.append({"anchor": root, "nodes": sorted(members), "pipe_work": dict(work),
                           "pipe_floor": max(work.values()), "sinks": sum(not succ[u] for u in members)})
    total = Counter()
    for u in compute:
        total[ops[u]["pipe"]] += max(1, ops[u]["cycles"])
    cp = longest({u: max(1, ops[u]["cycles"]) for u in compute}, [(a, b, 0) for a, b in original_edges])["value"]
    return dict(ops=ops, compute=compute, tensors=tensors, prod=prod, cons=cons, components=components,
                component_of=component_of, original_edges=original_edges, succ=succ, total_work=dict(total),
                raw_compute_pipe_floor=max((x + 4) // 5 for x in total.values()), original_compute_cp=cp,
                copy_bridge_extra_compute_edges=len({(a, b) for a in compute for b in succ[a]} - original_edges))


def analyze_plan(view, plan, result, split_anchors):
    mapping = {int(u): t for u, t in plan["node_to_subgraph"].items()}
    assert set(mapping) == view["compute"]
    members = defaultdict(set)
    for u, t in mapping.items():
        members[t].add(u)
    timeline = {t["task_id"]: {**t, "core": c["core_id"]} for c in result["per_core_timeline"] for t in c["tasks"]}
    assert set(timeline) == set(members)
    bw = result["bandwidth_bytes_per_cycle"]
    assert bw == 60
    assert result["task_same_core_wait_cycles"] == 100
    assert result["task_cross_core_wait_cycles"] == 1000
    tasks = {}
    for t, ns in members.items():
        work = Counter()
        roles = set()
        for u in sorted(ns):
            work[view["ops"][u]["pipe"]] += max(1, view["ops"][u]["cycles"])
            roles.add("split" if view["component_of"][u] in split_anchors else "retained")
        cp = longest({u: max(1, view["ops"][u]["cycles"]) for u in ns},
                     [(a, b, 0) for a, b in view["original_edges"] if a in ns and b in ns])["value"]
        copy_bytes = copy_service = inputs = outputs = 0
        for tid, tensor in view["tensors"].items():
            lp, lc = view["prod"][tid] & ns, view["cons"][tid] & ns
            consumers = view["cons"][tid] & view["compute"]
            n_in = int(bool(lc) and not lp)
            n_out = int(bool(lp) and (any(view["ops"][u]["op"] == "COPY_OUT" for u in view["cons"][tid]) or not consumers or bool(consumers - ns)))
            inputs += n_in
            outputs += n_out
            copy_bytes += (n_in + n_out) * tensor["size"]
            copy_service += (n_in + n_out) * max(1, (tensor["size"] + bw - 1) // bw)
        span = timeline[t]
        compute_floor = max(work.values())
        strong_floor = max(compute_floor, cp, copy_service)
        assert strong_floor <= span["duration"]
        tasks[t] = {**span, "compute_work": dict(work), "compute_floor": compute_floor,
                    "compute_cp_floor": cp, "boundary_copy_bytes": copy_bytes,
                    "boundary_copy_service": copy_service, "copy_in_count": inputs, "copy_out_count": outputs,
                    "strong_task_floor": strong_floor, "role": next(iter(roles)) if len(roles) == 1 else "mixed",
                    "component_anchors": sorted({view["component_of"][u] for u in ns})}
    expected_edges = {(mapping[u], mapping[v]) for u in view["compute"] for v in view["succ"][u] if mapping[u] != mapping[v]}
    observed_edges = {(e["source"], e["target"]) for e in result["task_dependencies"]}
    assert observed_edges == expected_edges
    macro = [(a, b, result["task_cross_core_wait_cycles"] if timeline[a]["core"] != timeline[b]["core"] else 0)
             for a, b in expected_edges]
    for order in plan["core_schedules"]:
        macro += [(a, b, result["task_same_core_wait_cycles"]) for a, b in zip(order, order[1:])]
    models = {}
    for name, field in [("compute_gate", "compute_floor"), ("strong_relaxed_gate", "strong_task_floor"), ("actual_duration_description", "duration")]:
        model = longest({t: r[field] for t, r in tasks.items()}, macro)
        if name == "actual_duration_description":
            assert model["value"] == result["makespan"]
            assert all(model["starts"][t] == timeline[t]["start"] for t in timeline)
        for point in model["path"]:
            point["role"] = tasks[point["task"]]["role"]
        models[name] = {"value": model["value"], "path": model["path"],
                        "gate_sum": sum(x["incoming_lag"] for x in model["path"])}
    boundary_bytes = sum(t["boundary_copy_bytes"] for t in tasks.values())
    boundary_service = sum(t["boundary_copy_service"] for t in tasks.values())
    movement = result["data_movement_bytes"]
    assert boundary_bytes == movement["original_graph_copy_bytes"] + movement["partition_added_copy_bytes"]
    compute_gate = models["compute_gate"]["value"]
    first = [tasks[order[0]]["role"] for order in plan["core_schedules"] if order]
    split_weights = {t: x["compute_floor"] for t, x in tasks.items() if x["role"] == "split"}
    split_tail_max = (longest(split_weights, [(a, b, 0) for a, b in expected_edges
                                             if a in split_weights and b in split_weights])["value"]
                      if split_weights else 0)
    component_floor = {x["anchor"]: x["pipe_floor"] for x in view["components"]}
    retained_priority = [{"task": t, "aggregate_weight": x["compute_floor"],
                          "largest_component_weight": max(component_floor[c] for c in x["component_anchors"]),
                          "component_count": len(x["component_anchors"])}
                         for t, x in sorted(tasks.items()) if x["role"] == "retained"]
    return {"makespan": result["makespan"], "task_count": len(tasks), "movement": movement,
            "boundary_copy_bytes": boundary_bytes, "boundary_copy_service": boundary_service,
            "compute_gate": compute_gate, "max_proxy": max(compute_gate, boundary_service),
            "additive_proxy_not_bound": compute_gate + boundary_service,
            "strong_fixed_plan_floor": max(boundary_service, models["strong_relaxed_gate"]["value"]),
            "first_core_tasks_roles": first, "all_initial_cores_retained": bool(first) and all(x == "retained" for x in first),
            "first_split_task_start": min((t["start"] for t in tasks.values() if t["role"] == "split"), default=None),
            "split_only_data_tail_max": split_tail_max,
            "retained_priority_witness": retained_priority,
            "macro_models": models, "tasks": {str(t): tasks[t] for t in sorted(tasks)}}


def main():
    for path in ["data/raw/a/official/code/multicore_cut_evaluate_problem_1.py",
                 "data/raw/a/official/code/schedule_step3.py", "data/raw/a/official/data/config.txt",
                 "src/q1/component_overload.py"]:
        read_bytes(path)
    comparisons = read(BASE + "activation18-comparison.json")
    heavy = {row["case"]: row for row in read(BASE + "heavy-comparison.json")}
    lower = json.loads((ROOT / "results/a/q1-lower-bounds-20260924/static_bounds.json").read_text())
    lows = {c["input_member"].split("case_")[1][:3]: c for c in lower["cases"]}
    rows = []
    with zipfile.ZipFile(ROOT / "data/raw/a/official-cases.zip") as archive:
        for row in comparisons:
            c = row["case"]
            evidence = row["overload_evidence"]
            sha, prefix = evidence.get("commit", SHA), evidence["path"] + "/"
            cell = prefix + f"cells/{c}/k5/"
            run = read(cell + "run.json", sha)
            graph_bytes = archive.read(f"data/case_{c}.json")
            assert hashlib.sha256(graph_bytes).hexdigest() == run["graph_sha256"] == lows[c]["input_sha256"]
            view = graph_view(json.loads(graph_bytes))
            # This audit's local-CP and boundary reconstruction proof only uses
            # these observed graph conditions; no general COPY-bridge CP claim.
            assert view["copy_bridge_extra_compute_edges"] == 0
            assert set(view["total_work"]) <= {"PIPE_M", "PIPE_V"}
            diag = read(cell + "diagnostics.json", sha)
            assert not diag["chunks"]["split_tasks"]
            split = {x["anchor"] for x in diag["split_components"]}
            p = read(cell + f"case_{c}_multicore_res.json", sha)
            r = read(cell + "result.json.gz", sha)
            for kind, path in [("plan", cell + f"case_{c}_multicore_res.json"), ("diagnostics", cell + "diagnostics.json"), ("result", cell + "result.json.gz")]:
                assert RECEIPTS[sha + ":" + path] == run["artifacts"][kind]["sha256"]
            new = analyze_plan(view, p, r, split)
            assert new["makespan"] == row["overload_makespan_cycles"]
            assert new["compute_gate"] == diag["placement"]["compute_gate_proxy_finish"]
            refprefix = prefix + "references/"
            bounded = analyze_plan(view, read(refprefix + f"bounded-{c}-plan-case_{c}_multicore_res.json", sha),
                                   read(refprefix + f"bounded-{c}-result-result.json.gz", sha), split)
            assert bounded["makespan"] == row["bounded_makespan_cycles"]
            fallback = bounded
            old_heavy = None
            if c in heavy:
                h = heavy[c]
                for name in ["plan", "result"]:
                    read(h["preserved"][name]["path"])
                    assert RECEIPTS[SHA + ":" + h["preserved"][name]["path"]] == h["preserved"][name]["sha256"]
                old_heavy = analyze_plan(view, read(h["preserved"]["plan"]["path"]), read(h["preserved"]["result"]["path"]), split)
                assert old_heavy["makespan"] == h["heavy_makespan"]
                fallback = old_heavy
            components = []
            for comp in view["components"]:
                item = {k: v for k, v in comp.items() if k != "nodes"}
                item.update(ops=len(comp["nodes"]), split_in_candidate=comp["anchor"] in split)
                ns = set(comp["nodes"])
                standalone_bytes = standalone_service = 0
                for tid, tensor in view["tensors"].items():
                    lp, lc = view["prod"][tid] & ns, view["cons"][tid] & ns
                    eligible = view["cons"][tid] & view["compute"]
                    n_in = int(bool(lc) and not lp)
                    n_out = int(bool(lp) and (any(view["ops"][u]["op"] == "COPY_OUT" for u in view["cons"][tid]) or not eligible or bool(eligible - ns)))
                    standalone_bytes += (n_in + n_out) * tensor["size"]
                    standalone_service += (n_in + n_out) * max(1, (tensor["size"] + 59) // 60)
                item.update(standalone_boundary_bytes=standalone_bytes, standalone_boundary_service=standalone_service)
                item["overloaded_pipes"] = [p for p, w in comp["pipe_work"].items() if w > (view["total_work"][p] + 4) // 5]
                if not item["split_in_candidate"]:
                    item["retention_reason_static"] = ("below_all_pipe_thresholds" if not item["overloaded_pipes"] else
                                                       "single_sink" if comp["sinks"] == 1 else
                                                       "sink_budget" if comp["sinks"] > diag["max_sinks"] else "not_reported")
                components.append(item)
            assert (c in heavy) == (diag["base"]["selected"] == "heavy-suffix")
            old_retained = [t for t in new["tasks"].values() if t["role"] == "retained"]
            whole_retained = [t for t in components if not t["split_in_candidate"]]
            fields = {"case": c, "global_bound": next(x["lower_bound_cycles"] for x in lows[c]["bounds"] if x["cores"] == 5),
                      "raw_compute_pipe_floor": view["raw_compute_pipe_floor"], "original_compute_cp": view["original_compute_cp"],
                      "total_work": view["total_work"], "components": components, "split_components": diag["split_components"],
                      "retained_component_pipe_floor": max((x["pipe_floor"] for x in components if not x["split_in_candidate"]), default=0),
                      "copy_bridge_extra_compute_edges": view["copy_bridge_extra_compute_edges"],
                      "overload": new, "bounded": bounded, "heavy": old_heavy,
                      "fallback_kind": "heavy" if old_heavy else "bounded", "fallback": fallback,
                      "recorded_proxy": diag["placement"]["compute_gate_proxy_finish"],
                      "ungrouped_retained_metadata_not_plan": {
                          "old_retained_tasks": len(old_retained), "component_tasks": len(whole_retained),
                          "additional_task_count": len(whole_retained) - len(old_retained),
                          "boundary_bytes_increase": sum(t["standalone_boundary_bytes"] for t in whole_retained) - sum(t["boundary_copy_bytes"] for t in old_retained),
                          "boundary_service_increase": sum(t["standalone_boundary_service"] for t in whole_retained) - sum(t["boundary_copy_service"] for t in old_retained)},
                      "observed_worse_than_bounded": new["makespan"] > bounded["makespan"],
                      "observed_worse_than_fallback": new["makespan"] > fallback["makespan"],
                      "hypothesis_signals": {"all_initial_cores_retained": new["all_initial_cores_retained"],
                                             "compute_gate_no_improvement": new["compute_gate"] >= fallback["compute_gate"],
                                             "max_proxy_no_improvement": new["max_proxy"] >= fallback["max_proxy"],
                                             "additive_proxy_no_improvement": new["additive_proxy_not_bound"] >= fallback["additive_proxy_not_bound"]}}
            if c in PRIORITY:
                tr = read(cell + "trace.json.gz", sha)
                assert RECEIPTS[sha + ":" + cell + "trace.json.gz"] == run["artifacts"]["trace"]["sha256"]
                ev = [e for e in tr["traceEvents"] if e.get("ph") == "X" and e.get("args", {}).get("op_id") in view["compute"]]
                assert len(ev) == len(view["compute"])
                assert {e["args"]["op_id"] for e in ev} == view["compute"]
                last = max(ev, key=lambda e: e["ts"] + e["dur"])
                fields["trace_checks"] = {"last_original_compute": {"op": last["args"]["op_id"],
                    "task": last["args"]["task_id"], "end": last["ts"] + last["dur"],
                    "component_anchor": view["component_of"][last["args"]["op_id"]]},
                    "all_compute_durations_match": all(e["dur"] == max(1, view["ops"][e["args"]["op_id"]]["cycles"]) for e in ev)}
            rows.append(fields)
            old = fields["fallback"]
            print(c, "M", old["makespan"], new["makespan"], "G", old["compute_gate"], new["compute_gate"],
                  "DDR", old["boundary_copy_service"], new["boundary_copy_service"], "retfloor", fields["retained_component_pipe_floor"],
                  "initialret", new["all_initial_cores_retained"], "sumguard", fields["hypothesis_signals"]["additive_proxy_no_improvement"])
    report = {"kind": "sealed_regression_static_review_not_new_performance", "source_commit": SHA,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "artifact_sha256": RECEIPTS,
              "archive_sha256": hashlib.sha256((ROOT / "data/raw/a/official-cases.zip").read_bytes()).hexdigest(),
              "global_bounds_sha256": hashlib.sha256((ROOT / "results/a/q1-lower-bounds-20260924/static_bounds.json").read_bytes()).hexdigest(),
              "calls": {"constructor": 0, "task_compiler": 0, "E0": 0, "E1": 0, "E2": 0}, "cases": rows}
    report["signal_audit_in_sample_only"] = {}
    for name in rows[0]["hypothesis_signals"]:
        report["signal_audit_in_sample_only"][name] = {
            "flagged_observed_regressions": [x["case"] for x in rows if x["hypothesis_signals"][name] and x["observed_worse_than_fallback"]],
            "flagged_observed_improvements": [x["case"] for x in rows if x["hypothesis_signals"][name] and not x["observed_worse_than_fallback"]],
            "missed_observed_regressions": [x["case"] for x in rows if not x["hypothesis_signals"][name] and x["observed_worse_than_fallback"]]}
    (OUT / "analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    table = []
    for x in rows:
        n, b = x["overload"], x["fallback"]
        table.append(dict(case=x["case"], fallback=x["fallback_kind"], M_old=b["makespan"], M_new=n["makespan"],
                          G_old=b["compute_gate"], G_new=n["compute_gate"], D_old=b["boundary_copy_service"], D_new=n["boundary_copy_service"],
                          retained_floor=x["retained_component_pipe_floor"], **x["hypothesis_signals"]))
    with (OUT / "summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(table[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(table)


if __name__ == "__main__":
    main()
