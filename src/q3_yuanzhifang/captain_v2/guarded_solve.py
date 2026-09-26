"""One structural anchor plus one release-aware proposal with certified rejection.

The strict acceptance guarantee is relative to this invocation's evaluated
anchor, not every historical method. E0 and bound costs are online costs.
"""
import hashlib

from .construct import UnsupportedStructure
from .pipe_bound import UnsupportedBound, analyze
from .reduction_tree import construct as balanced
from .release_tree import construct as release
from .safe_solve import encoded, main
from .solve import select


def choose_anchor(index, cores):
    try:
        plan, meta = balanced(index, cores)
        return plan, meta, {"rule": "single_reduction_tree_balanced_anchor"}
    except UnsupportedStructure:
        strategy, selection = select(index)
        plan, meta = index.build(cores, strategy)
        return plan, meta, selection


def evaluate_candidates(index, cores, evaluate, save):
    # The CLI uses the frozen canonical config; read delay rather than silently
    # assuming that the mathematical proxy's default 500 matches custom input.
    from evaluation_validation import EvaluationValidationError, read_required_settings
    from .construct import ROOT
    delay = read_required_settings(ROOT / "data/raw/a/official/data/config.txt", "multicore_scene_b",
                                   ("cross_core_copy_delay_cycles",))["cross_core_copy_delay_cycles"]
    anchor, meta, selection = choose_anchor(index, cores)
    result = evaluate(anchor)
    artifacts = save("seed", anchor, result) or {}
    winner = anchor, result, meta["strategy"]
    records = [{"name": "seed", "strategy": meta["strategy"], "status": "ok",
                "makespan": result["makespan"], "metadata": meta, "artifacts": artifacts}]
    try:
        proposal, info = release(index, cores, place=True, cross_delay=delay)
    except UnsupportedStructure as error:
        records.append({"name": "release", "strategy": "release_place_forest",
                        "status": "unsupported", "makespan": None, "reason": str(error)})
        return winner, 1, records, selection
    record = {"name": "release", "strategy": info["strategy"], "makespan": None,
              "metadata": info}
    if len(index.components) > 1 and not info["cuts"]:
        # Scope restriction motivated by the 080 counterexample. It does not
        # prove that every uncut forest order is inferior: keep the existing
        # inter-tree overlap policy until that distinct problem is addressed.
        records.append({**record, "status": "unsupported",
                        "reason": "uncut multi-tree forest: preserve structural overlap policy"})
        return winner, 1, records, selection
    if encoded(proposal) == encoded(anchor):
        records.append({**record, "status": "duplicate"})
        return winner, 1, records, selection
    try:
        bound = analyze(index.graph, proposal, delay)
        lower = bound["with_cross_core_delay"]["lower_bound_cycles"]
        record["certified_lower_bound_cycles"] = lower
        if lower >= result["makespan"]:
            record.update(status="bound_pruned", reason="Cannot strictly improve anchor Makespan; secondary metrics may differ.")
            record["unscored_plan"] = proposal
            record["unscored_plan_sha256"] = hashlib.sha256(encoded(proposal)).hexdigest()
            records.append(record)
            return winner, 1, records, selection
    except UnsupportedBound as error:
        record["bound_unavailable"] = str(error)
    # A small lower bound is never acceptance evidence. Run the unchanged E0.
    try:
        candidate = evaluate(proposal)
    except EvaluationValidationError as error:
        records.append({**record, "status": "rejected", "reason": str(error)})
        return winner, 2, records, selection
    artifacts = save("release", proposal, candidate) or {}
    records.append({**record, "status": "ok", "makespan": candidate["makespan"], "artifacts": artifacts})
    if candidate["makespan"] < result["makespan"]:
        winner = proposal, candidate, info["strategy"]
    return winner, 2, records, selection


if __name__ == "__main__":
    main(policy=evaluate_candidates)
