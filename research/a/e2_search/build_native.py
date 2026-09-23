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


def build(compiler=None):
    compiler = compiler or shutil.which("clang++") or shutil.which("g++")
    if compiler is None:
        raise RuntimeError("A C++17 compiler is required for native scoring; E1 fallback remains available")
    suffix = ".dll" if sys.platform == "win32" else ".so"
    source, target = HERE / "native/replay.cpp", HERE / ("native/libreplay" + suffix)
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
    args = parser.parse_args()
    print(json.dumps(build(args.compiler), indent=2))
