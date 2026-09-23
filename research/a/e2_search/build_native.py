"""Explicit build; evaluation never invokes a compiler or installs packages."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def build(compiler=None, *, problem=1):
    if problem not in (1, 2, 3):
        raise ValueError('problem must be 1, 2 or 3')
    compiler = compiler or shutil.which("clang++") or shutil.which("g++")
    if compiler is None:
        raise RuntimeError("A C++17 compiler is required for native scoring; E1 fallback remains available")
    suffix = ".dll" if sys.platform == "win32" else ".so"
    name = "replay" if problem == 1 else "replay_bc"
    source, target = HERE / ("native/" + name + ".cpp"), HERE / ("native/lib" + name + suffix)
    command = [compiler, "-std=c++17", "-O3", "-shared", "-fno-fast-math",
               "-ffp-contract=off", "-Wall", "-Wextra"]
    if sys.platform != "win32":
        command.append("-fPIC")
    command += [str(source), "-o", str(target)]
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    return dict(command=[s.replace(str(HERE), "research/a/e2_search") for s in command],
                compiler=subprocess.check_output([compiler, "--version"], text=True),
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                binary_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                diagnostics=completed.stdout + completed.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler")
    parser.add_argument("--problem", type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args()
    print(json.dumps(build(args.compiler, problem=args.problem), indent=2))
