"""Provision the selected compiler's runtime DLLs beside the generated library."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from research.a.e2_search import E2Evaluator
from research.a.e2_search.tests.test_search import simple_graph, PLAN
from src.eval_exact import read_config
from research.a.review.e2_windows_20260924.run_checks import redact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = read_config(ROOT / "data/raw/a/official/data/config.txt")
    before = E2Evaluator(simple_graph()).evaluate_record(PLAN, **config)
    copied = {}
    for name in ("libc++.dll", "libunwind.dll"):
        source = args.bin / name
        target = ROOT / "research/a/e2_search/native" / name
        if target.exists():
            raise FileExistsError(target)
        shutil.copyfile(source, target)
        copied[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    after = E2Evaluator(simple_graph()).evaluate_record(PLAN, **config)
    # Strip only filesystem location from error metadata; keep error class/message.
    if "fallback_reason" in before:
        before["fallback_reason"]["message"] = redact(before["fallback_reason"]["message"])
    args.output.write_text(json.dumps(dict(before=before, after=after, runtime_sha256=copied,
        note="Compiler runtime deployment only. Evaluator source and original compiler flags unchanged. Two E2 requests; no direct E0."), indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(before_route=before["route"], after_route=after["route"], runtime_sha256=copied)))
    if after["route"] != "native":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
