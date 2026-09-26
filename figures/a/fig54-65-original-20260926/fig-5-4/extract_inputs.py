# -*- coding: utf-8 -*-
"""fig-5-4 输入提取脚本（独立于绘图；plot.py 只读本脚本产出的交付 CSV）。

从两项固定来源只读取件并核对 SHA-256，生成交付表：
- --r05-zip    S15 单例配对：results/a/q2-nikolastarx/pro-r05-official-pair-20260925/result.zip
               固定提交 e6ae3699870c78b11c8c47b0fa9001249a428e1c，
               SHA-256 c90065d9d90aae3be4144080483e3ac394a6ef150f92fc7d4450d81114ba2c66
- --s16-report S16 全量对照：results/a/q2-nikolastarx/secondary-ddr-full500-20260925/report.json
               固定提交 70f2e8bd8e850f1d49c924a86b654b29c24e087f，
               SHA-256 86347e8aae52ec3e4ee8001f1a9f2471af92f84004f402fe2a4cb55444889adf

用法（工作目录=仓库根）：
  .venv/Scripts/python.exe figures/a/jia-fig5-4-20260926/extract_inputs.py \
      --r05-zip <result.zip 路径> --s16-report <report.json 路径>

产出（写入本目录）：events.csv / markers.csv / results.csv / bytes.csv / tradeoff.csv。
原始 Trace 不复制入图包；哈希不符立即中止，不生成任何表。
"""
import argparse
import csv
import hashlib
import json
import os
import sys
import zipfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))

EXPECT_ZIP = ("e6ae3699870c78b11c8c47b0fa9001249a428e1c",
              "c90065d9d90aae3be4144080483e3ac394a6ef150f92fc7d4450d81114ba2c66")
EXPECT_REPORT = ("70f2e8bd8e850f1d49c924a86b654b29c24e087f",
                 "86347e8aae52ec3e4ee8001f1a9f2471af92f84004f402fe2a4cb55444889adf")

MAKESPAN = {"seed": 248166, "recovered": 254508}
PLAN_SHA = {"seed": "e6c87dd7e78e2b5bfe4e2c55b48583d5cae7c0fdec9198c1ab384c42f30a9c53",
            "recovered": "d6da7474af3fe2bf2e3b83ec01015415bc63b33439647eb2ad40822d93511252"}


