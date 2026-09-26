from pathlib import Path
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time

root = Path.cwd()
source = "6fba2f5bab01af27efcd5e4c54db77cd853196e5"
sha = lambda b: hashlib.sha256(b).hexdigest()
git = lambda *a: subprocess.check_output(["git", *a], cwd=root)
files = ["src/q1_yuanzhifang/" + n + ".py" for n in ("ddr_barrier_bound", "star_frontier", "fork_frontier", "construct", "diagnose")]
files.append("tests/q1_yuanzhifang/test_ddr_barrier_bound.py")
source_hashes = {}
for f in files:
    data = (root / f).read_bytes()
    assert data == git("show", source + ":" + f), f
    source_hashes[f] = sha(data)
manifest_path = "docs/a/source-manifest.json"
manifest_bytes = git("show", source + ":" + manifest_path)
manifest = json.loads(manifest_bytes)
official_hashes = {}
for f in manifest["files"]:
    if not f["path"].endswith(".py"):
        continue
    path = "data/raw/a/official/" + f["path"]
    value = sha((root / path).read_bytes())
    assert value == f["sha256"], path
    assert (root / path).read_bytes() == git("show", source + ":" + path), path
    official_hashes[path] = value
assert len(official_hashes) == 10
graph = "data/raw/a/official/data/case_051.json"
config = "data/raw/a/official/data/config.txt"
for path in (graph, config):
    key = path.removeprefix("data/raw/a/official/")
    expected = next(f["sha256"] for f in manifest["files"] if f["path"] == key)
    assert sha((root / path).read_bytes()) == expected
old = "45fde88569b4ce877bda397ae32bc9a1b4abf082"
feed_path = "results/a/q1-yuanzhifang/stage-g-20260925/board-feed-20260924T175725Z-stage-g.json"
record = json.loads(git("show", old + ":" + feed_path))["records"][0]
plan = record["artifacts"]["plan"]["path"]
plan_bytes = (root / plan).read_bytes()
assert plan_bytes == git("show", old + ":" + plan)
assert sha(plan_bytes) == record["artifacts"]["plan"]["sha256"]
out = root / "results/a/q1-yuanzhifang/ddr-proof-20260925"
out.mkdir(parents=True, exist_ok=False)
argv = ["-X", "utf8", "-B", "src/q1_yuanzhifang/ddr_barrier_bound.py", graph,
        (out / "051-bound.json").relative_to(root).as_posix(), "--config", config, "--plan", plan]
t0, start = time.perf_counter(), dt.datetime.now(dt.timezone.utc).isoformat()
run = subprocess.run([sys.executable, *argv], text=True, encoding="utf-8", capture_output=True)
wall = time.perf_counter() - t0
finish = dt.datetime.now(dt.timezone.utc).isoformat()
(out / "stdout.txt").write_text(run.stdout, encoding="utf-8", newline="\n")
(out / "stderr.txt").write_text(run.stderr, encoding="utf-8", newline="\n")
metadata = {"source_commit": source, "source_hashes": source_hashes,
            "official_code_hash": manifest["official_code_hash"], "official_source_hashes": official_hashes,
            "manifest_git_sha256": sha(manifest_bytes), "G_plan_commit": old, "G_feed": feed_path,
            "argv": ["python", *argv], "python": sys.version,
            "started_at": start, "finished_at": finish, "analysis_subprocess_wall_seconds": wall,
            "returncode": run.returncode, "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0, "Task_compiler": 0},
            "scope": "One original graph's static structure and formula check, not scoring, not completed independent proof audit.",
            "script_sha256": sha(Path(__file__).read_bytes())}
(out / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(run.stdout.strip())
print(json.dumps({"returncode": run.returncode, "wall_seconds": wall, "official_files_verified": len(official_hashes)}))
if run.returncode:
    print(run.stderr)
    raise SystemExit(run.returncode)
