"""Independent read-only audit of the saved P2 batch; never runs solver or E0."""
from __future__ import annotations

import gzip
import hashlib
import json
import statistics
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
BASE = Path(__file__).resolve().parent
REL = BASE.relative_to(ROOT).as_posix()
SPEC_COMMIT = "027d4bf9ccecdc82e2c5ddbce52cea5345e95b8b"
PIPES = ("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def artifact(item):
    data = (ROOT / item["path"]).read_bytes()
    assert sha(data) == item["sha256"], item["path"]
    return data


def main():
    ledger = read(f"{REL}/ledger.json")
    spec = read(f"{REL}/spec.json")
    spec_path = f"{REL}-spec.json"
    spec_bytes = (ROOT / spec_path).read_bytes()
    assert sha(spec_bytes) == ledger["spec_sha256"]
    assert spec_bytes == subprocess.check_output(["git", "show", f"{SPEC_COMMIT}:{spec_path}"], cwd=ROOT)
    assert spec == json.loads(spec_bytes)
    feed_path, = (p for p in BASE.glob("board-feed-*.json") if "preflight" not in p.name)
    feed = json.loads(feed_path.read_text(encoding="utf-8"))
    preflight = read(feed_path.with_name(feed_path.stem + "-preflight.json").relative_to(ROOT))
    assert preflight["returncode"] == 0
    assert artifact(preflight["feed"]) == feed_path.read_bytes()
    by_case = {r["case_id"]: r for r in feed["records"]}
    n = len(spec["cases"])
    assert list(by_case) == spec["cases"] and len(by_case) == n
    assert json.loads(preflight["stdout"])["eligible"] == n
    assert ledger["state"] == "completed"
    assert ledger["charged_calls"] == dict(solver=n, E0=n, E1=0, E2=0)
    assert len(ledger["attempts"]) == n and len(ledger["reservations"]) == 2*n
    reservations = {(r["attempt_id"], r["stage"]): r for r in ledger["reservations"]}
    assert len(reservations) == 2*n
    source_checks = []
    for path, expected in ledger["source_hashes"].items():
        commit = (spec["evaluator_commit"] if path.startswith("data/raw/") else
                  spec["runner_commit"] if path.endswith("/measure.py") else spec["solver_commit"])
        assert sha((ROOT/path).read_bytes()) == expected
        assert sha(subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)) == expected
        source_checks.append({"path": path, "sha256": expected, "commit": commit})
    official_lines = "".join(f"{p.removeprefix('data/raw/a/official/')}\t{v}\n"
                             for p, v in sorted(ledger["source_hashes"].items()) if p.startswith("data/raw/"))
    official_sha = sha(official_lines.encode())
    stages, cases = [], []
    gz_count = trace_ops_count = feed_artifact_count = 0
    for run_path in ledger["attempts"]:
        run = read(run_path)
        cid = run["case_id"]
        rec = by_case[cid]
        folder = (ROOT/run_path).parent
        assert run["status"] == "ok" and run["failure"] is None
        assert run["source_hashes"] == ledger["source_hashes"]
        assert run["calls"] == dict(solver=1, E0=1, E1=0, E2=0)
        assert run["identity"] == rec["identity"]
        assert run["identity"]["official_sha256"] == official_sha
        assert sha((ROOT/f"data/raw/a/official/data/case_{cid}.json").read_bytes()) == run["identity"]["graph_sha256"]
        assert all(run[k] == spec[k] for k in ("solver_commit", "runner_commit", "evaluator_commit"))
        for item in rec["artifacts"].values():
            artifact(item)
            feed_artifact_count += 1
        decoded = {}
        for name, item in run["compression"].items():
            stored = artifact(item["artifact"])
            raw = gzip.decompress(stored)
            assert sha(raw) == item["raw_sha256"] and len(raw) == item["raw_bytes"]
            assert len(stored) == item["stored_bytes"] and int.from_bytes(stored[4:8], "little") == 0
            decoded[name] = json.loads(raw)
            gz_count += 1
        result, trace = decoded["result.json"], decoded["trace.json"]
        makespan = result["makespan"]
        assert makespan == run["metrics"]["makespan_cycles"] == rec["metrics"]["makespan_cycles"] == trace["otherData"]["makespan"]
        assert result["num_cores"] == spec["cores"] and result["scene"] == "B"
        assert result["data_movement_bytes"] == run["metrics"]["data_movement_bytes"]
        assert rec["metrics"]["ddr_bytes"] == result["data_movement_bytes"]["scheduled_copy_bytes"]
        assert rec["metrics"]["extra_ddr_bytes"] == result["data_movement_bytes"]["added_copy_bytes"]
        assert rec["metrics"]["spill_bytes"] == result["data_movement_bytes"]["spill_added_copy_bytes"]
        assert f"makespan={makespan}" in (folder/"E0.stdout.txt").read_text()
        assert f"makespan: {makespan}" in (folder/"result.txt").read_text()
        for stage in ("solver", "E0"):
            st = run["stages"][stage]
            reserved = reservations[(run["attempt_id"], stage)]
            assert st["status"] == "ok" and st["returncode"] == 0 and st["launched"]
            assert reserved["state"] == "ok" and reserved["launched"]
            assert reserved["actual_wall_seconds"] == st["wall_seconds"]
            assert reserved["reserved_at"] <= st["started_at"] < st["finished_at"]
            assert (folder/f"{stage}.stderr.txt").read_bytes() == b""
            stages.append((st["started_at"], st["finished_at"], cid, stage))
        report = json.loads((folder/"solver.stdout.txt").read_text())
        assert report == rec["parameters"]["solver_report"] and report["online_E0_calls"] == 0
        plan = json.loads(artifact(run["artifacts"]["plan"]))
        assert set(plan) == {"node_to_subgraph", "core_schedules"}
        assert len(plan["core_schedules"]) == spec["cores"]
        scheduled = [s for core in plan["core_schedules"] for s in core]
        assert len(set(scheduled)) == len(scheduled) and set(scheduled) == set(plan["node_to_subgraph"].values())
        graph = read(f"data/raw/a/official/data/case_{cid}.json")
        eligible = {str(op["id"]) for op in graph["ops"] if op["op"] not in ("COPY_IN", "COPY_OUT")}
        assert set(plan["node_to_subgraph"]) == eligible
        trace_ops = {(e["args"]["core_id"], e["args"]["op_id"]): (e["cat"], e["ts"], e["ts"]+e["dur"])
                     for e in trace["traceEvents"] if e.get("ph") == "X" and e.get("cat") in PIPES}
        result_ops = {}
        for core in result["per_core_timeline"]:
            for pipe in PIPES:
                ops = sorted((op for op in core["ops"] if op["pipe"] == pipe), key=lambda x: (x["start"], x["end"]))
                assert all(a["end"] <= b["start"] for a, b in zip(ops, ops[1:]))
            for op in core["ops"]:
                assert op["end"]-op["start"] == op["duration"] and 0 <= op["start"] <= op["end"] <= makespan
                result_ops[(core["core_id"], op["op_id"])] = (op["pipe"], op["start"], op["end"])
        assert trace_ops == result_ops and max(v[2] for v in result_ops.values()) == makespan
        trace_ops_count += len(result_ops)
        baseline_path = f"results/benchmark-board/official-singlecore-20260924/{cid}/run.json"
        baseline = read(baseline_path)
        assert baseline["status"] == "ok"
        assert baseline["graph_sha256"] == run["identity"]["graph_sha256"]
        assert baseline["config_sha256"] == run["identity"]["config_sha256"]
        assert baseline["official_code_hash"] == official_sha
        item = baseline["artifacts"]["result.json"]
        raw = gzip.decompress(artifact(item))
        assert sha(raw) == item["raw_sha256"] and json.loads(raw)["makespan"] == baseline["makespan_cycles"]
        cases.append({"case_id": cid, "makespan_cycles": makespan,
                      "singlecore_cycles": baseline["makespan_cycles"],
                      "speedup": baseline["makespan_cycles"]/makespan,
                      "solver_wall_seconds": run["stages"]["solver"]["wall_seconds"],
                      "E0_wall_seconds": run["stages"]["E0"]["wall_seconds"],
                      "data_movement_bytes": result["data_movement_bytes"],
                      "route": report["selected"], "trace_ops_verified": len(result_ops)})
    stages.sort()
    assert all(a[1] <= b[0] for a, b in zip(stages, stages[1:]))
    assert ledger["started_at"] <= stages[0][0] and stages[-1][1] <= ledger["finished_at"]
    output = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "Read-only audit of saved batch; no solver or evaluator calls.",
              "batch": {k: ledger[k] for k in ("run_id", "started_at", "finished_at", "state", "charged_calls", "batch_wall_seconds", "preparation", "environment")},
              "spec_commit": SPEC_COMMIT, "spec_sha256": ledger["spec_sha256"],
              "source_checks": source_checks,
              "integrity": {"gzip_raw_and_stored_verified_count": gz_count,
                            "feed_artifact_reference_hashes_verified": feed_artifact_count,
                            "trace_operation_intervals_verified": trace_ops_count,
                            "stage_order_single_worker_verified": True, "empty_stderr_count": 2*n},
              "feed": {"path": feed_path.relative_to(ROOT).as_posix(), "sha256": sha(feed_path.read_bytes()),
                       "records": n, "eligible": n, "failed": 0},
              "cases": cases,
              "partial_summary": {"case_count": n,
                                  "arithmetic_mean_speedup": statistics.mean(c["speedup"] for c in cases),
                                  "solver_sum_seconds": sum(c["solver_wall_seconds"] for c in cases),
                                  "solver_median_seconds": statistics.median(c["solver_wall_seconds"] for c in cases),
                                  "solver_max_seconds": max(c["solver_wall_seconds"] for c in cases),
                                  "E0_sum_seconds": sum(c["E0_wall_seconds"] for c in cases)},
              "limitations": ["Partial batch mean is not the full 100-case mean.",
                              "Fresh process per case; OS caches and shared background load uncontrolled.",
                              "External E0 is separate from solver wall; peak RSS was not sampled."]}
    (BASE/"measurement-audit.json").write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"batch": BASE.name, "cases": n, "gzip_verified": gz_count,
                      "trace_ops_verified": trace_ops_count, "mean": output["partial_summary"]["arithmetic_mean_speedup"]}))


if __name__ == "__main__":
    main()
