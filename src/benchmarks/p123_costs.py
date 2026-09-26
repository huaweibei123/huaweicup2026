"""Read-only cost accounting for P123 receipts; never import an evaluator.

Counts are evidence bounds, not a claim that every submitted request completed
the simulator. No gzip results are opened and no artifact trees are rehashed.
Without --output the report goes only to stdout; --output refuses overwrite.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path


P1_COMMIT = "4dff90ef699fd51845cf482951e8477066f5f566"
E1_COMMIT = "5bfe53a29c1ba05167239f51ea937e602f7f85b4"
CACHE_FIELDS = ("hits", "misses", "evictions", "bypasses")


def count(value):
    return value if type(value) is int and value >= 0 else None


def seconds(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


class Reader:
    def __init__(self, root):
        self.root = root
        self.warnings = []
        self.cache = {}

    def label(self, path):
        return path.relative_to(self.root).as_posix()

    def read(self, path):
        if path in self.cache:
            return self.cache[path]
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            if type(value) is not dict:
                raise ValueError("expected object")
        except FileNotFoundError:
            value = None
        except (OSError, ValueError, UnicodeError) as error:
            self.warnings.append({"path": self.label(path), "error_type": type(error).__name__})
            value = None
        self.cache[path] = value
        return value


def new_calls():
    return dict(observed_slots=0, confirmed_function_calls=0,
                additional_function_calls_upper=0, confirmed_cli_process_launches=0,
                confirmed_no_call_slots=0, outcomes=Counter())


def wrapper_calls(reader, summary_path, process_path, category):
    summary, process = reader.read(summary_path), reader.read(process_path)
    if summary is None and process is None and not summary_path.parent.exists() and not process_path.parent.exists():
        return
    category["observed_slots"] += 1
    category["outcomes"][(summary or process or {}).get("status", "receipt_missing")] += 1
    if count((process or {}).get("pid")) is not None:
        category["confirmed_cli_process_launches"] += 1
    calls = count((summary or {}).get("official_calls"))
    if calls in (0, 1):
        category["confirmed_function_calls"] += calls
        category["confirmed_no_call_slots"] += calls == 0
    else:
        # Includes the controller's literal 'unknown; reserve one' timeout value.
        category["additional_function_calls_upper"] += 1
        if calls is not None:
            reader.warnings.append({"path": reader.label(summary_path),
                                    "error_type": "unexpected_official_call_count"})


def p1_confirmation(reader, folder, report, name, category, solver_seen):
    value = (report or {}).get(name)
    value = value if type(value) is dict else None
    target = folder / "search" / name
    if value is None and not target.exists() and not solver_seen:
        return
    category["observed_slots"] += 1
    state = (value or {}).get("status", "receipt_missing")
    category["outcomes"][state] += 1
    if state in ("no_plan", "no_incumbent"):
        category["confirmed_no_call_slots"] += 1
    elif state == "ok":
        category["confirmed_function_calls"] += 1
        category["confirmed_cli_process_launches"] += 1
    else:
        # confirm() returns error/timeout after subprocess.run, but an error can
        # occur in the official CLI before it reaches the evaluation function.
        if state in ("error", "timeout"):
            category["confirmed_cli_process_launches"] += 1
        category["additional_function_calls_upper"] += 1


def p3_calls(reader, folder, category):
    receipt = reader.read(folder / "online/receipt.json")
    process = reader.read(folder / "solver/process.json")
    if receipt is None and process is None and not (folder / "online").exists() and not (folder / "solver").exists():
        return
    category["observed_slots"] += 1
    category["outcomes"]["receipt_complete" if receipt else (process or {}).get("status", "receipt_missing")] += 1
    if count((process or {}).get("pid")) is not None:
        category["confirmed_cli_process_launches"] += 1
    calls = count((receipt or {}).get("official_e0_calls"))
    if calls in (0, 1):
        category["confirmed_function_calls"] += calls
        category["confirmed_no_call_slots"] += calls == 0
    else:
        # A solver can fail before evaluation or lose its receipt after E0.
        category["additional_function_calls_upper"] += 1


def add_time(times, key, value):
    value = seconds(value)
    if value is not None:
        times[key]["observations"] += 1
        times[key]["seconds_sum"] += value


def p1_requests(reader, folder, report, progress, limit, evidence, times):
    process = reader.read(folder / "solver/process.json")
    exists = process is not None or (folder / "search").exists() or (folder / "solver").exists()
    if not exists:
        return
    evidence["observed_solver_slots"] += 1
    completed = report is not None
    source = report if completed else (progress or {})
    evidence["final_search_summaries" if completed else "missing_final_search_summaries"] += 1
    if completed and (source.get("code_base_commit") != P1_COMMIT or source.get("evaluator_commit") != E1_COMMIT):
        reader.warnings.append({"path": reader.label(folder / "search/summary.json"),
                                "error_type": "unrecognized_p1_or_e1_version"})
    requested = count(source.get("evaluations"))
    records = source.get("records", [])
    records = records if type(records) is list else []
    returned_rows = [row for row in records if type(row) is dict
                     and count(row.get("evaluation_number")) not in (None, 0)]
    distinct_rows = {row["evaluation_number"]: row for row in returned_rows}
    if len(distinct_rows) != len(returned_rows):
        reader.warnings.append({"path": reader.label(folder / "search/summary.json"),
                                "error_type": "duplicate_evaluation_numbers"})
    returned = list(distinct_rows.values())
    if completed and requested is not None and requested != len(returned):
        reader.warnings.append({"path": reader.label(folder / "search/summary.json"),
                                "error_type": "summary_count_differs_from_returned_records"})
    observed = max(requested or 0, len(returned))
    evidence["confirmed_returned_requests"] += observed
    # Every returned record follows a call to evaluate_batch([plan]); no returned
    # record proves whether the worker received the request on a broken pipe.
    evidence["confirmed_api_submissions"] += observed
    if not completed or requested is None:
        evidence["additional_api_submissions_upper"] += max(0, limit - observed)
    if observed > limit:
        reader.warnings.append({"path": reader.label(folder), "error_type": "request_count_exceeds_protocol_limit"})
    attempts = count(source.get("attempts"))
    evidence["recorded_proposal_attempts_lower_bound"] += attempts or 0
    for row in records:
        if type(row) is dict:
            evidence["proposal_record_outcomes"][row.get("status", "unknown")] += 1
    confirmed_entered = 0
    prior_cache = {}
    for row in sorted(returned, key=lambda row: row["evaluation_number"]):
        evidence["returned_request_outcomes"][row.get("status", "unknown")] += 1
        cache = row.get("cache")
        # A cache-bearing response is emitted by evaluator.evaluate_record after
        # entering its evaluate call, including official validation rejection.
        if type(cache) is dict:
            confirmed_entered += 1
            pid = row.get("worker_pid")
            if type(pid) is int:
                previous = prior_cache.get(pid, {})
                for field in CACHE_FIELDS:
                    current = count(cache.get(field))
                    old = count(previous.get(field))
                    if current is not None:
                        delta = current if old is None or current < old else current - old
                        evidence["observed_cache_counters_lower_bound"][field] += delta
                prior_cache[pid] = cache
        add_time(times, "P1_returned_worker_wall_included_in_search", row.get("wall_seconds"))
    evidence["confirmed_worker_evaluate_entries"] += confirmed_entered
    evidence["additional_worker_evaluate_entries_upper"] += max(0, observed - confirmed_entered)
    if not completed or requested is None:
        evidence["additional_worker_evaluate_entries_upper"] += max(0, limit - observed)
    for field in ("search_seconds", "proposal_seconds", "evaluation_seconds", "total_seconds"):
        add_time(times, "P1_" + field + "_included_in_solver", (report or {}).get(field))
    for name in ("e0_best", "e0_baseline"):
        add_time(times, "P1_" + name + "_included_in_solver", ((report or {}).get(name) or {}).get("seconds"))


def process_category(relative):
    parts = relative.parts
    if parts[0] == "baselines":
        return "singlecore_wrapper_process"
    if len(parts) >= 6 and parts[0] == "cells":
        names = {"solver": "solver_process", "e0_process": "final_e0_wrapper_process",
                 "no_cache_process": "same_plan_P2_wrapper_process"}
        return parts[1] + "_" + names.get(parts[-2], parts[-2])
    return "other_process"


def build_report(root):
    reader = Reader(root)
    protocol = reader.read(root / "protocol.json") or {}
    limit = count(protocol.get("P1_parameters", {}).get("candidates"))
    if limit is None:
        limit = 32
        reader.warnings.append({"path": "protocol.json", "error_type": "missing_candidate_limit_assumed_32"})
    calls = {key: new_calls() for key in (
        "singlecore", "P1_best", "P1_stub", "P2_final", "P3_online", "P3_same_plan_P2")}
    requests = dict(observed_solver_slots=0, final_search_summaries=0, missing_final_search_summaries=0,
                    confirmed_returned_requests=0, confirmed_api_submissions=0, additional_api_submissions_upper=0,
                    confirmed_worker_evaluate_entries=0, additional_worker_evaluate_entries_upper=0,
                    recorded_proposal_attempts_lower_bound=0,
                    proposal_record_outcomes=Counter(), returned_request_outcomes=Counter(),
                    observed_cache_counters_lower_bound=Counter())
    outcomes = {key: Counter() for key in ("singlecore", "P1", "P2", "P3", "P3_cache_pair")}
    times = defaultdict(lambda: dict(observations=0, seconds_sum=0.0))
    cells = {key: sorted((root / "cells" / key).glob("*/k*")) for key in ("P1", "P2", "P3")}
    for folder in sorted((root / "baselines").glob("*")):
        if not folder.is_dir():
            continue
        value = reader.read(folder / "e0/summary.json")
        outcomes["singlecore"][(value or {}).get("status", "receipt_missing")] += 1
        wrapper_calls(reader, folder / "e0/summary.json", folder / "process/process.json", calls["singlecore"])
        add_time(times, "singlecore_function_included_in_wrapper", (value or {}).get("eval_seconds"))
    for problem, folders in cells.items():
        for folder in folders:
            if not folder.is_dir():
                continue
            cell = reader.read(folder / "cell.json")
            outcomes[problem][((cell or {}).get("row") or {}).get("status", "receipt_missing")] += 1
            add_time(times, problem + "_cell_includes_processes", (cell or {}).get("cell_wall_seconds"))
            if problem == "P1":
                report = reader.read(folder / "search/summary.json")
                progress = None if report is not None else reader.read(folder / "search/progress.json")
                p1_requests(reader, folder, report, progress, limit, requests, times)
                solver_seen = (folder / "solver").exists() or (folder / "search").exists()
                for key, category in (("e0_best", "P1_best"), ("e0_baseline", "P1_stub")):
                    p1_confirmation(reader, folder, report, key, calls[category], solver_seen)
            elif problem == "P2":
                wrapper_calls(reader, folder / "e0/summary.json", folder / "e0_process/process.json", calls["P2_final"])
                value = reader.read(folder / "e0/summary.json") or {}
                add_time(times, "P2_function_included_in_e0_wrapper", value.get("eval_seconds"))
            else:
                p3_calls(reader, folder, calls["P3_online"])
                receipt = reader.read(folder / "online/receipt.json") or {}
                add_time(times, "P3_official_import_config_evaluate_included_in_solver",
                         receipt.get("official_import_config_evaluate_seconds"))
                wrapper_calls(reader, folder / "no_cache/summary.json", folder / "no_cache_process/process.json",
                              calls["P3_same_plan_P2"])
                no_cache = reader.read(folder / "no_cache/summary.json")
                pair_process = reader.read(folder / "no_cache_process/process.json")
                outcomes["P3_cache_pair"][(no_cache or pair_process or {}).get("status", "not_started_or_missing")] += 1
                add_time(times, "P3_pair_P2_function_included_in_pair_wrapper", (no_cache or {}).get("eval_seconds"))
    processes = Counter()
    for path in sorted(root.rglob("process.json")):
        receipt = reader.read(path)
        if receipt is None:
            continue
        category = process_category(path.relative_to(root))
        processes[category + ":" + str(receipt.get("status", "unknown"))] += 1
        add_time(times, category, receipt.get("wall_seconds"))
    artifacts = dict(file_count=0, bytes=0, stat_errors=0, symlinks_skipped=0)
    # Metadata only: no full-result JSON/gzip reads and no content hashes.
    for path in root.rglob("*"):
        if path.is_symlink():
            artifacts["symlinks_skipped"] += 1
            continue
        try:
            if path.is_file():
                artifacts["file_count"] += 1
                artifacts["bytes"] += path.stat().st_size
        except OSError:
            artifacts["stat_errors"] += 1
    for value in calls.values():
        value["function_calls_possible_upper"] = value["confirmed_function_calls"] + value["additional_function_calls_upper"]
    totals = {key: sum(value[key] for value in calls.values()) for key in (
        "confirmed_function_calls", "additional_function_calls_upper", "function_calls_possible_upper",
        "confirmed_cli_process_launches", "confirmed_no_call_slots")}
    return dict(
        schema_version=1, observed_at_utc=datetime.now(timezone.utc).isoformat(),
        scope="point-in-time local receipts; read-only and non-atomic if experiments are active",
        source_semantics={"P1": P1_COMMIT, "E1_pool": E1_COMMIT},
        planned_full_scope=dict(singlecore_baselines=100, P1_solver_cells=400, P2_solver_cells=400,
                                P3_solver_cells=500, P3_same_plan_P2_pairs=500,
                                E1_upper_reservations=12800, E0_upper_reservations=2300),
        declared_protocol_reservations=protocol.get("full_upper_call_reservations"),
        outcomes=outcomes, E0_by_route=calls, E0_totals_for_observed_slots=totals, P1_E1=requests,
        process_outcomes=processes, wall_time_components=dict(times), local_artifacts=artifacts,
        warnings=reader.warnings,
        interpretation=[
            "Confirmed function calls count entries, not necessarily successful or complete simulations.",
            "P1 E0 ok proves one evaluation; error/timeout proves CLI launch but leaves function entry uncertain; no_plan/no_incumbent means zero.",
            "Numeric wrapper official_calls and P3 official_e0_calls are evidence; missing/string unknown values reserve at most one per observed slot.",
            "P1 evaluations counts returned pool requests, including timeouts/errors. Proposals/duplicates/no_parent are not evaluations.",
            "A cache-bearing E1 worker response proves entry; timeout/WorkerError without cache remains uncertain. No final summary reserves remaining candidate capacity conservatively.",
            "Observed cache counters use per-worker deltas/reset handling; these are lower bounds for local preparation caching, never saved full evaluations or result-cache hits.",
            "Unstarted future cells are excluded from observed call totals; planned full-run reservations are separate.",
            "Wall sums overlap: worker/proposal/search and P1 E0 are included in P1 solver; P3 E0 is included in P3 solver. P2 final E0 and P3 paired P2 are separate processes.",
            "Cell wall includes its processes. Never add all component rows. Process sums across two concurrent units are work-seconds, not elapsed runtime or CPU seconds.",
            "Artifact totals use stat only, include existing reports, and precede writing this requested output. No RSS or hard memory measurement is inferred.",
        ])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.run_dir.resolve()
    if not root.is_dir():
        parser.error("--run-dir must be an existing run directory")
    if args.output is not None and args.output.exists():
        parser.error("--output must be a new file")
    value = build_report(root)
    if args.output is None:
        print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
    else:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
