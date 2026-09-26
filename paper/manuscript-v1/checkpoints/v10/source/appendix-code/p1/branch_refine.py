"""Research-only one-shot R6 refinement of the current structural parent.

This is a separate entrypoint. It adds at most one E1 candidate score and no
E0, E2, historical-plan selection, case-ID route, or full-matrix claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "data/raw/a/official/code"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from src.q1 import branch_aid, response_refine, structural_refine, unified
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

ALGORITHM_ID = "q1-branch-refine-research-v1"
MAX_ADDITIONAL_E1 = 1


def digest(plan):
    return hashlib.sha256(unified.plan_bytes(plan)).hexdigest()


def objective_pair(value):
    """Require exactly (official Makespan cycles, scheduled COPY bytes)."""
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or type(value[0]) is not int or value[0] <= 0
            or type(value[1]) is not int or value[1] < 0):
        raise ValueError("objective must be positive Makespan and nonnegative scheduled COPY bytes")
    return tuple(value)


def validate_candidate(graph, cores, candidate):
    if (not isinstance(candidate, dict)
            or set(candidate) != {"node_to_subgraph", "core_schedules"}
            or not isinstance(candidate["core_schedules"], list)
            or len(candidate["core_schedules"]) != cores):
        raise ValueError("candidate needs exactly two plan keys and requested core count")
    validate_task_order(derive_multicore_plan(graph, candidate))


def solve(graph, cores, *, parent_solve=None, constructor=None,
          validator=None, scorer=None):
    """One parent, at most one construction and one extra E1 attempt."""
    started = time.perf_counter()
    parent_solve = structural_refine.solve if parent_solve is None else parent_solve
    constructor = branch_aid.construct if constructor is None else constructor
    validator = validate_candidate if validator is None else validator
    scorer = response_refine.score_once if scorer is None else scorer
    parent_plan, parent = parent_solve(graph, cores)
    parent_wall = time.perf_counter() - started
    parent_hash = digest(parent_plan)
    info = {"algorithm_id": ALGORITHM_ID, "scope": (
        "Research one-shot R6 refinement; E1 selection only, no E0/full-matrix acceptance"),
        "parent": parent, "parent_plan_sha256": parent_hash,
        "parent_wall_seconds": parent_wall,
        "selected": "parent", "selected_plan_sha256": parent_hash,
        "selected_objective": None,
        "budget": {"max_additional_e1_scores": MAX_ADDITIONAL_E1, "workers": 1,
                   "score_timeout_seconds": 60, "startup_timeout_seconds": 10,
                   "score_worker_max_tasks": 1},
        "attempt": {"constructor_attempts": 0, "score_attempts": 0,
                    "actual_e1_worker_calls": 0, "actual_e1_worker_calls_range": [0, 0]},
    }
    attempt = info["attempt"]
    try:
        if type(cores) is not int or not 2 <= cores <= 5:
            info["stop_reason"] = "single-core-or-invalid"
            return parent_plan, info
        if not isinstance(parent, dict) or parent.get("selected_plan_sha256") != parent_hash:
            info["stop_reason"] = "parent-plan-hash-mismatch"
            return parent_plan, info
        try:
            parent_objective = objective_pair(parent.get("selected_objective"))
        except ValueError:
            info["stop_reason"] = "parent-objective-unavailable-or-invalid"
            return parent_plan, info
        info["parent_objective"] = list(parent_objective)
        info["selected_objective"] = list(parent_objective)

        attempt["constructor_attempts"] = 1
        begun = time.perf_counter()
        try:
            candidate, constructor_diag = constructor(graph, cores, parent_plan)
            attempt["constructor_diagnostics"] = constructor_diag
            attempt["construction_seconds"] = time.perf_counter() - begun
            if not isinstance(constructor_diag, dict) or constructor_diag.get("status") != "candidate-unscored":
                info["stop_reason"] = "structural-candidate-unsupported"
                return parent_plan, info
            if (not isinstance(candidate, dict)
                    or set(candidate) != {"node_to_subgraph", "core_schedules"}
                    or not isinstance(candidate["core_schedules"], list)
                    or len(candidate["core_schedules"]) != cores):
                raise ValueError("candidate needs exactly two plan keys and requested core count")
            candidate_hash = digest(candidate)
            attempt["candidate_plan_sha256"] = candidate_hash
            if unified.plan_bytes(candidate) == unified.plan_bytes(parent_plan):
                info["stop_reason"] = "byte-identical-candidate"
                return parent_plan, info
            validator(graph, cores, candidate)
            attempt["validation_seconds"] = time.perf_counter() - begun
        except Exception as exc:
            attempt["construction_seconds"] = time.perf_counter() - begun
            attempt["error_type"] = type(exc).__name__
            attempt["error_message"] = str(exc)
            info["stop_reason"] = "construction-or-validation-failed"
            return parent_plan, info

        attempt["score_attempts"] = 1
        # Dispatch can happen before scorer returns/raises. No returned PID
        # means the actual worker count is unknown, never silently zero.
        attempt["actual_e1_worker_calls"] = None
        attempt["actual_e1_worker_calls_range"] = [0, 1]
        score_started = time.perf_counter()
        try:
            score = scorer(graph, candidate)
            attempt["score"] = score
            if isinstance(score, dict) and score.get("worker_pid") is not None:
                attempt["actual_e1_worker_calls"] = 1
                attempt["actual_e1_worker_calls_range"] = [1, 1]
            if not isinstance(score, dict) or score.get("status") != "ok":
                info["stop_reason"] = "candidate-score-failed"
                return parent_plan, info
            score_objective = objective_pair(response_refine.objective(score))
            attempt["candidate_objective"] = list(score_objective)
            if score_objective < parent_objective:
                info.update(selected="branch-aid", selected_plan_sha256=candidate_hash,
                            selected_objective=list(score_objective),
                            stop_reason="strict-objective-improvement")
                return candidate, info
            info["stop_reason"] = "no-strict-improvement"
            return parent_plan, info
        except Exception as exc:
            attempt["score_error_type"] = type(exc).__name__
            attempt["score_error_message"] = str(exc)
            info["stop_reason"] = "candidate-score-failed"
            return parent_plan, info
        finally:
            attempt["score_wall_seconds"] = time.perf_counter() - score_started
    finally:
        known_parent = parent.get("actual_e1_calls_total") if isinstance(parent, dict) else None
        extra = attempt["actual_e1_worker_calls"]
        info["actual_e1_calls_total"] = (known_parent + extra if type(known_parent) is int
                                         and type(extra) is int else None)
        parent_lower_bound = (known_parent if type(known_parent) is int else
                              parent.get("known_e1_calls_lower_bound", 0)
                              if isinstance(parent, dict) else 0)
        if type(parent_lower_bound) is not int or parent_lower_bound < 0:
            parent_lower_bound = 0
        info["known_e1_calls_lower_bound"] = (
            parent_lower_bound
            + (extra if type(extra) is int else 0))
        info["solve_function_seconds"] = time.perf_counter() - started


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    args = parser.parse_args()
    if args.output == args.diagnostics or args.output.exists() or args.diagnostics.exists():
        raise FileExistsError("refuse to overwrite solver artifacts")
    started = time.perf_counter()
    plan, info = solve(json.loads(args.graph.read_bytes()), args.cores)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(unified.plan_bytes(plan))
        stream.flush()
        os.fsync(stream.fileno())
    info["cli_before_diagnostics_write_seconds"] = time.perf_counter() - started
    with args.diagnostics.open("x", encoding="utf-8") as stream:
        json.dump(info, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"event": "solver_completed", "selected": info["selected"],
                      "cli_read_to_outputs_fsync_seconds": time.perf_counter() - started}),
          flush=True)


if __name__ == "__main__":
    main()
