"""Audit fixed static bounds and compute bounds on the 100-case mean.

No construction, simulation, parameter selection, or performance measurement.
The ceilings are necessary bounds, not achievable scores or optimality proofs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BOUND_PATH = "results/a/q1-lower-bounds-20260924/static_bounds.json"
SINGLE_ROOT = "results/benchmark-board/official-singlecore-20260924"
TARGETS = {2: Fraction(187, 100), 3: Fraction(257, 100),
           4: Fraction(314, 100), 5: Fraction(357, 100)}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def objects(specs):
    """One Git process, preserving exact bytes including gzip and line endings."""
    output = subprocess.check_output(["git", "cat-file", "--batch"], cwd=ROOT,
                                     input=("\n".join(specs) + "\n").encode())
    pos, result = 0, {}
    for spec in specs:
        end = output.index(b"\n", pos)
        header = output[pos:end].split()
        if len(header) != 3 or header[1] != b"blob":
            raise ValueError(f"Expected fixed Git blob: {spec}")
        length = int(header[2]); pos = end + 1
        result[spec] = output[pos:pos + length]
        pos += length
        assert output[pos:pos + 1] == b"\n"
        pos += 1
    assert pos == len(output)
    return result


def build(bound_commit, baseline_commit):
    specs = [f"{bound_commit}:{BOUND_PATH}", f"{bound_commit}:src/q1/lower_bounds.py",
             f"{baseline_commit}:docs/a/source-manifest.json", f"{baseline_commit}:uv.lock",
             f"{baseline_commit}:{SINGLE_ROOT}/manifest.json"]
    specs += [f"{baseline_commit}:{SINGLE_ROOT}/{c:03}/{name}"
              for c in range(1, 101) for name in ("run.json", "result.json.gz")]
    blobs = objects(specs)
    raw_report = blobs[specs[0]]
    bound_report = json.loads(raw_report)
    source_manifest = json.loads(blobs[specs[2]])
    official = {f["path"]: f["sha256"] for f in source_manifest["files"]}
    identity = bound_report["code_identity"]
    assert identity["implementation_sha256"] == sha(blobs[specs[1]])
    assert identity["uv_lock_sha256"] == sha(blobs[specs[3]])
    assert identity["config_sha256"] == official["data/config.txt"]
    for name, digest in identity["official_source_sha256"].items():
        assert digest == official["code/" + name]
    assert bound_report["case_count"] == 100
    assert bound_report["core_counts"] == [1, 2, 3, 4, 5]
    assert all(v == 0 for v in bound_report["calls"].values())
    rows, seen = [], set()
    ratios = {k: [] for k in range(1, 6)}
    for case in bound_report["cases"]:
        case_id = Path(case["input_member"]).stem[-3:]
        assert case_id not in seen
        seen.add(case_id)
        graph_path = "data/" + f"case_{case_id}.json"
        graph_sha = case["input_sha256"]
        assert graph_sha == official[graph_path]
        actual_graph = ROOT / "data/raw/a/official" / graph_path
        assert sha(actual_graph.read_bytes()) == graph_sha
        run_spec = f"{baseline_commit}:{SINGLE_ROOT}/{case_id}/run.json"
        result_spec = f"{baseline_commit}:{SINGLE_ROOT}/{case_id}/result.json.gz"
        run = json.loads(blobs[run_spec])
        assert run["status"] == "ok" and run["returncode"] == 0
        assert run["entrypoint"] == "singlecore_evaluate.evaluate_singlecore"
        assert run["graph_sha256"] == graph_sha
        assert run["config_sha256"] == identity["config_sha256"]
        assert run["official_code_hash"] == source_manifest["official_code_hash"]
        packed = blobs[result_spec]
        raw = gzip.decompress(packed)
        artifact = run["artifacts"]["result.json"]
        assert sha(packed) == artifact["sha256"] and sha(raw) == artifact["raw_sha256"]
        baseline = json.loads(raw)["makespan"]
        assert type(baseline) is int and baseline > 0 and baseline == run["makespan_cycles"]
        assert sorted(b["cores"] for b in case["bounds"]) == [1, 2, 3, 4, 5]
        for bound in case["bounds"]:
            k, lower = bound["cores"], bound["lower_bound_cycles"]
            assert type(lower) is int and 0 < lower <= baseline
            assert bound["proof_scope"]["copy_bridge_contraction"] is False
            ratio = Fraction(baseline, lower)
            ratios[k].append(ratio)
            rows.append({"case_id": case_id, "cores": k, "graph_sha256": graph_sha,
                         "official_singlecore_cycles": baseline,
                         "universal_lower_bound_cycles": lower,
                         "speedup_upper_bound": float(ratio),
                         "denominator_result_gzip_sha256": sha(packed),
                         "denominator_result_raw_sha256": sha(raw)})
    assert seen == {f"{c:03}" for c in range(1, 101)}
    summaries = []
    for k, values in ratios.items():
        mean = sum(values, Fraction()) / 100
        summaries.append({"cores": k, "cases": len(values), "mean_speedup_upper_bound": float(mean),
                          "minimum_case_upper_bound": float(min(values)),
                          "maximum_case_upper_bound": float(max(values)),
                          "screenshot_target": float(TARGETS[k]) if k in TARGETS else None,
                          "target_ruled_out_by_this_bound": mean < TARGETS[k] if k in TARGETS else None})
    return {"kind": "mean_speedup_ceiling_not_achievable_performance", "schema_version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "command": ["python", "src/q1_yuanzhifang/ceiling_report.py", *sys.argv[1:]],
            "analysis_source_sha256": sha(Path(__file__).read_bytes()),
            "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "bound_source": {"commit": bound_commit, "path": BOUND_PATH, "sha256": sha(raw_report),
                             "original_code_identity": identity},
            "denominator_source": {"commit": baseline_commit, "path": SINGLE_ROOT,
                                   "manifest": json.loads(blobs[specs[4]])},
            "checks": {"fixed_git_blobs": len(blobs), "input_graph_hashes": 100,
                       "denominator_raw_and_gzip_hashes": 100, "bound_rows": len(rows),
                       "bounds_recomputed": False,
                       "claim": "For each legal plan M_i >= L_i > 0, B_i/M_i <= B_i/L_i; summing preserves inequality. Assumes the cited universal-bound proof is valid under frozen E0."},
            "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
            "limitations": ["Static bound calculations reused, not independently reproduced in this command.",
                            "No existence/achievability claim; no bound on full solver wall or exact global optimality.",
                            "Screenshot targets have unverified source/config; only numerical comparisons.",
                            "Official singlecore can be inefficient; a ratio upper bound exceeding k is not a violation of the work bound."],
            "summary": summaries, "rows": rows}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bound-commit", required=True)
    p.add_argument("--baseline-commit", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = build(args.bound_commit, args.baseline_commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write("\n")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
