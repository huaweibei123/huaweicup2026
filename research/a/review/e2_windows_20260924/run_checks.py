"""Independent fixed-HEAD Windows checks; never edits evaluator sources."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
TESTED_HEAD = "f4ee4756fc15c65ddc4256f3c73ff4efc89accfc"


def redact(text):
    for path, label in ((str(ROOT), "<WORKTREE>"), (str(Path.home()), "<USER>"),
                        (str(Path(sys.executable)), "<PYTHON>")):
        variants = [path, path.replace("\\", "/")]
        for _ in range(3):
            variants += [json.dumps(v)[1:-1] for v in list(variants)]
        for variant in sorted(set(variants), key=len, reverse=True):
            text = text.replace(variant, label)
    return text


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compiler", type=Path)
    parser.add_argument("--private-output", type=Path)
    parser.add_argument("--phase", choices=["preflight", "native"], required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if args.private_output:
        args.private_output.mkdir(parents=True, exist_ok=False)
    source_dirs = ["research/a/e2_search", "src/eval_exact", "data/raw/a/official/code"]
    sources = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for folder in source_dirs for p in sorted((ROOT / folder).rglob("*"))
               if p.is_file() and p.suffix in (".py", ".cpp")}
    receipt = dict(tested_head=TESTED_HEAD, platform=platform.platform(), python=sys.version,
                   phase=args.phase, source_sha256=sources, commands=[])
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if args.compiler:
        env["PATH"] = str(args.compiler.parent) + os.pathsep + env["PATH"]
    commands = [("build", ["-m", "research.a.e2_search.build_native"] +
                 (["--compiler", str(args.compiler)] if args.compiler else []))]
    if args.phase == "native":
        commands.append(("unittest", ["research/a/review/e2_windows_20260924/counted_suite.py"]))
    commands.append(("cli", ["-m", "research.a.e2_search.cli_probe", "--output",
                              str(args.output / "cli")]))
    if args.phase == "preflight":
        commands.append(("rss_recycling", ["-m", "unittest",
                         "research.a.e2_search.tests.test_search.SearchTest.test_pool_order_error_recycling_and_cleanup", "-v"]))
    for name, argv in commands:
        start = time.perf_counter()
        try:
            run = subprocess.run([sys.executable, *argv], cwd=ROOT, env=env, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=180)
            raw = dict(argv=[sys.executable, *argv], returncode=run.returncode,
                       stdout=run.stdout, stderr=run.stderr)
            raw_bytes = (json.dumps(raw, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            if args.private_output:
                (args.private_output / (name + ".json")).write_bytes(raw_bytes)
            record = dict(name=name, argv=redact("python " + " ".join(argv)),
                          returncode=run.returncode, wall_seconds=time.perf_counter() - start,
                          stdout=redact(run.stdout), stderr=redact(run.stderr))
            if args.private_output:
                record["private_raw_sha256"] = hashlib.sha256(raw_bytes).hexdigest()
        except subprocess.TimeoutExpired:
            record = dict(name=name, status="timeout", wall_seconds=time.perf_counter() - start)
        save(args.output / (name + ".json"), record)
        receipt["commands"].append(record)
        save(args.output / "run.json", receipt)
        print(name, record.get("returncode", record.get("status")), flush=True)
        if name == "build" and args.phase == "native" and record.get("returncode") != 0:
            break


if __name__ == "__main__":
    main()
