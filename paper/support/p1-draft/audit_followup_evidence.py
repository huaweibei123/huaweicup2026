"""Read fixed research archives and recompute paper claims; no algorithm execution.

Candidate frontiers are recomputed from the author's exported E1 scores, not
from new E0 runs or an independent extraction of all producer diagnostics.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

from recompute_snapshot import ARCHIVE, FEED, FEED_SHA256, read_blob

FOLLOWUP = "eb001049a7946e0150359a655bd5563ffe80b6fd"
PILOT_SOURCE = "4fc5e5e91e4a2ac9feaf05267c1f8ab713ca5990"
PILOT = "results/a/p1-lazy-seed-colab-20260925/run-0511Z"
DDR = "results/a/p1-secondary-ddr-audit-20260925"
SINK_COMMIT = "cd2821896e83b2059feac9d16a99c19087e78882"
SINK = "results/a/q1-sink-member-runs/farmer-20260925T0426Z-sink8"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def audit(repo: Path) -> dict:
    inventory = {}

    def raw(commit, path, expected=None):
        data = read_blob(repo, commit, path)
        digest = hashlib.sha256(data).hexdigest()
        require(expected is None or digest == expected, f"hash mismatch: {path}")
        inventory[f"{commit}:{path}"] = {"bytes": len(data), "sha256": digest}
        return data

    def obj(commit, path, expected=None):
        return json.loads(raw(commit, path, expected))

    v4 = obj(ARCHIVE, FEED, FEED_SHA256)["records"]
    index4 = {(r["case_id"], r["cores"]): r for r in v4}
    ddr_report = obj(FOLLOWUP, DDR + "/audit.json")
    v1_info = ddr_report["v1"]
    v1 = obj(v1_info["commit"], v1_info["feed_path"], v1_info["feed_sha256"])["records"]
    index1 = {(r["case_id"], r["cores"]): r for r in v1}
    expected_cells = {(f"{i:03d}", k) for i in range(1, 101) for k in range(1, 6)}
    require(len(v1) == len(v4) == 500 and set(index1) == set(index4) == expected_cells,
            "incomplete or duplicate paired full batches")
    changes = {}
    for k in range(1, 6):
        counts = Counter()
        totals = [0, 0]
        for case in sorted(f"{i:03d}" for i in range(1, 101)):
            a, b = index1[case, k], index4[case, k]
            require(a["status"] == b["status"] == "ok", "unsuccessful feed row")
            require(a["solver_commit"] == v1_info["solver_commit"] and
                    b["solver_commit"] == ddr_report["v4"]["solver_commit"], "paired solver identity")
            for field in ("graph_sha256", "config_sha256", "official_sha256"):
                require(a["identity"][field] == b["identity"][field], "paired identity mismatch")
            require(a["baseline"]["result"]["sha256"] == b["baseline"]["result"]["sha256"],
                    "paired baseline mismatch")
            x, y = a["metrics"]["extra_ddr_bytes"], b["metrics"]["extra_ddr_bytes"]
            counts["increased" if y > x else "decreased" if y < x else "equal"] += 1
            totals[0] += x
            totals[1] += y
        saved = ddr_report["per_core_extra_ddr_delta_v4_minus_v1"][str(k)]
        require(all(counts[t] == saved[f"extra_ddr_{t}"] for t in ("increased", "decreased", "equal")),
                "DDR change counts disagree")
        require(totals == [saved["v1_total_extra_ddr_bytes"], saved["v4_total_extra_ddr_bytes"]],
                "DDR totals disagree")
        changes[str(k)] = {"counts": dict(counts), "v1_total_bytes": totals[0], "v4_total_bytes": totals[1]}
    k5 = [r for r in v4 if r["cores"] == 5]
    spill = sum(r["metrics"]["spill_bytes"] for r in k5)
    extra = sum(r["metrics"]["extra_ddr_bytes"] for r in k5)
    pair028 = {v: idx["028", 5]["metrics"] for v, idx in (("v1", index1), ("v4", index4))}

    frontiers = obj(FOLLOWUP, DDR + "/candidate-frontiers.json")
    require(frontiers["feed_sha256"] == FEED_SHA256 and not frontiers["discrepancies"], "frontier source")
    frontier_rows = frontiers["per_case_scored_candidates_and_frontier"]
    require(len(frontier_rows) == 100 and {r["case_id"] for r in frontier_rows} ==
            {f"{i:03d}" for i in range(1, 101)}, "candidate case coverage")
    counts = Counter()
    for row in frontier_rows:
        case = row["case_id"]
        selected = index4[case, 5]
        published = row["official_E0_selected_plan"]
        require(published["plan_sha256"] == selected["identity"]["plan_sha256"], "selected hash")
        for field, feed_field in (("makespan_cycles", "makespan_cycles"), ("extra_ddr_bytes", "extra_ddr_bytes"),
                                  ("scheduled_copy_bytes", "ddr_bytes")):
            require(published[field] == selected["metrics"][feed_field], "selected metrics")
        scores = row["e1_successful_scored_candidates"]
        counts["scored_cells" if scores else "unscored_cells"] += 1
        counts["successful_scores"] += len(scores)
        require(all(c["status"] == "ok" for c in scores), "unsuccessful candidate in successful list")
        pairs = {(c["makespan_cycles"], c["extra_ddr_bytes"]) for c in scores}
        pareto = {p for p in pairs if not any(q != p and q[0] <= p[0] and q[1] <= p[1] for q in pairs)}
        require(pareto == {(p["makespan_cycles"], p["extra_ddr_bytes"]) for p in row["pareto_frontier"]},
                "exported candidate frontier mismatch")
        counts["frontier_points"] += len(pareto)
        counts["tradeoff_cells"] += len(pareto) > 1
        counts["unselected_joint_improvements"] += sum(
            c["plan_sha256"] != published["plan_sha256"] and
            c["makespan_cycles"] <= published["makespan_cycles"] and
            c["extra_ddr_bytes"] < published["extra_ddr_bytes"] for c in scores)
    require(dict(counts) == {"unscored_cells": 6, "scored_cells": 94, "successful_scores": 268,
                            "frontier_points": 152, "tradeoff_cells": 50,
                            "unselected_joint_improvements": 0}, "candidate counts changed")

    receipt = obj(FOLLOWUP, PILOT + "/receipt.json")
    archive = raw(FOLLOWUP, PILOT + "/evidence.tar.gz", receipt["archive"]["sha256"])
    require(len(archive) == receipt["archive"]["bytes"], "pilot archive size")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
        files = {}
        for item in receipt["evidence_files"]:
            member = package.getmember(item["path"])
            require(member.isfile(), "pilot member is not a regular file")
            data = package.extractfile(member).read()
            require(len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"],
                    "pilot evidence member hash")
            files[item["path"]] = data
        manifest = json.load(package.extractfile("evidence/evidence-manifest.json"))
        require(manifest["files"] == receipt["evidence_files"], "pilot evidence manifest")
    report = json.loads(files["workspace/evidence/lazy-seed-008/report.json"])
    plan_bytes = files["workspace/evidence/lazy-seed-008/plan.json"]
    plan = json.loads(plan_bytes)
    require(receipt["algorithm_source"] == PILOT_SOURCE, "pilot source")
    require(report["status"] == "verified_model" and receipt["probe"]["returncode"] == 0, "pilot status")
    require(hashlib.sha256(plan_bytes).hexdigest() == report["plan_sha256"] == receipt["plan_sha256"], "pilot plan")
    require(report["source_scope"] == report["source_scope_after"] and
            report["official_source_scope"] == report["official_source_scope_after"], "pilot source changed")
    for path, digest in report["source_scope"].items():
        raw(PILOT_SOURCE, path, digest)
    for path, digest in report["official_source_scope"][0]:
        raw(PILOT_SOURCE, "data/raw/a/official/" + path, digest)
    for path, digest in report["official_source_scope"][1]:
        raw(PILOT_SOURCE, path, digest)
    with zipfile.ZipFile(io.BytesIO(raw(PILOT_SOURCE, "data/raw/a/official-cases.zip"))) as graphs:
        names = [n for n in graphs.namelist() if n.endswith("/case_008.json") and "__MACOSX/" not in n]
        require(len(names) == 1, "008 graph entry")
        graph_bytes = graphs.read(names[0])
    require(hashlib.sha256(graph_bytes).hexdigest() == report["graph_sha256"] ==
            index4["008", 5]["identity"]["graph_sha256"], "pilot graph identity")
    graph = json.loads(graph_bytes)
    compute = {str(op["id"]) for op in graph["ops"] if op["op"] not in {"COPY_IN", "COPY_OUT"}}
    require(set(plan) == {"node_to_subgraph", "core_schedules"}, "two-key plan contract")
    require(set(plan["node_to_subgraph"]) == compute, "pilot operation coverage")
    require(len(plan["core_schedules"]) == report["cores"] == 5, "pilot cores")
    tasks = set(plan["node_to_subgraph"].values())
    schedules = [task for line in plan["core_schedules"] for task in line]
    require(len(schedules) == len(set(schedules)) and set(schedules) == tasks, "pilot Task bijection")
    require(len(tasks) == report["full_plan_tasks"] == receipt["full_plan_tasks"] == 8, "pilot Task count")
    for group in report["selected_groups"]:
        expected_nodes = {int(u) for u, task in plan["node_to_subgraph"].items() if task == group["task_id"]}
        require(expected_nodes == set(group["nodes"]) and
                group["task_id"] in plan["core_schedules"][group["core"]], "pilot group mapping")
    for report_field, receipt_field in (("task_compile_confirmed_completed", "Task_compile_confirmed_completed"),
                                         ("response_confirmed_completed", "Fraction_response_completed")):
        require(report[report_field] == receipt["calls"][receipt_field], "pilot call accounting")
    cert = report["certificate"]
    require(all(t["execution_contract_validated"] for t in cert["tasks"].values()), "Step3 contract flags")
    require(cert["traffic"] == receipt["compiler_traffic"], "pilot traffic mismatch")
    require(report["scalar"]["upper"] == receipt["model_upper"] and not report["scalar"]["optimal"], "pilot scalar")
    require(receipt["official_Makespan"] is None and not receipt["official_score_claim"], "not an E0 result")

    sink_feed = obj(SINK_COMMIT, SINK + "/board-feed.json")["records"]
    sink_rows = []
    for row in sink_feed:
        old = index4[row["case_id"], 4]
        require(row["status"] == "ok" and row["cores"] == 4, "sink batch coverage")
        for field in ("graph_sha256", "config_sha256", "official_sha256"):
            require(row["identity"][field] == old["identity"][field], "sink identity")
        for name in ("plan", "result"):
            artifact = row["artifacts"][name]
            data = raw(SINK_COMMIT, artifact["path"], artifact["sha256"])
            if name == "result":
                result = json.loads(gzip.decompress(data))
        require(result["makespan"] == row["metrics"]["makespan_cycles"], "sink result cycles")
        require(result["data_movement_bytes"]["added_copy_bytes"] == row["metrics"]["extra_ddr_bytes"],
                "sink result bytes")
        sink_rows.append({"case_id": row["case_id"], "makespan_cycles": result["makespan"],
                          "same_cycles_as_v4": result["makespan"] == old["metrics"]["makespan_cycles"],
                          "same_plan_bytes_as_v4": row["identity"]["plan_sha256"] == old["identity"]["plan_sha256"],
                          "same_extra_ddr_as_v4": row["metrics"]["extra_ddr_bytes"] == old["metrics"]["extra_ddr_bytes"]})
    require(len(sink_rows) == 8 and len({r["case_id"] for r in sink_rows}) == 8, "eight sink cases")
    return {
        "kind": "fixed_archives_readonly_paper_evidence_audit",
        "ddr": {"paired_cells": 500, "per_core_v1_v4": changes, "case028_k5": pair028,
                "k5_v4_extra_bytes": extra, "k5_v4_spill_bytes": spill, "k5_v4_partition_bytes": extra - spill,
                "k5_extra_change_vs_v1_percent": 100 * (extra / changes["5"]["v1_total_bytes"] - 1)},
        "e1_frontiers": {"counts_recomputed": dict(counts),
                         "scope": "author-exported candidate scores only; no independent read of all raw diagnostics; not candidate-by-candidate E0"},
        "real_memory_pilot": {"archive_commit": FOLLOWUP, "algorithm_source": PILOT_SOURCE,
                              "evidence_files_hashed": len(files), "compute_ops": len(compute), "tasks": len(tasks),
                              "archived_calls": receipt["calls"], "scalar": report["scalar"], "seed": report["seed"],
                              "traffic": cert["traffic"], "example_task0": {k: cert["tasks"]["0"][k] for k in
                                    ("footprint", "memory_peak", "execution_contract_validated")},
                              "probe_wall_seconds": receipt["probe"]["wall_seconds"], "official_Makespan": None,
                              "scope": "verified archived bytes and static coverage; no new compilation or response simulation"},
        "sink_windows_replication": {"archive_commit": SINK_COMMIT, "rows": sink_rows,
                                     "scope": "eight targeted K4 E0 archives; standalone sink constructor, not a full v4 rerun"},
        "source_blob_inventory": inventory,
        "new_calls": {"solver": 0, "Task_compile": 0, "response": 0, "E0": 0, "E1": 0, "E2": 0},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "output already exists; preserve prior snapshot")
    result = audit(Path(__file__).resolve().parents[3])
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"status": "passed", "source_blobs": len(result["source_blob_inventory"]),
                      "paired_cells": 500, "pilot_evidence_files": 5, "sink_cells": 8,
                      "new_calls": result["new_calls"]}))
