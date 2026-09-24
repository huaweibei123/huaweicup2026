"""Minimal CLI wrapper for the fixed sink-peel construct; no scoring."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1.sink_peel import construct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cores", type=int, required=True)
    parser.add_argument("--max-rounds", type=int, default=64)
    parser.add_argument("--max-sinks", type=int, default=64)
    parser.add_argument("--diagnostics", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.diagnostics.exists():
        raise FileExistsError("Refuse to overwrite artifacts")
    plan, diagnostics = construct(json.loads(args.graph.read_text()), args.cores,
                                  max_rounds=args.max_rounds, max_sinks=args.max_sinks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as f:
        json.dump(plan, f, separators=(",", ":"))
        f.write("\n")
    with args.diagnostics.open("x") as f:
        json.dump(diagnostics, f, indent=2)
        f.write("\n")
    print(json.dumps(diagnostics))


if __name__ == "__main__":
    main()
