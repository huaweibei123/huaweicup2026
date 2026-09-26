"""Summarize a frozen measured batch without evaluating or selecting plans."""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, type=Path)
    args = parser.parse_args()
    batch = args.batch.resolve()
    ledger = read(batch / "ledger.json")
    if ledger["state"] == "running":
        raise ValueError("wait for immutable completed/stopped batch")
    rows = []
    for name in ledger["attempts"]:
        run = read(ROOT / name)
        row = {"case_id": run["case_id"], "variant": run["method"]["variant"],
               "cores": run["cores"], "status": run["status"], "makespan_cycles": None,
               "solver_wall_seconds": run["stages"]["solver"]["wall_seconds"],
               "evaluation_wall_seconds": run["stages"].get("E0", {}).get("wall_seconds"),
               "singlecore_cycles": None, "speedup": None, "scheduled_copy_bytes": None,
               "added_copy_bytes": None, "spill_added_copy_bytes": None,
               "plan_sha256": run["identity"]["plan_sha256"], "run_path": name}
        if run["status"] == "ok":
            result = read(ROOT / run["artifacts"]["result"]["path"])
            base = read(ROOT / "results/benchmark-board/official-singlecore-20260924" / run["case_id"] / "run.json")
            for b, i in (("graph_sha256", "graph_sha256"), ("config_sha256", "config_sha256"), ("official_code_hash", "official_sha256")):
                if base[b] != run["identity"][i]:
                    raise ValueError("baseline frozen identity mismatch")
            row.update(makespan_cycles=result["makespan"], singlecore_cycles=base["makespan_cycles"],
                       speedup=base["makespan_cycles"] / result["makespan"])
            row.update({key: result["data_movement_bytes"][key]
                        for key in ("scheduled_copy_bytes", "added_copy_bytes", "spill_added_copy_bytes")})
        rows.append(row)
    cases = {}
    for case in sorted({r["case_id"] for r in rows}):
        successful = [r for r in rows if r["case_id"] == case and r["status"] == "ok"]
        best = min((r["makespan_cycles"] for r in successful), default=None)
        pareto = [r["variant"] for r in successful if not any(
            s["makespan_cycles"] <= r["makespan_cycles"] and s["solver_wall_seconds"] <= r["solver_wall_seconds"]
            and (s["makespan_cycles"] < r["makespan_cycles"] or s["solver_wall_seconds"] < r["solver_wall_seconds"])
            for s in successful)]
        cases[case] = {"best_cycles": best, "best_variants": [r["variant"] for r in successful if r["makespan_cycles"] == best],
                       "observed_single_run_pareto_variants": pareto}
    summary = {"ledger": str((batch / "ledger.json").relative_to(ROOT)).replace("\\", "/"),
               "state": ledger["state"], "calls": ledger["charged_calls"],
               "batch_wall_seconds": ledger["batch_wall_seconds"], "preparation": ledger["preparation"],
               "scope": "Post-hoc public development comparisons at one core count, one process per measurement, OS cache uncontrolled. Pareto membership uses noisy single measurements and is not a latency-significance claim or an online portfolio result.",
               "cases": cases, "rows": rows}
    with (batch / "summary.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    with (batch / "summary.csv").open("x", encoding="utf-8", newline="") as stream:
        stream.write(buf.getvalue())
    print(json.dumps({"cases": cases, "calls": ledger["charged_calls"]}))


if __name__ == "__main__":
    main()
