"""Read-only Stage C evidence analysis: no solver, Task compiler or evaluator.

Reconstruct only boundary COPY metadata, fixed-Task gate constraints and
descriptive duration substitutions. Never import the solver or official code.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import heapq
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a"
BATCH = "results/a/q1-yuanzhifang/stage-c-20260924"
FEED = BATCH + "/board-feed-20260924T153000Z-stage-c.json"
OUTPUT = "results/a/q1-yuanzhifang/stage-c-analysis-20260924"
NEW = "chain-atomic-grain4"
OLD = "frontier-then-independent-chunks"
FOCUS = (("051", 4, NEW), ("051", 5, NEW), ("008", 4, OLD),
         ("008", 4, NEW), ("071", 4, OLD), ("071", 4, NEW))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Snapshot:
    def __init__(self):
        self.data = {}

    def load(self, paths):
        paths = sorted(set(paths) - self.data.keys())
        if not paths:
            return
        raw = subprocess.check_output(["git", "cat-file", "--batch"],
                                      input="".join(SOURCE + ":" + p + "\n" for p in paths).encode(), cwd=ROOT)
        offset = 0
        for path in paths:
            end = raw.index(b"\n", offset)
            _, kind, length = raw[offset:end].split()
            assert kind == b"blob", path
            offset = end + 1
            content = raw[offset:offset + int(length)]
            self.data[path] = content
            assert (ROOT / path).read_bytes() == content, "Local source differs: " + path
            offset += int(length)
            assert raw[offset:offset + 1] == b"\n"
            offset += 1
        assert offset == len(raw)

    def json(self, path):
        self.load([path])
        raw = self.data[path]
        return json.loads(gzip.decompress(raw) if path.endswith(".gz") else raw)


def boundary_metadata(graph, plan, bandwidth):
    """Mirror official boundary conditions/ID allocation, without scheduling.

    multicore_cut_evaluate_problem_1.py lines 38-49, 93-174; no Step1/2/3.
    Only non-spill boundary COPY IDs are reconstructed. Unmatched spill IDs
    would be retained separately, never guessed into an original tensor.
    """
    ops = {o["id"]: o for o in graph["ops"]}
    tensors = {t["id"]: t for t in graph["tensors"]}
    mapping = {int(o): int(t) for o, t in plan["node_to_subgraph"].items()}
    groups = defaultdict(set)
    for op, task in mapping.items():
        groups[task].add(op)
        assert ops[op]["op"] not in ("COPY_IN", "COPY_OUT")
    producers, consumers, op_in, op_out = (defaultdict(set) for _ in range(4))
    for e in graph["edges"]:
        a, b = e["source"], e["target"]
        if a in ops and b in tensors:
            producers[b].add(a); op_out[a].add(b)
        if a in tensors and b in ops:
            consumers[a].add(b); op_in[b].add(a)
    original = sum(sum(tensors[t]["size"] for t in (op_out[o] if op["op"] == "COPY_IN" else op_in[o]))
                   for o, op in ops.items() if op["op"] in ("COPY_IN", "COPY_OUT"))
    next_op, next_tensor = max([*ops, 0]) + 1, max([*tensors, 10000]) + 1
    used = set(ops) | set(tensors)
    boundary = []
    for task in sorted(groups):
        members = groups[task]
        touched = set()
        for op in members:
            touched.update(op_in[op]); touched.update(op_out[op])
        for tensor in sorted(touched):
            local_prod, local_cons = producers[tensor] & members, consumers[tensor] & members
            eligible_cons = consumers[tensor] & mapping.keys()
            has_copy_out = any(ops[o]["op"] == "COPY_OUT" for o in consumers[tensor])
            is_input = bool(local_cons) and not local_prod
            is_output = bool(local_prod) and (has_copy_out or not eligible_cons or bool(eligible_cons - members))
            for direction, included in (("COPY_IN", is_input), ("COPY_OUT", is_output)):
                if not included:
                    continue
                while next_tensor in used:
                    next_tensor += 1
                ddr = next_tensor; used.add(ddr); next_tensor += 1
                while next_op in used:
                    next_op += 1
                copy = next_op; used.add(copy); next_op += 1
                size = tensors[tensor]["size"]
                boundary.append({"task": task, "copy_op": copy, "tensor": tensor, "direction": direction,
                                 "bytes": size, "solo_service_cycles": max(1, (size + bandwidth - 1) // bandwidth),
                                 "source_kind": "compute_produced" if producers[tensor] & mapping.keys() else "external_input",
                                 "producer_tasks": sorted({mapping[o] for o in producers[tensor] if o in mapping})})
    reloads = []
    by_tensor = defaultdict(list)
    for b in boundary:
        if b["direction"] == "COPY_IN":
            by_tensor[b["tensor"]].append(b)
    for tensor, loads in sorted(by_tensor.items()):
        reloads.append({"tensor": tensor, "bytes": tensors[tensor]["size"], "input_task_count": len(loads),
                        "task_ids": [b["task"] for b in loads], "source_kind": loads[0]["source_kind"],
                        "copy_in_bytes": tensors[tensor]["size"] * len(loads),
                        "repeat_above_one_load_bytes": tensors[tensor]["size"] * (len(loads) - 1)})
    return boundary, reloads, original, groups, ops


def intervals(spans):
    points = defaultdict(int)
    for start, end in spans:
        assert end >= start
        points[start] += 1; points[end] -= 1
    histogram, active, prev = defaultdict(int), 0, None
    for tick, delta in sorted(points.items()):
        if prev is not None and active:
            histogram[active] += tick - prev
        active += delta; prev = tick
        assert active >= 0
    assert active == 0
    return {"union_cycles": sum(histogram.values()),
            "summed_request_elapsed_cycles": sum(k * v for k, v in histogram.items()),
            "concurrency_histogram_cycles": dict(sorted(histogram.items()))}


def recurrence(tasks, preds, previous, durations, same, cross):
    """Longest path in an already fixed Task/core DAG; no operation scheduler."""
    edges = defaultdict(dict)
    for task in tasks:
        for p in preds[task]:
            edges[p][task] = cross if tasks[p]["core"] != tasks[task]["core"] else 0
        p = previous[task]
        if p is not None:
            edges[p][task] = max(edges[p].get(task, 0), same)
    indegree = Counter(t for ds in edges.values() for t in ds)
    ready = [t for t in tasks if not indegree[t]]; heapq.heapify(ready)
    starts, ends, incoming = {}, {}, {}
    while ready:
        task = heapq.heappop(ready)
        starts.setdefault(task, 0)
        ends[task] = starts[task] + durations[task]
        for target, wait in sorted(edges[task].items()):
            candidate = ends[task] + wait
            if candidate > starts.get(target, -1):
                starts[target] = candidate; incoming[target] = (task, wait)
            indegree[target] -= 1
            if not indegree[target]:
                heapq.heappush(ready, target)
    assert len(ends) == len(tasks)
    tail = max(ends, key=lambda t: (ends[t], -t)); path, waits = [tail], []
    while tail in incoming:
        tail, wait = incoming[tail]
        path.append(tail); waits.append(wait)
    path.reverse(); waits.reverse()
    return {"makespan": max(ends.values()), "start_by_task": starts, "end_by_task": ends,
            "critical_path": path, "critical_waits": waits,
            "critical_duration_sum": sum(durations[t] for t in path), "critical_gate_sum": sum(waits)}


def analyse(record, snap, graph):
    a = record["artifacts"]
    plan, result, trace, run = (snap.json(a[k]["path"]) for k in ("plan", "result", "trace", "run"))
    diag = run["diagnostics"]
    cores, same, cross = record["cores"], result["task_same_core_wait_cycles"], result["task_cross_core_wait_cycles"]
    boundary, reloads, original, groups, ops = boundary_metadata(graph, plan, result["bandwidth_bytes_per_cycle"])
    tasks, actual_ops, previous, preds = {}, {}, {}, defaultdict(set)
    for core in result["per_core_timeline"]:
        prev = None
        for t in core["tasks"]:
            task = t["task_id"]
            tasks[task] = {**t, "core": core["core_id"]}; previous[task] = prev; prev = task
        for op in core["ops"]:
            actual_ops[(op["task_id"], op["op_id"])] = {**op, "core": core["core_id"]}
    for edge in result["task_dependencies"]:
        preds[edge["target"]].add(edge["source"])
    assert set(tasks) == set(groups)
    trace_ops = {(e["args"]["task_id"], e["args"]["op_id"]): e
                 for e in trace["traceEvents"] if e.get("ph") == "X" and str(e.get("cat", "")).startswith("PIPE_")}
    assert set(trace_ops) == set(actual_ops)
    for key, op in actual_ops.items():
        event = trace_ops[key]
        assert (event["ts"], event["dur"], event["args"]["core_id"]) == (op["start"], op["duration"], op["core"])
    ddr_ids = {(x["issued"]["task_id"], x["issued"]["op_id"]) for x in result["ddr_contention_log"]}
    boundary_ids = {(b["task"], b["copy_op"]) for b in boundary}
    assert result["data_movement_bytes"]["spill_added_copy_bytes"] == 0, "Focused analysis does not reconstruct spill IDs"
    assert ddr_ids == boundary_ids
    for b in boundary:
        op = actual_ops[(b["task"], b["copy_op"])]
        assert op["op"] == b["direction"]
        b.update(core=op["core"], start=op["start"], end=op["end"], elapsed_cycles=op["duration"])
    movement = result["data_movement_bytes"]
    assert sum(b["bytes"] for b in boundary) == movement["scheduled_copy_bytes"]
    assert original == movement["original_graph_copy_bytes"]
    assert sum(b["bytes"] for b in boundary) - original == movement["partition_added_copy_bytes"]
    diagnostic_tasks = {t["task"]: t for t in diag.get("tasks", [])}
    task_rows, work_duration, local_duration, observed_duration = [], {}, {}, {}
    for task, t in sorted(tasks.items()):
        work = defaultdict(int)
        for op in groups[task]:
            cost = max(1, ops[op].get("cycles", 1)); work[ops[op]["pipe"]] += cost
            assert actual_ops[(task, op)]["duration"] == cost
        prev = previous[task]
        chain_ready = tasks[prev]["end"] if prev is not None else 0
        remote = {p: tasks[p]["end"] + cross for p in preds[task] if tasks[p]["core"] != t["core"]}
        release = max([chain_ready + same if prev is not None else 0, *remote.values(),
                       *(tasks[p]["end"] for p in preds[task])])
        ready_without_gates = max([chain_ready, *(tasks[p]["end"] for p in preds[task])])
        work_duration[task] = max(work.values(), default=0)
        local_duration[task] = result["step3_by_task"][str(task)]["local_makespan"]
        observed_duration[task] = t["duration"]
        d = diagnostic_tasks.get(task, {})
        task_rows.append({"task": task, "core": t["core"], "stage": d.get("stage"), "phase": d.get("phase"),
                          "start": t["start"], "end": t["end"], "duration": t["duration"],
                          "previous_core_task": prev, "previous_core_end": chain_ready,
                          "pred_tasks": sorted(preds[task]), "remote_release_constraints": remote,
                          "release": release, "start_minus_release": t["start"] - release,
                          "idle_since_previous_core_task": t["start"] - chain_ready,
                          "gate_increment_over_all_ready": release - ready_without_gates,
                          "binding_remote_tasks": [p for p, r in remote.items() if r == release],
                          "core_gate_binding": prev is not None and chain_ready + same == release,
                          "compute_work_by_pipe": dict(work), "pure_v_cycles": work.get("PIPE_V", 0),
                          "compute_max_pipe_cycles": work_duration[task], "local_makespan": local_duration[task],
                          "duration_minus_local": t["duration"] - local_duration[task],
                          "local_minus_compute_max_pipe": local_duration[task] - work_duration[task],
                          "estimated_finish": d.get("estimated_finish")})
        assert t["start"] == release
    models = {name: recurrence(tasks, preds, previous, duration, same, cross)
              for name, duration in (("compute_work", work_duration), ("official_local", local_duration), ("observed_duration", observed_duration))}
    assert models["observed_duration"]["makespan"] == result["makespan"]
    assert all(models["observed_duration"]["start_by_task"][t] == tasks[t]["start"] for t in tasks)
    critical = models["observed_duration"]["critical_path"]
    model_summary = {name: {k: v for k, v in model.items() if k not in ("start_by_task", "end_by_task")}
                     for name, model in models.items()}
    stages, last_end = [], 0
    for stage in sorted({r["stage"] for r in task_rows if r["stage"] is not None}):
        rows = [r for r in task_rows if r["stage"] == stage]
        end = max(r["end"] for r in rows)
        stages.append({"stage": stage, "task_ids": [r["task"] for r in rows], "start": min(r["start"] for r in rows),
                       "end": end, "progress_since_previous_stage_end": end - last_end,
                       "estimated_finish": max(r["estimated_finish"] for r in rows),
                       "frontier_compute_v_cycles": [r["pure_v_cycles"] for r in rows if r["phase"] == 0],
                       "frontier_local_cycles": [r["local_makespan"] for r in rows if r["phase"] == 0],
                       "frontier_actual_cycles": [r["duration"] for r in rows if r["phase"] == 0],
                       "frontier_starts": [r["start"] for r in rows if r["phase"] == 0],
                       "tail_actual_cycles": [r["duration"] for r in rows if r["phase"] == 1],
                       "tail_starts": [r["start"] for r in rows if r["phase"] == 1]})
        last_end = end
    ddr = intervals((b["start"], b["end"]) for b in boundary)
    ddr["solo_service_cycles"] = sum(b["solo_service_cycles"] for b in boundary)
    ddr["union_minus_solo_service_cycles"] = ddr["union_cycles"] - ddr["solo_service_cycles"]
    repeats = {kind: sum(x["repeat_above_one_load_bytes"] for x in reloads if x["source_kind"] == kind)
               for kind in ("external_input", "compute_produced")}
    summary = {"case_id": record["case_id"], "cores": cores, "variant": record["variant"],
               "makespan": result["makespan"], "task_count": len(tasks), "stage_count": len(stages),
               "diagnostic_estimated_finish": max((t["estimated_finish"] for t in diagnostic_tasks.values()), default=None),
               "task_models": model_summary, "movement_bytes": movement, "ddr": ddr,
               "boundary_copy_count": len(boundary), "static_repeated_input_bytes_above_one_load": repeats,
               "all_task_start_equals_reconstructed_release": True,
               "actual_critical_path_decomposition": {"compute_max_pipe_sum": sum(work_duration[t] for t in critical),
                    "local_minus_compute_sum": sum(local_duration[t] - work_duration[t] for t in critical),
                    "actual_minus_local_sum": sum(observed_duration[t] - local_duration[t] for t in critical),
                    "gate_sum": models["observed_duration"]["critical_gate_sum"]},
               "critical_path_is_descriptive": "Differences along this observed longest path add to its makespan; not an independent causal attribution or validated counterfactual.",
               "checks": {"trace_ops_equal_result_ops": len(actual_ops), "boundary_ids_equal_ddr_issue_ids": len(ddr_ids),
                          "boundary_bytes_equal_official": True, "original_copy_bytes_equal_official": True}}
    return {"summary": summary, "tasks": task_rows, "stages": stages, "boundary_copies": boundary,
            "input_tensor_reloads": sorted(reloads, key=lambda x: (-x["repeat_above_one_load_bytes"], x["tensor"]))}


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False); f.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphs", required=True, type=Path)
    args = parser.parse_args()
    started, tick = utc(), time.perf_counter()
    code_commit = git("rev-parse", "HEAD").decode().strip()
    source_path = "src/q1_yuanzhifang/trace_c.py"
    assert (ROOT / source_path).read_bytes() == git("show", code_commit + ":" + source_path)
    snap = Snapshot(); feed = snap.json(FEED)
    paths = {a["path"] for r in feed["records"] for a in r["artifacts"].values()}
    paths |= {BATCH + "/protocol.json", BATCH + "/completion.json"}
    snap.load(paths)
    checked = []
    for record in feed["records"]:
        for name, ref in record["artifacts"].items():
            assert sha(snap.data[ref["path"]]) == ref["sha256"]
        run = snap.json(record["artifacts"]["run"]["path"])
        for item in run["artifacts"].values():
            assert sha(gzip.decompress(snap.data[item["path"]])) == item["raw_sha256"]
        checked.append({"attempt_id": record["attempt_id"], "status": record["status"], "artifact_count": len(record["artifacts"])})
    protocol = snap.json(BATCH + "/protocol.json")
    outputs = {}
    for case, cores, variant in FOCUS:
        record = next(r for r in feed["records"] if (r["case_id"], r["cores"], r["variant"]) == (case, cores, variant))
        raw = (args.graphs / f"case_{case}.json").read_bytes()
        assert sha(raw) == protocol["input_sha256"][f"case_{case}.json"]
        outputs[f"{case}-k{cores}-{variant}"] = analyse(record, snap, json.loads(raw))
    out = ROOT / OUTPUT; out.mkdir(parents=True, exist_ok=False)
    for name, value in outputs.items():
        write_json(out / (name + ".json"), value)
    write_json(out / "summary.json", [o["summary"] for o in outputs.values()])
    with (out / "tasks.csv").open("x", encoding="utf-8", newline="") as f:
        rows = [{"case_variant": key, **r} for key, value in outputs.items() for r in value["tasks"]]
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    write_json(out / "verification.json", {"source_commit": SOURCE, "feed": FEED, "feed_sha256": sha(snap.data[FEED]),
                "analysis_commit": code_commit, "analysis_source_sha256": sha((ROOT / source_path).read_bytes()),
                "records_checked": checked, "git_blob_count": len(snap.data),
                "source_hashes": {p: sha(raw) for p, raw in sorted(snap.data.items())},
                "official_source": {"commit": SOURCE, "path": "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py",
                                    "sha256": protocol["official_source_sha256"]["code/multicore_cut_evaluate_problem_1.py"]},
                "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0, "task_compiler": 0},
                "started_at": started, "finished_at": utc(), "wall_seconds": time.perf_counter() - tick,
                "method": "JSON read, static boundary metadata, interval aggregation and longest path on already fixed Task graph only; no scorer imports.",
                "limitations": ["Observed operation start/end lacks complete readiness/FIFO/memory state; no unique stall cause inferred.",
                                "Duration substitutions keep one plan/gates fixed; are descriptive timing models, not re-evaluations or plan quality guarantees.",
                                "Repeated tensor input counts are static Task-boundary loads, not proof a cache can retain that tensor across Tasks.",
                                "Selected six plans have zero official spill; boundary ID reconstruction intentionally excludes spill IDs."],
                "mailbox_read": "check --full fetched 6 issues/397 comments; task Issue98 actual read through 5817206034 (12 comments). Other task transcripts not imported.",
                "metadata_scan": [str(p.relative_to(out)) for p in out.rglob("*") if p.name.startswith("._") or p.name in (".DS_Store", "__MACOSX")],
                "dot_clean": "unavailable on Windows"})
    print(json.dumps({"output": OUTPUT, "plans_analysed": len(outputs), "all_records_hash_checked": len(checked),
                      "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}, "wall_seconds": time.perf_counter() - tick}))


if __name__ == "__main__":
    main()
