"""Verify existing feed evidence and compute fixed-plan bounds; no scoring."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from construct import ROOT, OFFICIAL
from diagnose import lower_bounds, read_scene_a_config


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(path, expected):
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError(f"SHA256 mismatch: {path}")
    return raw


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("feed", type=Path)
    p.add_argument("--artifact-commit", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    feed_path = args.feed.resolve().relative_to(ROOT).as_posix()
    fixed_feed = subprocess.check_output(["git", "show", f"{args.artifact_commit}:{feed_path}"], cwd=ROOT)
    checked(args.feed, sha(fixed_feed))
    records = json.loads(fixed_feed)["records"]
    config_raw = (OFFICIAL / "data/config.txt").read_bytes()
    waits = read_scene_a_config(str(OFFICIAL / "data/config.txt"))
    official_hashes = {}
    analyzed, omitted = [], []
    for r in records:
        if r["status"] != "ok":
            omitted.append({"attempt_id": r["attempt_id"], "status": r["status"]})
            continue
        if r["problem"] != "P1" or r["evaluator"]["route"] != "E0":
            raise ValueError("Only existing P1 E0 results are supported")
        if sha(config_raw) != r["identity"]["config_sha256"]:
            raise ValueError("Config identity mismatch")
        protocol_ref = r["artifacts"]["manifest"]
        protocol = json.loads(checked(ROOT / protocol_ref["path"], protocol_ref["sha256"]))
        for name, digest in protocol["official_source_sha256"].items():
            if name not in official_hashes:
                checked(OFFICIAL / name, digest)
                official_hashes[name] = digest
            elif official_hashes[name] != digest:
                raise ValueError("Mixed official source identities")
        graph_path = OFFICIAL / f"data/case_{r['case_id']}.json"
        graph = json.loads(checked(graph_path, r["identity"]["graph_sha256"]))
        plan_ref, result_ref = r["artifacts"]["plan"], r["artifacts"]["result"]
        plan = json.loads(checked(ROOT / plan_ref["path"], plan_ref["sha256"]))
        raw = checked(ROOT / result_ref["path"], result_ref["sha256"])
        result = json.loads(gzip.decompress(raw) if result_ref["path"].endswith(".gz") else raw)
        if result["makespan"] != r["metrics"]["makespan_cycles"] or result["num_cores"] != r["cores"]:
            raise ValueError("Official result/feed mismatch")
        bounds = lower_bounds(graph, plan, waits)
        if bounds["task_gate_lower_bound_cycles"] > result["makespan"]:
            raise ValueError(f"Bound exceeds E0 for {r['attempt_id']}")
        analyzed.append({"attempt_id": r["attempt_id"], "case_id": r["case_id"],
                         "variant": r["variant"], "solver_commit": r["solver_commit"],
                         "identity": r["identity"], "metrics": r["metrics"],
                         "artifacts": {"plan": plan_ref, "result": result_ref}, **bounds})
    report = {"kind": "fixed_plan_lower_bounds_not_new_performance", "schema_version": 1,
              "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "artifact_commit": args.artifact_commit, "feed_path": feed_path,
              "feed_sha256": sha(fixed_feed),
              "analysis_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "analysis_source_sha256": {f"src/q1_yuanzhifang/{name}": sha((Path(__file__).parent / name).read_bytes())
                                          for name in ("analyze_feed.py", "diagnose.py", "construct.py")},
              "official_source_sha256": official_hashes, "config_sha256": sha(config_raw),
              "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
              "rows": analyzed, "omitted_non_success_rows": omitted,
              "scope": "Fixed-plan bound; does not certify global optimality or removable waiting. "
                       "No COPY-bridge contraction within rebuilt Tasks. Evidence hashes checked; no E0 rerun."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(report, out, indent=2, ensure_ascii=False)
        out.write("\n")
    print(json.dumps({"analyzed": len(analyzed), "omitted": len(omitted), "calls": report["calls"]}))


if __name__ == "__main__":
    main()
