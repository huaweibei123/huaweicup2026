"""Check the separately delivered exact evaluator against our Q1 E0 artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COMMIT = "5bfe53a29c1ba05167239f51ea937e602f7f85b4"


def strict_equal(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(strict_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(strict_equal(x, y) for x, y in zip(a, b))
    return a == b


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluator-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.evaluator_root, text=True).strip()
    if actual != EXPECTED_COMMIT:
        raise ValueError(f"Expected fixed evaluator commit {EXPECTED_COMMIT}; got {actual}")
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=args.evaluator_root):
        raise ValueError("Evaluator tracked tree must be clean")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.evaluator_root.resolve()))
    from src.eval_exact import P1BatchEvaluator, read_config

    config = read_config(str(ROOT / "data/raw/a/official/data/config.txt"))
    rows = []
    for case in ("002", "008", "051"):
        run = ROOT / f"results/a/q1-prototype-20260924/case{case}-structural-v1"
        summary = json.loads((run / "summary.json").read_text())
        names = [row["candidate"] for row in summary["results"]]
        # Repeat the last plan to exercise reuse after changes of partition.
        names.append(names[-1])
        graph = json.loads((ROOT / summary["graph"]).read_text())
        plans = [json.loads((run / name / "plan.json").read_text()) for name in names]
        with tarfile.open(run / "execution-evidence.tar.xz") as archive:
            expected = [json.load(archive.extractfile(name + "/result.json")) for name in names]
        # E0 CLI adds its two input filenames AFTER evaluate_scene_a returns.
        # API receives objects, not filenames; compare the complete engine result.
        for reference in expected:
            reference.pop("input_graph")
            reference.pop("input_plan")
        with P1BatchEvaluator(graph, workers=1, cache_bytes=16 << 20,
                              timeout_seconds=60, max_tasks_per_worker=256) as pool:
            start = time.perf_counter()
            for row, name, reference in zip(pool.evaluate_batch(plans, full=True, **config), names, expected, strict=True):
                result = json.loads(json.dumps(row["result"])) if row["status"] == "ok" else None
                match = strict_equal(result, reference)
                rows.append({"case": case, "candidate": name, "index": row["index"],
                             "status": row["status"], "full_json_equal": match,
                             "makespan": row.get("makespan"), "cache": row.get("cache"),
                             "reference_sha256": hashlib.sha256(json.dumps(reference, sort_keys=True).encode()).hexdigest()})
                if not match:
                    (args.output / "failure.json").write_text(json.dumps(row, indent=2))
                    raise AssertionError(f"Full E0 mismatch: {case}/{name}")
            print(case, len(names), round(time.perf_counter() - start, 3), flush=True)
    report = {"evaluator_commit": actual, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "comparison": "Full engine JSON, recursively equal keys, scalar types, list order and values; only CLI-added input_graph/input_plan filename metadata excluded",
              "scope": "Algorithm-session integration check on 27 prior E0 candidates plus 3 repeats; not full independent acceptance or timing benchmark",
              "all_full_json_equal": all(r["full_json_equal"] for r in rows), "rows": rows}
    (args.output / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
