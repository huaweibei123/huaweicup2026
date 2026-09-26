"""Read only the fixed 021/k3 P2/P3 Git objects; emit a compact audit JSON."""
from __future__ import annotations

from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent / "audit.json"
P2_COMMIT = "19bebf35205d23fdd832781540f8879da52eeb62"
P3_COMMIT = "130dfe4c6a10d394a6d04257f660d5a66c51c624"
SUMMARY_COMMIT = "27409658d869671d30e940f536bbab30d50d3ef9"
P2_PATH = "results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft/cache_pair/021-k3/result.json.gz"
P3_PATH = "results/a/q3-nikolastarx/witness-full500-20260925-s59/20260924T2032Z-s59ee/s06/cells/021-k3-unified-attention-witness-e0/evidence/result.json.gz"
P3_PLAN_PATH = "results/a/q3-nikolastarx/witness-full500-20260925-s59/20260924T2032Z-s59ee/s06/cells/021-k3-unified-attention-witness-e0/case_021_multicore_res.json"
SUMMARY_PATH = "results/a/q3-nikolastarx/cachepair500-feedback-20260925/summary.json"


def git_bytes(commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def load_result(commit, path, expected):
    packed = git_bytes(commit, path)
    actual = hashlib.sha256(packed).hexdigest()
    if actual != expected:
        raise ValueError(f"result gzip SHA mismatch: {path}")
    return json.loads(gzip.decompress(packed)), dict(commit=commit, path=path,
        gzip_sha256=actual, gzip_bytes=len(packed))


def op_index(result):
    indexed = {}
    orders = {}
    for core in result["per_core_timeline"]:
        c = core["core_id"]
        keys = []
        for op in core["ops"]:
            key = (c, op["task_id"], op["op_id"])
            if key in indexed:
                raise ValueError(f"duplicate op key: {key}")
            indexed[key] = op
            keys.append(key)
        orders[c] = keys
    return indexed, orders


def small(key, a, b):
    return dict(core_id=key[0], task_id=key[1], op_id=key[2],
        op=a["op"], pipe=a["pipe"], p2_start=a["start"], p2_end=a["end"],
        p2_duration=a["duration"], p3_start=b["start"], p3_end=b["end"],
        p3_duration=b["duration"], p3_cache_hit=b.get("cache_hit"),
        p3_memory_path=b.get("memory_path"))


def main():
    summary = json.loads(git_bytes(SUMMARY_COMMIT, SUMMARY_PATH))
    row = next(x for x in summary["negative_cells"] if x["case_id"] == "021" and x["cores"] == 3)
    plan_sha = hashlib.sha256(git_bytes(P3_COMMIT, P3_PLAN_PATH)).hexdigest()
    if plan_sha != row["source_plan_sha256"]:
        raise ValueError("P3 plan does not match paired summary")
    p2, p2_ref = load_result(P2_COMMIT, P2_PATH, row["result_sha256"])
    p3, p3_ref = load_result(P3_COMMIT, P3_PATH, row["cache_result_sha256"])
    if (p2["makespan"], p3["makespan"]) != (row["no_l2_makespan"], row["cache_makespan"]):
        raise ValueError("paired Makespan mismatch")
    a, a_order = op_index(p2)
    b, b_order = op_index(p3)
    if set(a) != set(b):
        raise ValueError("operation identity sets differ")
    static = ("op", "subgraph_id", "pipe")
    static_changes = [key for key in a if any(a[key].get(k) != b[key].get(k) for k in static)]
    if static_changes:
        raise ValueError(f"op/subgraph/pipe mismatch count={len(static_changes)}")
    changed_start = [k for k in a if a[k]["start"] != b[k]["start"]]
    changed_end = [k for k in a if a[k]["end"] != b[k]["end"]]
    changed_duration = [k for k in a if a[k]["duration"] != b[k]["duration"]]
    same_start_slower_copy = [k for k in a if a[k]["op"] == "COPY_IN" and
                              a[k]["start"] == b[k]["start"] and
                              b[k]["duration"] > a[k]["duration"]]
    first_start = min(changed_start, key=lambda k: (min(a[k]["start"], b[k]["start"]), k)) if changed_start else None
    first_end = min(changed_end, key=lambda k: (min(a[k]["end"], b[k]["end"]), k)) if changed_end else None
    first_slower = min(same_start_slower_copy, key=lambda k: (a[k]["start"], a[k]["end"], k)) if same_start_slower_copy else None
    order_differences = [(c, i, a_order[c][i], b_order[c][i])
                         for c in a_order for i in range(len(a_order[c]))
                         if a_order[c][i] != b_order[c][i]]
    first_order = None
    if order_differences:
        c, i, ka, kb = min(order_differences,
                           key=lambda x: (min(a[x[2]]["start"], b[x[3]]["start"]), x[0], x[1]))
        first_order = dict(core_id=c, list_index=i, p2_op_key=list(ka),
                           p2_start=a[ka]["start"], p2_end=a[ka]["end"],
                           p3_op_key=list(kb), p3_start=b[kb]["start"], p3_end=b[kb]["end"])
    pipe_orders_equal = all([k for k in a_order[c] if a[k]["pipe"] == pipe] ==
                            [k for k in b_order[c] if b[k]["pipe"] == pipe]
                            for c in a_order for pipe in ("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3"))
    by_type = Counter(a[k]["op"] for k in a)
    changed_by_type = Counter(a[k]["op"] for k in changed_end)
    report = dict(schema="q3-021-k3-cache-nonmonotone-audit-v1",
        source=dict(p2=p2_ref, p3=p3_ref, summary_commit=SUMMARY_COMMIT,
                    summary_path=SUMMARY_PATH, source_plan_sha256=plan_sha,
                    p3_plan_path=P3_PLAN_PATH),
        identity=dict(p2_scene=p2.get("scene"), p3_scene=p3.get("scene"),
                      p2_cores=p2.get("num_cores"), p3_cores=p3.get("num_cores"),
                      p3_problem=p3.get("problem"), p3_cache_mode=p3.get("cache_mode")),
        makespan=dict(p2=p2["makespan"], p3=p3["makespan"], increase=p3["makespan"]-p2["makespan"],
                      cache_gain=p2["makespan"]/p3["makespan"]),
        movement_equal=p2["data_movement_bytes"] == p3["data_movement_bytes"],
        movement=p2["data_movement_bytes"],
        operation_keys_equal=True, per_core_list_order_equal=a_order == b_order,
        first_per_core_list_order_difference=first_order,
        per_core_pipe_filtered_list_order_equal=pipe_orders_equal,
        operation_count=len(a), op_type_counts=dict(by_type),
        changed_start_count=len(changed_start), changed_end_count=len(changed_end),
        changed_duration_count=len(changed_duration), changed_end_by_type=dict(changed_by_type),
        first_start_change=small(first_start,a[first_start],b[first_start]) if first_start else None,
        first_completion_time_change=small(first_end,a[first_end],b[first_end]) if first_end else None,
        first_same_start_slower_copy_in=small(first_slower,a[first_slower],b[first_slower]) if first_slower else None,
        same_start_slower_copy_in_count=len(same_start_slower_copy),
        definition="First by earliest min(P2,P3) start/end timestamp, then (core,task,op); tied event ordering is not inferred",
        limitation="Two observed timelines; differences and unchanged movement do not establish a complete causal path")
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(out=OUT.relative_to(ROOT).as_posix(), operation_count=len(a),
                          makespan_increase=report["makespan"]["increase"])))


if __name__ == "__main__":
    main()
