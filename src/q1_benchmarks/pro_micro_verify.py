"""Read-only fixed-Git integrity check; never invokes a solver or evaluator."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(commit, folder):
    def blob(rev, path):
        return subprocess.check_output(["git", "show", f"{rev}:{path}"], cwd=ROOT)

    def data(path):
        return json.loads(blob(commit, f"{folder}/{path}"))

    batch, manifest = data("batch.json"), data("manifest.json")
    assert len(commit) == 40
    assert batch["status"] == "complete" and batch["statuses"] == {"ok": 6}
    assert batch["gate"] == "CLOSED" and batch["owned_processes_released"]
    assert batch["calls"] == {"official_solver": 0, "prototype_solver_process": 0,
                              "C_encode": 1, "reused_author_plans": 5, "E0": 6, "E1": 0, "E2": 0}
    assert batch["wall_seconds"] <= 240
    checked = {}

    def refs(value):
        if isinstance(value, dict):
            if "path" in value and "sha256" in value:
                raw = blob(commit, value["path"])
                assert digest(raw) == value["sha256"], value["path"]
                if "bytes" in value:
                    assert len(raw) == value["bytes"]
                checked[value["path"]] = len(raw)
            for child in value.values():
                refs(child)
        elif isinstance(value, list):
            for child in value:
                refs(child)

    refs(batch)
    source = manifest["source_commit"]
    assert batch["source_commit"] == source
    for item in manifest["source_files"]:
        raw = blob(source, item["git_path"])
        assert digest(raw) == item["sha256"] and len(raw) == item["bytes"]
    for item in manifest["official_files"]:
        assert digest(blob(source, item["path"])) == item["sha256"]
        assert digest(blob(batch["runner_commit"], item["path"])) == item["sha256"]
    assert blob(batch["runner_commit"], batch["runner"]["path"]) == blob(commit, batch["runner"]["path"])
    prefix = manifest["material_git_root"]
    pids = []
    for cell, row in zip(manifest["cells"], batch["rows"], strict=True):
        assert cell["id"] == row["id"] and row["status"] == "ok"
        assert data(f"{cell['id']}/run.json") == row
        assert blob(commit, row["input"]["path"]) == blob(source, f"{prefix}/{cell['input']}")
        if cell["plan_mode"] == "reuse_author_bytes":
            assert blob(commit, row["plan"]["path"]) == blob(source, f"{prefix}/{cell['plan']}")
            assert row["solver_wall_seconds"] is None
        plan = json.loads(blob(commit, row["plan"]["path"]))
        graph = json.loads(blob(commit, row["input"]["path"]))
        assert set(plan) == {"node_to_subgraph", "core_schedules"}
        assert len(plan["core_schedules"]) == 1
        expected = {o["id"] for o in graph["ops"] if o["op"] not in {"COPY_IN", "COPY_OUT"}}
        assert set(map(int, plan["node_to_subgraph"])) == expected
        result = json.loads(blob(commit, row["result.json"]["path"]))
        trace = json.loads(blob(commit, row["trace.json"]["path"]))
        assert result["scene"] == "A" and result["num_cores"] == 1
        assert result["makespan"] == row["observed"]["makespan_cycles"]
        for key, value in result["data_movement_bytes"].items():
            assert row["observed"][key] == value
        for key, expected in cell["assertions"].items():
            assert row["observed"][key] == expected and row["assertions"][key]["passed"]
        assert trace["traceEvents"]
        assert max(o["end"] for core in result["per_core_timeline"] for o in core["ops"]) == result["makespan"]
        receipt = data(f"{cell['id']}/e0-process.json")
        assert row["e0"] == receipt
        assert receipt["status"] == "ok" and receipt["exit_code"] == 0 and not receipt["timed_out"]
        assert receipt["cleanup_confirmed"] and receipt["wall_seconds"] <= 30
        pids.append(receipt["pid"])
    assert len(set(pids)) == 6
    release = data("resource-release.json")
    # The release receipt enumerates the filesystem, whereas rows preserve
    # dispatch order. PID membership must match; enumeration order need not.
    assert release["all_owned_child_groups_exited"] and len(release["pids"]) == 6
    assert set(release["pids"]) == set(pids) and release["E0_calls"] == 6
    return {"data_commit": commit, "source_commit": source, "runner_commit": batch["runner_commit"],
            "checks": "passed", "synthetic_cells": 6, "artifact_references": len(checked),
            "artifact_reference_bytes": sum(checked.values()), "source_files": len(manifest["source_files"]),
            "official_files": len(manifest["official_files"]), "new_solver_or_E0_calls": 0,
            "verification_script_sha256": digest(Path(__file__).read_bytes()),
            "boundary": "Fixed Git integrity and recorded assertions verified; not an independent rerun or formal-board admission"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("commit")
    parser.add_argument("folder")
    args = parser.parse_args()
    print(json.dumps(verify(args.commit, args.folder), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
