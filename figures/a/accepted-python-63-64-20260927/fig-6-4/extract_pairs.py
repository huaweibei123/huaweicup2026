# -*- coding: utf-8 -*-
"""fig-6-4 输入整理脚本：从 fetch_pair_inputs.py 的 verified-pairs.json
构建逐例指标表、负收益清单与分核汇总。

输入（fetch_pair_inputs.py 产出，500 格全部经 plan 字节相同断言 + 两端 gzip
SHA + 核数/Makespan 核对）：--pairs <verified-inputs/verified-pairs.json>

产出（写入本目录）：
- pair_metrics.csv      逐例指标表（500 行：cache_gain / byte_hit_rate / 类别）
- negative_cases.csv    负收益清单（cache_gain < 1 的格，按真实配对复算）
- per_core_summary.csv  分核汇总（均值与汇总字节命中率分列，不混用）

口径：CacheGain = 同核数无 L2 Makespan / Cache Makespan；命中率按字节计
hit_bytes/(hit_bytes+miss_bytes)，无访问样本（分母为 0）命中率留空并单独标记。
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True, help="path to verified-pairs.json (500 rows)")
    args = ap.parse_args()

    pairs = json.load(open(args.pairs, encoding="utf-8"))
    assert len(pairs) == 500, len(pairs)
    assert all(p["no_l2_makespan"] > 0 and p["cache_makespan"] > 0 for p in pairs)
    assert all(p["hit_bytes"] >= 0 and p["miss_bytes"] >= 0 for p in pairs)

    rows = []
    neg = []
    by_core = defaultdict(lambda: {"gains": [], "hit": 0, "miss": 0, "no_access": 0})
    for p in sorted(pairs, key=lambda x: (x["cores"], x["case"])):
        gain = p["no_l2_makespan"] / p["cache_makespan"]
        denom = p["hit_bytes"] + p["miss_bytes"]
        rate = "" if denom == 0 else p["hit_bytes"] / denom
        if gain < 1:
            cat = "negative"
            neg.append(p | {"cache_gain": gain, "byte_hit_rate": rate})
        elif gain == 1:
            cat = "parity"
        else:
            cat = "positive"
        rows.append({"case": p["case"], "cores": p["cores"],
                     "plan_sha256": p["plan_sha256"], "p2_sha256": p["p2_sha256"],
                     "p3_sha256": p["p3_sha256"],
                     "no_l2_makespan": p["no_l2_makespan"],
                     "cache_makespan": p["cache_makespan"],
                     "cache_gain": repr(gain),
                     "hit_bytes": p["hit_bytes"], "miss_bytes": p["miss_bytes"],
                     "byte_hit_rate": rate, "category": cat})
        c = by_core[p["cores"]]
        c["gains"].append(gain)
        c["hit"] += p["hit_bytes"]
        c["miss"] += p["miss_bytes"]
        if denom == 0:
            c["no_access"] += 1

    n_neg = len(neg)
    n_noaccess = sum(1 for r in rows if r["byte_hit_rate"] == "")
    print("pairs:", len(rows), "| negative:", n_neg,
          "| no-access cells:", n_noaccess)
    print("negative cases:", [(r["case"], "k%d" % r["cores"]) for r in neg])
    for k in sorted(by_core):
        c = by_core[k]
        pooled = c["hit"] / (c["hit"] + c["miss"]) if (c["hit"] + c["miss"]) else ""
        print("k%d: mean_gain=%.10f pooled_byte_hit_rate=%s n=%d no_access=%d" %
              (k, sum(c["gains"]) / len(c["gains"]),
               ("%.10f" % pooled) if pooled != "" else "NA", len(c["gains"]), c["no_access"]))

    def write_csv(name, rows_, header):
        with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows_)

    write_csv("pair_metrics.csv", rows,
              ["case", "cores", "plan_sha256", "p2_sha256", "p3_sha256",
               "no_l2_makespan", "cache_makespan", "cache_gain",
               "hit_bytes", "miss_bytes", "byte_hit_rate", "category"])
    write_csv("negative_cases.csv",
              [{k: (repr(v) if k == "cache_gain" else v) for k, v in r.items()} for r in neg],
              ["case", "cores", "no_l2_makespan", "cache_makespan", "cache_gain",
               "hit_bytes", "miss_bytes", "byte_hit_rate"])
    summary_rows = []
    for k in sorted(by_core):
        c = by_core[k]
        pooled = c["hit"] / (c["hit"] + c["miss"]) if (c["hit"] + c["miss"]) else ""
        summary_rows.append({"cores": k, "n_cases": len(c["gains"]),
                             "mean_cache_gain": repr(sum(c["gains"]) / len(c["gains"])),
                             "mean_byte_hit_rate_case_wise":
                                 repr(sum(r["byte_hit_rate"] for r in rows
                                          if int(r["cores"]) == k and r["byte_hit_rate"] != "")
                                      / max(1, sum(1 for r in rows
                                                   if int(r["cores"]) == k and r["byte_hit_rate"] != ""))),
                             "pooled_byte_hit_rate": pooled,
                             "no_access_cells": c["no_access"]})
    write_csv("per_core_summary.csv", summary_rows,
              ["cores", "n_cases", "mean_cache_gain", "mean_byte_hit_rate_case_wise",
               "pooled_byte_hit_rate", "no_access_cells"])
    print("3 CSV written to", HERE)


if __name__ == "__main__":
    sys.exit(main())
