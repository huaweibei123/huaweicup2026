"""Official-compatible problem-1 CLI backed by the first E1 candidate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._official import load_problem1_bundle
from .problem1 import evaluate_scene_a, read_scene_a_config


def _run(argv=None) -> int:
    _, support = load_problem1_bundle("_huaweicup_eval_exact_cli_support")
    contest_io = support["contest_io"]
    read_evaluation_config = support["evaluation_validation"].read_evaluation_config
    parser = argparse.ArgumentParser(description="评估问题 1 的多核执行时间")
    parser.add_argument("graph", help="原始计算图 JSON")
    parser.add_argument("plan", nargs="?", help="多核方案 JSON；默认取同名文件")
    parser.add_argument("--config", help="固定评估配置；默认取图所在目录/config.txt")
    parser.add_argument("-o", "--output", help="结果 JSON 路径")
    parser.add_argument("--trace-output", help="Perfetto Trace JSON 路径")
    parser.add_argument("--log-output", help="简短文本日志路径")
    args = parser.parse_args(argv)
    if args.config and not Path(args.config).is_file():
        raise FileNotFoundError(f"configuration file not found: {args.config}")

    graph_path, plan_path, config_path, output_path, trace_path, log_path = (
        contest_io._common_paths(args, "problem_1")
    )
    if str(config_path) != args.config and not config_path.is_file():
        raise FileNotFoundError(
            "configuration file not found: "
            f"{config_path} (defaults to <graph dir>/config.txt; "
            "pass --config to choose another file)"
        )
    graph = contest_io._read_json(graph_path)
    plan = contest_io._read_json(plan_path)
    settings = read_evaluation_config(str(config_path))
    scene = read_scene_a_config(str(config_path))
    result = evaluate_scene_a(
        graph,
        plan,
        bandwidth=settings["bandwidth"],
        capacity=settings["capacity"],
        cross_core_wait=scene["task_cross_core_wait_cycles"],
        same_core_wait=scene["task_same_core_wait_cycles"],
    )
    result["input_graph"] = graph_path.name
    result["input_plan"] = plan_path.name
    contest_io._write_json(output_path, result)
    contest_io.write_text(
        trace_path,
        contest_io.format_scene_a_trace_json(graph_path.name, result) + "\n",
    )
    contest_io.write_text(
        log_path,
        contest_io.format_multicore_result_log(graph_path.name, result),
    )
    contest_io.emit(contest_io.format_data_movement_log(result))
    contest_io.emit(
        f"OK: problem 1 makespan={result['makespan']}; result={output_path}"
    )
    return 0


def main(argv=None) -> int:
    """Match the official CLI's input/runtime error category and exit behavior."""
    try:
        return _run(argv)
    except (ValueError, RuntimeError, OSError) as error:
        print(f"[EVALUATION ERROR] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
