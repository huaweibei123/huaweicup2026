"""Revise P3 source-label metadata without rerunning or changing scores."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD_COMMIT = "36a9e7a9dceb24c432d4c4eca100ae143464de9c"
OLD_FEED = "results/a/q3-nikolastarx/unified-full500-20260925-s59/20260924T1741Z-s59ee/board-feed-500.json"
AREA = ROOT / "results/a/q3-nikolastarx/unified-full500-20260925-s59"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if not source.is_relative_to(AREA) or output.parent != source.parent or output.exists():
        parser.error("source and fresh output must be in this P3 batch")
    feed = json.loads(source.read_text())
    if len(feed["records"]) != 500 or {r["revision"] for r in feed["records"]} != {1}:
        raise RuntimeError("expected exactly 500 corrected first-revision rows")
    for record in feed["records"]:
        parameters = record["parameters"]
        if not {"controller_source_sha256", "dispatch_receipt_sha256"}.issubset(parameters):
            raise RuntimeError("corrected source/receipt fields missing")
        record["revision"] = 2
        record["notes"].append(
            "Revision 2 corrects source-label metadata only. Revision 1 from "
            f"{OLD_COMMIT}:{OLD_FEED} called the completed dispatch receipt SHA "
            "controller_sha256. The controller source SHA and dispatch receipt SHA "
            "are separately named here; plan, official E0 result, calls, timing, "
            "algorithm version and run identity are unchanged."
        )
    output.write_text(json.dumps(feed, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(json.dumps({"records": len(feed["records"]), "revision": 2,
                      "feed": output.relative_to(ROOT).as_posix(), "sha256": digest}))


if __name__ == "__main__":
    main()