def sha256_path(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description="fig-5-4 input extraction with fixed-source hash check")
    ap.add_argument("--r05-zip", required=True, help="path to S15 result.zip (fixed commit e6ae3699)")
    ap.add_argument("--s16-report", required=True, help="path to S16 report.json (fixed commit 70f2e8bd)")
    args = ap.parse_args()

    # ---- 固定来源只读与哈希核对（不符即中止）----
    z_sha = sha256_path(args.r05_zip)
    print("r05-zip sha256:", z_sha)
    assert z_sha == EXPECT_ZIP[1], "result.zip SHA mismatch vs fixed commit %s" % EXPECT_ZIP[0]
    r_sha = sha256_path(args.s16_report)
    print("s16-report sha256:", r_sha)
    assert r_sha == EXPECT_REPORT[1], "report.json SHA mismatch vs fixed commit %s" % EXPECT_REPORT[0]

    z = zipfile.ZipFile(args.r05_zip)
    report = json.loads(open(args.s16_report, encoding="utf-8").read())
    batch = json.loads(z.read("output/batch.json"))

    res, traces = {}, {}
    for r in batch["rows"]:
        label = r["label"]
        res[label] = json.loads(z.read("output/%s/result.json" % label))
        traces[label] = json.loads(z.read("output/%s/trace.json" % label))
        assert res[label]["makespan"] == MAKESPAN[label], (label, res[label]["makespan"])
        assert r["plan_sha256"] == PLAN_SHA[label], (label, r["plan_sha256"])
    print("results OK:", {k: res[k]["makespan"] for k in res})

    # ---- events.csv：全部 X 事件；core 规范化为 1/2（source_core_id 保留原 0/1）----
    events = []
    eid = 0
    for v in ("seed", "recovered"):
        for e in traces[v]["traceEvents"]:
            if e.get("ph") != "X":
                continue
            sc = e["args"].get("core_id")
            assert sc in (0, 1), sc
            start = int(e["args"].get("start", e["ts"]))
            end = int(e["args"].get("end", e["ts"] + e["dur"]))
            events.append({"variant": v, "event_id": eid,
                           "op_id": e["name"].split("#")[-1].strip() if "#" in e["name"] else e["name"],
                           "core": sc + 1, "source_core_id": sc, "pipe": e["cat"],
                           "start": start, "end": end})
            eid += 1
    for r in events:
        assert r["core"] == r["source_core_id"] + 1 and r["core"] in (1, 2)
        assert 0 <= r["start"] <= r["end"]
    for v in ("seed", "recovered"):
        mx = max(r["end"] for r in events if r["variant"] == v)
        assert mx == MAKESPAN[v], (v, mx)
    print("events rows:", len(events), "| cores 1..2, endpoints == makespan OK")

    # ---- markers.csv：三类引用真实 event_id，周期放独立 cycles/endpoint 列 ----
    ev_idx = {(r["variant"], r["event_id"]): r for r in events}
    markers = []
    for v in ("seed", "recovered"):
        sub = [r for r in events if r["variant"] == v]
        # makespan_end：end 最大的事件
        mk_ev = max(sub, key=lambda r: (int(r["end"]), -int(r["event_id"])))
        # last_copy_in_end：PIPE_MTE2 的 end 最大事件
        m2 = [r for r in sub if r["pipe"] == "PIPE_MTE2"]
        m2_ev = max(m2, key=lambda r: (int(r["end"]), -int(r["event_id"])))
        # first_op_start：非 SUBGRAPH 操作中 start 最早；并列取最小 event_id
        ns = [r for r in sub if r["pipe"] != "SUBGRAPH"]
        fo_ev = min(ns, key=lambda r: (int(r["start"]), int(r["event_id"])))
        for kind, ev_, ep in (("makespan_end", mk_ev, "end"),
                              ("last_copy_in_end", m2_ev, "end"),
                              ("first_op_start", fo_ev, "start")):
            markers.append({"variant": v, "kind": kind, "event_id": ev_["event_id"],
                            "endpoint": ep, "cycles": int(ev_[ep])})
    for m in markers:
        ev_ = ev_idx[(m["variant"], m["event_id"])]
        assert int(ev_[m["endpoint"]]) == m["cycles"], m
    assert {m["kind"] for m in markers} == {"makespan_end", "last_copy_in_end", "first_op_start"}
    assert len(markers) == 6
    print("markers:", [(m["variant"], m["kind"], m["event_id"], m["cycles"]) for m in markers])

    # ---- bytes.csv / results.csv（F54-R03：extra_ddr=added_copy_bytes；总量另列）----
    bytes_rows, results_rows = [], []
    for v in ("seed", "recovered"):
        dm = res[v]["data_movement_bytes"]
        base, added, sched = (dm["original_graph_copy_bytes"], dm["added_copy_bytes"],
                              dm["scheduled_copy_bytes"])
        assert dm["spill_added_copy_bytes"] == 0
        assert base + added == sched, (v, base, added, sched)
        bytes_rows.append({"variant": v, "base": base, "extra": added, "total": sched})
        results_rows.append({"variant": v, "case": "003", "cores": 2,
                             "makespan": MAKESPAN[v], "extra_ddr": added,
                             "scheduled_copy_bytes": sched, "plan_hash": PLAN_SHA[v]})
    assert results_rows[0]["extra_ddr"] == 5067158 and results_rows[1]["extra_ddr"] == 3923290
    assert results_rows[0]["scheduled_copy_bytes"] == 6351422 and results_rows[1]["scheduled_copy_bytes"] == 5207554

    # ---- tradeoff.csv（F54-R02：relative_ddr 全精度，不预 round；零分母留空）----
    tradeoff = []
    zero_old = 0
    cat_count = Counter()
    for c in report["cells"]:
        dc = c["new_makespan"] - c["old_makespan"]
        db = c["new_extra"] - c["old_extra"]
        if c["old_extra"] == 0:
            rel = ""
            zero_old += 1
        else:
            rel = db / c["old_extra"]        # 完整精度，float repr 写入
        if c["new_makespan"] < c["old_makespan"] and db < 0:
            cat = "both_down"
        elif c["new_makespan"] < c["old_makespan"] and db == 0:
            cat = "mk_down_ddr_same"
        elif c["new_makespan"] < c["old_makespan"]:
            cat = "mk_down_ddr_up"
        elif c["new_makespan"] == c["old_makespan"] and db == 0:
            cat = "unchanged"
        else:
            cat = "other"
        cat_count[cat] += 1
        tradeoff.append({"case": c["case"], "cores": c["cores"],
                         "old_makespan": c["old_makespan"], "new_makespan": c["new_makespan"],
                         "old_ddr": c["old_extra"], "new_ddr": c["new_extra"],
                         "delta_cycles": dc, "delta_bytes": db, "relative_ddr": rel,
                         "category": cat})
    assert len(tradeoff) == 500
    print("categories:", dict(cat_count), "| old_ddr==0 cells:", zero_old)

    def write_csv(name, rows, header):
        with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    write_csv("events.csv", events,
              ["variant", "event_id", "op_id", "core", "source_core_id", "pipe", "start", "end"])
    write_csv("markers.csv", markers,
              ["variant", "kind", "event_id", "endpoint", "cycles"])
    write_csv("results.csv", results_rows,
              ["variant", "case", "cores", "makespan", "extra_ddr",
               "scheduled_copy_bytes", "plan_hash"])
    write_csv("bytes.csv", bytes_rows, ["variant", "base", "extra", "total"])
    write_csv("tradeoff.csv", tradeoff,
              ["case", "cores", "old_makespan", "new_makespan", "old_ddr", "new_ddr",
               "delta_cycles", "delta_bytes", "relative_ddr", "category"])
    print("5 CSV written to", HERE)


if __name__ == "__main__":
    sys.exit(main())
