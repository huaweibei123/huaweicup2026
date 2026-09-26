"""Rebuild the fixed 33-unit P2 comparison from saved bytes; no solver or E0."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import statistics
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
BASE = ROOT / "results/a/q2-yuanzhifang/feedback-20260924"
OUT = Path(__file__).resolve().parent
NEW_SOURCE = "384b6c2a7ff937ca44180dee09a9d4bcaea0c50d"
OLD_SOURCE = "e64723bdf99669c44f76d8e90ab0379a8578522e"
SPEC_COMMIT = "027d4bf9ccecdc82e2c5ddbce52cea5345e95b8b"
RUNNER = "fa6522a3266fe040379dd064092beb27c0b20a5e"
E0 = "45f647b395b84e9569f418fd33d62c2b8eb4d190"
BATCHES = ("round10a", "round10b", "round11a", "round11b", "round11c")
FIELDS = ("batch", "case_id", "cores", "variant", "route", "new_makespan_cycles",
          "old_tensor_makespan_cycles", "makespan_change_cycles", "makespan_comparison",
          "new_B_over_M", "old_tensor_B_over_M", "new_extra_ddr_bytes",
          "old_tensor_extra_ddr_bytes", "extra_ddr_change_bytes", "new_spill_bytes",
          "old_tensor_spill_bytes", "spill_change_bytes", "new_solver_wall_seconds",
          "old_tensor_solver_wall_seconds", "new_external_E0_wall_seconds",
          "old_tensor_external_E0_wall_seconds", "new_run_path", "old_run_path")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def git_blob(commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def check_artifact(item):
    raw = (ROOT / item["path"]).read_bytes()
    assert sha(raw) == item["sha256"], item["path"]
    return raw


def main():
    old_csv = BASE / "full-coverage/all500/per-cell.csv"
    old_summary_path = BASE / "full-coverage/all500/summary.json"
    old_sources_path = BASE / "full-coverage/all500/frozen-sources.json"
    with old_csv.open(newline="", encoding="utf-8") as f:
        old_rows = list(csv.DictReader(f))
    old_summary = read(old_summary_path)
    old_sources = read(old_sources_path)
    assert len(old_rows) == 500 and old_summary["solver_commit"] == OLD_SOURCE
    assert old_summary["calls"] == {"solver": 501, "E0": 500, "E1": 0, "E2": 0}
    assert all(x["commit"] == OLD_SOURCE and sha(git_blob(OLD_SOURCE, x["path"])) == x["sha256"]
               for x in old_sources["sources"])
    old = {(r["case_id"], int(r["cores"])): r for r in old_rows}
    assert len(old) == 500
    assert set(old) == {(f"{i:03}", k) for i in range(1, 101) for k in range(1, 6)}
    old_run_verified = {}
    for key, row in old.items():
        run = read(ROOT / row["run_path"])
        assert run["status"] == "ok" and run["solver_commit"] == OLD_SOURCE
        assert run["metrics"]["makespan_cycles"] == int(row["makespan_cycles"])
        assert run["metrics"]["data_movement_bytes"]["added_copy_bytes"] == int(row["extra_ddr_bytes"])
        assert run["metrics"]["data_movement_bytes"]["spill_added_copy_bytes"] == int(row["spill_bytes"])
        assert run["stages"]["solver"]["wall_seconds"] == float(row["solver_wall_seconds"])
        assert run["stages"]["E0"]["wall_seconds"] == float(row["E0_wall_seconds"])
        assert run["artifacts"]["result"]["sha256"] == row["result_sha256"]
        assert sha((ROOT / run["artifacts"]["result"]["path"]).read_bytes()) == row["result_sha256"]
        assert int(row["baseline_cycles"]) / int(row["makespan_cycles"]) == float(row["speedup"])
        old_run_verified[key] = run
    batches, rows = [], []
    new_sources = {}
    for batch in BATCHES:
        folder = BASE / batch
        ledger = read(folder / "ledger.json")
        spec = read(folder / "spec.json")
        spec_path = (folder.relative_to(ROOT).as_posix() + "-spec.json")
        spec_raw = (ROOT / spec_path).read_bytes()
        assert spec_raw == git_blob(SPEC_COMMIT, spec_path)
        assert sha(spec_raw) == ledger["spec_sha256"] and spec == json.loads(spec_raw)
        assert spec["solver_commit"] == NEW_SOURCE and spec["runner_commit"] == RUNNER
        assert spec["evaluator_commit"] == E0 and spec["budget"]["workers"] == 1
        assert ledger["state"] == "completed" and len(ledger["attempts"]) == len(spec["cases"])
        n = len(spec["cases"])
        assert ledger["charged_calls"] == {"solver": n, "E0": n, "E1": 0, "E2": 0}
        for path, expected in ledger["source_hashes"].items():
            commit = E0 if path.startswith("data/raw/") else RUNNER if path.endswith("/measure.py") else NEW_SOURCE
            assert sha((ROOT / path).read_bytes()) == expected == sha(git_blob(commit, path))
            new_sources[path] = {"path": path, "commit": commit, "sha256": expected}
        feed_path, = (p for p in folder.glob("board-feed-*.json") if "preflight" not in p.name)
        feed = read(feed_path)
        preflight = read(feed_path.with_name(feed_path.stem + "-preflight.json"))
        assert preflight["returncode"] == 0 and check_artifact(preflight["feed"]) == feed_path.read_bytes()
        assert json.loads(preflight["stdout"])["eligible"] == n
        assert len(feed["records"]) == n
        recs = {r["case_id"]: r for r in feed["records"]}
        assert list(recs) == spec["cases"]
        audit_path = folder / "measurement-audit.json"
        audit = read(audit_path)
        if isinstance(audit["batch"], dict):
            assert audit["batch"]["state"] == "completed"
            assert audit["batch"]["charged_calls"] == ledger["charged_calls"]
            assert audit["feed"]["sha256"] == sha(feed_path.read_bytes())
            assert len(audit["cases"]) == n
        else:
            assert audit["batch"] == folder.relative_to(ROOT).as_posix()
            assert audit["state"] == "completed" and audit["calls"] == ledger["charged_calls"]
            assert audit["feed_sha256"] == sha(feed_path.read_bytes())
            assert audit["cases"] == n
        batches.append({"batch": batch, "variant": spec["methods"][0]["variant"],
                        "cores": spec["cores"], "cases": spec["cases"],
                        "T0": ledger["started_at"], "T1": ledger["finished_at"],
                        "batch_wall_seconds": ledger["batch_wall_seconds"],
                        "charged_calls": ledger["charged_calls"],
                        "spec_path": spec_path, "spec_sha256": sha(spec_raw),
                        "ledger_path": (folder / "ledger.json").relative_to(ROOT).as_posix(),
                        "ledger_sha256": sha((folder / "ledger.json").read_bytes()),
                        "feed_path": feed_path.relative_to(ROOT).as_posix(),
                        "feed_sha256": sha(feed_path.read_bytes()),
                        "preflight_path": feed_path.with_name(feed_path.stem + "-preflight.json").relative_to(ROOT).as_posix(),
                        "preflight_sha256": sha(feed_path.with_name(feed_path.stem + "-preflight.json").read_bytes()),
                        "audit_path": audit_path.relative_to(ROOT).as_posix(),
                        "audit_sha256": sha(audit_path.read_bytes())})
        for p in ledger["attempts"]:
            run_path = ROOT / p
            run = read(run_path)
            key = (run["case_id"], run["cores"])
            prior = old[key]
            prior_run = old_run_verified[key]
            rec = recs[run["case_id"]]
            assert run["status"] == "ok" and run["failure"] is None
            assert run["solver_commit"] == NEW_SOURCE and run["runner_commit"] == RUNNER
            assert run["evaluator_commit"] == E0 and run["cores"] == spec["cores"]
            assert run["method"]["variant"] == spec["methods"][0]["variant"]
            assert run["calls"] == {"solver": 1, "E0": 1, "E1": 0, "E2": 0}
            assert run["identity"] == rec["identity"]
            assert all(run["identity"][q] == prior_run["identity"][q]
                       for q in ("graph_sha256", "config_sha256", "official_sha256"))
            result_item = run["compression"]["result.json"]
            raw = gzip.decompress(check_artifact(result_item["artifact"]))
            assert sha(raw) == result_item["raw_sha256"] and len(raw) == result_item["raw_bytes"]
            result = json.loads(raw)
            metrics = result["data_movement_bytes"]
            assert result["scene"] == "B" and result["num_cores"] == run["cores"]
            assert result["makespan"] == run["metrics"]["makespan_cycles"] == rec["metrics"]["makespan_cycles"]
            assert metrics == run["metrics"]["data_movement_bytes"]
            assert metrics["added_copy_bytes"] == rec["metrics"]["extra_ddr_bytes"]
            assert metrics["spill_added_copy_bytes"] == rec["metrics"]["spill_bytes"]
            report = read(run_path.parent / "solver.stdout.txt")
            assert report == rec["parameters"]["solver_report"] and report["online_E0_calls"] == 0
            baseline = int(prior["baseline_cycles"])
            new_m = result["makespan"]
            old_m = int(prior["makespan_cycles"])
            rows.append({"batch": batch, "case_id": run["case_id"], "cores": run["cores"],
                         "variant": run["method"]["variant"], "route": report["selected"],
                         "new_makespan_cycles": new_m, "old_tensor_makespan_cycles": old_m,
                         "makespan_change_cycles": new_m - old_m,
                         "makespan_comparison": "better" if new_m < old_m else "equal" if new_m == old_m else "worse",
                         "new_B_over_M": baseline/new_m, "old_tensor_B_over_M": baseline/old_m,
                         "new_extra_ddr_bytes": metrics["added_copy_bytes"],
                         "old_tensor_extra_ddr_bytes": int(prior["extra_ddr_bytes"]),
                         "extra_ddr_change_bytes": metrics["added_copy_bytes"]-int(prior["extra_ddr_bytes"]),
                         "new_spill_bytes": metrics["spill_added_copy_bytes"],
                         "old_tensor_spill_bytes": int(prior["spill_bytes"]),
                         "spill_change_bytes": metrics["spill_added_copy_bytes"]-int(prior["spill_bytes"]),
                         "new_solver_wall_seconds": run["stages"]["solver"]["wall_seconds"],
                         "old_tensor_solver_wall_seconds": float(prior["solver_wall_seconds"]),
                         "new_external_E0_wall_seconds": run["stages"]["E0"]["wall_seconds"],
                         "old_tensor_external_E0_wall_seconds": float(prior["E0_wall_seconds"]),
                         "new_run_path": p, "old_run_path": prior["run_path"]})
    assert len(rows) == 33 and sum(b["charged_calls"]["solver"] for b in batches) == 33
    assert sum(b["charged_calls"]["E0"] for b in batches) == 33
    assert len({(r["case_id"], r["cores"], r["variant"]) for r in rows}) == 33
    assert Counter(r["variant"] for r in rows) == {"capacity_window": 20, "gap_packet": 13}
    comparison = Counter(r["makespan_comparison"] for r in rows)
    by_variant = {v: {"units": sum(r["variant"] == v for r in rows),
                      "comparison": dict(Counter(r["makespan_comparison"] for r in rows if r["variant"] == v))}
                  for v in ("capacity_window", "gap_packet")}
    cell = {k: {"baseline": int(r["baseline_cycles"]), "best_m": int(r["makespan_cycles"]),
                "chosen": "tensor_packet", "source_run": r["run_path"]} for k, r in old.items()}
    for r in rows:
        c = cell[(r["case_id"], r["cores"])]
        if r["new_makespan_cycles"] < c["best_m"]:
            c["best_m"] = r["new_makespan_cycles"]
            c["chosen"] = r["variant"]
            c["source_run"] = r["new_run_path"]
    combined = {}
    for k in range(1, 6):
        items = [cell[(f"{i:03}", k)] for i in range(1, 101)]
        mean = statistics.mean(c["baseline"]/c["best_m"] for c in items)
        old_mean = statistics.mean(int(old[(f"{i:03}", k)]["baseline_cycles"])/int(old[(f"{i:03}", k)]["makespan_cycles"]) for i in range(1, 101))
        assert abs(old_mean-old_summary["cores"][str(k)]["full100_arithmetic_mean"]) < 1e-12
        assert len(items) == 100 and all(c["baseline"] > 0 and c["best_m"] > 0 for c in items)
        combined[str(k)] = {"cells": 100, "fixed_tensor_packet_mean": old_mean,
                            "posthoc_best_of_measured_mean": mean,
                            "mean_gain": mean-old_mean,
                            "chosen_count": dict(Counter(c["chosen"] for c in items))}
    rows.sort(key=lambda r: (r["cores"], r["case_id"], r["variant"]))
    payload = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
               "scope": "33 predeclared public development units only; no new solver/E0. Historical per-cell minimum is kept in a separate diagnostic file, not the main score.",
               "identity": {"new_solver_commit": NEW_SOURCE, "old_tensor_solver_commit": OLD_SOURCE,
                            "runner_commit": RUNNER, "official_E0_commit": E0,
                            "new_spec_commit": SPEC_COMMIT, "new_sources": sorted(new_sources.values(), key=lambda x:x["path"]),
                            "old_sources": old_sources["sources"],
                            "old_csv_path": old_csv.relative_to(ROOT).as_posix(), "old_csv_sha256": sha(old_csv.read_bytes()),
                            "old_summary_path": old_summary_path.relative_to(ROOT).as_posix(), "old_summary_sha256": sha(old_summary_path.read_bytes()),
                            "old_sources_path": old_sources_path.relative_to(ROOT).as_posix(), "old_sources_sha256": sha(old_sources_path.read_bytes())},
               "batches": batches, "calls": {"solver": 33, "E0": 33, "E1": 0, "E2": 0},
               "comparison": dict(comparison), "by_variant": by_variant,
               "rows": rows,
               "limitations": ["Selected 33 public development units are not a randomized or complete new-algorithm sample.",
                               "Posthoc selection needs prior measured E0 outcomes; it is not an online zero-cost selector.",
                               "Solver process wall and separate E0 wall were observed under shared CPU/memory and uncontrolled filesystem cache.",
                               "No missing cell is imputed: the 500-cell fixed tensor_packet matrix supplies all untouched cells."]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    diagnostic = {"created_at_utc": payload["created_at_utc"],
                  "scope": "Diagnostic historical lower envelope of measured cells only. Not a fixed single-algorithm full500 result, official main score, paper result, route winner, or online selector; no new solver/E0 calls.",
                  "source_summary": "summary.json", "old_csv_sha256": payload["identity"]["old_csv_sha256"],
                  "new_solver_commit": NEW_SOURCE, "old_tensor_solver_commit": OLD_SOURCE,
                  "posthoc_min_m_by_core": combined,
                  "selection_rule": "For each of 500 existing tensor_packet cells, use its measured M unless one of the 33 measured new results for that same graph/core has a strictly smaller M. Ties retain tensor_packet. No missing value is imputed.",
                  "limitation": "Selecting a new result requires knowing its saved E0 outcome. No fixed unified entrypoint, parameters and structural branch rule has been run over all 500 cells."}
    (OUT / "diagnostic-envelope.json").write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    with (OUT / "per-unit.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"units": len(rows), "comparison": dict(comparison),
                      "calls": payload["calls"], "diagnostic_file": "diagnostic-envelope.json"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
