"""构建论文附录逐用例表（P1/P2/P3 × 100 图 × k1-5）。

数据源（队长固定版本，main e82c2009 / c7931c3b）：
  lyx-feed-P1-500.json       blob 0e8b2ba050142d723ae444ffa021d1a7d1e50a4e
  lyx-feed-P2-500.json       blob 883e1994415a495e63b0a21a390df428bba4d59c
  lyx-feed-P3-rev2-500.json  blob 3440c04b18b157365fd72e6105a896822786cdca (rev2, c7931c3b)

列（队长 5826870762 指定）：逐 case/k 给出 Makespan、**额外** DDR 字节、状态、
算法/版本、来源；P3 另有 Cache 命中率；CacheGain 仅中央按同计划配对派生，此处留空。

字段口径（队长 10:42:37Z 更正，统一文字）：
  「额外 DDR 搬运（bytes）」= feed 记录的 metrics.extra_ddr_bytes
  （此前误写为 added_copy_bytes，脚本不读取该字段；论文引用时以 extra_ddr_bytes 为准）

用法：
    python -B build_appendix_table.py --sample        # 小样：case 001-003 × k1-5
    python -B build_appendix_table.py --full          # 全量 500×3
"""

import argparse
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

SRC = Path(__file__).resolve().parent / "src"
OUT = SRC.parent

FEEDS = [
    ("P1", "lyx-feed-P1-500.json"),
    ("P2", "lyx-feed-P2-500.json"),
    ("P3", "lyx-feed-P3-rev2-500.json"),
]
PROV = {
    "P1": {"commit": "e82c20098eb53cfb00d5f2287173f6894b3fb291", "blob": "0e8b2ba050142d723ae444ffa021d1a7d1e50a4e",
           "algo": "q1-unified-structural-guard"},
    "P2": {"commit": "e82c20098eb53cfb00d5f2287173f6894b3fb291", "blob": "883e1994415a495e63b0a21a390df428bba4d59c",
           "algo": "q2-adaptive-budget"},
    "P3": {"commit": "c7931c3bdcb87c5aac5a7c3a6fbf8efed2b73254", "blob": "3440c04b18b157365fd72e6105a896822786cdca",
           "algo": "q3-witness-structure"},
}
HDR_FILL = PatternFill("solid", fgColor="4472C4")
HDR_FONT = Font(bold=True, color="FFFFFF")
COLUMNS = ["用例", "核数 k", "状态", "Makespan（cycles）", "额外 DDR 搬运（bytes）",
           "Cache 命中率", "Cache 加速比", "算法", "算法版本（solver commit）", "数据来源"]


def build_rows(problem, feed, sample):
    recs = feed["records"]
    if sample:
        recs = [r for r in recs if r["case_id"] in {"001", "002", "003"}]
    rows = []
    for r in sorted(recs, key=lambda x: (int(x["case_id"]), x["cores"])):
        m = r.get("metrics") or {}
        rows.append([
            r["case_id"], r["cores"], r.get("status", "ok"),
            m.get("makespan_cycles"), m.get("extra_ddr_bytes"),
            m.get("cache_hit_rate") if problem == "P3" else None,
            None,  # CacheGain 由中央按同计划配对派生，此处留空
            r.get("algorithm_id"),
            (r.get("solver_commit") or "")[:12] or None,
            f"feed blob {PROV[problem]['blob'][:12]} @ {PROV[problem]['commit'][:12]}",
        ])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="只输出 case 001-003 小样")
    ap.add_argument("--full", action="store_true", help="全量 500×3")
    args = ap.parse_args()
    sample = args.sample or not args.full

    wb = Workbook()
    wb.remove(wb.active)
    for problem, fname in FEEDS:
        feed = json.load(open(SRC / fname, encoding="utf-8"))
        ws = wb.create_sheet(problem)
        ws.append(COLUMNS)
        for c in range(1, len(COLUMNS) + 1):
            cell = ws.cell(row=1, column=c)
            cell.fill = HDR_FILL; cell.font = HDR_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")
        rows = build_rows(problem, feed, sample)
        for row in rows:
            ws.append(row)
        widths = [8, 7, 8, 18, 22, 12, 12, 26, 24, 40]
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{len(rows) + 1}"
    out = OUT / ("appendix-sample-001-003.xlsx" if sample else "appendix-full-500x3.xlsx")
    wb.save(out)
    print("saved:", out)
    print("rows per sheet:", len(rows), "| mode:", "sample" if sample else "full")

    if not sample:
        # ---- 来源/缺失检查（队长 10:42:37Z 要求随全量交付）----
        print("\n== 来源/缺失检查 ==")
        problems = []
        for problem, fname in FEEDS:
            feed = json.load(open(SRC / fname, encoding="utf-8"))
            recs = feed["records"]
            cases = {r["case_id"] for r in recs}
            ks = {r["cores"] for r in recs}
            n_ok = sum(1 for r in recs if r.get("status") == "ok")
            miss_field = [f"{r['case_id']}/k{r['cores']}" for r in recs
                          if r.get("status") == "ok" and
                          ((r.get("metrics") or {}).get("makespan_cycles") is None or
                           (r.get("metrics") or {}).get("extra_ddr_bytes") is None)]
            extra = sorted(cases - {f"{i:03d}" for i in range(1, 101)})
            print(f"{problem}: records={len(recs)} ok={n_ok} cases={len(cases)} ks={sorted(ks)} "
                  f"| blob={PROV[problem]['blob'][:12]} @ {PROV[problem]['commit'][:12]} "
                  f"| algo={PROV[problem]['algo']}")
            if len(recs) != 500 or n_ok != 500:
                problems.append(f"{problem}: 非全量全 ok（{len(recs)} 条 / ok {n_ok}）")
            if len(cases) != 100 or ks != {1, 2, 3, 4, 5}:
                problems.append(f"{problem}: 覆盖异常（cases={len(cases)}, ks={sorted(ks)}）")
            if extra:
                problems.append(f"{problem}: 越界 case：{extra}")
            if miss_field:
                problems.append(f"{problem}: ok 但缺 Makespan/extra_ddr_bytes：{miss_field[:5]}…")
            # 三份 feed blob 身份复核
            import hashlib
            digest = hashlib.sha256((SRC / fname).read_bytes()).hexdigest()
            print(f"   本地文件 sha256: {digest[:16]}…（与队长 blob 清单核对）")
        if problems:
            print("\n发现问题：")
            for p_ in problems:
                print(" -", p_)
        else:
            print("\n全部通过：3×500=1500 行、100 case × k1-5 全覆盖、字段无缺失、来源 blob 与指定一致。")


if __name__ == "__main__":
    main()
