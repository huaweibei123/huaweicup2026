"""P1/P2/P3 benchmark 独立聚合核查与图表（farmer）。

任务卡：tasks/a/P123-BENCHMARK-DELIVERY.md @ 25f446c0（PR82）。
只读聚合：本模块不运行任何 solver / E0 / E1 / E2，只读取已落盘的
运行产物（farmer Q1 v3 目录布局、后续可扩展 LYX 的 results 布局），
输出规范化表、审计报告与图件。

统计口径（任务卡 §指标与最小表结构）：
- 分母 B(G) 只认冻结官方 ``singlecore_evaluate``（baseline_source 必须如实标注）；
- 加速比 = B(G) / M(核数)，逐 case 先求比值，均值是比值的算术平均；
- 分母缺失/超时 → baseline_speedup 为 null（NA），并计入有效 n；
- evaluator_route 只允许 E0 / 准入清单内的 E1；出现 E2 视为污染行；
- 重复键（problem, case_id, cores, attempt_id）必须被报告，不允许静默覆盖；
- 图与表逐项对应，缺失不填零。

命令行：
    python -m src.analysis.p123_benchmark_report_farmer build \
        --source farmer-q1-v3=results/a/review/accel-100-20260924 \
        --run-id farmer-q1-v3-20260924 \
        --tables results/a/p123-report-farmer/<run> \
        --figures figures/a/p123-report-farmer/<run>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
from pathlib import Path

# 任务卡规定的规范化表最小字段集（顺序即 CSV 列序）
SCHEMA_FIELDS = [
    "run_id", "algorithm_id", "solver_commit", "problem", "case_id", "cores",
    "status", "evaluation_status", "makespan_cycles", "baseline_status",
    "baseline_cycles", "baseline_source", "baseline_speedup",
    "paired_p2_status", "paired_p2_cycles", "cache_gain",
    "solver_wall_seconds", "evaluation_wall_seconds",
    "timing_includes_evaluation", "peak_rss_mib",
    "evaluator_route", "evaluator_commit", "calibration_ref",
    "official_confirmation_status", "graph_hash", "config_hash",
    "official_hash", "runtime_id", "plan_hash", "result_ref", "result_hash",
    "attempt_id",
]

ALLOWED_EVALUATOR_ROUTES = {"E0"}  # 准入 E1 出现时在此登记其校准引用

# 用户提供的两批外部参考值（只作并列展示，一律标"外部参考/可比性待核"）
EXTERNAL_REFERENCE = {
    "source": "user screenshot 2026-09-24（未提供聚合/分母/版本，可比性待核）",
    "P1": {2: 1.87, 3: 2.57, 4: 3.14, 5: 3.57},
    "P2": {2: 2.26, 3: 3.18, 4: 3.96, 5: 4.53},
    "P3": {2: 2.28, 3: 3.23, 4: 4.09, 5: 4.76},
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _new_row(**kw) -> dict:
    row = {f: None for f in SCHEMA_FIELDS}
    row.update(kw)
    return row


# ---------------------------------------------------------------------------
# loader：farmer Q1 v3 目录布局（results/a/review/accel-100-20260924）
# ---------------------------------------------------------------------------

_FAIL_RE = re.compile(r"^case(\d+) c1official: FAIL rc=(\d+) (.+)$", re.M)


def load_farmer_q1_v3(root: Path, run_id: str = "farmer-q1-v3",
                      algorithm_id: str = "q1-propose-e0",
                      solver_commit: str = "4dff90ef699fd51845cf482951e8477066f5f566",
                      runtime_id: str = "windows-x64-cpython-3.13",
                      include_denominator: bool = True,
                      case_range: tuple[int, int] | None = None) -> list[dict]:
    """include_denominator=False 用于分片合并：分母以主工作区（全 100 例）为准，
    其他分片只贡献多核分子行，避免同一分母格出现重复键。"""
    """读取 farmer Q1 v3 批次目录，返回规范化行。

    目录约定（v3/README.md）：
      caseXXX/c1official/{summary.json, singlecore.cmd.txt, ...}  官方单核分母
      caseXXX/cN/summary.json (N=2..5)                            多核分子
      caseXXX/c1/                                                  v2 stub 分母（不引用，仅对照）
      interrupted-v2-attempts/caseXXX-cN/                          v2 被中断旧尝试
      v3/w*.log                                                    驱动日志（超时/失败账）
    """
    root = Path(root)
    rows: list[dict] = []

    # 分母：先从日志收集超时/失败账（含 rc），再按目录状态补齐
    denom_status: dict[str, tuple[str, str]] = {}  # case -> (status, detail)
    for log in sorted(root.glob("v3/w*.log")):
        for m in _FAIL_RE.finditer(log.read_text(encoding="utf-8", errors="replace")):
            case, rc, detail = m.group(1), m.group(2), m.group(3)
            prev = denom_status.get(case)
            # 只记录第一次失败（分母每例只应尝试一次；重复出现本身就是要报告的问题）
            if prev is None:
                denom_status[case] = ("timeout" if "timeout" in detail else "failed",
                                      f"rc={rc} {detail}")

    for case_dir in sorted(root.glob("case*")):
        if not case_dir.is_dir() or "-summary" in case_dir.name:
            continue
        case_id = case_dir.name.replace("case", "")

        # ---- 分母行（含 baseline 元数据）----
        d1 = case_dir / "c1official" if include_denominator else None
        s1 = (d1 / "summary.json") if d1 is not None else None
        if d1 is not None and s1.exists():
            meta = json.loads(s1.read_text(encoding="utf-8"))
            baseline = _new_row(
                run_id=run_id, algorithm_id=algorithm_id, solver_commit=solver_commit,
                problem="P1", case_id=case_id, cores=1,
                status="success", evaluation_status="success",
                makespan_cycles=meta["makespan"],
                baseline_status="success", baseline_cycles=meta["makespan"],
                baseline_source="official singlecore_evaluate.py (frozen)",
                evaluator_route="E0", runtime_id=runtime_id,
                result_ref=str(s1), attempt_id=f"{run_id}-denom",
                timing_includes_evaluation=False,
            )
            cmd = d1 / "singlecore.cmd.txt"
            if cmd.exists():
                baseline["official_hash"] = sha256_file(
                    root.parent.parent / "data/raw/a/official/code/singlecore_evaluate.py") \
                    if (root.parent.parent / "data/raw/a/official/code/singlecore_evaluate.py").exists() else None
            rows.append(baseline)
        elif d1 is not None and d1.exists():
            status, detail = denom_status.get(case_id, ("failed", "no summary; no log entry"))
            rows.append(_new_row(
                run_id=run_id, algorithm_id=algorithm_id, solver_commit=solver_commit,
                problem="P1", case_id=case_id, cores=1,
                status=status, evaluation_status=status,
                baseline_status=status, baseline_source="official singlecore_evaluate.py (frozen)",
                evaluator_route="E0", runtime_id=runtime_id,
                result_ref=str(d1), attempt_id=f"{run_id}-denom",
                official_confirmation_status=f"no-result ({detail})",
            ))
        # 无 c1official 目录 → 分母"未运行"，不在本源产行（由跨源聚合报告缺口）

        # ---- 多核分子行 ----
        case_no = int(case_id)
        in_range = case_range is None or (case_range[0] <= case_no <= case_range[1])
        attempt_suffix = "sweep" if in_range else "v2-archive"
        row_run_id = run_id if in_range else f"{run_id}-v2-archive"
        for cores in (2, 3, 4, 5):
            dn = case_dir / f"c{cores}"
            sn = dn / "summary.json"
            if sn.exists():
                meta = json.loads(sn.read_text(encoding="utf-8"))
                best_result = dn / "best-result.json"
                rows.append(_new_row(
                    run_id=row_run_id, algorithm_id=algorithm_id, solver_commit=solver_commit,
                    problem="P1", case_id=case_id, cores=cores,
                    status="success", evaluation_status="success",
                    makespan_cycles=meta["makespan"],
                    evaluator_route="E0", runtime_id=runtime_id,
                    result_ref=str(best_result) if best_result.exists() else str(sn),
                    solver_wall_seconds=meta.get("elapsed_s"),
                    timing_includes_evaluation=True,  # 60s 预算含内部 E0
                    attempt_id=f"{row_run_id}-{attempt_suffix}",
                ))
            elif in_range or (case_dir / f"c{cores}").exists():
                # 无 summary：查 case 级 summary 的 null 值 → 该格为 failed（无成功评价）
                case_summary = None
                for name in (f"case{case_id}-summary-v3.json", f"case{case_id}-summary.json"):
                    csp = root / name
                    if csp.exists():
                        case_summary = json.loads(csp.read_text(encoding="utf-8"))
                        break
                if case_summary is not None and case_summary.get(f"c{cores}") is None:
                    rows.append(_new_row(
                        run_id=row_run_id, algorithm_id=algorithm_id,
                        solver_commit=solver_commit,
                        problem="P1", case_id=case_id, cores=cores,
                        status="failed", evaluation_status="failed_no_best",
                        evaluator_route="E0", runtime_id=runtime_id,
                        result_ref=str(dn) if dn.exists() else None,
                        attempt_id=f"{row_run_id}-{attempt_suffix}",
                        official_confirmation_status=(
                            "no-best：全部候选 E0 评价失败/超时（30s），无成功 makespan"),
                    ))
            # cN 目录存在但无 summary 且 case 级 summary 也没有：本源不产行；
            # 中断残留由 interrupted-v2-attempts 与日志账反映，避免把中断当完成。
        # v2 的 stub 行不读取：口径作废，仅目录保留。

    # ---- v2 被中断旧尝试（旧身份，明确区分）----
    for old in sorted((root / "interrupted-v2-attempts").glob("case*-c*")):
        m = re.fullmatch(r"case(\d+)-c(\d+)", old.name)
        if not m:
            continue
        rows.append(_new_row(
            run_id=run_id + "-v2-interrupted", algorithm_id=algorithm_id + "-v2",
            solver_commit=solver_commit, problem="P1",
            case_id=m.group(1), cores=int(m.group(2)),
            status="truncated", evaluation_status="truncated",
            evaluator_route="E0", runtime_id=runtime_id,
            result_ref=str(old), attempt_id=f"{old.name}-v2-killed",
            official_confirmation_status="v2 旧尝试，被按口径纠正指示中止；不并入正式统计",
        ))
    return rows


# ---------------------------------------------------------------------------
# 校验与聚合
# ---------------------------------------------------------------------------

def validate_rows(rows: list[dict]) -> dict:
    """返回审计问题清单；每项 {level, kind, detail}。"""
    issues: list[dict] = []
    seen: dict[tuple, dict] = {}
    for r in rows:
        key = (r["problem"], r["case_id"], r["cores"], r["attempt_id"])
        if key in seen:
            issues.append({"level": "error", "kind": "duplicate_key",
                           "detail": f"{key} 首见于 attempt {seen[key]['result_ref']}"})
        seen[key] = r

        route = r.get("evaluator_route")
        if route is not None and route not in ALLOWED_EVALUATOR_ROUTES:
            issues.append({"level": "error", "kind": "evaluator_route_not_admitted",
                           "detail": f"{key} route={route}（E2 或未准入后端 → 该行拒绝进入正式统计）"})

        # 比值重算一致性
        if r.get("cores") != 1 and r.get("baseline_speedup") is not None:
            issues.append({"level": "error", "kind": "speedup_on_solver_row",
                           "detail": f"{key} 多核行不应自带 baseline_speedup（聚合时统一计算）"})
    return {"issues": issues, "rows": len(rows), "unique_keys": len(seen)}


def aggregate(rows: list[dict], problems=("P1",), cores_list=(1, 2, 3, 4, 5),
              total_cases: int = 100) -> dict:
    """按 (problem, cores) 聚合。

    - solver 行：makespan 有效数、比值有效数（需配到成功分母）、
      算术平均/中位数/尾部的逐 case 比值统计；
    - 分母覆盖：n/100 及失败明细；
    - 拒绝 E2/未准入路由行。
    """
    baselines = {}   # (problem, case) -> (cycles, source) 仅 status==success
    solvers = {}     # (problem, case, cores) -> row
    for r in rows:
        if r.get("evaluator_route") not in ALLOWED_EVALUATOR_ROUTES:
            continue
        if r.get("cores") == 1 and r.get("status") == "success" and r.get("makespan_cycles"):
            baselines[(r["problem"], r["case_id"])] = (r["makespan_cycles"], r.get("baseline_source"))
        elif r.get("cores") != 1:
            key = (r["problem"], r["case_id"], r["cores"])
            prev = solvers.get(key)
            is_archive = str(r.get("run_id", "")).endswith("-v2-archive")
            prev_archive = prev is not None and str(prev.get("run_id", "")).endswith("-v2-archive")
            if prev is None or (prev_archive and not is_archive):
                solvers[key] = r

    out = {}
    for problem in problems:
        denom_ok = [c for (p, c) in baselines if p == problem]
        entry = {
            "baseline": {
                "valid_n": len(denom_ok), "total": total_cases,
                "source": next((s for (p, c), (v, s) in baselines.items() if p == problem), None),
                "missing_or_failed_n": total_cases - len(denom_ok),
            },
            "by_cores": {},
        }
        for k in cores_list:
            if k == 1:
                continue
            cases = sorted(c for (p, c, kk) in solvers if p == problem and kk == k)
            ratios, n_run, n_na = [], 0, 0
            for c in cases:
                row = solvers[(problem, c, k)]
                if row["status"] != "success" or not row["makespan_cycles"]:
                    n_na += 1
                    continue
                n_run += 1
                b = baselines.get((problem, c))
                if b is None:
                    n_na += 1  # 比值 NA：分母缺失（保留 makespan）
                    continue
                ratios.append(b[0] / row["makespan_cycles"])
            entry["by_cores"][k] = {
                "cells_n": len(cases),
                "makespan_valid_n": n_run,
                "speedup_valid_n": len(ratios),
                "speedup_na_n": n_na,
                "mean_speedup": round(statistics.fmean(ratios), 4) if ratios else None,
                "median_speedup": round(statistics.median(ratios), 4) if ratios else None,
                "min_speedup": round(min(ratios), 4) if ratios else None,
                "max_speedup": round(max(ratios), 4) if ratios else None,
                "reference": EXTERNAL_REFERENCE.get(problem, {}).get(k),
            }
        out[problem] = entry
    return out


def iter_normalized_rows(rows: list[dict]):
    """把逐案分母/分子行合并成逐格视图（cores=1 行即分母行）。"""
    baselines = {(r["problem"], r["case_id"]): r for r in rows
                 if r["cores"] == 1 and r["status"] == "success"}
    for r in rows:
        if r.get("cores") == 1:
            yield r
            continue
        b = baselines.get((r["problem"], r["case_id"]))
        row = dict(r)
        if r.get("status") == "success" and b is not None:
            row["baseline_status"] = "success"
            row["baseline_cycles"] = b["makespan_cycles"]
            row["baseline_source"] = b["baseline_source"]
            row["baseline_speedup"] = round(b["makespan_cycles"] / r["makespan_cycles"], 4)
        elif r["status"] == "success":
            row["baseline_status"] = "missing_or_failed"
            row["baseline_speedup"] = None  # NA：不得填 0
        yield row


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SCHEMA_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


# ---------------------------------------------------------------------------
# 图件（只读消费规范化表；中文字体用本机微软雅黑，缺字时回退）
# ---------------------------------------------------------------------------

def _mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for name in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC"):
        if any(f.name == name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def plot_heatmap(grid: dict[tuple[str, int], dict[int, float | None]],
                 problem: str, out_path: Path, title: str) -> None:
    plt = _mpl()
    import numpy as np
    cases = sorted({c for (p, c) in grid if p == problem},
                   key=lambda x: int(x))
    cores = [2, 3, 4, 5]
    data = np.full((len(cases), len(cores)), np.nan)
    for i, c in enumerate(cases):
        for j, k in enumerate(cores):
            v = grid.get((problem, c), {}).get(k)
            if v is not None:
                data[i, j] = v
    fig, ax = plt.subplots(figsize=(4.2, max(4.0, 0.16 * len(cases) + 1.2)))
    masked = np.ma.masked_invalid(data)
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad(color="0.85")  # NA/超时：明确灰色，不填零
    vmax = np.nanmax(data) if np.isfinite(np.nanmax(data)) else 1.0
    im = ax.pcolormesh(np.arange(len(cores) + 1), np.arange(len(cases) + 1),
                       masked, cmap=cmap, vmin=0, vmax=math.ceil(vmax * 2) / 2,
                       edgecolors="white", linewidth=0.2)
    fig.colorbar(im, ax=ax, label="加速比 B(G)/M（官方单核分母）")
    ax.set_yticks(np.arange(len(cases)) + 0.5)
    ax.set_yticklabels(cases, fontsize=5)
    ax.set_xticks([j + 0.5 for j in range(len(cores))])
    ax.set_xticklabels([f"{k}核" for k in cores])
    ax.set_ylabel("算例")
    ax.set_title(title, fontsize=10)
    ax.invert_yaxis()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".svg", ".pdf"):
        fig.savefig(out_path.with_suffix(suffix), dpi=200)
    plt.close(fig)


def plot_mean_curve(agg: dict, problem: str, out_path: Path, title: str) -> None:
    """官方口径平均曲线 + 外部参考并列（虚线，标可比性待核）。"""
    plt = _mpl()
    by = agg[problem]["by_cores"]
    ks = sorted(by)
    means = [by[k]["mean_speedup"] for k in ks]
    ns = [by[k]["speedup_valid_n"] for k in ks]
    refs = [by[k]["reference"] for k in ks]

    fig, ax = plt.subplots(figsize=(5.6, 4.0))
    ax.plot([k for k, m in zip(ks, means) if m is not None],
            [m for m in means if m is not None],
            "o-", color="#1f6f43", label="本队实测均值（逐 case 比值算术平均）")
    for k, m, n in zip(ks, means, ns):
        if m is not None:
            ax.annotate(f"n={n}", (k, m), textcoords="offset points",
                        xytext=(0, 7), ha="center", fontsize=8, color="#1f6f43")
    if any(r is not None for r in refs):
        ax.plot([k for k, r in zip(ks, refs) if r is not None],
                [r for r in refs if r is not None],
                "s--", color="#888888",
                label="外部参考（用户截图，可比性待核）")
    ax.set_xticks(ks)
    ax.set_xticklabels([f"{k}核" for k in ks])
    ax.set_xlabel("核数")
    ax.set_ylabel("平均加速比 B(G)/M")
    ax.set_title(title, fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".svg", ".pdf"):
        fig.savefig(out_path.with_suffix(suffix), dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_sources(items: list[str]):
    out = []
    for item in items:
        kind, _, rest = item.partition("=")
        root_spec, _, rng = rest.partition("#")
        case_range = None
        if rng:
            a, _, b = rng.partition("-")
            case_range = (int(a), int(b))
        out.append((kind, Path(root_spec), case_range))
    return out


def build(sources, run_id: str, tables_dir: Path, figures_dir: Path,
          total_cases: int = 100) -> dict:
    rows: list[dict] = []
    for kind, root, case_range in sources:
        if kind == "farmer-q1-v3":
            rows.extend(load_farmer_q1_v3(
                root, run_id=run_id, case_range=case_range,
                include_denominator=not any(r for r in rows if r.get("cores") == 1)))
        else:
            raise SystemExit(f"未知数据源类型: {kind}（当前支持 farmer-q1-v3）")
    audit = validate_rows(rows)
    grid: dict[tuple[str, int], dict[int, float | None]] = {}
    baseline_by_case = {(r["problem"], r["case_id"]): r["makespan_cycles"]
                        for r in rows if r["cores"] == 1 and r["status"] == "success"}
    for r in rows:
        if r["cores"] and r["cores"] != 1 and r["status"] == "success" and r["makespan_cycles"]:
            b = baseline_by_case.get((r["problem"], r["case_id"]))
            grid.setdefault((r["problem"], r["case_id"]), {})[r["cores"]] = (
                round(b / r["makespan_cycles"], 4) if b else None)
    agg = aggregate(rows, total_cases=total_cases)

    tables_dir.mkdir(parents=True, exist_ok=True)
    write_csv(list(iter_normalized_rows(rows)), tables_dir / "normalized_cells.csv")
    (tables_dir / "aggregate.json").write_text(
        json.dumps(agg, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    (tables_dir / "audit.json").write_text(
        json.dumps(audit["issues"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")

    for problem in agg:
        plot_heatmap(grid, problem, figures_dir / f"{problem.lower()}_speedup_heatmap",
                     f"{problem} 多核加速比（官方单核分母 B(G)；灰色=NA/超时）")
        plot_mean_curve(agg, problem, figures_dir / f"{problem.lower()}_mean_curve",
                         f"{problem} 平均加速比 vs 核数（含有效 n）")
    return {"audit": audit, "aggregate": agg}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="聚合 + 审计 + 图表（只读输入，0 evaluator 调用）")
    b.add_argument("--source", action="append", required=True,
                   help="kind=root，如 farmer-q1-v3=results/a/review/accel-100-20260924（可重复）")
    b.add_argument("--run-id", required=True)
    b.add_argument("--tables", required=True)
    b.add_argument("--figures", required=True)
    b.add_argument("--total-cases", type=int, default=100)
    args = ap.parse_args(argv)
    if args.cmd == "build":
        result = build(_parse_sources(args.source), args.run_id,
                       Path(args.tables), Path(args.figures), args.total_cases)
        print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2))
        issues = result["audit"]["issues"]
        print(f"audit: rows={result['audit']['rows']} "
              f"unique_keys={result['audit']['unique_keys']} issues={len(issues)}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
