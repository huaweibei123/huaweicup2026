"""Read-only, two-cell audit of recorded P2 pipe gaps and cross-core releases.

No evaluator, graph construction, or counterfactual scheduling is performed.
"""
from __future__ import annotations

import collections
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee"
SUMMARY = ROOT / "results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json"
DEST = ROOT / "results/a/q2-nikolastarx/trace-wait-audit-20260925"
CELLS = ("cases-061-070/069-k5", "cases-071-080/071-k5")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def audit_cell(folder: str, summary: dict) -> dict:
    base = ARCHIVE / folder
    run_raw = (base / "run.json").read_bytes()
    run = json.loads(run_raw)
    row = run["accepted_row"]
    matches = [x for x in summary["rows"] if (x["case"], x["cores"]) == (row["case"], row["cores"])]
    assert len(matches) == 1 and matches[0] == row
    compressed = (base / "result.json.gz").read_bytes()
    result_raw = gzip.decompress(compressed)
    assert sha(result_raw) == row["official"]["result_sha256"]
    result = json.loads(result_raw)
    assert result["makespan"] == row["official"]["makespan"]
    assert result["cross_task_traffic"] == row["official"]["cross_task_traffic"]
    assert result["data_movement_bytes"] == row["official"]["movement"]

    previous = {}
    by_id = {}
    pipe_gap_count = 0
    pipe_gap_cycles = 0
    core_ends = {}
    for core in result["per_core_timeline"]:
        cid = core["core_id"]
        groups = collections.defaultdict(list)
        for op in core["ops"]:
            groups[op["pipe"]].append(op)
            by_id[(cid, op["op_id"])] = op
        core_ends[cid] = max((op["end"] for op in core["ops"]), default=0)
        for pipe, ops in groups.items():
            ops.sort(key=lambda op: (op["start"], op["op_id"]))
            for prev, current in zip(ops, ops[1:]):
                assert prev["end"] <= current["start"]
                gap = current["start"] - prev["end"]
                if gap:
                    pipe_gap_count += 1
                    pipe_gap_cycles += gap
                previous[(cid, current["op_id"])] = (prev, current, pipe)

    events = []
    for transfer in result["cross_core_transfers"]:
        source = by_id[(transfer["source_core"], transfer["source_copy_out_id"])]
        target = by_id[(transfer["target_core"], transfer["target_copy_in_id"])]
        assert source["end"] == transfer["copy_out_end"]
        assert target["start"] == transfer["copy_in_start"]
        assert target["end"] == transfer["copy_in_end"]
        release = transfer["copy_in_release"]
        assert release == source["end"] + result["cross_core_copy_delay_cycles"]
        assert release <= target["start"]
        pair = previous.get((transfer["target_core"], target["op_id"]))
        if pair is None:
            continue
        prev, _, pipe = pair
        gap = target["start"] - prev["end"]
        # This subinterval lies in the recorded idle gap and before mandatory
        # external release. It is a bound, not an exclusive cause or M saving.
        pre_release = max(0, min(release, target["start"]) - prev["end"])
        if pre_release:
            events.append({
                "target_core": transfer["target_core"], "pipe": pipe,
                "previous_op_id": prev["op_id"], "previous_end": prev["end"],
                "target_copy_in_id": target["op_id"], "target_start": target["start"],
                "target_end": target["end"], "source_core": transfer["source_core"],
                "source_copy_out_id": source["op_id"], "copy_out_end": source["end"],
                "copy_in_release": release, "gap_cycles": gap,
                "pre_release_idle_cycles": pre_release,
                "release_equals_start": release == target["start"],
            })
    events.sort(key=lambda e: (-e["pre_release_idle_cycles"], e["target_core"], e["target_copy_in_id"]))
    terminal = [cid for cid, end in core_ends.items() if end == result["makespan"]]
    return {
        "case": row["case"], "cores": row["cores"], "makespan": result["makespan"],
        "archive_run_sha256": sha(run_raw), "result_raw_sha256": sha(result_raw),
        "result_gzip_sha256": sha(compressed), "published_accepted_row_equal_archived_run": True,
        "cross_core_transfers": len(result["cross_core_transfers"]),
        "all_positive_pipe_gaps": pipe_gap_count, "all_pipe_gap_cycles": pipe_gap_cycles,
        "positive_pre_release_events": len(events),
        "sum_pre_release_idle_cycles_across_pipes": sum(e["pre_release_idle_cycles"] for e in events),
        "criticality_unknown": True,
        "release_equals_start_events": sum(e["release_equals_start"] for e in events),
        "terminal_cores": terminal, "core_end": core_ends,
        "terminal_core_pre_release_events": sum(e["target_core"] in terminal for e in events),
        "terminal_core_latest_events": sorted(
            (e for e in events if e["target_core"] in terminal),
            key=lambda e: (-e["target_start"], e["target_copy_in_id"]),
        )[:8],
        "largest_events": events[:12],
    }


def main() -> None:
    summary_raw = SUMMARY.read_bytes()
    summary = json.loads(summary_raw)
    assert summary["status"] == "completed" and len(summary["rows"]) == 500
    out = {
        "published_completed_summary_path": str(SUMMARY.relative_to(ROOT)),
        "published_completed_summary_sha256": sha(summary_raw),
        "published_completed_summary_status": summary["status"],
        "official_source": "data/raw/a/official/code/multicore_cut_evaluate_problem_2.py",
        "official_source_sha256": sha((ROOT / "data/raw/a/official/code/multicore_cut_evaluate_problem_2.py").read_bytes()),
        "cells": [audit_cell(cell, summary) for cell in CELLS],
    }
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "audit.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(DEST / "audit.json")


if __name__ == "__main__":
    main()
