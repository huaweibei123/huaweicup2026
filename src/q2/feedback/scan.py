"""Read-only graph family survey. Does not import or invoke an evaluator."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from .construct import Index, ROOT, UnsupportedStructure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    start = time.perf_counter()
    rows = []
    for path in sorted((ROOT / "data/raw/a/official/data").glob("case_*.json")):
        raw = path.read_bytes()
        index = Index(json.loads(raw))
        try:
            word = index.word_descriptor()
        except UnsupportedStructure:
            word = None
        jobs = index.assignment(4)
        row = {"case_id": path.stem[-3:], "sha256": hashlib.sha256(raw).hexdigest(),
               "ops": len(index.ops), "components": len(index.components),
               "max_component_ops": max(map(len, index.components), default=0),
               "word_descriptor": word, "jobs_by_core": list(map(len, jobs)),
               "window_by_core": [index.window_size(j) for j in jobs]}
        rows.append(row)
    result = {"scope": "graph structure only; zero solver/evaluator calls",
              "graphs": len(rows), "wall_seconds": time.perf_counter() - start, "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"graphs": len(rows), "word_matches": [r["case_id"] for r in rows if r["word_descriptor"]],
                      "wall_seconds": result["wall_seconds"]}))


if __name__ == "__main__":
    main()
