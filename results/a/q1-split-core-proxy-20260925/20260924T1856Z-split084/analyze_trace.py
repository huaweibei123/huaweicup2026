#!/usr/bin/env python3
"""Summarize archived P1 result and Chrome trace artifacts."""
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RUNS = {
    "split_core": ROOT / "results/a/q1-split-core-proxy-20260925/20260924T1856Z-split084",
    "capacity_return": ROOT / "results/a/q1-capacity-return-20260925/20260924T1830Z-capacity084",
}


def read_gzip(path):
    raw = gzip.decompress(path.read_bytes())
    return raw, json.loads(raw)


def summarize(run_dir):
    result_raw, result = read_gzip(run_dir / "result.json.gz")
    trace_raw, trace = read_gzip(run_dir / "trace.json.gz")
    cores = {}
    for core in result["per_core_timeline"]:
        tasks = core["tasks"]
        cores[core["core_id"]] = {
            "core_id": core["core_id"],
            "finish_time": max((t["end"] for t in tasks), default=0),
            "task_count": len(tasks), "pipe_m_busy": 0, "pipe_v_busy": 0,
        }
    ddr = []
    for event in trace["traceEvents"]:
        if event.get("ph") != "X" or "dur" not in event:
            continue
        args = event.get("args", {})
        pipe = event.get("cat") or args.get("pipe")
        core_id = args.get("core_id")
        if pipe in ("PIPE_M", "PIPE_V") and core_id in cores:
            field = "pipe_m_busy" if pipe == "PIPE_M" else "pipe_v_busy"
            cores[core_id][field] += event["dur"]
        if pipe in ("PIPE_MTE2", "PIPE_MTE3"):
            ddr.append((event["ts"], event["ts"] + event["dur"]))
    ddr.sort()
    union = 0
    if ddr:
        lo, hi = ddr[0]
        for start, end in ddr[1:]:
            if start <= hi:
                hi = max(hi, end)
            else:
                union += hi - lo
                lo, hi = start, end
        union += hi - lo
    return {
        "result_sha256_decompressed": hashlib.sha256(result_raw).hexdigest(),
        "trace_sha256_decompressed": hashlib.sha256(trace_raw).hexdigest(),
        "makespan": result.get("makespan"),
        "per_core": [cores[k] for k in sorted(cores)],
        "global_ddr_busy_union": union,
    }


def main():
    output = {
        "method": {
            "per_core_finish": "max task end in per_core_timeline",
            "pipe_busy": "sum traceEvents dur for PIPE_M and PIPE_V by args.core_id",
            "ddr_busy_union": "union length of PIPE_MTE2 and PIPE_MTE3 trace intervals",
        },
        "runs": {name: summarize(path) for name, path in RUNS.items()},
    }
    print(json.dumps(output, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
