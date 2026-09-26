# 本程序及代码是在人工智能工具辅助下完成的。
# 代码生成主要使用 GPT-6 系列模型辅助。
# 工具名称：GPT-6 Astra；版本/型号：gpt-6-astra。
# 开发机构/公司：OpenAI；版本颁布日期：2026-09-03。
# 日期指 Astra 模型发布日，不是安装日或知识截止日。
# 本展示版仅新增声明，原始程序内容保持不变。
# 依据：竞赛人工智能工具及输出使用规定（2026）第5条。

"""Try one reduction-forest memory order after the fresh witness incumbent."""
import hashlib

from . import witness_solve
from .construct import ROOT, UnsupportedStructure
from .forest_memory_order import construct
from .pipe_bound import UnsupportedBound, analyze
from .safe_solve import encoded, main as run_solver
from evaluation_validation import EvaluationValidationError, read_required_settings


def evaluate_candidates(index, cores, evaluate, save):
    winner, calls, records, selection = witness_solve.evaluate_candidates(
        index, cores, evaluate, save)
    policy = {"total_e0_limit": 3, "evaluation_calls": calls,
              "acceptance": "strictly_lower_official_makespan_than_fresh_incumbent"}
    if calls >= 3:
        policy.update(status="skip", skip_reason="three_call_budget_already_used",
                      strategy="forest_memory_order")
        return winner, calls, records, {**selection, "forest_policy": policy}

    try:
        proposal, metadata = construct(index, cores)
    except UnsupportedStructure as error:
        policy.update(status="skip", skip_reason=str(error),
                      strategy="forest_memory_order")
        return winner, calls, records, {**selection, "forest_policy": policy}
    policy.update(status="constructed", strategy=metadata["strategy"])
    record = {"name": "forest_memory_order", "strategy": metadata["strategy"],
              "metadata": metadata, "makespan": None}
    selection = {**selection, "forest_policy": policy}
    if encoded(proposal) == encoded(winner[0]):
        policy["status"] = "duplicate"
        return winner, calls, records + [{**record, "status": "duplicate"}], selection

    config = ROOT / "data/raw/a/official/data/config.txt"
    delay = read_required_settings(
        config, "multicore_scene_b", ("cross_core_copy_delay_cycles",)
    )["cross_core_copy_delay_cycles"]
    try:
        lower = analyze(index.graph, proposal, delay)["with_cross_core_delay"]["lower_bound_cycles"]
        record["certified_lower_bound_cycles"] = lower
        if lower >= winner[1]["makespan"]:
            record.update(status="bound_pruned", unscored_plan=proposal,
                          unscored_plan_sha256=hashlib.sha256(encoded(proposal)).hexdigest())
            policy.update(status="bound_pruned", lower_bound_cycles=lower)
            return winner, calls, records + [record], selection
    except UnsupportedBound as error:
        record["bound_unavailable"] = str(error)

    calls += 1
    policy.update(status="evaluating", evaluation_calls=calls)
    try:
        result = evaluate(proposal)
    except EvaluationValidationError as error:
        record.update(status="rejected", reason=str(error))
        policy["status"] = "rejected"
        return winner, calls, records + [record], selection
    artifacts = save("forest_memory_order", proposal, result) or {}
    record.update(status="ok", makespan=result["makespan"], artifacts=artifacts)
    policy["status"] = "evaluated"
    if result["makespan"] < winner[1]["makespan"]:
        winner = proposal, result, metadata["strategy"]
        policy["status"] = "accepted"
    return winner, calls, records + [record], selection


def main():
    return run_solver(policy=evaluate_candidates, candidate_limit=3)


if __name__ == "__main__":
    main()
