"""Recalculate the frozen P2 reference inventory; never run a solver/evaluator.

Default execution is offline. --fetch-missing restores only the small fixed
source files already named and hashed in this inventory's manifests.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results/a/q2-yuanzhifang/feedback-20260924/goal-baseline"
BASE = ROOT / "results/benchmark-board/official-singlecore-20260924"
TARGETS = {2: 2.26, 3: 3.18, 4: 3.96, 5: 4.53}
FEEDS = {"captain-k1": "board-feed-full100.json", "captain-k2-k5": "board-feed-full400.json",
         "captain-feedback6": "board-feed.json", "captain-pruning6": "board-feed.json"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def save(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    path.write_bytes(raw)


def csv_save(path, rows):
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(text.getvalue(), encoding="utf-8", newline="")


def stats(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return {"n": 0, "mean": None, "median": None, "p95": None, "max": None, "sum": None}
    index = (len(values) - 1) * .95
    lower, upper = math.floor(index), math.ceil(index)
    return {"n": len(values), "mean": statistics.mean(values), "median": statistics.median(values),
            "p95": values[lower] + (values[upper] - values[lower]) * (index - lower),
            "max": max(values), "sum": sum(values)}


def check_sources(fetch_missing):
    entries = []
    for path in sorted(OUT.glob("*source-manifest.json")):
        entries.extend(read(path)["retrieved_files"])
    for item in entries:
        target = ROOT / item["stored_path"]
        if not target.exists() and fetch_missing:
            try:
                raw = subprocess.check_output(["git", "show", item["commit"] + ":" + item["path"]], cwd=ROOT, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                raw = subprocess.check_output(["gh", "api", "-H", "Accept: application/vnd.github.raw+json",
                      "repos/huaweibei123/huaweicup2026/contents/" + item["path"] + "?ref=" + item["commit"]], cwd=ROOT)
            if sha(raw) != item["sha256"]:
                raise ValueError("restored source hash mismatch: " + item["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        raw = target.read_bytes()
        if len(raw) != item["bytes"] or sha(raw) != item["sha256"]:
            raise ValueError("cached source differs from its fixed snapshot: " + item["stored_path"])
    return entries


def baseline_inventory():
    frozen = read(ROOT / "docs/a/source-manifest.json")
    files = {r["path"]: r["sha256"] for r in frozen["files"]}
    rows = {}
    for case in (f"{i:03d}" for i in range(1, 101)):
        run = read(BASE / case / "run.json")
        item = run["artifacts"]["result.json"]
        raw = (ROOT / item["path"]).read_bytes()
        plain = gzip.decompress(raw)
        result = json.loads(plain)
        assert sha(raw) == item["sha256"] and sha(plain) == item["raw_sha256"]
        assert run["graph_sha256"] == files[f"data/case_{case}.json"]
        assert run["config_sha256"] == files["data/config.txt"]
        assert run["official_code_hash"] == frozen["official_code_hash"]
        assert run["status"] == "ok" and run["entrypoint"] == "singlecore_evaluate.evaluate_singlecore"
        assert result["scene"] == "A" and result["num_cores"] == 1
        assert result["makespan"] == run["makespan_cycles"] > 0
        rows[case] = {"case_id": case, "cycles": result["makespan"], "graph_sha256": run["graph_sha256"],
                      "config_sha256": run["config_sha256"], "official_sha256": run["official_code_hash"],
                      "artifact_path": item["path"], "stored_sha256": item["sha256"], "raw_sha256": item["raw_sha256"]}
    return rows


def checked_feed(path, baselines):
    from src.benchmark_board.protocol import validate_feed
    feed = read(path)
    validate_feed(feed, submission=True)
    keys = set()
    for row in feed["records"]:
        key = (row["case_id"], row["cores"])
        assert key not in keys
        keys.add(key)
        assert row["problem"] == "P2" and row["evaluator"]["route"] == "E0"
        base = baselines[row["case_id"]]
        for field in ("graph_sha256", "config_sha256", "official_sha256"):
            assert row["identity"][field] == base[field]
            assert row["baseline"][field] == base[field]
        assert row["baseline"]["result"]["sha256"] == base["stored_sha256"]
        assert row["baseline"]["entrypoint"] == "singlecore_evaluate.evaluate_singlecore"
    return feed["records"]


def aggregate(rows, baselines):
    good = [r for r in rows if r["status"] == "ok"]
    output = {"records": len(rows), "successful": len(good), "status_counts": dict(Counter(r["status"] for r in rows)),
              "cases": sorted(r["case_id"] for r in rows),
              "arithmetic_mean_speedup": statistics.mean(baselines[r["case_id"]]["cycles"] / r["metrics"]["makespan_cycles"] for r in good) if good else None,
              "solver_wall_seconds": stats([r["metrics"].get("solver_wall_seconds") for r in good]),
              "external_evaluation_wall_seconds": stats([r["metrics"].get("evaluation_wall_seconds") for r in good]),
              "scheduled_copy_bytes": stats([r["metrics"].get("ddr_bytes") for r in good]),
              "extra_ddr_bytes": stats([r["metrics"].get("extra_ddr_bytes") for r in good]),
              "spill_bytes": stats([r["metrics"].get("spill_bytes") for r in good]),
              "algorithms": sorted({r["algorithm_id"] for r in rows}), "variants": sorted({r["variant"] for r in rows}),
              "solver_commits": sorted({r["solver_commit"] for r in rows}),
              "environment_workers": sorted({r["provenance"]["environment"]["workers"] for r in rows}),
              "cpus": sorted({r["provenance"]["environment"]["cpu"] for r in rows}),
              "calls": {key: sum(r["provenance"]["measurement"]["calls"][key] for r in rows) for key in ("solver", "E0", "E1", "E2")}}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-missing", action="store_true")
    args = parser.parse_args()
    sources = check_sources(args.fetch_missing)
    baselines = baseline_inventory()
    feeds = {name: checked_feed(OUT / "sources" / name / filename, baselines) for name, filename in FEEDS.items()}
    full = feeds["captain-k1"] + feeds["captain-k2-k5"]
    assert {(r["case_id"], r["cores"]) for r in full} == {(f"{i:03d}", k) for i in range(1, 101) for k in range(1, 6)}
    aggregates = {}; core_rows = []
    for k in range(1, 6):
        rows = [r for r in full if r["cores"] == k]
        a = aggregate(rows, baselines); aggregates[str(k)] = a
        core_rows.append({"cores": k, "n": a["successful"], "mean_B_over_M": a["arithmetic_mean_speedup"],
                          "image_reference_unverified": TARGETS.get(k),
                          "reference_minus_mean": TARGETS[k] - a["arithmetic_mean_speedup"] if k in TARGETS else None,
                          "solver_mean_seconds": a["solver_wall_seconds"]["mean"], "solver_p95_seconds": a["solver_wall_seconds"]["p95"],
                          "solver_max_seconds": a["solver_wall_seconds"]["max"], "E0_mean_seconds": a["external_evaluation_wall_seconds"]["mean"],
                          "mean_scheduled_copy_bytes": a["scheduled_copy_bytes"]["mean"], "mean_extra_ddr_bytes": a["extra_ddr_bytes"]["mean"],
                          "mean_spill_bytes": a["spill_bytes"]["mean"]})
    strong = {name: aggregate(feeds[name], baselines) for name in ("captain-feedback6", "captain-pruning6")}
    for name, report in strong.items():
        cases = set(report["cases"])
        report["contiguous_mean_on_same_six_cases"] = aggregate([r for r in full if r["cores"] == 4 and r["case_id"] in cases], baselines)["arithmetic_mean_speedup"]
    first = {r["case_id"]: r for r in feeds["captain-feedback6"]}
    assert all(r["identity"]["plan_sha256"] == first[r["case_id"]]["identity"]["plan_sha256"] and r["metrics"]["makespan_cycles"] == first[r["case_id"]]["metrics"]["makespan_cycles"] for r in feeds["captain-pruning6"])
    structure = {r["case_id"]: r for r in read(OUT.parent / "structure-scan.json")["rows"]}
    best = {(r["case_id"], r["cores"]): (r["metrics"]["makespan_cycles"], "contiguous-full500") for r in full}
    for name in ("captain-feedback6", "captain-pruning6"):
        for r in feeds[name]:
            key = (r["case_id"], r["cores"])
            if r["status"] == "ok" and r["metrics"]["makespan_cycles"] < best[key][0]:
                best[key] = (r["metrics"]["makespan_cycles"], name)
    for number in (1, 2):
        rows = read(OUT.parent / f"round{number}/summary.json")["rows"]
        for r in rows:
            key = (r["case_id"], r["cores"])
            if r["status"] == "ok" and r["makespan_cycles"] < best[key][0]:
                best[key] = (r["makespan_cycles"], f"fang-round{number}-" + r["variant"])
    for case, r in read(OUT / "sources/captain-joint2/summary.json")["winners"].items():
        key = (case, 4)
        if r["cycles"] < best[key][0]: best[key] = (r["cycles"], "captain-joint2-reported")
    rankings = []
    for r in full:
        case, k = r["case_id"], r["cores"]
        s = structure[case]
        assert s["sha256"] == baselines[case]["graph_sha256"]
        ratio = baselines[case]["cycles"] / r["metrics"]["makespan_cycles"]
        known, source = best[(case, k)]
        rankings.append({"case_id": case, "cores": k, "full_contiguous_cycles": r["metrics"]["makespan_cycles"],
                         "singlecore_cycles": baselines[case]["cycles"], "speedup_B_over_M": ratio, "speedup_over_k": ratio / k,
                         "known_reported_envelope_cycles": known, "envelope_source": source,
                         "contiguous_over_known_envelope": r["metrics"]["makespan_cycles"] / known,
                         "extra_ddr_bytes": r["metrics"].get("extra_ddr_bytes"), "spill_bytes": r["metrics"].get("spill_bytes"),
                         "eligible_ops": s["ops"], "weak_components": s["components"], "max_component_ops": s["max_component_ops"],
                         "largest_component_fraction": s["max_component_ops"] / s["ops"],
                         "homogeneous_word_guard": s["word_descriptor"] is not None,
                         "structure_class": "single-component" if s["components"] == 1 else ("dominant-component" if s["max_component_ops"] / s["ops"] >= .8 else "multiple-components")})
    rankings.sort(key=lambda r: (r["cores"], r["speedup_B_over_M"], r["case_id"]))
    worst = {str(k): [r for r in rankings if r["cores"] == k][:20] for k in range(2, 6)}
    earlier = read(OUT / "sources/captain-target-audit/audit-summary.json")
    for row in earlier["by_core"]:
        assert abs(row["fang_fixed_contiguous"]["mean_individual_baseline_speedup"] - aggregates[str(row["cores"])]["arithmetic_mean_speedup"]) < 1e-12
    report = {"scope": "zero new scoring; independent arithmetic from frozen author feeds, with 100 local official singlecore result bytes verified; remote multicore plan/result/run bytes not downloaded or independently re-evaluated",
              "source_files": len(sources), "source_bytes": sum(s["bytes"] for s in sources), "baseline_verified": len(baselines),
              "full500_owner": "yuanzhifang30-sudo algorithm 0b58c123, run by NikolaStarx local production; cumulative-work contiguous partition, NOT fixed64",
              "full500_per_core": aggregates, "small_sample_portfolios_separate": strong,
              "same_six_pruned_final_plans_and_cycles": True, "source_discovery": read(OUT / "discovery.json"),
              "captain_earlier_central_audit": {
                  "captured_at": earlier["captured_at"], "reported_central_records": earlier["central_records_after"],
                  "reported_p2_latest_eligible_attempts": earlier["p2_latest_eligible_attempts"],
                  "reported_historical_best_mean_by_core": {str(r["cores"]): r["history_best_combination"]["mean_individual_baseline_speedup"] for r in earlier["by_core"]},
                  "full_contiguous_means_match_this_independent_recalculation": True,
                  "scope": "fixed author's earlier snapshot only; captured central record pages/original multicore bytes not downloaded here; not current central state"},
              "image_targets": {str(k): v for k,v in TARGETS.items()},
              "image_target_scope": "user image numeric reference only; denominator, method, coverage and aggregation not verified",
              "known_envelope_scope": "selected downloaded sources plus own R1/R2 and historical two-case report, not complete central board and not a runnable portfolio; do not combine its timings",
              "known_envelope_mean_by_core": {str(k): statistics.mean(r["singlecore_cycles"] / r["known_reported_envelope_cycles"] for r in rankings if r["cores"] == k) for k in range(1, 6)},
              "worst20_per_core": worst,
              "structure_counts": dict(Counter(r["structure_class"] for r in rankings if r["cores"] == 4)),
              "structure_sets": {label: sorted(r["case_id"] for r in rankings if r["cores"] == 4 and r["structure_class"] == label) for label in ("single-component", "dominant-component", "multiple-components")},
              "homogeneous_word_guard_cases": sorted(case for case,s in structure.items() if s["word_descriptor"] is not None),
              "largest_spill_k4": sorted([r for r in rankings if r["cores"] == 4], key=lambda r: -(r["spill_bytes"] or 0))[:12],
              "no_speedup_case_count_by_core": {str(k): sum(r["speedup_B_over_M"] <= 1 for r in rankings if r["cores"] == k) for k in range(2,6)},
              "new_solver_calls": 0, "new_E0_calls": 0, "new_E1_calls": 0, "new_E2_calls": 0}
    save(OUT / "inventory.json", report)
    save(OUT / "verified-singlecore.json", {"scope": "existing original compressed bytes and raw hashes checked; no rerun", "rows": list(baselines.values())})
    csv_save(OUT / "per-core.csv", core_rows)
    csv_save(OUT / "graph-priorities.csv", rankings)
    print(json.dumps({"baseline_verified": len(baselines), "source_files": len(sources), "per_core": core_rows,
                      "strong6": {name: {"n": r["successful"], "mean_speedup": r["arithmetic_mean_speedup"], "calls":r["calls"]} for name,r in strong.items()},
                      "worst_k4": [r["case_id"] for r in worst["4"][:12]], "new_E0":0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
