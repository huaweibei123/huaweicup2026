"""方案成绩台三批次数据 → 统一规范化表。

三组批次（当前最优来源，2026-09-25 选定）：
  A. farmer-q1-v3        P1 × 100 图 × k2-5（本方 propose+官方E0，703fed feed，含 k1 分母）
  B. lyx-p123-multicore  P1/P2/P3 × 100 图 × k1-5 全矩阵快照（12:17Z，749+ ok，LYX runner）
  C. official-singlecore 队长本机官方单核分母 100/100（PR89）

输出统一长表 columns：
  batch, problem, case_id, cores, status, makespan_cycles, singlecore_cycles,
  speedup, solver_wall_seconds, evaluation_wall_seconds, ddr_bytes, extra_ddr_bytes,
  spill_bytes, cache_hit_rate, cache_speedup, algorithm_id, source

数据文件被下一轮优化替换后，重跑本 loader + make_all 即可全量重绘。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

BASE_COLUMNS = [
    "batch", "problem", "case_id", "cores", "status", "makespan_cycles",
    "singlecore_cycles", "speedup", "solver_wall_seconds",
    "evaluation_wall_seconds", "ddr_bytes", "extra_ddr_bytes", "spill_bytes",
    "cache_hit_rate", "cache_speedup", "algorithm_id", "source",
]

EXTERNAL_REFERENCE = {  # 用户截图目标值（外部参考/可比性待核）
    "P1": {2: 1.87, 3: 2.57, 4: 3.14, 5: 3.57},
    "P2": {2: 2.26, 3: 3.18, 4: 3.96, 5: 4.53},
    "P3": {2: 2.28, 3: 3.23, 4: 4.09, 5: 4.76},
}


def _f(v):
    try:
        x = float(v)
        return x
    except (TypeError, ValueError):
        return None


def load_batch_a(feed_path: Path) -> pd.DataFrame:
    """Batch A：farmer-q1-v3 board feed（502 条 → 400 格 + 100 分母 + v2arch 保留）。"""
    feed = json.load(open(feed_path, encoding="utf-8"))
    # 分母行（k1, ok）→ 逐图基线，供 k2-5 现算 speedup（协议不携带比值）
    baseline = {}
    for r in feed["records"]:
        if r["cores"] == 1 and r["status"] == "ok":
            baseline[r["case_id"]] = (r.get("metrics") or {}).get("makespan_cycles")
    rows = []
    for r in feed["records"]:
        m = r.get("metrics") or {}
        rows.append({
            "batch": "A-farmer-q1-v3",
            "problem": r["problem"],
            "case_id": r["case_id"],
            "cores": r["cores"],
            "status": r["status"],
            "makespan_cycles": m.get("makespan_cycles"),
            "singlecore_cycles": None,
            "speedup": ((baseline.get(r["case_id"]) / m.get("makespan_cycles"))
                        if (r["cores"] != 1 and r["status"] == "ok"
                            and m.get("makespan_cycles") and baseline.get(r["case_id"])) else
                        (1.0 if (r["cores"] == 1 and r["status"] == "ok") else None)),
            "solver_wall_seconds": m.get("solver_wall_seconds"),
            "evaluation_wall_seconds": m.get("evaluation_wall_seconds"),
            "ddr_bytes": m.get("ddr_bytes"),
            "extra_ddr_bytes": m.get("extra_ddr_bytes"),
            "spill_bytes": m.get("spill_bytes"),
            "cache_hit_rate": m.get("cache_hit_rate"),
            "cache_speedup": m.get("cache_speedup"),
            "algorithm_id": r.get("algorithm_id"),
            "source": "703fed17 (feed 638c565a)",
        })
    return pd.DataFrame(rows, columns=BASE_COLUMNS)


def load_batch_b(comparison_csv: Path) -> pd.DataFrame:
    """Batch B：lyx-p123-multicore 快照 comparison.csv（1500 行全矩阵）。"""
    rows = []
    with open(comparison_csv, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({
                "batch": "B-lyx-p123-multicore",
                "problem": r["problem"],
                "case_id": r["case"],
                "cores": int(r["cores"]),
                "status": r["status"],
                "makespan_cycles": _f(r.get("makespan_cycles")),
                "singlecore_cycles": _f(r.get("singlecore_cycles")),
                "speedup": _f(r.get("multicore_speedup")),
                "solver_wall_seconds": _f(r.get("solver_wall_seconds")),
                "evaluation_wall_seconds": _f(r.get("e0_wall_seconds")),
                "ddr_bytes": _f(r.get("data_movement_bytes")),
                "extra_ddr_bytes": None,
                "spill_bytes": None,
                "cache_hit_rate": _f(r.get("cache_hit_rate")),
                "cache_speedup": _f(r.get("cache_speedup")),
                "algorithm_id": r.get("algorithm"),
                "source": "fd0a78b3 (snapshot 20260924T121711Z)",
            })
    return pd.DataFrame(rows, columns=BASE_COLUMNS)


def load_batch_c(progress_json: Path) -> pd.DataFrame:
    """Batch C：队长本机官方单核分母 100/100。"""
    prog = json.load(open(progress_json, encoding="utf-8"))
    items = prog.get("cases") or prog.get("records") or []
    if isinstance(prog, dict) and not items and "results" in prog:
        items = prog["results"]
    rows = []
    for it in items:
        if not isinstance(it, dict):
            continue
        case = it.get("case") or it.get("case_id") or it.get("graph")
        case = str(case).replace("case_", "").replace(".json", "").zfill(3) if case else None
        status = it.get("status", "ok")
        rows.append({
            "batch": "C-official-singlecore",
            "problem": "P1",
            "case_id": case,
            "cores": 1,
            "status": status,
            "makespan_cycles": it.get("makespan") or it.get("makespan_cycles"),
            "singlecore_cycles": it.get("makespan") or it.get("makespan_cycles"),
            "speedup": None,
            "solver_wall_seconds": None,
            "evaluation_wall_seconds": it.get("wall_seconds") or it.get("wall") or it.get("elapsed_seconds"),
            "ddr_bytes": None, "extra_ddr_bytes": None, "spill_bytes": None,
            "cache_hit_rate": None, "cache_speedup": None,
            "algorithm_id": "official-singlecore",
            "source": "b0937de5 (PR89)",
        })
    return pd.DataFrame(rows, columns=BASE_COLUMNS)


def load_all(data_dir: Path) -> pd.DataFrame:
    """从 board-charts-data 目录装配三批次统一长表。"""
    data_dir = Path(data_dir)
    frames = []
    a = data_dir / "board-feed-20260924T135603Z-farmer-q1-v3.json"
    if a.exists():
        frames.append(load_batch_a(a))
    b = data_dir / "lyx-comparison.csv"
    if b.exists():
        frames.append(load_batch_b(b))
    c = data_dir / "captain-baseline-progress.json"
    if c.exists():
        frames.append(load_batch_c(c))
    df = pd.concat(frames, ignore_index=True)
    df["case_no"] = pd.to_numeric(df["case_id"], errors="coerce")
    return df
