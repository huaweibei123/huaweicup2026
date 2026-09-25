"""p123_benchmark_report_farmer 的表结构/口径测试（微型夹具，0 evaluator 调用）。

任务卡要求覆盖：缺分母、超时、重复键、E2 污染、错配、均值口径与时间包含关系。
夹具是明确标注的微型表，不制造合成"成绩"。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from analysis.p123_benchmark_report_farmer import (  # noqa: E402
    aggregate, iter_normalized_rows, validate_rows,
)


def _row(**kw):
    base = dict(
        run_id="t", algorithm_id="alg", solver_commit="c0", problem="P1",
        status="success", evaluation_status="success", evaluator_route="E0",
        attempt_id="a1", timing_includes_evaluation=False,
    )
    base.update(kw)
    return base


class TestValidateRows(unittest.TestCase):
    def test_duplicate_key_reported_not_overwritten(self):
        rows = [
            _row(case_id="001", cores=2, makespan_cycles=100, attempt_id="a1",
                 result_ref="x1"),
            _row(case_id="001", cores=2, makespan_cycles=90, attempt_id="a1",
                 result_ref="x2"),
        ]
        audit = validate_rows(rows)
        kinds = [i["kind"] for i in audit["issues"]]
        self.assertIn("duplicate_key", kinds)
        self.assertEqual(audit["unique_keys"], 1)

    def test_e2_route_rejected(self):
        rows = [_row(case_id="001", cores=2, makespan_cycles=100,
                     evaluator_route="E2")]
        audit = validate_rows(rows)
        kinds = [i["kind"] for i in audit["issues"]]
        self.assertIn("evaluator_route_not_admitted", kinds)
        # E2 行不得进入聚合
        agg = aggregate(rows, problems=("P1",), total_cases=1)
        self.assertEqual(agg["P1"]["by_cores"][2]["makespan_valid_n"], 0)

    def test_speedup_field_on_solver_row_rejected(self):
        rows = [_row(case_id="001", cores=2, makespan_cycles=100,
                     baseline_speedup=1.5)]
        kinds = [i["kind"] for i in validate_rows(rows)["issues"]]
        self.assertIn("speedup_on_solver_row", kinds)


class TestAggregate(unittest.TestCase):
    def _setup(self):
        self.denom = _row(case_id="001", cores=1, makespan_cycles=200,
                          baseline_source="official singlecore_evaluate.py (frozen)")
        self.solver = _row(case_id="001", cores=2, makespan_cycles=100)

    def test_mean_is_mean_of_per_case_ratios(self):
        # 两例：比值 2.0 与 4.0 → 算术平均 3.0（不是总 cycles 之比 600/300=2.0）
        rows = [
            _row(case_id="001", cores=1, makespan_cycles=200),
            _row(case_id="001", cores=2, makespan_cycles=100),
            _row(case_id="002", cores=1, makespan_cycles=400),
            _row(case_id="002", cores=2, makespan_cycles=100),
        ]
        agg = aggregate(rows, problems=("P1",), total_cases=2)
        self.assertEqual(agg["P1"]["by_cores"][2]["mean_speedup"], 3.0)
        self.assertEqual(agg["P1"]["by_cores"][2]["speedup_valid_n"], 2)

    def test_missing_denominator_is_na_not_zero(self):
        # 002 无分母：保留 makespan，比值 NA 计数，不进均值、不得当 0
        rows = [
            _row(case_id="001", cores=1, makespan_cycles=200),
            _row(case_id="001", cores=2, makespan_cycles=100),
            _row(case_id="002", cores=2, makespan_cycles=100),  # 无分母
        ]
        agg = aggregate(rows, problems=("P1",), total_cases=2)
        bc = agg["P1"]["by_cores"][2]
        self.assertEqual(bc["makespan_valid_n"], 2)
        self.assertEqual(bc["speedup_valid_n"], 1)
        self.assertEqual(bc["speedup_na_n"], 1)
        self.assertEqual(bc["mean_speedup"], 2.0)
        self.assertEqual(agg["P1"]["baseline"]["valid_n"], 1)

    def test_timeout_cell_excluded_and_counted(self):
        rows = [
            _row(case_id="001", cores=1, makespan_cycles=200),
            _row(case_id="001", cores=2, makespan_cycles=100),
            _row(case_id="003", cores=2, status="timeout",
                 evaluation_status="timeout", makespan_cycles=None),
        ]
        agg = aggregate(rows, problems=("P1",), total_cases=2)
        bc = agg["P1"]["by_cores"][2]
        self.assertEqual(bc["cells_n"], 2)
        self.assertEqual(bc["makespan_valid_n"], 1)
        self.assertEqual(bc["speedup_na_n"], 1)

    def test_iter_normalized_rows_pairs_baseline_and_na(self):
        self._setup()
        missing = _row(case_id="002", cores=2, makespan_cycles=100)
        out = list(iter_normalized_rows([self.denom, self.solver, missing]))
        paired = [r for r in out if r["case_id"] == "001" and r["cores"] == 2][0]
        self.assertEqual(paired["baseline_cycles"], 200)
        self.assertEqual(paired["baseline_speedup"], 2.0)
        na = [r for r in out if r["case_id"] == "002"][0]
        self.assertEqual(na["baseline_status"], "missing_or_failed")
        self.assertIsNone(na["baseline_speedup"])

    def test_timing_inclusion_field_is_carried(self):
        # v3 的 60s 搜索预算含内部 E0：该事实必须随行携带，不得相加重复计时
        row = _row(case_id="001", cores=2, makespan_cycles=100,
                   solver_wall_seconds=55.0, timing_includes_evaluation=True)
        out = [r for r in iter_normalized_rows([row]) if r["cores"] == 2][0]
        self.assertTrue(out["timing_includes_evaluation"])
        self.assertEqual(out["solver_wall_seconds"], 55.0)


if __name__ == "__main__":
    unittest.main()
