# -*- coding: utf-8 -*-
"""fig-6-5 输入提取脚本（独立于绘图；plot.py 只读本脚本产出的交付 CSV）。

从两项固定来源只读取件并核对 SHA-256，生成交付表：
- --audit-json    prefix-realized-path 审计（固定提交 28e8c7ddfe2223b2261056f554259c43d5bba272 的
                  results/a/q3-nikolastarx/prefix-realized-path-20260925/audit.json），
                  SHA-256 bcdb051a978bc0c1e44fba43213c62460bb0eed8971090b702413cbe588c1755
- --evidence-tar  机制单格证据包（同一固定提交的
                  results/a/q3-nikolastarx/pipeline-prefix-linux-20260925/run-local/evidence.tar.gz），
                  SHA-256 a923a07fc1ad549eecaae227e534d7a7de83ef1647a67a60a70d130c4aef8b05
                  （= 审计文件 source_archive_sha256；其成员 probe/official-p3.json.gz
                  解压前 SHA-256 = d4cdf8dbabe22923b9a74329741fb39e74a588e619d9f101db1fd28ecd629da1
                  = 审计文件 official_result_sha256）

用法（工作目录=仓库根）：
  .venv/Scripts/python.exe figures/a/jia-fig6-5-20260926/extract_inputs.py \
      --audit-json <prefix-realized-path audit.json 路径> \
      --evidence-tar <evidence.tar.gz 路径>

产出（写入本目录）：prefix_ops.csv / critical_path_ops.csv / evidence_points.csv /
path_contributions.csv。哈希不符立即中止，不生成任何表。0 新实验。
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))

EXPECT_AUDIT = ("28e8c7ddfe2223b2261056f554259c43d5bba272",
                "bcdb051a978bc0c1e44fba43213c62460bb0eed8971090b702413cbe588c1755")
EXPECT_TAR = ("28e8c7ddfe2223b2261056f554259c43d5bba272",
              "a923a07fc1ad549eecaae227e534d7a7de83ef1647a67a60a70d130c4aef8b05")
EXPECT_RESULT_GZ = "d4cdf8dbabe22923b9a74329741fb39e74a588e619d9f101db1fd28ecd629da1"

MAKESPAN = 38024
EXCL_BOUND = 29780          # 乐观独占界（prepared 图最中路，带/不带 167 条内存复用边同值）
SHARED_BOUND = 36592        # 有理数处理器共享+取整模型界（式 6-18 完成下限接入后继约束）


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser(description="fig-6-5 input extraction with fixed-source hash check")
    ap.add_argument("--audit-json", required=True,
                    help="path to prefix-realized-path audit.json (fixed commit 28e8c7dd)")
    ap.add_argument("--evidence-tar", required=True,
                    help="path to evidence.tar.gz (fixed commit 28e8c7dd)")
    args = ap.parse_args()

    # ---- 固定来源只读与哈希核对 ----
    audit_raw = open(args.audit_json, "rb").read()
    h = sha256_bytes(audit_raw)
    print("audit-json sha256:", h)
    assert h == EXPECT_AUDIT[1], "audit.json SHA mismatch vs fixed commit %s" % EXPECT_AUDIT[0]
    tar_raw = open(args.evidence_tar, "rb").read()
    h = sha256_bytes(tar_raw)
    print("evidence-tar sha256:", h)
    assert h == EXPECT_TAR[1], "evidence.tar.gz SHA mismatch vs fixed commit %s" % EXPECT_TAR[0]

    audit = json.loads(audit_raw)
    assert audit["source_archive_sha256"] == EXPECT_TAR[1]
    assert audit["official_result_sha256"] == EXPECT_RESULT_GZ
    assert audit["official_makespan"] == MAKESPAN
    assert audit["without_memory_lower_bound"] == EXCL_BOUND
    assert audit["rounded_sharing_model_lower_bound"] == SHARED_BOUND

    with tarfile.open(args.evidence_tar, "r:gz") as tf:
        m = tf.getmember("probe/official-p3.json.gz")
        assert m.isfile()
        rr = tf.extractfile(m).read()
    assert sha256_bytes(rr) == EXPECT_RESULT_GZ, "official-p3.json.gz member SHA mismatch"
    result = json.loads(gzip.decompress(rr))
    assert result["makespan"] == MAKESPAN and result["num_cores"] == 5

    # ---- per_core_timeline 节点表 ----
    byid = {}
    for c in result["per_core_timeline"]:
        for o in c["ops"]:
            byid.setdefault(o["op_id"], []).append((c["core_id"], o))
    assert len(byid) == audit["op_count"] == 1678

    # ---- prefix_ops.csv：四条冷读前缀全部操作（真实 start/end，全 cold）----
    prefix_rows = []
    for k in ("1", "2", "3", "4"):
        p = audit["cold_prefixes"][k]
        rows = sorted(((cid, o) for i in p["ops"] for cid, o in byid[i]), key=lambda t: t[1]["start"])
        assert len(rows) == len(p["ops"])
        assert len({cid for cid, _ in rows}) == 1, "prefix ops span multiple cores"
        for cid, o in rows:
            assert o["cache_hit"] is False and o["op"] == "COPY_IN" and o["pipe"] == "PIPE_MTE2"
            assert o["end"] == p["official_finish"] or o["end"] < p["official_finish"]
            prefix_rows.append({"prefix_id": "prefix" + k, "core": cid + 1,
                                "source_core_id": cid, "op_id": o["op_id"], "op": o["op"],
                                "pipe": o["pipe"], "start": o["start"], "end": o["end"],
                                "duration": o["duration"], "cache_hit": o["cache_hit"]})
    # 官方完成事件核对：每条前缀 max(end) == official_finish
    for k in ("1", "2", "3", "4"):
        p = audit["cold_prefixes"][k]
        mx = max(r["end"] for r in prefix_rows if r["prefix_id"] == "prefix" + k)
        assert mx == p["official_finish"], (k, mx, p["official_finish"])
    print("prefix_ops rows:", len(prefix_rows),
          "| per-prefix max(end) == official_finish OK")

    # ---- critical_path_ops.csv：已核关键路径 366 操作（含最小时长/入边等待）----
    cp_rows = []
    for seq, o in enumerate(audit["critical_path"], start=1):
        n = byid[o["op_id"]][0][1]
        assert n["start"] == o["start"] and n["end"] == o["end"], o["op_id"]
        cp_rows.append({"seq": seq, "core": o["core"] + 1, "source_core_id": o["core"],
                        "op_id": o["op_id"], "op": o["op"], "pipe": o["pipe"],
                        "start": o["start"], "end": o["end"], "duration": o["duration"],
                        "minimum_duration": o["minimum_duration"],
                        "incoming_lag": o.get("incoming_lag", 0),
                        "cache_hit": n.get("cache_hit", "")})
    assert len(cp_rows) == audit["critical_path_node_count"] == 366
    assert max(r["end"] for r in cp_rows) == MAKESPAN
    contrib = audit["realized_path_contributions"]
    s = (contrib["COPY_IN"] + contrib["COPY_OUT"] + contrib["CONV"] + contrib["RELU"]
         + contrib["ADD"])
    assert s + contrib["cross_lag"] == MAKESPAN, (s, contrib["cross_lag"])
    assert contrib["duration_excess_above_minimum"] == MAKESPAN - EXCL_BOUND == 8244
    print("critical_path_ops rows:", len(cp_rows),
          "| contributions sum + cross_lag == makespan OK; excess == 38024-29780 == 8244 OK")

    # ---- evidence_points.csv：三类证据点（15 行）----
    ev_rows = []
    for k in ("1", "2", "3", "4"):
        p = audit["cold_prefixes"][k]
        ev_rows.append({"object": "prefix" + k, "evidence_type": "exclusive_optimistic",
                        "cycles": p["work"],
                        "source_field": "cold_prefixes.%s.work" % k})
        ev_rows.append({"object": "prefix" + k, "evidence_type": "conditional_shared_bound",
                        "cycles": p["finish_lower_bound"],
                        "source_field": "cold_prefixes.%s.finish_lower_bound" % k})
        ev_rows.append({"object": "prefix" + k, "evidence_type": "official_measured",
                        "cycles": p["official_finish"],
                        "source_field": "cold_prefixes.%s.official_finish" % k})
    ev_rows.append({"object": "overall", "evidence_type": "exclusive_optimistic",
                    "cycles": EXCL_BOUND, "source_field": "without_memory_lower_bound"})
    ev_rows.append({"object": "overall", "evidence_type": "conditional_shared_bound",
                    "cycles": SHARED_BOUND, "source_field": "rounded_sharing_model_lower_bound"})
    ev_rows.append({"object": "overall", "evidence_type": "official_measured",
                    "cycles": MAKESPAN, "source_field": "official_makespan"})
    assert len(ev_rows) == 15
    print("evidence_points rows:", len(ev_rows))

    # ---- path_contributions.csv：关键路径分项贡献 ----
    pc_rows = [
        {"component": "COPY_IN", "cycles": contrib["COPY_IN"]},
        {"component": "COPY_OUT", "cycles": contrib["COPY_OUT"]},
        {"component": "CONV", "cycles": contrib["CONV"]},
        {"component": "RELU", "cycles": contrib["RELU"]},
        {"component": "ADD", "cycles": contrib["ADD"]},
        {"component": "cross_lag", "cycles": contrib["cross_lag"]},
        {"component": "duration_excess_above_minimum", "cycles": contrib["duration_excess_above_minimum"]},
    ]

    def write_csv(name, rows, header):
        with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    write_csv("prefix_ops.csv", prefix_rows,
              ["prefix_id", "core", "source_core_id", "op_id", "op", "pipe",
               "start", "end", "duration", "cache_hit"])
    write_csv("critical_path_ops.csv", cp_rows,
              ["seq", "core", "source_core_id", "op_id", "op", "pipe",
               "start", "end", "duration", "minimum_duration", "incoming_lag", "cache_hit"])
    write_csv("evidence_points.csv", ev_rows,
              ["object", "evidence_type", "cycles", "source_field"])
    write_csv("path_contributions.csv", pc_rows, ["component", "cycles"])
    print("4 CSV written to", HERE)


if __name__ == "__main__":
    sys.exit(main())
