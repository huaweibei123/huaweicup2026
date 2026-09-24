"""Internal CLI for the two experimental E2 directions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ..eval_exact._official import OFFICIAL_CODE_HASH, load_problem1_bundle
from .event_model import evaluate_event
from .model import (
    ProxyPlanError,
    ProxyUnsupportedError,
    evaluate_batch,
    prepare_graph,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an internal E2 direction (public team_eval pending)"
    )
    parser.add_argument("graph")
    parser.add_argument("plan")
    parser.add_argument("--problem", type=int, default=1)
    parser.add_argument("--engine", choices=("rank", "event"), default="rank")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    graph_path = Path(args.graph)
    plan_path = Path(args.plan)
    config_path = Path(args.config)
    output_path = Path(args.output)
    graph_hash = _sha256(graph_path)
    plan_hash = _sha256(plan_path)
    config_hash = _sha256(config_path)
    if args.engine == "event":
        engine = "proxy-task-event-v0"
        capability = "makespan_estimate"
        numeric_kind = "estimate"
    else:
        engine = "proxy-rank-v0"
        capability = "rank_only"
        numeric_kind = "none"
    try:
        _, support = load_problem1_bundle("_huaweicup_eval_proxy_cli_support")
        contest_io = support["contest_io"]
        validation = support["evaluation_validation"]
        graph = contest_io._read_json(graph_path)
        plan = contest_io._read_json(plan_path)
        settings = validation.read_evaluation_config(str(config_path))
        scene = validation.read_required_settings(
            str(config_path),
            "multicore_scene_a",
            ("task_cross_core_wait_cycles", "task_same_core_wait_cycles"),
        )
        context = prepare_graph(
            graph,
            problem=args.problem,
            bandwidth=settings["bandwidth"],
            capacity=settings["capacity"],
            cross_core_wait=scene["task_cross_core_wait_cycles"],
            same_core_wait=scene["task_same_core_wait_cycles"],
            graph_hash=graph_hash,
            config_hash=config_hash,
        )
        if args.engine == "event":
            response = evaluate_event(context, plan)
            response["request_id"] = plan_path.name
        else:
            response = evaluate_batch(
                context, [{"request_id": plan_path.name, "plan": plan}]
            )[0]
    except ProxyUnsupportedError as error:
        response = {
            "interface": "internal-e2-v0",
            "engine": engine,
            "engine_version": "0.1.0",
            "contract_version": "v1.0-draft-internal",
            "official_code_hash": OFFICIAL_CODE_HASH,
            "capability": capability,
            "status": "unsupported",
            "numeric_kind": numeric_kind,
            "checks": {
                "input": "pass",
                "plan": "unchecked",
                "execution": "unchecked",
            },
            "problem": args.problem,
            "message": str(error),
            "risk_flags": ["execution_unchecked"],
            "identity": {},
        }
    except (ProxyPlanError, ValueError) as error:
        response = {
            "interface": "internal-e2-v0",
            "engine": engine,
            "engine_version": "0.1.0",
            "contract_version": "v1.0-draft-internal",
            "official_code_hash": OFFICIAL_CODE_HASH,
            "capability": capability,
            "status": "invalid",
            "numeric_kind": numeric_kind,
            "checks": {
                "input": "fail",
                "plan": "unchecked",
                "execution": "unchecked",
            },
            "problem": args.problem,
            "message": str(error),
            "risk_flags": ["execution_unchecked"],
            "identity": {},
        }
    response["identity"].update(
        {
            "graph_hash": graph_hash,
            "plan_hash": plan_hash,
            "config_hash": config_hash,
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(response, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(response, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
