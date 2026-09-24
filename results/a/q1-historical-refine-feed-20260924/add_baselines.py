"""Revision 2: attach existing identity-matched E0 denominators; no evaluation."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = "6664a63adc3464d28d1f835d907cdeaea23e6b35"
FEED = "results/a/local-p1-fixed64-20260924/20260924T1337Z-s59ee/board-feed-full500.json"


def read(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT)


def save(path, data):
    if path.exists() and path.read_bytes() != data:
        raise ValueError(f"Refuse to overwrite different bytes: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main():
    original = json.loads((OUT / "board-feed-historical-refine.json").read_text())
    source = json.loads(read(FEED))
    updated = deepcopy(original)
    for row in updated["records"]:
        match = next(r for r in source["records"]
                     if r["case_id"] == row["case_id"] and r["cores"] == row["cores"])
        baseline = deepcopy(match["baseline"])
        for key in ("graph_sha256", "config_sha256", "official_sha256"):
            assert baseline[key] == row["identity"][key]
        data = read(baseline["result"]["path"])
        assert hashlib.sha256(data).hexdigest() == baseline["result"]["sha256"]
        assert json.loads(gzip.decompress(data))["makespan"] > 0
        path = OUT / "baselines" / f"{row['case_id']}.json.gz"
        save(path, data)
        baseline["result"]["path"] = path.relative_to(ROOT).as_posix()
        row["baseline"] = baseline
        row["revision"] = 2
        row["notes"].append(
            f"Revision 2 adds the existing official singlecore denominator from {BASE}, "
            "after graph/config/official identity and result-byte hash checks. "
            "Same historical attempt; no new solver/evaluator call; metrics and unknown wall time unchanged.")
    save(OUT / "board-feed-historical-refine-r2.json",
         (json.dumps(updated, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"revision": 2, "records": len(updated["records"]),
                      "new_solver_calls": 0, "new_evaluator_calls": 0}))


if __name__ == "__main__":
    main()
