"""Read fixed Stage L artifacts and explain the failed proxy, with zero scoring."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TRIAL = "2dadb457ecd998dbdfca574329e76000e8c1f906"
PREFIX = "results/a/q1-yuanzhifang-stage-l/stage-l-mem512-20260925/run"
CAPTAIN = "9c5f87548cc7588465a638e032993969b5cac891"
FEED = "results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/board-feed-500.json"


def read(commit, path):
    raw = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)
    return json.loads(raw), dict(commit=commit, path=path,
                               sha256=hashlib.sha256(raw).hexdigest())


def analyze():
    feed, reference = read(CAPTAIN, FEED)
    graph_raw = (ROOT / "data/raw/a/official/data/case_044.json").read_bytes()
    graph, graph_sha = json.loads(graph_raw), hashlib.sha256(graph_raw).hexdigest()
    ops = {o["id"]: o for o in graph["ops"]}
    tensors = {t["id"]: t for t in graph["tensors"]}
    producers, consumers = defaultdict(set), defaultdict(set)
    for edge in graph["edges"]:
        a, b = edge["source"], edge["target"]
        if a in ops and b in tensors:
            producers[b].add(a)
        if a in tensors and b in ops:
            consumers[a].add(b)
    result = dict(scope="Read-only analysis of two completed development cells; no new plan construction, Task compilation or scoring", calls=dict(solver=0, E0=0, E1=0, E2=0), captain_feed=reference, graph_sha256=graph_sha, cells=[])
    for cores in (3, 4):
        cell = f"{PREFIX}/044-k{cores}"
        measured, measured_source = read(TRIAL, f"{cell}/e0_result.json")
        diag, diag_source = read(TRIAL, f"{cell}/diagnostics.json")
        plan, plan_source = read(TRIAL, f"{cell}/case_044_multicore_res.json")
        old = next(r for r in feed["records"] if r["case_id"] == "044" and r["cores"] == cores)
        if diag["graph_sha256"] != graph_sha or old["identity"]["graph_sha256"] != graph_sha:
            raise ValueError("graph identity differs")
        mapping = {int(op): task for op, task in plan["node_to_subgraph"].items()}
        scheduled_bytes = service = shared_external_bytes = 0
        copies = []
        for tid, tensor in tensors.items():
            before = {mapping[u] for u in producers[tid] if u in mapping}
            after = {mapping[u] for u in consumers[tid] if u in mapping}
            original_out = any(ops[u]["op"] == "COPY_OUT" for u in consumers[tid])
            copies_in = len(after - before)
            copies_out = sum(original_out or not after or bool(after - {task}) for task in before)
            count = copies_in + copies_out
            scheduled_bytes += count * tensor["size"]
            service += count * max(1, (tensor["size"] + 59) // 60)
            if not before and len(after) > 1:
                shared_external_bytes += copies_in * tensor["size"]
            if count:
                copies.append([tid, copies_in, copies_out, tensor["size"]])
        movement = measured["data_movement_bytes"]
        if movement["spill_added_copy_bytes"] or scheduled_bytes != movement["scheduled_copy_bytes"]:
            raise ValueError("static boundary copy bytes do not reconcile with the no-spill result")
        cores_info = []
        all_tasks = []
        for row in measured["per_core_timeline"]:
            tasks = row["tasks"]
            all_tasks.extend(tasks)
            cores_info.append(dict(core=row["core_id"], tasks=tasks,
                first_task_start=min(t["start"] for t in tasks),
                last_task_end=max(t["end"] for t in tasks),
                total_task_duration=sum(t["duration"] for t in tasks),
                pipe_busy_cycles={pipe: sum(o["duration"] for o in row["ops"] if o["pipe"] == pipe)
                                  for pipe in sorted({o["pipe"] for o in row["ops"]})}))
        if max(t["end"] for t in all_tasks) != measured["makespan"]:
            raise ValueError("timeline end differs from result")
        result["cells"].append(dict(cores=cores, result_source=measured_source,
            model_source=diag_source, plan_source=plan_source,
            makespan=measured["makespan"], captain_makespan=old["metrics"]["makespan_cycles"],
            selected_proxy=diag["selected"], movement=movement,
            captain_scheduled_copy_bytes=old["metrics"]["ddr_bytes"],
            captain_extra_ddr_bytes=old["metrics"]["extra_ddr_bytes"],
            reconstructed_boundary_copy_bytes=scheduled_bytes,
            isolated_boundary_copy_service_cycles=service,
            repeated_external_inputs_copy_bytes=shared_external_bytes,
            copy_multiset_sha256=hashlib.sha256(json.dumps(copies, separators=(",", ":")).encode()).hexdigest(),
            memory_dependency_count=sum(x["memory_dependency_count"] for x in measured["step3_by_task"].values()),
            actual_memory_peak_by_core=measured["memory_peak_by_core"], cores_timeline=cores_info))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = analyze()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    print(json.dumps([{k:r[k] for k in ("cores", "makespan", "captain_makespan", "reconstructed_boundary_copy_bytes", "isolated_boundary_copy_service_cycles", "memory_dependency_count")} for r in result["cells"]]))


if __name__ == "__main__":
    main()
