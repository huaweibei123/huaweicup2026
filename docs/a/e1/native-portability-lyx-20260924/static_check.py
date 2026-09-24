"""Text/AST/Git-blob checks only; never import or execute evaluator code."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
BASE = "03f02e79de4b4bd6f55241385664b154f4332454"
NEW = ["src/eval_exact/native_backend.py", "src/eval_exact/native.py",
       "src/eval_exact/_native_replay.py", "tests/eval_exact/test_native_portability.py"]
UNCHANGED = ["src/eval_exact/__init__.py", "src/eval_exact/batch.py",
             "src/eval_exact/_official.py", "src/eval_exact/_scene_a.py",
             "src/eval_exact/problem1.py", "src/eval_exact/cli.py", "src/eval_exact/pool.py",
             "research/a/native-replay-20260924/replay_api.py",
             "research/a/native-replay-20260924/src/replay.cpp"]


def original(name):
    return subprocess.check_output(["git", "cat-file", "blob", f"{BASE}:{name}"], cwd=ROOT)


def main():
    trees = {name: ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name) for name in NEW}
    subprocess.run(["git", "diff", "--exit-code", BASE, "--", *UNCHANGED], cwd=ROOT, check=True)
    prototype = ast.parse(original("research/a/native-replay-20260924/replay_api.py"))
    bridge = trees["src/eval_exact/_native_replay.py"]
    preserved = ["Input", "Output", "ptr", "array", "Unsupported", "CandidateError", "validate_orders"]
    before = {item.name: item for item in prototype.body if hasattr(item, "name")}
    after = {item.name: item for item in bridge.body if hasattr(item, "name")}
    for name in preserved:
        if ast.dump(before[name]) != ast.dump(after[name]):
            raise ValueError(f"unexpected bridge change in {name}")
    tests = sorted(item.name for item in ast.walk(trees[NEW[-1]])
                   if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"))
    print(json.dumps({
        "check_kind": "static_text_ast_git_only", "base": BASE,
        "ast_parsed": NEW, "preserved_bridge_ast": preserved,
        "new_source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in NEW},
        "unchanged_git_blob_sha256": {name: hashlib.sha256(original(name)).hexdigest() for name in UNCHANGED},
        "test_methods_not_run": tests,
        "target_imports_builds_evaluations_workers_tests": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
