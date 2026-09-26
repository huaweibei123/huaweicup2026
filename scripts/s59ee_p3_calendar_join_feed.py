"""Join ten completed fixed P3 shards into one full-algorithm submission."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.q3.board_export import export_batch  # noqa: E402

SOURCE = "8314351854c716091bc6d31215569825ae45ec55"
GROUP_RUN = "q3-calendar-full500-20260925-s59"
AREA = ROOT / "results/a/q3-nikolastarx/calendar-full500-20260925-s59"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    batch = args.batch.resolve()
    output = args.output.resolve()
    if not batch.is_relative_to(AREA) or output.parent != batch or output.exists():
        p.error("batch/output must be a fresh feed in this producer's P3 result area")
    dispatch_path = batch / "dispatch.json"
    dispatch = read(dispatch_path)
    if dispatch["status"] != "complete" or dispatch["source_commit"] != SOURCE:
        raise RuntimeError("ten-shard dispatch has not completed on fixed source")
    if len(dispatch["shards"]) != 10 or any(x["status"] != "stage_complete" for x in dispatch["shards"].values()):
        raise RuntimeError("shard missing or incomplete")
    controller_path = ROOT / dispatch["controller_path"]
    controller_source_sha = sha(controller_path)
    if dispatch["controller_sha256"] != controller_source_sha:
        raise RuntimeError("as-run controller source bytes changed")
    dispatch_receipt_sha = sha(dispatch_path)
    rows = []
    all_coords = set()
    calls = {"solver": 0, "E0": 0, "E1": 0, "E2": 0}
    for n in range(1, 11):
        shard_dir = batch / f"s{n:02}"
        source_batch = read(shard_dir / "batch.json")
        if source_batch["solver_commit"] != SOURCE or source_batch["status"] != "stage_complete":
            raise RuntimeError(f"s{n:02} source/status changed")
        exported = export_batch(shard_dir / "batch.json", root=ROOT)
        if len(exported["records"]) != 50:
            raise RuntimeError(f"s{n:02} is not a complete 50-cell shard")
        for record in exported["records"]:
            coordinate = (record["case_id"], record["cores"])
            if coordinate in all_coords or record["status"] != "ok":
                raise RuntimeError(f"duplicate or unsuccessful coordinate: {coordinate}")
            all_coords.add(coordinate)
            native_run = record["run_id"]
            if native_run != source_batch["run_id"] or record["solver_commit"] != SOURCE:
                raise RuntimeError("native shard identity changed")
            record["run_id"] = GROUP_RUN
            record["parameters"].update(native_shard_run_id=native_run,
                                        global_max_shards=dispatch["max_workers"],
                                        controller_source_sha256=controller_source_sha,
                                        dispatch_receipt_sha256=dispatch_receipt_sha)
            record["notes"].append(
                "This complete algorithm run groups ten disjoint, fixed 50-cell shards. "
                f"Native shard run_id={native_run}; its manifest and per-cell original receipts retain that identity. "
                "One worker executes cells serially within each shard, with up to eight shards active together. "
                "Controller source and final dispatch receipt use separately labeled SHA-256 fields."
            )
            rows.append(record)
        for item in source_batch["records"]:
            for key in calls:
                calls[key] += item["calls"][key]
    expected = {(f"{i:03d}", k) for i in range(1, 101) for k in range(1, 6)}
    if all_coords != expected or calls["solver"] != 500 or not 500 <= calls["E0"] <= 1000 or calls["E1"] != 0 or calls["E2"] != 0:
        raise RuntimeError("full coverage or call ledger changed")
    payload = {"schema_version": 1, "submission_version": 1, "records": rows}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"feed": output.relative_to(ROOT).as_posix(), "records": len(rows),
                      "run_id": GROUP_RUN, "calls": calls, "sha256": sha(output)}))


if __name__ == "__main__":
    main()
