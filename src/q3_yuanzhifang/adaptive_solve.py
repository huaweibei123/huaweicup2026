"""A frozen structural router combining shared-chain stages and captain V2.

No case identifiers or historical scores enter the router. The added route
uses one construction and one online E0; all other graphs retain the pinned
captain policy (at most two online E0 calls). This is not a non-regression
guarantee across routes. All guards and evaluations are online solver costs.
"""
from __future__ import annotations

from .captain_v2.adaptive_solve import (
    _evaluate_direct, evaluate_candidates as captain_candidates,
)
from .captain_v2.construct import ROOT, UnsupportedStructure
from .captain_v2.safe_solve import main as run_solver
from .active_stages import stage_structure
from .construct import SharingIndex
from .pipeline_stages import build as pipeline_build
from evaluation_validation import read_bandwidth_config


def pipeline_request(index, cores):
    """Cheap structural exclusions before creating the shared-input index."""
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("official core count must be an integer in 1..5")
    if cores == 1:
        return False, "preserve single-core captain policy"
    jobs = index.components
    if len(jobs) < cores:
        return False, "fewer independent jobs than requested cores"
    lengths = {len(job) for job in jobs}
    if len(lengths) != 1 or not 2 <= len(jobs[0]) <= 512:
        return False, "requires equal chain lengths in 2..512"
    if any(op["pipe"] not in {"PIPE_M", "PIPE_V"}
           or type(op["cycles"]) is not int or op["cycles"] <= 0
           for op in index.ops.values()):
        return False, "requires positive integer M/V work"
    if not all(all(v in index.succ[u] for u, v in zip(job, job[1:]))
               for job in jobs):
        return False, "requires an actual serial dependency chain per job"
    try:
        index.word_descriptor()
    except UnsupportedStructure:
        pass
    else:
        return False, "preserve the guarded M-V*-M resource-word policy"
    return True, "eligible for full homogeneous shared-input guard"


def evaluate_candidates(index, cores, evaluate, save):
    requested, reason = pipeline_request(index, cores)
    routing = {"pipeline_requested": requested, "request_reason": reason,
               "pipeline_construct_attempts": 0, "pipeline_candidate_plans": 0,
               "captain_policy_invocations": 0,
               "captain_source_commit": "2d5459fa042507cce0f0343e544ed43784c8488b"}
    if requested:
        sharing = SharingIndex(index.graph)
        if stage_structure(sharing) is None:
            routing["pipeline_guard_reason"] = "no identical shared-input chain signature"
        else:
            routing["pipeline_construct_attempts"] = 1
            bandwidth = read_bandwidth_config(ROOT / "data/raw/a/official/data/config.txt")
            plan, metadata = pipeline_build(sharing, cores, bandwidth)
            if not metadata["guard"] or metadata["selected"] != "pipeline_stages":
                raise AssertionError("full pipeline guard and constructor disagree")
            routing.update(route="shared_pipeline", pipeline_candidate_plans=1)
            metadata = {**metadata, "strategy": "shared_contiguous_pipeline",
                        "route": "shared_pipeline",
                        "constructor_source_commit": "6bae8dfa317bc71226068344b59dd65d2612c32b"}
            # Evaluation/save errors propagate; they are never guard rejections.
            return _evaluate_direct(plan, metadata, routing,
                                    "strict_shared_chain_contiguous_pipeline",
                                    evaluate, save)
    winner, calls, records, selection = captain_candidates(index, cores, evaluate, save)
    routing.update(route="captain_v2", captain_policy_invocations=1,
                   route_e0_limit=2, evaluation_calls=calls)
    return winner, calls, records, {**selection, "collaborative_router": routing}


def main():
    return run_solver(policy=evaluate_candidates)


if __name__ == "__main__":
    main()
