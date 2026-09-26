# -*- coding: utf-8 -*-
"""fig-6-6 输入提取脚本（独立于绘图；plot.py 只读本脚本产出的交付 CSV）。

从固定来源只读取件并核对 SHA-256，生成交付表：
- --audit-json    f26704ed8748f0a575b55f1a02b83d7335a1083f 的
                  results/a/q3-yuanzhifang/cache-counterexample-021-20260925/audit.json，
                  SHA-256 e50a97d724f7f79355bb98e75aafc382dba726a6d23002932e5cf114690b6135
- --p2-result-gz  19bebf35205d23fdd832781540f8879da52eeb62 的
                  results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/
                  revision2-baseline-draft/cache_pair/021-k3/result.json.gz，
                  gzip 原字节 SHA-256 e7b6d54df96bca81730c7dadc8b59a65d988da75476be81ea0b550e4f4dad3c6
                  （与旧 c2 配对摘要一致的同字节复用拷贝）
- --p3-result-gz  130dfe4c6a10d394a6d04257f660d5a66c51c624 的
                  results/a/q3-nikolastarx/witness-full500-20260925-s59/20260924T2032Z-s59ee/
                  s06/cells/021-k3-unified-attention-witness-e0/evidence/result.json.gz，
                  gzip 原字节 SHA-256 f6e460a78209a37b3edb003692efd590378687e4efa7575b286dfa0245c2edb5
- --p3-plan-json  同 P3 提交的 case_021_multicore_res.json，
                  SHA-256 13362774572585a30167aed18b9929d52f1962390d05fafb3dc4dbd318a098c4
                  （= 配对摘要 source_plan_sha256，两端计划同一性绑定）

用法（工作目录=仓库根）：
  .venv/Scripts/python.exe figures/a/jia-fig6-6-20260926/extract_inputs.py \
      --audit-json <021 audit.json> --p2-result-gz <p2 result.json.gz> \
      --p3-result-gz <p3 result.json.gz> --p3-plan-json <case_021_multicore_res.json>

产出（写入本目录）：aligned_ops.csv / key_events.csv / summary_metrics.csv。
哈希不符立即中止，不生成任何表。0 新实验。
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

EXPECT = {
    "audit": "e50a97d724f7f79355bb98e75aafc382dba726a6d23002932e5cf114690b6135",
    "p2": "e7b6d54df96bca81730c7dadc8b59a65d988da75476be81ea0b550e4f4dad3c6",
    "p3": "f6e460a78209a37b3edb003692efd590378687e4efa7575b286dfa0245c2edb5",
    "plan": "13362774572585a30167aed18b9929d52f1962390d05fafb3dc4dbd318a098c4",
}
MK_P2, MK_P3 = 2140720, 2140863
WIN1 = (4900, 7000)      # 首次命中相关变化窗口（首完成差异/首开始差异/首列表换位）
WIN2 = (443050, 443250)  # 后续 DDR 读取变化窗口（同起点变慢 COPY_IN）


def sha_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description="fig-6-6 input extraction with fixed-source hash check")
    ap.add_argument("--audit-json", required=True)
    ap.add_argument("--p2-result-gz", required=True)
    ap.add_argument("--p3-result-gz", required=True)
    ap.add_argument("--p3-plan-json", required=True)
    args = ap.parse_args()

    # ---- 固定来源哈希核对（不符即中止）----
    for label, path, expect in (("audit-json", args.audit_json, EXPECT["audit"]),
                                ("p2-result-gz", args.p2_result_gz, EXPECT["p2"]),
                                ("p3-result-gz", args.p3_result_gz, EXPECT["p3"]),
                                ("p3-plan-json", args.p3_plan_json, EXPECT["plan"])):
        h = sha_file(path)
        print("%s sha256: %s" % (label, h))
        assert h == expect, "%s SHA mismatch vs fixed commit" % label

    audit = json.load(open(args.audit_json, encoding="utf-8"))
    p2 = json.loads(gzip.decompress(open(args.p2_result_gz, "rb").read()))
    p3 = json.loads(gzip.decompress(open(args.p3_result_gz, "rb").read()))

    # ---- 官方值与计划绑定断言 ----
    assert p2["makespan"] == MK_P2 and p3["makespan"] == MK_P3
    assert p2["makespan"] == audit["makespan"]["p2"] and p3["makespan"] == audit["makespan"]["p3"]
    assert audit["makespan"]["increase"] == 143
    assert abs(audit["makespan"]["cache_gain"] - 0.9999332045067807) < 1e-15
    assert p2["data_movement_bytes"] == p3["data_movement_bytes"] == audit["movement"]
    assert p2["num_cores"] == p3["num_cores"] == 3 and p2["scene"] == p3["scene"] == "B"
    assert p3["cache_mode"] == "read_only"
    print("makespan P2/P3 = %d/%d (+%d), cache_gain %.10f OK" %
          (MK_P2, MK_P3, MK_P3 - MK_P2, audit["makespan"]["cache_gain"]))
    print("movement five fields equal OK:", audit["movement"]["scheduled_copy_bytes"])

    # ---- 按 (core_id, task_id, op_id) 对齐两端 8,881 条操作（不平移）----
    def keymap(r):
        m = {}
        for c in r["per_core_timeline"]:
            for o in c["ops"]:
                m[(c["core_id"], o["task_id"], o["op_id"])] = o
        return m
    m2, m3 = keymap(p2), keymap(p3)
    assert set(m2) == set(m3) and len(m2) == audit["operation_count"] == 8881
    assert all(m2[k]["op"] == m3[k]["op"] and m2[k]["pipe"] == m3[k]["pipe"] for k in m2)

    rows = []
    for (cid, tid, oid) in sorted(m2):
        a2, a3 = m2[(cid, tid, oid)], m3[(cid, tid, oid)]
        rows.append({
            "core": cid + 1, "source_core_id": cid, "task_id": tid, "op_id": oid,
            "op": a2["op"], "pipe": a2["pipe"],
            "p2_start": a2["start"], "p2_end": a2["end"], "p2_duration": a2["duration"],
            "p3_start": a3["start"], "p3_end": a3["end"], "p3_duration": a3["duration"],
            "p3_cache_hit": a3.get("cache_hit", ""),
            "p3_memory_path": a3.get("memory_path", ""),
            "start_diff": a3["start"] - a2["start"],
            "end_diff": a3["end"] - a2["end"],
            "duration_diff": a3["duration"] - a2["duration"],
        })
    ch_s = sum(1 for r in rows if r["start_diff"] != 0)
    ch_e = sum(1 for r in rows if r["end_diff"] != 0)
    ch_d = sum(1 for r in rows if r["duration_diff"] != 0)
    assert (ch_s, ch_e, ch_d) == (audit["changed_start_count"],
                                  audit["changed_end_count"], audit["changed_duration_count"])
    print("aligned_ops rows:", len(rows), "| changed start/end/dur = %d/%d/%d OK" % (ch_s, ch_e, ch_d))

    # ---- 关键事件核对（与 audit 记录逐一相等）----
    def find(rid):
        return next(r for r in rows if r["op_id"] == rid)
    fct = audit["first_completion_time_change"]
    r = find(fct["op_id"])
    assert (r["p2_start"], r["p2_end"], r["p3_start"], r["p3_end"]) == \
           (fct["p2_start"], fct["p2_end"], fct["p3_start"], fct["p3_end"])
    assert r["p3_cache_hit"] == fct["p3_cache_hit"] is True
    fss = audit["first_same_start_slower_copy_in"]
    r2 = find(fss["op_id"])
    assert (r2["p2_start"], r2["p2_end"], r2["p3_start"], r2["p3_end"]) == \
           (fss["p2_start"], fss["p2_end"], fss["p3_start"], fss["p3_end"])
    assert r2["p3_cache_hit"] is False and r2["p3_memory_path"] == "DDR"
    fst = audit["first_start_change"]
    r3 = find(fst["op_id"])
    assert r3["p2_start"] == fst["p2_start"] and r3["p3_start"] == fst["p3_start"]
    print("key events verified against audit (first completion gain / first start change / first same-start slower)")

    ev_rows = [
        {"event": "makespan_end_p2", "core": "", "op_id": "", "endpoint": "end", "cycles": MK_P2,
         "note": "P2（无 L2）全量最晚结束 == 官方 makespan"},
        {"event": "makespan_end_p3", "core": "", "op_id": "", "endpoint": "end", "cycles": MK_P3,
         "note": "P3（只读 Cache）全量最晚结束 == 官方 makespan；+143 cycles 非单调"},
        {"event": "first_completion_gain", "core": fct["core_id"] + 1, "op_id": fct["op_id"],
         "endpoint": "start/end", "cycles": fct["p3_end"] - fct["p3_start"],
         "note": "最早完成时间差异：P2 %d-%d(%d cy) vs P3 %d-%d(%d cy, CACHE_READ 命中)" %
                 (fct["p2_start"], fct["p2_end"], fct["p2_duration"],
                  fct["p3_start"], fct["p3_end"], fct["p3_duration"])},
        {"event": "first_start_change", "core": fst["core_id"] + 1, "op_id": fst["op_id"],
         "endpoint": "start", "cycles": fst["p3_start"],
         "note": "最早开始时间差异：P2 %d vs P3 %d" % (fst["p2_start"], fst["p3_start"])},
        {"event": "first_same_start_slower_copy_in", "core": fss["core_id"] + 1, "op_id": fss["op_id"],
         "endpoint": "start/end", "cycles": fss["p3_end"] - fss["p3_start"],
         "note": "最早同起点但服务变慢：P2 %d cy vs P3 %d cy（走 DDR）；与 Cache 改变共享服务相容，非完整因果" %
                 (fss["p2_duration"], fss["p3_duration"])},
    ]

    st = p3["cache_stats"]
    sm_rows = [
        {"metric": "makespan_p2_cycles", "value": MK_P2},
        {"metric": "makespan_p3_cycles", "value": MK_P3},
        {"metric": "increase_cycles", "value": MK_P3 - MK_P2},
        {"metric": "cache_gain_p2_over_p3", "value": audit["makespan"]["cache_gain"]},
        {"metric": "operation_count_aligned", "value": audit["operation_count"]},
        {"metric": "changed_start", "value": ch_s},
        {"metric": "changed_end", "value": ch_e},
        {"metric": "changed_duration", "value": ch_d},
        {"metric": "original_graph_copy_bytes", "value": audit["movement"]["original_graph_copy_bytes"]},
        {"metric": "scheduled_copy_bytes", "value": audit["movement"]["scheduled_copy_bytes"]},
        {"metric": "added_copy_bytes", "value": audit["movement"]["added_copy_bytes"]},
        {"metric": "partition_added_copy_bytes", "value": audit["movement"]["partition_added_copy_bytes"]},
        {"metric": "spill_added_copy_bytes", "value": audit["movement"]["spill_added_copy_bytes"]},
        {"metric": "cache_copy_in_hits", "value": st["copy_in_hits"]},
        {"metric": "cache_copy_in_misses", "value": st["copy_in_misses"]},
        {"metric": "cache_hit_bytes", "value": st["hit_bytes"]},
        {"metric": "cache_miss_bytes", "value": st["miss_bytes"]},
        {"metric": "cache_hit_rate", "value": st["hit_rate"]},
    ]

    def write_csv(name, rows, header):
        with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    write_csv("aligned_ops.csv", rows,
              ["core", "source_core_id", "task_id", "op_id", "op", "pipe",
               "p2_start", "p2_end", "p2_duration", "p3_start", "p3_end", "p3_duration",
               "p3_cache_hit", "p3_memory_path", "start_diff", "end_diff", "duration_diff"])
    write_csv("key_events.csv", ev_rows,
              ["event", "core", "op_id", "endpoint", "cycles", "note"])
    write_csv("summary_metrics.csv", sm_rows, ["metric", "value"])
    print("win1 rows in [4900,7000]:", sum(1 for r in rows if r["p2_start"] < 7000 and r["p2_end"] > 4900))
    print("3 CSV written to", HERE)


if __name__ == "__main__":
    sys.exit(main())
