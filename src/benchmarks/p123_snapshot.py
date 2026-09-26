"""Export a non-atomic, receipt-only snapshot of a live P1/P2/P3 run.

This standalone standard-library program never imports benchmark modules, launches
processes, or reads/copies plans, results, traces, stdout or stderr. Run once with:
    python -B src/benchmarks/p123_snapshot.py --run-dir results/a/<run>
Only a new UTC-named directory beneath <run>/snapshots is written.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import re


ROOT = Path(__file__).resolve().parents[2]
PROBLEMS = ("P1", "P2", "P3")
CASES = tuple(f"{case:03d}" for case in range(1, 101))
OFFICIAL_COMMIT = "f27ef37bb76dcf556f35d3f2328e405d92241d9c"
FIELDS = (
    "case", "problem", "cores", "algorithm", "status", "makespan_cycles",
    "singlecore_cycles", "multicore_speedup", "solver_wall_seconds",
    "e0_wall_seconds", "data_movement_bytes", "cache_hit_rate",
    "no_cache_makespan_cycles", "cache_speedup", "error", "source_commit",
    "result_path", "slot_kind", "capture_state", "source_status",
    "status_reason", "multicore_ratio_missing_reason", "cache_ratio_missing_reason",
    "baseline_status", "baseline_summary_sha256", "pair_status",
    "pair_reported_makespan_cycles", "pair_plan_identity", "pair_wall_seconds",
    "pair_eval_seconds", "cell_wall_seconds", "baseline_wall_seconds",
    "baseline_eval_seconds", "source_receipt", "source_receipt_sha256",
    "harness_sha256", "harness_lineage_basis", "plan_sha256",
    "timing_note", "result_path_base",
)
PROCESS_FIELDS = (
    "status", "started_at", "finished_at", "timeout_seconds", "pid",
    "returncode", "wall_seconds", "harness_sha256", "cleanup_unconfirmed",
)
SUMMARY_FIELDS = (
    "mode", "status", "official_calls", "makespan_cycles", "num_cores",
    "data_movement_bytes", "cache_hit_rate", "cache_stats", "eval_seconds",
    "runner_seconds", "graph_sha256", "config_sha256", "plan_sha256",
    "result_sha256", "result_gzip_sha256", "manifest_sha256",
    "official_code_hash", "graph_manifest_verified", "result_gzip_verified",
    "exception_type",
)
ONLINE_FIELDS = (
    "strategy", "components", "eligible_ops", "cores", "selection",
    "official_e0_calls", "makespan", "data_movement_bytes", "cache_stats",
    "graph_sha256", "config_sha256", "plan_sha256", "result_sha256",
    "construct_main_seconds", "official_import_config_evaluate_seconds",
)
PRIVATE = re.compile(
    r"(?i)(?:[a-z]:[\\/]|\\\\[^\\\s]+\\|/(?:Users|home|private|tmp)/|"
    r"github_pat_|gh[pousr]_[a-z0-9]|sk-proj-|(?:token|session)[_-]?(?:url)?=)"
)
HASH = re.compile(r"^[0-9a-f]{64}$")


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def selected(value: dict, keys: tuple[str, ...]) -> dict:
    return {key: value[key] for key in keys if key in value}


def number(value, *, positive: bool = False):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(value) and (value > 0 if positive else value >= 0):
            return value
    return None


def safe_relative(value) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value or PRIVATE.search(value):
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    return path.as_posix()


def scrub(value):
    """Keep extracted evidence portable; raw capture files are checked, not edited."""
    if isinstance(value, str):
        return "[redacted private path or token-like text]" if PRIVATE.search(value) else value
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    return value


class Capture:
    """Read each relative input once; all later derivation uses these exact bytes."""

    def __init__(self, root: Path):
        self.root = root
        self.files: dict[str, dict] = {}

    def read(self, name: str, *, as_json: bool = True) -> dict:
        if name in self.files:
            return self.files[name]
        if safe_relative(name) != name:
            raise ValueError("unsafe input relative path")
        path = self.root / name
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("input symlink escapes run directory")
        record = {"source": name, "read_started_at": utc(), "state": "missing"}
        self.files[name] = record
        try:
            before = path.stat()
            if before.st_size > 8 * 1024 * 1024:
                record["state"] = "size_limit"
                return record
            raw = path.read_bytes()
            after = path.stat()
        except FileNotFoundError:
            return record
        except OSError as error:
            record.update(state="read_error", error_type=type(error).__name__)
            return record
        finally:
            record["read_finished_at"] = utc()
        record.update(
            state="captured", raw=raw, bytes=len(raw), sha256=digest(raw),
            changed_during_read=(before.st_size != after.st_size
                                 or before.st_mtime_ns != after.st_mtime_ns
                                 or len(raw) != after.st_size),
        )
        if as_json:
            try:
                value = json.loads(raw.decode("utf-8-sig"))
                if not isinstance(value, dict):
                    raise ValueError("receipt root must be an object")
                record["value"] = value
            except (UnicodeError, ValueError):
                record["state"] = "invalid_json"
        return record

    def value(self, name: str) -> dict:
        return self.read(name).get("value", {})


def metadata(record: dict) -> dict:
    return {key: value for key, value in record.items() if key not in {"raw", "value"}}


def incomplete_status(folder: Path, records: list[dict]) -> tuple[str, str, str]:
    for record in records:
        value = record.get("value", {})
        if (value.get("started_at") and value.get("pid")
                and not value.get("finished_at")
                and value.get("status") not in {"ok", "error", "timeout", "fatal_cleanup"}):
            return "running_unconfirmed", "incomplete", "process_start_receipt_without_completion"
    if any(record["state"] not in {"missing", "captured"} for record in records):
        return "incomplete", "incomplete", "receipt_unreadable_or_partial_at_capture"
    if folder.is_dir() or any(record["state"] != "missing" for record in records):
        return "incomplete", "incomplete", "no_final_receipt;directory_or_partial_evidence_only"
    return "missing", "no_receipt", "not_observed_at_capture"


def terminal_status(status, makespan) -> tuple[str, str]:
    if status == "ok":
        return ("ok", "") if number(makespan, positive=True) is not None else (
            "error", "receipt_ok_but_valid_makespan_missing")
    if status in {"error", "timeout"}:
        return status, "final_receipt_" + status
    return "error", "final_receipt_status_" + str(status or "missing")


def extract_cell(value: dict) -> dict:
    item = selected(value, (
        "started_at", "finished_at", "harness_sha256", "cell_wall_seconds",
        "plan_sha256", "timing_note", "p3_strategy", "cache_pair_error", "evidence",
    ))
    item["row"] = selected(value.get("row", {}), FIELDS[:17])
    item["processes"] = [selected(process, PROCESS_FIELDS)
                         for process in value.get("processes", [])]
    if "p1_search" in value:
        item["p1_search"] = selected(value["p1_search"], (
            "attempts", "evaluations", "search_seconds", "e0_best", "e0_baseline",
            "e0_confirms_selected_makespan", "parameters",
        ))
    return item


def pair_reason(row: dict, cell: dict, online: dict, pair: dict) -> str:
    if row["status"] != "ok":
        return "cell_status_" + row["status"]
    if not pair:
        return "same_plan_P2_receipt_missing_or_unreadable"
    if pair.get("status") != "ok":
        return "same_plan_P2_status_" + str(pair.get("status", "missing"))
    if number(pair.get("makespan_cycles"), positive=True) is None:
        return "same_plan_P2_makespan_missing_or_invalid"
    hashes = [cell.get("plan_sha256"), online.get("plan_sha256"), pair.get("plan_sha256")]
    if not all(isinstance(value, str) and HASH.fullmatch(value) for value in hashes):
        return "plan_identity_missing"
    if len(set(hashes)) != 1:
        return "plan_identity_mismatch"
    for key in ("graph_sha256", "config_sha256"):
        if not online.get(key) or online.get(key) != pair.get(key):
            return key + "_missing_or_mismatch"
    if online.get("cores") != row["cores"] or pair.get("num_cores") != row["cores"]:
        return "pair_core_count_missing_or_mismatch"
    if pair.get("mode") != "P2" or online.get("makespan") != row["makespan_cycles"]:
        return "pair_mode_or_online_makespan_mismatch"
    return ""


def build_snapshot(capture: Capture, protocol: dict, ledger: dict) -> tuple[list, list, dict]:
    evidence = []
    legacy_info = ledger.get("legacy_evidence", {})
    legacy_path = safe_relative(legacy_info.get("file"))
    legacy_record = capture.read(legacy_path) if legacy_path else {}
    legacy_valid = bool(legacy_record.get("sha256") == legacy_info.get("sha256")
                        and legacy_record.get("value"))
    legacy = legacy_record.get("value", {}) if legacy_valid else {}
    registered = {item.get("sha256") for item in ledger.get("revisions", [])}
    lineage_counts = Counter()

    def lineage(record: dict, value: dict) -> tuple[str | None, str]:
        actual = value.get("harness_sha256")
        if actual:
            return actual, "receipt_declared_registered" if actual in registered else "receipt_declared_unregistered"
        observed = legacy.get("files", {}).get(record.get("source"), {})
        if record.get("sha256") and observed.get("sha256") == record["sha256"]:
            return legacy.get("harness_sha256"), "legacy_manifest_exact_receipt_hash"
        return None, "not_recorded"

    def add_evidence(record: dict, kind: str, fields: dict):
        if record["state"] == "missing":
            return
        evidence.append({**metadata(record), "kind": kind, "extracted": scrub(fields)})

    baselines = {}
    for case in CASES:
        name = f"baselines/{case}"
        receipt = capture.read(name + "/e0/summary.json")
        process = capture.read(name + "/process/process.json")
        value, proc = receipt.get("value", {}), process.get("value", {})
        if value:
            status, reason = terminal_status(value.get("status"), value.get("makespan_cycles"))
            state = "final_receipt"
        else:
            status, state, reason = incomplete_status(capture.root / name, [process, receipt])
        baselines[case] = {"receipt": receipt, "value": value, "process": proc,
                           "status": status, "state": state, "reason": reason}
        add_evidence(receipt, "baseline_summary", selected(value, SUMMARY_FIELDS))
        add_evidence(process, "baseline_process", selected(proc, PROCESS_FIELDS))

    rows = []
    for problem in PROBLEMS:
        for case in CASES:
            base = baselines[case]
            single = (number(base["value"].get("makespan_cycles"), positive=True)
                      if base["status"] == "ok" else None)
            for cores in range(1, 6):
                row = dict.fromkeys(FIELDS)
                row.update(case=case, problem=problem, cores=cores, singlecore_cycles=single,
                           baseline_status=base["status"],
                           baseline_summary_sha256=base["receipt"].get("sha256"),
                           baseline_wall_seconds=number(base["process"].get("wall_seconds")),
                           baseline_eval_seconds=number(base["value"].get("eval_seconds")),
                           error="", result_path_base="source_run_directory")
                if problem in {"P1", "P2"} and cores == 1:
                    row.update(
                        slot_kind="reused_baseline_anchor", algorithm="official_singlecore_baseline",
                        status=base["status"], capture_state=base["state"],
                        source_status=base["value"].get("status"), status_reason=base["reason"],
                        makespan_cycles=single, multicore_speedup=1.0 if single else None,
                        multicore_ratio_missing_reason="" if single else "baseline_status_" + base["status"],
                        cache_ratio_missing_reason="not_applicable", source_commit=OFFICIAL_COMMIT,
                        source_receipt=base["receipt"]["source"],
                        source_receipt_sha256=base["receipt"].get("sha256"),
                        result_path=f"baselines/{case}/e0/result.json.gz" if single else None,
                        timing_note="Reused official baseline; no P1/P2 solver execution for this anchor.",
                        data_movement_bytes=json.dumps(base["value"].get("data_movement_bytes")),
                    )
                    row["harness_sha256"], row["harness_lineage_basis"] = lineage(
                        capture.read(f"baselines/{case}/process/process.json"), base["process"])
                    if not row["harness_sha256"]:
                        row["harness_sha256"], row["harness_lineage_basis"] = lineage(
                            base["receipt"], base["value"])
                    rows.append(row)
                    continue
                prefix = f"cells/{problem}/{case}/k{cores}"
                receipt = capture.read(prefix + "/cell.json")
                process = capture.read(prefix + "/solver/process.json")
                cell, proc = receipt.get("value", {}), process.get("value", {})
                source = cell.get("row", {})
                supporting = {}
                if problem == "P2":
                    supporting = {"official_summary": capture.read(prefix + "/e0/summary.json"),
                                  "official_process": capture.read(prefix + "/e0_process/process.json")}
                elif problem == "P3":
                    supporting = {"online_receipt": capture.read(prefix + "/online/receipt.json"),
                                  "pair_summary": capture.read(prefix + "/no_cache/summary.json"),
                                  "pair_process": capture.read(prefix + "/no_cache_process/process.json")}
                if source and cell.get("finished_at"):
                    status, reason = terminal_status(source.get("status"), source.get("makespan_cycles"))
                    state = "final_receipt"
                    if (source.get("problem"), source.get("case"), source.get("cores")) != (problem, case, cores):
                        status, reason = "error", "receipt_slot_identity_mismatch"
                else:
                    status, state, reason = incomplete_status(
                        capture.root / prefix, [receipt, process, *supporting.values()])
                row.update(
                    slot_kind="solver", algorithm=source.get("algorithm") or protocol["algorithms"][problem],
                    status=status, capture_state=state, source_status=source.get("status"),
                    status_reason=reason, makespan_cycles=number(source.get("makespan_cycles"), positive=True),
                    solver_wall_seconds=number(source.get("solver_wall_seconds", proc.get("wall_seconds"))),
                    e0_wall_seconds=number(source.get("e0_wall_seconds")),
                    data_movement_bytes=source.get("data_movement_bytes"),
                    cache_hit_rate=number(source.get("cache_hit_rate")),
                    error=scrub(source.get("error", "")),
                    source_commit=source.get("source_commit") or protocol["versions"][problem]["commit"],
                    result_path=safe_relative(source.get("result_path")),
                    source_receipt=receipt["source"], source_receipt_sha256=receipt.get("sha256"),
                    plan_sha256=cell.get("plan_sha256"),
                    cell_wall_seconds=number(cell.get("cell_wall_seconds")),
                    timing_note=cell.get("timing_note"),
                )
                row["harness_sha256"], row["harness_lineage_basis"] = lineage(receipt, cell)
                if not row["harness_sha256"]:
                    row["harness_sha256"], row["harness_lineage_basis"] = lineage(process, proc)
                if state == "final_receipt":
                    lineage_counts[row["harness_lineage_basis"]] += 1
                row["multicore_ratio_missing_reason"] = (
                    "cell_status_" + status if status != "ok" else
                    "baseline_status_" + base["status"] if single is None else "")
                if not row["multicore_ratio_missing_reason"]:
                    row["multicore_speedup"] = single / row["makespan_cycles"]
                row["cache_ratio_missing_reason"] = "not_applicable"
                if problem == "P3":
                    online = supporting["online_receipt"].get("value", {})
                    pair = supporting["pair_summary"].get("value", {})
                    pair_process = supporting["pair_process"].get("value", {})
                    missing = pair_reason(row, cell, online, pair)
                    row.update(
                        pair_status=pair.get("status", pair_process.get("status", "missing")),
                        pair_reported_makespan_cycles=number(pair.get("makespan_cycles"), positive=True),
                        pair_wall_seconds=number(pair_process.get("wall_seconds")),
                        pair_eval_seconds=number(pair.get("eval_seconds")),
                        pair_plan_identity="matched" if not missing else "not_validated",
                        cache_ratio_missing_reason=missing,
                    )
                    if not missing:
                        row["no_cache_makespan_cycles"] = pair["makespan_cycles"]
                        row["cache_speedup"] = pair["makespan_cycles"] / row["makespan_cycles"]
                rows.append(scrub(row))
                add_evidence(receipt, "cell", extract_cell(cell))
                add_evidence(process, "solver_process", selected(proc, PROCESS_FIELDS))
                for label, record in supporting.items():
                    keys = (PROCESS_FIELDS if label.endswith("process") else
                            ONLINE_FIELDS if label == "online_receipt" else SUMMARY_FIELDS)
                    add_evidence(record, label, selected(record.get("value", {}), keys))

    harness_files = []
    for revision in ledger.get("revisions", []):
        sha = revision.get("sha256", "")
        if isinstance(sha, str) and HASH.fullmatch(sha):
            record = capture.read(f"harness/p123_run-{sha}.py", as_json=False)
            harness_files.append({**metadata(record), "expected_sha256": sha,
                                  "hash_matches": record.get("sha256") == sha})
    invocations = []
    for path in sorted((capture.root / "invocations").glob("*.json")):
        record = capture.read(path.relative_to(capture.root).as_posix())
        value = selected(record.get("value", {}), (
            "started_at", "finished_at", "harness_sha256", "status", "cases",
            "cores", "problems", "include_p3_one", "workers", "counts",
        ))
        invocations.append({**metadata(record), "declared_only": scrub(value)})
    return rows, evidence, {
        "protocol_original_harness_sha256": protocol.get("source_sha256", {}).get("p123_run.py"),
        "ledger_protocol_hash_matches": ledger.get("original_protocol_sha256") == capture.read("protocol.json").get("sha256"),
        "legacy_manifest": metadata(legacy_record) if legacy_record else None,
        "legacy_manifest_hash_matches": legacy_valid,
        "completed_cell_lineage_counts": dict(lineage_counts),
        "harness_source_files": harness_files, "invocations": invocations,
        "note": "Receipt/invocation declarations are provenance evidence, not OS liveness checks. Legacy attribution requires the exact receipt SHA256 in the pinned manifest.",
    }


def coverage(rows: list[dict]) -> dict:
    result = {}
    for kind in ("reused_baseline_anchor", "solver"):
        subset = [row for row in rows if row["slot_kind"] == kind]
        result[kind] = {
            "positions": len(subset), "status": dict(Counter(row["status"] for row in subset)),
            "final_receipts": sum(row["capture_state"] == "final_receipt" for row in subset),
            "multicore_ratios_available": sum(row["multicore_speedup"] is not None for row in subset),
            "P3_cache_ratios_available": sum(row["cache_speedup"] is not None for row in subset),
        }
    result["per_problem"] = {
        problem: {"positions": 500,
                  "solver_status": dict(Counter(row["status"] for row in rows
                                                 if row["problem"] == problem and row["slot_kind"] == "solver"))}
        for problem in PROBLEMS
    }
    result["successful_solver_missing_multicore_ratio"] = sum(
        row["slot_kind"] == "solver" and row["status"] == "ok" and row["multicore_speedup"] is None for row in rows)
    result["successful_P3_missing_cache_ratio"] = sum(
        row["problem"] == "P3" and row["status"] == "ok" and row["cache_speedup"] is None for row in rows)
    return result


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    if not run.is_dir() or not run.is_relative_to(ROOT):
        parser.error("--run-dir must be an existing run directory within this checkout")
    capture_start = utc()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    capture = Capture(run)
    original_csv = capture.read("comparison.csv", as_json=False)
    original_progress = capture.read("progress.json")
    protocol_record = capture.read("protocol.json")
    ledger_record = capture.read("harness/revisions.json")
    if not protocol_record.get("value") or not ledger_record.get("value"):
        raise ValueError("valid protocol and harness ledger are required")
    rows, evidence, lineage = build_snapshot(capture, protocol_record["value"], ledger_record["value"])
    capture_end = utc()
    assert len(rows) == len({(row["problem"], row["case"], row["cores"]) for row in rows}) == 1500
    counts = coverage(rows)
    assert counts["reused_baseline_anchor"]["positions"] == 200
    assert counts["solver"]["positions"] == 1300
    out = run / "snapshots" / stamp
    if not out.resolve().is_relative_to(run) or out.exists():
        raise ValueError("snapshot destination escapes run directory or already exists")

    outputs = {}
    raw_sources = {
        "captured-comparison.csv": original_csv, "captured-progress.json": original_progress,
        "protocol.json": protocol_record, "harness-revisions.json": ledger_record,
    }
    for name, record in raw_sources.items():
        if "raw" in record:
            if PRIVATE.search(record["raw"].decode("utf-8-sig")):
                raise ValueError("raw input contains private-path/token-like text; export stopped before writing")
            outputs[name] = record["raw"]
    csv_stream = io.StringIO(newline="")
    writer = csv.DictWriter(csv_stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    outputs["comparison.csv"] = csv_stream.getvalue().encode("utf-8-sig")
    outputs["receipts.jsonl"] = ("\n".join(json.dumps(item, ensure_ascii=False, separators=(",", ":"),
                                                       allow_nan=False) for item in evidence) + "\n").encode("utf-8")
    outputs["lineage.json"] = json_bytes(lineage)
    csv_observation = {"parsed_rows": None, "warnings": []}
    if "raw" in original_csv:
        try:
            raw_text = original_csv["raw"].decode("utf-8-sig")
            original_rows = list(csv.DictReader(io.StringIO(raw_text), strict=True))
            csv_observation["parsed_rows"] = len(original_rows)
            if any(None in row or any(value is None for value in row.values()) for row in original_rows):
                csv_observation["warnings"].append("incomplete_or_unexpected_column_count")
            if not raw_text.endswith("\n"):
                csv_observation["warnings"].append("no_final_newline;may_be_partial_live_write")
            observed_completed = sum(row["capture_state"] == "final_receipt" for row in rows)
            csv_observation["completed_positions_in_receipt_capture"] = observed_completed
            csv_observation["row_count_matches_receipt_capture"] = len(original_rows) == observed_completed
            if len(original_rows) != observed_completed:
                csv_observation["warnings"].append("row_count_differs;live_aggregate_may_lag_or_be_partial")
        except (UnicodeError, csv.Error):
            csv_observation["warnings"].append("captured_csv_not_parseable")
    else:
        csv_observation["warnings"].append("source_csv_not_captured")
    manifest = {
        "schema": "p123-readonly-snapshot-v1", "capture_started_at_utc": capture_start,
        "capture_finished_at_utc": capture_end, "non_atomic_live_snapshot": True,
        "source_run": run.relative_to(ROOT).as_posix(),
        "exporter": {"path": "src/benchmarks/p123_snapshot.py", "sha256": digest(Path(__file__).read_bytes())},
        "original_captures": {name: metadata(record) for name, record in raw_sources.items()},
        "coverage": counts,
        "original_progress_claim": scrub(original_progress.get("value", {})),
        "original_csv_observation": csv_observation,
        "receipt_evidence_count": len(evidence),
        "input_observation_counts": dict(Counter(record["state"] for record in capture.files.values())),
        "inputs_changed_during_read": [name for name, record in capture.files.items()
                                       if record.get("changed_during_read")],
        "limitations": [
            "Live files were read sequentially, once each, with no writer lock. This is not an atomic snapshot or proof of state at a single cursor/time.",
            "Captured comparison/progress bytes may be stale, partially written, or describe a different instant. The complete table is independently derived from captured receipts.",
            "No solver/evaluator/controller/audit import, evaluation, process launch or live-run mutation occurred. No plan/result/trace/stdout/stderr files were read or copied.",
            "Receipt result hashes are recorded claims, not a fresh verification of large result files or plan legality. No scientific acceptance or live-process verification is asserted.",
            "Directory existence only establishes incomplete evidence. running_unconfirmed requires a start/process receipt without completion; it is not confirmed running.",
            "An ok cell can lack a failed/missing baseline denominator or P3 same-plan P2 pair. Ratios stay NA with reasons; failed/missing cells are never replaced by zero.",
            "The 200 P1/P2 core1 rows reuse 100 official baselines; they are not 200 solver runs. There are 1300 actual solver positions.",
            "result_path refers to the source run, not copied snapshot artifacts. Missing slots use the protocol-pinned source commit/algorithm as intended provenance only.",
        ],
    }
    outputs["README.md"] = (
        "# Receipt-only benchmark snapshot\n\n"
        f"Capture: {capture_start} to {capture_end} (UTC).\n\n"
        "This is a **non-atomic snapshot of a live run**, not its final outcome. "
        "Use `comparison.csv` for 1500 unique expected positions: 200 reused baseline anchors "
        "(100 each for P1/P2 core1) and 1300 solver positions (P1/P2: 400 each; P3: 500). "
        "`captured-comparison.csv` and `captured-progress.json` preserve exact observed bytes; "
        "they may lag the independently reconstructed table. `manifest.json` records their SHA256 and coverage.\n\n"
        "`receipts.jsonl` contains compact allowlisted fields, source-relative paths and SHA256 of original "
        "receipt bytes. `protocol.json`, `harness-revisions.json` and `lineage.json` distinguish the "
        "original protocol from actual receipt harness declarations and hash-matched legacy evidence. "
        "Result/trace files and stdout/stderr are not copied or revalidated.\n\n"
        "`status` is the final cell outcome where observed. `capture_state` and `status_reason` "
        "explain incomplete slots; no directory or old PID proves OS liveness. `ok` does not imply "
        "all metrics are present. `multicore_speedup` uses a successful official baseline divided by "
        "successful Makespan. P3 `cache_speedup` additionally requires equal plan, graph, configuration "
        "and core identities in the recorded online/P2 pair. Each absent ratio has a reason.\n\n"
        "Timing units are seconds; Makespan units are simulated cycles. `solver_wall_seconds` is "
        "the recorded external solver duration. P1/P3 `e0_wall_seconds` is an included E0 component "
        "and must not be added again; P2 records its separate official process wall. "
        "`pair_wall_seconds` and `pair_eval_seconds` are the separate P3 no-cache process/function "
        "costs. `cell_wall_seconds` covers the controller cell; baseline wall/eval costs are shared "
        "across anchors, not additive per row. No missing timing is invented.\n\n"
        "Reproduce with `python -B src/benchmarks/p123_snapshot.py --run-dir <source_run>`. "
        "It creates a new timestamped directory and does not overwrite previous snapshots. "
        "Live state will have advanced, so a new capture is not byte-identical.\n"
    ).encode("utf-8")
    manifest["files"] = {name: {"sha256": digest(raw), "bytes": len(raw)} for name, raw in outputs.items()}
    outputs["manifest.json"] = json_bytes(manifest)
    out.mkdir(parents=True, exist_ok=False)
    for name, raw in outputs.items():
        with (out / name).open("xb") as stream:
            stream.write(raw)
    print(json.dumps({"snapshot": out.relative_to(ROOT).as_posix(), "coverage": counts,
                      "manifest_sha256": digest(outputs["manifest.json"]),
                      "capture_started_at_utc": capture_start, "capture_finished_at_utc": capture_end,
                      "non_atomic_live_snapshot": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
