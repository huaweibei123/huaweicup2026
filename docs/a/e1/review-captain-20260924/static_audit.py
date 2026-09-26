"""Read fixed Git blobs and AST/JSON only; never import or run target modules."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
BASE = "03f02e79de4b4bd6f55241385664b154f4332454"
HEAD = "0e0cdc656ae095f0d1f7cfe11347a0b3f997d9ac"
EXPECTED = {
    "docs/a/e1/native-portability-lyx-20260924/README.md",
    "docs/a/e1/native-portability-lyx-20260924/static_check.py",
    "docs/a/e1/native-portability-lyx-20260924/validation-plan.json",
    "src/eval_exact/native_backend.py", "src/eval_exact/native.py",
    "src/eval_exact/_native_replay.py", "tests/eval_exact/test_native_portability.py",
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def blob(ref, path):
    return git("cat-file", "blob", f"{ref}:{path}")


def main():
    changed = git("diff", "--name-only", BASE, HEAD).decode().splitlines()
    assert set(changed) == EXPECTED
    assert git("rev-parse", f"{HEAD}^").decode().strip() == BASE
    git("diff", "--check", BASE, HEAD)
    source = {p: blob(HEAD, p) for p in changed}
    trees = {p: ast.parse(raw, filename=p) for p, raw in source.items() if p.endswith(".py")}
    plan = json.loads(source["docs/a/e1/native-portability-lyx-20260924/validation-plan.json"])
    assert plan["execution_authorized"] is False
    assert plan["next_phase_proposal"]["approved"] is False
    original = ast.parse(blob(BASE, "research/a/native-replay-20260924/replay_api.py"))
    bridge = trees["src/eval_exact/_native_replay.py"]
    preserved = ["Input", "Output", "ptr", "array", "Unsupported", "CandidateError", "validate_orders"]
    before = {n.name: n for n in original.body if hasattr(n, "name")}
    after = {n.name: n for n in bridge.body if hasattr(n, "name")}
    assert all(ast.dump(before[n]) == ast.dump(after[n]) for n in preserved)
    tests = sorted(n.name for n in ast.walk(trees["tests/eval_exact/test_native_portability.py"])
                   if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))
    result = {
        "kind": "fixed_blob_text_ast_json_hash_review_only",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "static_runner_python": sys.version,
        "base": BASE, "reviewed_head": HEAD, "changed_files": changed,
        "source_sha256": {p: hashlib.sha256(raw).hexdigest() for p, raw in source.items()},
        "parsed_ast_files": sorted(trees), "preserved_ast_nodes": preserved,
        "test_methods_read_not_run": tests,
        "declared_budget_not_execution": {k: plan["next_phase_proposal"][k] for k in (
            "complete_E0_entries_reserved", "complete_E1_entries_reserved",
            "logical_program_starts_max", "real_replay_backend_loads_max")},
        "target_imports_tests_builds_workers_E0_E1_E2": 0,
        "limit": "AST identity and JSON parsing do not establish runtime correctness, ABI, call counts or performance",
    }
    Path(__file__).with_name("static-evidence.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"static_only": True, "files": len(changed), "asts": len(trees),
                      "preserved_nodes": len(preserved), "tests_not_run": len(tests)}))


if __name__ == "__main__":
    main()
