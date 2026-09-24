"""Extend the frozen stage/attention router with one general-DAG gap proposal.

The general proposal adapts Fang's fixed join-aware gap insertion. It replaces
the tree-only proposal only after a fork/join guard succeeds, and competes with
the exact same freshly evaluated structural anchor. At most two online E0 calls;
no per-case lookup, trial parameters or historical result input.
"""
import hashlib

from . import adaptive_solve
from .construct import ROOT, UnsupportedStructure
from .gap_dag import construct
from .guarded_solve import choose_anchor, evaluate_candidates as guarded
from .pipe_bound import UnsupportedBound, analyze
from .safe_solve import encoded, main as run_solver
from evaluation_validation import (
    EvaluationValidationError, read_bandwidth_config, read_required_settings,
)


def general_candidates(index, cores, evaluate, save):
    config = ROOT / "data/raw/a/official/data/config.txt"
    delay = read_required_settings(config, "multicore_scene_b",
                                  ("cross_core_copy_delay_cycles",))["cross_core_copy_delay_cycles"]
    try:
        proposal, meta = construct(index, cores, read_bandwidth_config(config), delay)
    except UnsupportedStructure:
        return guarded(index, cores, evaluate, save)
    anchor, anchor_meta, selection = choose_anchor(index, cores)
    result = evaluate(anchor)
    refs = save("seed", anchor, result) or {}
    winner = anchor, result, anchor_meta["strategy"]
    records = [{"name": "seed", "strategy": winner[2], "status": "ok",
                "makespan": result["makespan"], "metadata": anchor_meta, "artifacts": refs}]
    record = {"name": "gap", "strategy": meta["strategy"], "metadata": meta,
              "makespan": None}
    selection = {**selection, "general_proposal": "frozen_fang_gap_insertion",
                 "acceptance": "strictly_lower_official_makespan_than_fresh_anchor"}
    if encoded(proposal) == encoded(anchor):
        records.append({**record, "status": "duplicate"})
        return winner, 1, records, selection
    try:
        bound = analyze(index.graph, proposal, delay)
        lower = bound["with_cross_core_delay"]["lower_bound_cycles"]
        record["certified_lower_bound_cycles"] = lower
        if lower >= result["makespan"]:
            records.append({**record, "status": "bound_pruned",
                            "unscored_plan": proposal,
                            "unscored_plan_sha256": hashlib.sha256(encoded(proposal)).hexdigest()})
            return winner, 1, records, selection
    except UnsupportedBound as error:
        record["bound_unavailable"] = str(error)
    try:
        candidate = evaluate(proposal)
    except EvaluationValidationError as error:
        records.append({**record, "status": "rejected", "reason": str(error)})
        return winner, 2, records, selection
    refs = save("gap", proposal, candidate) or {}
    records.append({**record, "status": "ok", "makespan": candidate["makespan"],
                    "artifacts": refs})
    if candidate["makespan"] < result["makespan"]:
        winner = proposal, candidate, meta["strategy"]
    return winner, 2, records, selection


def evaluate_candidates(index, cores, evaluate, save):
    winner, calls, records, selection = adaptive_solve.evaluate_candidates(
        index, cores, evaluate, save, fallback=general_candidates)
    if "general_proposal" in selection:
        selection["router"].update(route="general_gap", guarded_policy_invocations=0,
                                   general_gap_policy_invocations=1)
    return winner, calls, records, selection


def main():
    return run_solver(policy=evaluate_candidates)


if __name__ == "__main__":
    main()
