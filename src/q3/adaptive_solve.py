"""Strict single-cut stage, ordinary stage, attention/FFN, then guarded policy.

Stage routing uses only the compute graph and core count. Exactly two heaviest
lane cores request rotation; all other lane-load patterns request fixed gather.
Only the full stage constructor can confirm that this interpretation is valid.
Five-core graphs with twelve compute sources first try the narrower original
4x524 stage signature, using only the single-cut migration template.
Stage and attention each have one candidate and one online E0 call, with no
historical-anchor or cross-route non-regression promise. Only declared shape
rejections advance the router. Other inputs retain guarded_solve's own policy.
"""
from .attention_rows import construct as attention_construct
from .construct import ROOT, UnsupportedStructure
from .guarded_solve import evaluate_candidates as guarded_candidates
from .safe_solve import main as run_solver
from .stage_fork_join import construct as stage_construct
from .stage_migration import construct as migration_construct
from evaluation_validation import read_required_settings


def stage_request(index, cores):
    """Cheap provisional lane counts; not a substitute for stage recognition."""
    if type(cores) is not int or cores < 1:
        raise ValueError("positive integer cores required")
    sources = sum(not index.pred[u] for u in index.ops)
    counts = [0] * cores
    for j in range(sources):
        counts[min(cores - 1, j * cores // sources)] += 1
    maximum = max(counts)
    heavy = [core for core, count in enumerate(counts) if count and count == maximum]
    return {
        "collector_policy": "rotate_heavy" if len(heavy) == 2 else "fixed",
        "source_count": sources,
        "lanes_by_core": counts,
        "heaviest_lane_cores": heavy,
        "feature_scope": "Provisional source-count partition; lane/load meaning is confirmed only by the strict stage guard.",
    }


def evaluate_candidates(index, cores, evaluate, save, *, fallback=None):
    # Optional extension point; the historical entrypoint retains its policy.
    fallback = guarded_candidates if fallback is None else fallback
    request = stage_request(index, cores)
    routing = {"stage_request": request, "migration_construct_attempts": 0,
               "migration_candidate_plans": 0, "stage_construct_attempts": 0,
               "stage_candidate_plans": 0, "attention_construct_attempts": 0,
               "attention_candidate_plans": 0, "guarded_policy_invocations": 0}
    if cores == 5 and request["source_count"] == 12:
        routing["migration_construct_attempts"] = 1
        delay = read_required_settings(ROOT / "data/raw/a/official/data/config.txt", "multicore_scene_b",
                                       ("cross_core_copy_delay_cycles",))["cross_core_copy_delay_cycles"]
        routing["migration_cross_delay_cycles"] = delay
        try:
            plan, metadata = migration_construct(index, cores, mode="single_cut",
                                                  cross_core_delay_cycles=delay)
        except UnsupportedStructure as error:
            routing["migration_guard_reason"] = str(error)
        else:
            routing.update(route="stage_migration", migration_candidate_plans=1)
            metadata = {**metadata, "route": "stage_migration"}
            return _evaluate_direct(plan, metadata, routing,
                                    "strict_five_core_twelve_lane_single_cut", evaluate, save)
    routing["stage_construct_attempts"] = 1
    try:
        # One construction attempt, not fixed-plan construction followed by a
        # second rotated-plan construction. The constructor performs its full
        # tensor-port / repeated-stage guard before emitting a plan.
        plan, metadata = stage_construct(index, cores, collector_policy=request["collector_policy"])
    except UnsupportedStructure as error:
        # Only a declared guard rejection changes routes. Constructor defects,
        # evaluator errors and save failures must not become silent fallbacks.
        routing.update(stage_guard_reason=str(error), attention_construct_attempts=1)
        delay = read_required_settings(ROOT / "data/raw/a/official/data/config.txt", "multicore_scene_b",
                                       ("cross_core_copy_delay_cycles",))["cross_core_copy_delay_cycles"]
        routing["attention_cross_delay_cycles"] = delay
        try:
            plan, metadata = attention_construct(index, cores, cross_delay=delay, pack_ffn=True)
        except UnsupportedStructure as attention_error:
            routing.update(attention_guard_reason=str(attention_error))
            winner, calls, records, selection = fallback(index, cores, evaluate, save)
            routing.update(route="guarded", guarded_policy_invocations=1,
                           route_e0_limit=2, evaluation_calls=calls,
                           count_scope="Router attempts only; guarded internal construction/decision records are preserved unchanged.")
            return winner, calls, records, {**selection, "router": routing}
        routing.update(route="attention", attention_candidate_plans=1,
                       attention_pack_ffn=True)
        metadata = {**metadata, "route": "attention", "pack_ffn": True}
        rule = "strict_stage_declined_then_closed_attention_ffn"
    else:
        if metadata["lane_count"] != request["source_count"]:
            raise AssertionError("recognized stage lane count differs from provisional source count")
        routing.update(route="stage", stage_candidate_plans=1)
        metadata = {**metadata, "route": "stage",
                    "collector_policy": request["collector_policy"],
                    "collector_cycle": metadata.get("collector_cycle", [metadata["collector_core"]])}
        rule = "strict_stage_guard_then_lane_load_collector"

    return _evaluate_direct(plan, metadata, routing, rule, evaluate, save)


def _evaluate_direct(plan, metadata, routing, rule, evaluate, save):
    # Deliberately outside all constructor guard handlers: even an evaluator
    # raising UnsupportedStructure must propagate, not try another candidate.
    routing.update(route_e0_limit=1, evaluation_calls=1,
                   count_scope="One successful direct construction and one injected online evaluation; no anchor comparison.")
    result = evaluate(plan)
    artifacts = save("seed", plan, result) or {}
    metadata = {**metadata, "router": routing,
                "construction_note": "The constructor performs no E0 calls; this saved candidate received one online evaluation. No historical or cross-route non-regression guarantee."}
    records = [{"name": "seed", "strategy": metadata["strategy"], "status": "ok",
                "makespan": result["makespan"], "metadata": metadata, "artifacts": artifacts}]
    selection = {"rule": rule, "router": routing}
    return (plan, result, metadata["strategy"]), 1, records, selection


def main():
    return run_solver(policy=evaluate_candidates)


if __name__ == "__main__":
    main()
