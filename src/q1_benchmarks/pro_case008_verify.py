"""Fixed-Git evidence verification for the single offline case008 candidate."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def verify(commit, folder):
    def blob(rev, path):
        return subprocess.check_output(["git", "show", f"{rev}:{path}"], cwd=ROOT)

    def sha(raw):
        return hashlib.sha256(raw).hexdigest()

    def data(name):
        return json.loads(blob(commit, f"{folder}/{name}"))

    run, manifest = data("run.json"), data("manifest.json")
    assert len(commit) == 40
    assert run["status"] == "ok" and run["gate"] == "CLOSED" and run["owned_processes_released"]
    assert run["calls"] == {"solver": 1, "E0": 1, "E1": 0, "E2": 0, "baseline_E0": 0}
    assert run["wall_seconds"] <= 120
    checked = {}

    def refs(value):
        if isinstance(value, dict):
            if "path" in value and "sha256" in value:
                raw = blob(commit, value["path"])
                assert sha(raw) == value["sha256"], value["path"]
                if "bytes" in value:
                    assert len(raw) == value["bytes"]
                checked[value["path"]] = len(raw)
            for item in value.values():
                refs(item)
        elif isinstance(value, list):
            for item in value:
                refs(item)
    refs(run)
    source, runner = manifest["source_commit"], run["runner_commit"]
    for item in manifest["source_files"]:
        assert sha(blob(source, item["git_path"])) == item["sha256"]
    for item in manifest["official_files"]:
        assert sha(blob(source, item["path"])) == item["sha256"]
        assert sha(blob(runner, item["path"])) == item["sha256"]
    for item in manifest["runtime_dependencies"]:
        assert sha(blob(runner, item["path"])) == item["sha256"]
    assert blob(commit, run["runner"]["path"]) == blob(runner, run["runner"]["path"])
    graph_raw = blob(commit, manifest["input"]["path"])
    archive = blob(source, manifest["input"]["archive"])
    assert sha(archive) == manifest["input"]["archive_sha256"]
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        assert graph_raw == z.read(manifest["input"]["member"])
    assert blob(runner, manifest["input"]["path"]) == graph_raw
    baseline = manifest["baseline"]
    for item in baseline["artifacts"]:
        assert sha(blob(item["commit"], item["path"])) == item["sha256"]
    old = json.loads(gzip.decompress(blob(baseline["commit"], baseline["result_path"])))
    assert old["makespan"] == baseline["makespan_cycles"] == 123060
    graph, plan, result, info = json.loads(graph_raw), data("plan.json"), data("result.json"), data("diagnostics.json")
    assert set(plan) == {"node_to_subgraph", "core_schedules"} and len(plan["core_schedules"]) == 4
    assert set(map(int, plan["node_to_subgraph"])) == {o["id"] for o in graph["ops"] if o["op"] not in {"COPY_IN", "COPY_OUT"}}
    assert result["scene"] == "A" and result["num_cores"] == 4
    assert result["makespan"] == run["makespan_cycles"] == 162326
    assert result["data_movement_bytes"] == run["data_movement_bytes"]
    assert data("trace.json")["traceEvents"]
    assert max(op["end"] for core in result["per_core_timeline"] for op in core["ops"]) == result["makespan"]
    for key in ("packet", "cut_chains", "whole_packet", "conservative_dominance_certificate"):
        assert run["constructor_selection"][key] == info[key]
    audit = data("official-structure-audit.json")
    assert audit["memory_dependency_count_by_task"] == {key: value["memory_dependency_count"] for key, value in result["step3_by_task"].items()}
    flattened = [op for row in audit["pipe_execution_order"] for op in row["ops_in_observed_start_order"]]
    expected = [op for core in result["per_core_timeline"] for op in core["ops"]]
    assert sorted(flattened, key=lambda x: (x["task_id"], x["op_id"])) == sorted(expected, key=lambda x: (x["task_id"], x["op_id"]))
    pids = []
    for name, field, limit in (("solver", "solver", 30), ("e0", "evaluation", 60)):
        receipt = data(f"{name}-process.json")
        assert receipt == run[field] and receipt["exit_code"] == 0 and receipt["status"] == "ok"
        assert receipt["cleanup_confirmed"] and not receipt["timed_out"] and receipt["wall_seconds"] <= limit
        pids.append(receipt["pid"])
    release = data("resource-release.json")
    assert release["all_owned_child_groups_exited"] and len(release["pids"]) == 2 and set(release["pids"]) == set(pids)
    assert release["calls"] == run["calls"]
    return {"checks": "passed", "data_commit": commit, "runner_commit": runner, "source_commit": source,
            "artifacts": len(checked), "artifact_bytes": sum(checked.values()), "graph_bytes": len(graph_raw),
            "official_files": len(manifest["official_files"]), "source_files": len(manifest["source_files"]),
            "old_makespan": old["makespan"], "new_makespan": result["makespan"],
            "new_solver_or_E0_calls": 0, "verifier_sha256": sha(Path(__file__).read_bytes()),
            "scope": "Fixed Git identity and result consistency, not an independent scoring rerun or board admission"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("commit")
    parser.add_argument("folder")
    args = parser.parse_args()
    print(json.dumps(verify(args.commit, args.folder), indent=2))
