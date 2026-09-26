"""Attach audited official same-plan no-L2 pairs as revision 2; no evaluation."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FEED = ROOT / "results/a/q3-nikolastarx/witness-full500-20260925-s59/20260924T2032Z-s59ee/board-feed-500-with-baselines.json"
SOURCE_SHA = "9ee5c4be495943e80f477abf08c0577964fb3d6791531c1f59e20b7f92b498d4"
AREA = ROOT / "results/a/q3-nikolastarx/witness-cachepair-20260925-s59"
MANIFEST_SHA = "746bacdc929aa859dbce8bec87e97c4d9955a144d53336ef5d91bc194b8cd527"
CONTROL_COMMIT = "3cee7baa029e98c706521a90a791447068a91f1c"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def ref(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path.read_bytes())}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("batch", type=Path)
    args = p.parse_args()
    batch = args.batch.resolve()
    if not batch.is_relative_to(AREA) or batch == AREA:
        p.error("batch outside fixed result area")
    manifest_raw = (batch / "manifest.json").read_bytes()
    if sha(manifest_raw) != MANIFEST_SHA:
        raise RuntimeError("fixed pair manifest hash differs")
    manifest = json.loads(manifest_raw)
    dispatch = json.loads((batch / "dispatch.json").read_bytes())
    if dispatch["status"] != "complete" or dispatch["attempted_e0_reservations"] != 500 \
            or dispatch["successful_e0_calls"] != 500 or dispatch["solver_calls"] != 0 \
            or dispatch["p3_e0_calls"] != 0 or len(dispatch["records"]) != 500:
        raise RuntimeError("pair batch incomplete or call ledger differs")
    raw = SOURCE_FEED.read_bytes()
    if sha(raw) != SOURCE_SHA:
        raise RuntimeError("original P3 submission changed")
    source = json.loads(raw)
    jobs = {(j["case_id"], j["cores"]): j for j in manifest["jobs"]}
    if len(jobs) != 500 or len(source["records"]) != 500:
        raise RuntimeError("incomplete source/manifest")
    all_rows = []
    summaries = {k: {"ratios": [], "walls": [], "negative": []} for k in range(1, 6)}
    for old in source["records"]:
        case, cores = old["case_id"], old["cores"]
        key = f"{case}-k{cores}"
        job = jobs[(case, cores)]
        run_path = batch / "cells" / key / "run.json"
        run = json.loads(run_path.read_bytes())
        if run != dispatch["records"][key] or run["status"] != "ok" or run["p2_e0_confirmed"] != 1 \
                or run["retry"] != 0 or job["attempt_id"] != old["attempt_id"] or old["revision"] != 1:
            raise RuntimeError("pair run/source row identity changed: " + key)
        if job["plan"] != old["artifacts"]["plan"] or job["cache_result"] != old["artifacts"]["result"] \
                or job["cache_makespan"] != old["metrics"]["makespan_cycles"] \
                or run["source_plan_sha256"] != old["identity"]["plan_sha256"]:
            raise RuntimeError("pair plan/cache artifact identity changed: " + key)
        identity = old["identity"]
        if any(run[a] != identity[b] for a, b in (("graph_sha256", "graph_sha256"),
                 ("config_sha256", "config_sha256"), ("official_sha256", "official_sha256"))):
            raise RuntimeError("pair frozen graph/config/code identity changed: " + key)
        result_path = batch / "cells" / key / "result.json.gz"
        compressed = result_path.read_bytes()
        result = json.loads(gzip.decompress(compressed))
        if sha(compressed) != run["result_sha256"] or result.get("scene") != "B" \
                or result.get("num_cores") != cores or result.get("makespan") != run["no_l2_makespan"] \
                or result.get("data_movement_bytes") != run["data_movement_bytes"]:
            raise RuntimeError("pair full official P2 result differs: " + key)
        row = json.loads(json.dumps(old))
        row["revision"] = 2
        row["cache_pair"] = {
            "graph_sha256": identity["graph_sha256"],
            "config_sha256": identity["config_sha256"],
            "official_sha256": identity["official_sha256"],
            "plan_sha256": identity["plan_sha256"],
            "cores": cores,
            "route": "E0",
            "result": ref(result_path),
        }
        if "log" in row["artifacts"]:
            raise RuntimeError("cannot overwrite an original log artifact")
        row["artifacts"]["log"] = ref(run_path)
        row["notes"].append(
            "Revision 2 adds exactly one separate unmodified official P2 no-L2 E0 evaluation "
            "of this unchanged P3 winning plan at the same graph/config/core count. "
            f"Pair runner/manifest fixed by {CONTROL_COMMIT}; per-cell external timing and call receipt are artifacts.log. "
            "Original P3 solver wall, online P3 E0 count, plan, result, and baseline are unchanged."
        )
        row["provenance"]["measurement"]["evaluation_scope"] = (
            "Original P3 final result reuses integrated official P3 E0 and has no separately timed final P3 evaluation. "
            "Revision 2 adds one independent same-plan official P2 no-L2 E0; its time is in artifacts.log, "
            "excluded from the unchanged original solver_wall_seconds and P3 E0 calls."
        )
        all_rows.append(row)
        stats = summaries[cores]
        ratio = result["makespan"] / old["metrics"]["makespan_cycles"]
        stats["ratios"].append(ratio)
        stats["walls"].append(run["wall_seconds"])
        if ratio < 1:
            stats["negative"].append({"case_id": case, "ratio": ratio,
                                      "no_l2_cycles": result["makespan"],
                                      "cache_cycles": old["metrics"]["makespan_cycles"]})
    payload = {"schema_version": 1, "submission_version": 1, "records": all_rows}
    feed_path = batch / "board-feed-500-revision2.json"
    with feed_path.open("x") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    report = {"schema": "q3-cachepair-audit-v1", "source_feed_sha256": SOURCE_SHA,
              "manifest_sha256": MANIFEST_SHA, "control_commit": CONTROL_COMMIT,
              "pair_dispatch_sha256": sha((batch / "dispatch.json").read_bytes()),
              "feed_revision2_sha256": sha(feed_path.read_bytes()),
              "calls": {"solver": 0, "P3_E0": 0, "P2_E0": 500, "retry": 0},
              "batch_elapsed_wall_seconds": dispatch["elapsed_wall_seconds"], "by_core": {}}
    for core, stats in summaries.items():
        if len(stats["ratios"]) != 100:
            raise RuntimeError("per-core pair coverage incomplete")
        report["by_core"][str(core)] = {
            "mean_same_plan_cache_gain": statistics.mean(stats["ratios"]),
            "min_cache_gain": min(stats["ratios"]),
            "max_cache_gain": max(stats["ratios"]),
            "negative_cases": stats["negative"],
            "mean_external_p2_e0_wall_seconds": statistics.mean(stats["walls"]),
            "max_external_p2_e0_wall_seconds": max(stats["walls"]),
        }
    report_path = batch / "audit-summary.json"
    with report_path.open("x") as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"feed": feed_path.relative_to(ROOT).as_posix(), "sha256": report["feed_revision2_sha256"],
                      "records": len(all_rows), "means": {k: v["mean_same_plan_cache_gain"] for k, v in report["by_core"].items()},
                      "negative": sum(len(v["negative_cases"]) for v in report["by_core"].values())}))


if __name__ == "__main__":
    main()
