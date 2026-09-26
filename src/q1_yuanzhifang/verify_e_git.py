"""Run the unchanged board validators against fixed Git blobs with one reader.

This only avoids per-blob Git process startup. The board schema, Ledger and
admission rules are unchanged; temporary validation state is never production.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from reuse_e import GitBlobs, require, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    temporary_root = args.temp_root.resolve()
    temporary_root.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    begin = time.perf_counter()
    loaded = {}
    with GitBlobs() as blobs:
        # SCHEMA and imported Python are read from the worktree by the original
        # validator, so verify those bytes against the fixed artifact commit.
        verified = {}
        for name in ("src/benchmark_board/protocol.py", "src/benchmark_board/core.py",
                     "docs/benchmarks/board-feed.schema.json", "src/q1_yuanzhifang/reuse_e.py"):
            raw = blobs.read(args.commit, name)
            materialized = (ROOT / name).read_bytes()
            # Shared board files permit Git's text checkout conversion. Admit
            # only CRLF/LF differences in validator code/schema, never in any
            # measured or reused evidence loaded below.
            require(raw.replace(b"\r\n", b"\n") == materialized.replace(b"\r\n", b"\n"), "Changed validator source/schema")
            verified[name] = {"fixed_git_sha256": hashlib.sha256(raw).hexdigest(),
                              "materialized_sha256": hashlib.sha256(materialized).hexdigest(),
                              "comparison": "exact bytes" if raw == materialized else "CRLF/LF only; no evidence normalization"}
        sys.path.insert(0, str(ROOT / "src/benchmark_board"))
        from protocol import validate_feed
        from core import Ledger, safe_path, MAX_BLOB

        def load(name):
            safe_path(name)
            raw = blobs.read(args.commit, name)
            require(len(raw) <= MAX_BLOB, "Oversized fixed artifact")
            loaded[name] = hashlib.sha256(raw).hexdigest()
            return raw

        raw = load(args.feed.as_posix())
        require(len(raw) <= 8 * 1024 * 1024, "Oversized feed")
        feed = json.loads(raw)
        strict = validate_feed(feed, submission=True)
        manifest = json.loads(load("docs/a/source-manifest.json"))
        calibrations = json.loads(load("docs/benchmarks/board-calibrations.json"))
        with tempfile.TemporaryDirectory(prefix="board-fixed-", dir=temporary_root) as temporary:
            # Check the final resolved cleanup target before context cleanup.
            state = Path(temporary).resolve()
            require(state != temporary_root and state.is_relative_to(temporary_root), "Temporary state escaped its named root")
            ledger = Ledger(state, manifest, calibrations)
            ingestion = ledger.ingest(feed, load, {"commit": args.commit,
                                                   "path": args.feed.as_posix(), "validation_only": True})
            rows = ledger.records()
            result = {"valid": True, "submission": strict, "records": len(rows),
                      "eligible": sum(row["eligible"] for row in rows),
                      "reported_or_failed": [{"attempt_id": row["attempt_id"], "reasons": row["admission_notes"]}
                                             for row in rows if not row["eligible"]],
                      "scope": "format and fixed Git bytes only; no solver/evaluator execution or production write"}
        receipt = {"artifact_commit": args.commit, "feed": args.feed.as_posix(),
                   "feed_sha256": loaded[args.feed.as_posix()], "started_at": started,
                   "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                   "wall_seconds": time.perf_counter() - begin, "result": result,
                   "verified_unchanged_validator_sha256": verified, "fixed_blob_sha256": loaded,
                   "loader": "GitBlobs git cat-file --batch; same fixed commit, board safe_path and MAX_BLOB limits",
                   "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "verifier_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                   "temporary_state": "Removed after validating its resolved location beneath the supplied task-specific temporary root.",
                   "ingestion": ingestion, "new_calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}}
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"artifact_commit": args.commit, "wall_seconds": receipt["wall_seconds"],
                      "fixed_blobs": len(loaded), "result": result}, ensure_ascii=False))
    require(result["records"] == 100 and result["eligible"] == 92, "Unexpected final evidence coverage")


if __name__ == "__main__":
    main()
