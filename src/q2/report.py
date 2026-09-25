"""Generate the stage A evidence report from saved outputs; never runs Q2."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .construct import ROOT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    folder = args.run.resolve()
    folder.relative_to(ROOT / "results/a/q2-yuanzhifang")
    run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    artifact_map = json.loads((folder / "artifacts.json").read_text(encoding="utf-8"))
    for name, identity in artifact_map.items():
        path = folder / name
        if sha(path) != identity["sha256"] or path.stat().st_size != identity["bytes"]:
            raise ValueError(f"Evidence changed: {name}")
    rows = {r["label"]: r for r in run["results"]}

    def full(label):
        return json.loads((folder / "evaluations" / label / "result.json").read_text(encoding="utf-8"))

    stub = full("02-case002-stub")
    baseline = full("03-case002-contiguous")
    peak = max(r["sampled_working_set_peak_bytes"] for r in rows.values()) / 1024**2
    report = [
        "# Q2/B stage A checkpoint — measured evidence",
        "",
        f"Evaluated source HEAD: `{run['code_head']}`. Task card: `35709578f01689c20eaf9ef2dd68c274393a3a53`.",
        "T0: 2026-09-24 03:56:25 Asia/Taipei. This is developer self-test, not independent acceptance.",
        "",
        "## Six-field delivery",
        "",
        "1. **Goal:** establish a deterministic Q2 baseline and verify priority/COPY/FIFO/capacity boundaries before search.",
        "2. **Inputs:** frozen official case002/config and PDF minimal input; fixed Pro3 head_blocking/fork graph-plan pairs; labelled local synthetic negatives and memory-pressure input. No sealed cases.",
        "3. **Outputs:** source constructor/runner, metrics.csv, all official result/trace/log files, negative stderr, hashes, environment and this generated report; method paragraph in paper/sections/a-q2.md.",
        "4. **Constraints:** stage A only, serial, maximum 12 Q2 calls including final confirmation; 1800-second aggregate allowance; unmodified official source/config. No Q1/shared-evaluator/dependency changes.",
        "5. **Checks:** fixed PDF answer, empty core, both fixed-assignment comparisons, rejection at three specific layers, legal spill/peak bounds and full repeat equality. Only the checks below were actually run.",
        "6. **Checkpoint:** first evidence requested 60–90 minutes after T0; produced early and submitted to local coordination. Stage B remains unstarted.",
        "",
        "## Results",
        "",
        "| Invocation | Status | Makespan (cycles) | Added COPY (B) | Spill (B) | Supervised wall (s) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for label, row in rows.items():
        if row["status"] == "ok":
            result = full(label)
            added = result["data_movement_bytes"]["added_copy_bytes"]
            spill = result["data_movement_bytes"]["spill_added_copy_bytes"]
        else:
            added = spill = "—"
        report.append(f"| {label} | {row['status']} | {row['makespan_cycles'] if row['makespan_cycles'] is not None else '—'} | {added} | {spill} | {row['wall_seconds']:.3f} |")
    report += [
        "",
        f"case002 contiguous construction: {baseline['makespan']} cycles versus random format stub {stub['makespan']} cycles ({100 * (stub['makespan'] - baseline['makespan']) / stub['makespan']:.4f}% lower). The stub is not a strong baseline; this single-case comparison does not establish search quality or generalization.",
        "",
        "The two Pro3 comparisons preserve core assignment and movement totals. They do not isolate every possible cause: changing priorities also changes shared DDR interactions. In fork, the source COPY_OUT completes earlier as shown below, directly explaining the earlier remote release in this input.",
        "",
        "| Fork plan | COPY_OUT end | COPY_IN release | COPY_IN start | COPY_IN end |",
        "|---|---:|---:|---:|---:|",
    ]
    for label in ("06-fork-coarse", "07-fork-fine"):
        transfer = full(label)["cross_core_transfers"][0]
        report.append(f"| {label} | {transfer['copy_out_end']} | {transfer['copy_in_release']} | {transfer['copy_in_start']} | {transfer['copy_in_end']} |")
    report += [
        "",
        "## Budget, preparation and limitations",
        "",
        f"Actual official Q2 launches: **{run['actual_q2_launches']} / 12**. Nine successful evaluations and three expected rejections; no timed-out or resource-limited Q2 invocation. The original run directory failed before any Q2 launch due to Windows GBK decoding of the UTF-8 manifest; its zero-call ledger and failure note are preserved. The continuation used a 1770-second ceiling, conservatively reserving 30 seconds for that preflight.",
        f"Recorded experiment wall: **{run['experiment_wall_seconds']:.3f} s**, through comparison checks and before final metrics/artifact hashing. Summed supervised Q2 intervals: **{sum(r['wall_seconds'] for r in rows.values()):.3f} s**. These include process startup, output and up to a sampling interval of observation delay; they are not evaluator speed benchmarks. Final report generation/hash verification and public setup are additional explicitly unbenchmarked overheads.",
        f"Largest sampled controller+child working set: **{peak:.3f} MiB** during monitored subprocesses. This does not include a continuous sample of static archive reading/reporting and is not an OS hard limit or proof of whole-run peak memory. All six monitor/control tests passed after fixing Windows venv redirector reaping; they invoked zero official evaluators.",
        "Public preparation: uv sync --locked succeeded (14 packages; uv reported installation in 1m 28s); scripts/a_materials.py --extract verified 114 originals and 100 cases. End-to-end setup was not stopwatch-instrumented, so no exact total setup-time claim is made. source/config/lock hashes and installed versions are in run.json.",
        "",
        "Capacity-negative input deliberately violates the official single-op input/output capacity guarantee. The separate legal pressure input keeps each op within capacity and demonstrates spill. Reported memory peaks are Step3 local outputs, not reconstructed global physical addresses.",
        "",
        "Not covered: cases008/044, all 100 cases, 2–5-core quality matrix, many seeds, multi-producer differential examples, backing/incarnation variations, priority-stage-only rejection distinct from the ordinary plan rejection, timeout/resource failure under large official graphs, formal equivalence, M1/M2 search, Linux/macOS. Control-path timeout/resource tests are not real official-graph stress tests.",
        "",
        "## Reproduce and inspect",
        "",
        "```powershell",
        "uv sync --locked",
        "uv run python -B scripts/a_materials.py --extract",
        "uv run python -B -m unittest discover -s tests/q2 -p test_*.py -v",
        "# Requires a separately authorized 12-call budget and a fresh output directory:",
        "uv run python -B -m src.q2.stage_a --output results/a/q2-yuanzhifang/<fresh-run-id> --wall-seconds 1770",
        "# Regenerate the report from saved evidence; does not evaluate any graph:",
        f"uv run python -B -m src.q2.report --run {folder.relative_to(ROOT).as_posix()}",
        "```",
        "",
        "Exact per-call commands are in evaluations/<name>/run.json. Artifacts retain original plan bytes and full traces; artifacts.json covers the original 89 evidence files, while delivery_manifest.json also covers this generated report and its generator receipt. Only input_plan filename is excluded from the final repeat comparison; the two plan byte hashes match.",
        "",
        "Next recommendation: independently review these fixed files and mechanisms, then decide whether to authorize the separately budgeted three-case D/M1/M2 comparison. No further E0 calls are made by this delivery.",
        "",
    ]
    (folder / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    receipt = {"generator": "src/q2/report.py", "generator_sha256": sha(Path(__file__)),
               "run_json_sha256": sha(folder / "run.json"),
               "verified_original_artifacts": len(artifact_map), "q2_calls": 0}
    (folder / "report_generation.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    delivery = {p.relative_to(folder).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
                for p in sorted(folder.rglob("*")) if p.is_file() and p.name != "delivery_manifest.json"}
    (folder / "delivery_manifest.json").write_text(json.dumps(delivery, indent=2) + "\n", encoding="utf-8")
    print(f"Generated report; verified {len(artifact_map)} original artifacts; no Q2 calls")


if __name__ == "__main__":
    main()
