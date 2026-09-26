"""Read-only comparison of two fixed P2 full-500 runs from saved originals."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).resolve().parent
CAPTAIN_COMMIT = "571536962b3f6ad9468584a0e5ae04398e684543"
CAPTAIN_FEED = (
    "results/a/q2-nikolastarx/semantic-benchmark-s59ee-20260925/"
    "20260924T1729Z-s59ee/board-feed-500.json"
)
CAPTAIN_SOLVER = "b7c05cf2205bd42ec23680e618a10796b37562f6"
OUR_SOLVER = "e64723bdf99669c44f76d8e90ab0379a8578522e"
OUR_CSV = ROOT / (
    "results/a/q2-yuanzhifang/feedback-20260924/"
    "full-coverage/all500/per-cell.csv"
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def git_blob(process: subprocess.Popen, path: str) -> bytes:
    assert path.startswith("results/") and ".." not in Path(path).parts
    process.stdin.write(f"{CAPTAIN_COMMIT}:{path}\n".encode())
    process.stdin.flush()
    header = process.stdout.readline().strip().split()
    if len(header) != 3 or header[1] != b"blob":
        raise ValueError(f"Git blob unavailable: {path}: {header!r}")
    size = int(header[2])
    raw = process.stdout.read(size)
    assert len(raw) == size and process.stdout.read(1) == b"\n", path
    return raw


def main() -> None:
    feed_raw = subprocess.check_output(
        ["git", "show", f"{CAPTAIN_COMMIT}:{CAPTAIN_FEED}"], cwd=ROOT
    )
    feed = json.loads(feed_raw)
    records = feed["records"]
    assert len(records) == 500
    keys = [(r["case_id"], r["cores"]) for r in records]
    expected = {(f"{i:03d}", k) for i in range(1, 101) for k in range(1, 6)}
    assert len(set(keys)) == 500 and set(keys) == expected

    with OUR_CSV.open(newline="", encoding="utf-8") as stream:
        ours = list(csv.DictReader(stream))
    own_keys = [(r["case_id"], int(r["cores"])) for r in ours]
    assert len(ours) == len(set(own_keys)) == 500 and set(own_keys) == expected
    own_by_key = dict(zip(own_keys, ours))
    baseline = {
        f"{i:03d}": load(
            ROOT / f"results/benchmark-board/official-singlecore-20260924/{i:03d}/run.json"
        )
        for i in range(1, 101)
    }

    rows = []
    captain_result_bytes = captain_run_bytes = own_result_bytes = 0
    process = subprocess.Popen(
        ["git", "cat-file", "--batch"], cwd=ROOT,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        for record in records:
            case, core = record["case_id"], record["cores"]
            key = case, core
            own = own_by_key[key]
            base = baseline[case]
            ident = record["identity"]
            assert record["problem"] == "P2" and record["status"] == "ok"
            assert record["solver_commit"] == CAPTAIN_SOLVER
            assert record["algorithm_id"] == "q2-adaptive-semantic"
            assert record["evaluator"]["route"] == "E0"
            assert record["baseline"]["route"] == "E0"
            assert record["parameters"]["candidate_limit"] == 1
            assert record["parameters"]["online_evaluator_calls"] == 0
            assert record["provenance"]["measurement"]["calls"] == {
                "solver": 1, "E0": 1, "E1": 0, "E2": 0
            }
            for key_name, base_name in (
                ("graph_sha256", "graph_sha256"),
                ("config_sha256", "config_sha256"),
                ("official_sha256", "official_code_hash"),
            ):
                assert ident[key_name] == base[base_name], (case, core, key_name)
                assert record["baseline"][key_name] == base[base_name]
            assert record["baseline"]["result"]["sha256"] == (
                base["artifacts"]["result.json"]["sha256"]
            )
            assert int(own["baseline_cycles"]) == base["makespan_cycles"]
            assert sha(
                (ROOT / f"results/benchmark-board/official-singlecore-20260924/{case}/run.json").read_bytes()
            ) == own["baseline_receipt_sha256"]

            cap_run_item = record["artifacts"]["run"]
            cap_run_raw = git_blob(process, cap_run_item["path"])
            assert sha(cap_run_raw) == cap_run_item["sha256"]
            cap_run = json.loads(cap_run_raw)
            assert cap_run["case_id"] == case and cap_run["cores"] == core
            assert cap_run["status"] == "ok" and cap_run["problem"] == "P2"
            assert cap_run["solver_commit"] == CAPTAIN_SOLVER
            assert cap_run["algorithm_id"] == record["algorithm_id"]
            assert cap_run["graph_sha256"] == ident["graph_sha256"]
            assert cap_run["config_sha256"] == ident["config_sha256"]
            assert cap_run["official_code_hash"] == ident["official_sha256"]
            assert cap_run["calls"] == record["provenance"]["measurement"]["calls"]
            captain_run_bytes += len(cap_run_raw)

            cap_result_item = record["artifacts"]["result"]
            cap_result_raw = git_blob(process, cap_result_item["path"])
            assert sha(cap_result_raw) == cap_result_item["sha256"]
            cap_result = json.loads(gzip.decompress(cap_result_raw))
            cap_move = cap_result["data_movement_bytes"]
            assert cap_result["scene"] == "B" and cap_result["num_cores"] == core
            assert cap_result["makespan"] == record["metrics"]["makespan_cycles"]
            assert cap_run["makespan_cycles"] == cap_result["makespan"]
            assert cap_run["data_movement_bytes"] == cap_move
            assert cap_move["added_copy_bytes"] == record["metrics"]["extra_ddr_bytes"]
            assert cap_move["spill_added_copy_bytes"] == record["metrics"]["spill_bytes"]
            captain_result_bytes += len(cap_result_raw)

            own_run = load(ROOT / own["run_path"])
            assert own_run["status"] == "ok" and own_run["solver_commit"] == OUR_SOLVER
            assert own_run["case_id"] == case and own_run["cores"] == core
            assert own_run["identity"]["graph_sha256"] == base["graph_sha256"]
            assert own_run["identity"]["config_sha256"] == base["config_sha256"]
            assert own_run["identity"]["official_sha256"] == base["official_code_hash"]
            own_result_item = own_run["artifacts"]["result"]
            own_result_raw = (ROOT / own_result_item["path"]).read_bytes()
            assert sha(own_result_raw) == own_result_item["sha256"] == own["result_sha256"]
            own_result = json.loads(gzip.decompress(own_result_raw))
            own_move = own_result["data_movement_bytes"]
            assert own_result["scene"] == "B" and own_result["num_cores"] == core
            assert own_result["makespan"] == int(own["makespan_cycles"])
            assert own_move["added_copy_bytes"] == int(own["extra_ddr_bytes"])
            assert own_move["spill_added_copy_bytes"] == int(own["spill_bytes"])
            own_result_bytes += len(own_result_raw)

            B = base["makespan_cycles"]
            cM, oM = cap_result["makespan"], own_result["makespan"]
            rows.append({
                "case_id": case, "cores": core, "baseline_A_cycles": B,
                "captain_M_cycles": cM, "our_M_cycles": oM,
                "winner_by_M": "captain" if cM < oM else "ours" if oM < cM else "tie",
                "captain_A_over_M": B / cM, "our_A_over_M": B / oM,
                "captain_minus_our_speedup": B / cM - B / oM,
                "captain_extra_DDR_bytes": cap_move["added_copy_bytes"],
                "our_extra_DDR_bytes": own_move["added_copy_bytes"],
                "captain_spill_bytes": cap_move["spill_added_copy_bytes"],
                "our_spill_bytes": own_move["spill_added_copy_bytes"],
                "captain_solver_wall_seconds": record["metrics"]["solver_wall_seconds"],
                "our_solver_wall_seconds": float(own["solver_wall_seconds"]),
                "captain_external_E0_wall_seconds": record["metrics"]["evaluation_wall_seconds"],
                "our_external_E0_wall_seconds": float(own["E0_wall_seconds"]),
                "captain_result_path": cap_result_item["path"],
                "captain_result_sha256": cap_result_item["sha256"],
                "our_result_path": own_result_item["path"],
                "our_result_sha256": own_result_item["sha256"],
            })
    finally:
        process.stdin.close()
        process.stdout.close()
        process.wait(timeout=30)
        if process.returncode != 0:
            raise RuntimeError(process.stderr.read().decode(errors="replace"))
        process.stderr.close()

    assert len(rows) == 500
    summary = {
        "scope": "Read-only, two fixed single-SHA P2 full-500 runs; no new solver/E0 call",
        "captain_commit": CAPTAIN_COMMIT,
        "captain_feed_path": CAPTAIN_FEED,
        "captain_feed_sha256": sha(feed_raw),
        "captain_solver_commit": CAPTAIN_SOLVER,
        "our_solver_commit": OUR_SOLVER,
        "identities": {
            "coordinates": "exact 001..100 x cores 1..5, unique in both",
            "status": "500 ok in each",
            "baseline": "same saved official A receipt, graph/config/official SHA per case",
            "captain_evaluator_commit": sorted({r["evaluator"]["commit"] for r in records}),
            "captain_official_sha256": sorted({r["identity"]["official_sha256"] for r in records}),
            "our_official_sha256": sorted({load(ROOT / r["run_path"])["identity"]["official_sha256"] for r in ours}),
        },
        "verified_originals": {
            "captain_run_git_blobs": 500, "captain_result_gzip_git_blobs": 500,
            "our_result_gzip_files": 500, "captain_run_bytes": captain_run_bytes,
            "captain_result_gzip_bytes": captain_result_bytes,
            "our_result_gzip_bytes": own_result_bytes,
            "scope_limit": "Captain plan, trace, log and baseline gzip bytes not independently replayed here; baseline receipt hashes checked against frozen local records. Saved E0 outputs are inspected, not rerun.",
        },
        "by_core": {},
    }
    for core in range(1, 6):
        group = [r for r in rows if r["cores"] == core]
        assert len(group) == 100
        summary["by_core"][str(core)] = {
            "captain_mean_A_over_M": statistics.mean(r["captain_A_over_M"] for r in group),
            "our_mean_A_over_M": statistics.mean(r["our_A_over_M"] for r in group),
            "captain_minus_our_mean": statistics.mean(r["captain_minus_our_speedup"] for r in group),
            "M_captain_better": sum(r["winner_by_M"] == "captain" for r in group),
            "M_equal": sum(r["winner_by_M"] == "tie" for r in group),
            "M_ours_better": sum(r["winner_by_M"] == "ours" for r in group),
            "captain_extra_DDR_bytes_total": sum(r["captain_extra_DDR_bytes"] for r in group),
            "our_extra_DDR_bytes_total": sum(r["our_extra_DDR_bytes"] for r in group),
            "captain_spill_bytes_total": sum(r["captain_spill_bytes"] for r in group),
            "our_spill_bytes_total": sum(r["our_spill_bytes"] for r in group),
            "captain_solver_wall_seconds_total": sum(r["captain_solver_wall_seconds"] for r in group),
            "our_solver_wall_seconds_total": sum(r["our_solver_wall_seconds"] for r in group),
            "captain_external_E0_wall_seconds_total": sum(r["captain_external_E0_wall_seconds"] for r in group),
            "our_external_E0_wall_seconds_total": sum(r["our_external_E0_wall_seconds"] for r in group),
        }
    with (OUT / "per-cell.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["cores"], r["case_id"])))
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary["by_core"], ensure_ascii=False))


if __name__ == "__main__":
    main()
