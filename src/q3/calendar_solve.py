"""Keep the expanded router, with one gap-placement proposal for attention.

Both proposals use the same guarded row/FFN capsules and singleton submission.
Only ownership construction changes. Online official comparison, including the
unchanged anchor, remains inside complete solver wall time; at most two E0 calls.
"""
import hashlib

from . import expanded_solve
from .attention_rows import construct
from .pipe_bound import UnsupportedBound, analyze
from .safe_solve import encoded, main as run_solver
from evaluation_validation import EvaluationValidationError


def evaluate_candidates(index, cores, evaluate, save):
    winner, calls, records, selection = expanded_solve.evaluate_candidates(
        index, cores, evaluate, save)
    routing = selection.get("router", {})
    if routing.get("route") != "attention":
        return winner, calls, records, selection
    if calls != 1:
        raise AssertionError("attention anchor must have exactly one E0 call")
    if cores == 1:
        # Both placement modes assign every op to core zero. _ready_word then
        # depends only on that ownership and the unchanged original graph,
        # so the submitted plans are identical without constructing both.
        return winner, calls, records, {**selection,
                                      "attention_gap_skip": "single_core_assignment_invariant"}
    delay = routing["attention_cross_delay_cycles"]
    proposal, metadata = construct(index, cores, cross_delay=delay,
                                   pack_ffn=True, placement_mode="gap")
    record = {"name": "attention_gap", "strategy": metadata["strategy"],
              "metadata": metadata, "makespan": None}
    selection = {**selection, "attention_gap_policy": "one_frozen_gap_placement",
                 "acceptance": "strictly_lower_official_makespan_than_fresh_attention",
                 "router": {**routing, "attention_candidate_plans": 2,
                            "attention_gap_construct_attempts": 1,
                            "route_e0_limit": 2,
                            "count_scope": "One evaluated anchor and one proposed gap plan; duplicate/bound checks may avoid the second E0."}}
    if encoded(proposal) == encoded(winner[0]):
        return winner, calls, records + [{**record, "status": "duplicate"}], selection
    try:
        bound = analyze(index.graph, proposal, delay)
        lower = bound["with_cross_core_delay"]["lower_bound_cycles"]
        record["certified_lower_bound_cycles"] = lower
        if lower >= winner[1]["makespan"]:
            record.update(status="bound_pruned", unscored_plan=proposal,
                          unscored_plan_sha256=hashlib.sha256(encoded(proposal)).hexdigest())
            return winner, calls, records + [record], selection
    except UnsupportedBound as error:
        record["bound_unavailable"] = str(error)
    selection["router"].update(evaluation_calls=2,
                              count_scope="One fresh attention anchor and one gap proposal, both online.")
    try:
        result = evaluate(proposal)
    except EvaluationValidationError as error:
        return winner, 2, records + [{**record, "status": "rejected", "reason": str(error)}], selection
    artifacts = save("attention_gap", proposal, result) or {}
    records = records + [{**record, "status": "ok", "makespan": result["makespan"],
                          "artifacts": artifacts}]
    if result["makespan"] < winner[1]["makespan"]:
        winner = proposal, result, metadata["strategy"]
    return winner, 2, records, selection


def main():
    return run_solver(policy=evaluate_candidates)


if __name__ == "__main__":
    main()
