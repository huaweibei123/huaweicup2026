"""Frozen, serial Stage B: 4 public graphs x 2 one-candidate methods.

Never retries or selects a candidate using measured scores. The caller must
commit this runner before invoking it. All outputs are exclusive-create.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SOLVER = "50263673b6c40f5978e8d00afa90cc10ffffbbd1"
BASELINE = "4dff90ef699fd51845cf482951e8477066f5f566"
CASES = ("019", "048", "071", "080")
VARIANTS = ("fixed64-propose", "structural-switch")
OUTPUT = "results/a/q1-yuanzhifang/stage-b-20260924"
SESSION = "yuanzhifang30-sudo/s-57863f3c1318476ab027cd8a1338c117"


def utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(path, obj):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def git(*argv, root=ROOT):
    return subprocess.check_output(["git", *argv], cwd=root)


def relative(path):
    return Path(os.path.relpath(path, ROOT)).as_posix()


def verify_source(root, commit, paths):
    result = {}
    for path in paths:
        raw = (root / path).read_bytes()
        if raw != git("show", f"{commit}:{path}"):
            raise ValueError(f"Source differs from fixed commit: {path}")
        result[path] = sha(raw)
    return result


def official_check(root, manifest):
    result = {}
    items = [i for i in manifest["files"] if i["path"].startswith("code/")]
    assert len(items) == 10
    for item in items:
        path = "data/raw/a/official/" + item["path"]
        actual = sha((root / path).read_bytes())
        if actual != item["sha256"]:
            raise ValueError(f"Frozen official mismatch: {path}")
        result[item["path"]] = actual
    joined = "".join(f"{p}\t{result[p]}\n" for p in sorted(result)).encode()
    assert sha(joined) == manifest["official_code_hash"]
    return result


def environment():
    raw = subprocess.check_output([
        "powershell", "-NoProfile", "-Command",
        "$c=Get-CimInstance Win32_Processor; $m=Get-CimInstance Win32_ComputerSystem; "
        "[PSCustomObject]@{cpu=($c.Name -join '; ');ram_bytes=[long]$m.TotalPhysicalMemory} | ConvertTo-Json -Compress",
    ], text=True, encoding="utf-8")
    hardware = json.loads(raw)
    return {"os": platform.platform(), "cpu": hardware["cpu"], "gpu": "none (not used)",
            "ram_bytes": hardware["ram_bytes"], "python": sys.version,
            "dependencies": "uv sync --locked; uv.lock sha256=" + sha((ROOT / "uv.lock").read_bytes()),
            "threads": 1, "workers": 1, "peak_rss_bytes": None,
            "logical_cpu_count": os.cpu_count(),
            "resource_isolation": "No exclusive host reservation; other user tasks may be active."}


def call(argv, folder, stage, timeout):
    # stdout/stderr bytes stay unmodified; argv executable is normalized only
    # in the public receipt (the exact interpreter version is separately saved).
    entry = {"stage": stage, "argv": ["python", *argv[1:]], "working_directory": ".",
             "started_at": utc(), "timeout_seconds": timeout}
    with (folder / f"{stage}.stdout.txt").open("xb") as stdout, (folder / f"{stage}.stderr.txt").open("xb") as stderr:
        start = time.perf_counter()
        try:
            result = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=timeout,
                                    env={**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
                                         "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
            entry.update(returncode=result.returncode, status="ok" if result.returncode == 0 else "failed")
        except subprocess.TimeoutExpired:
            entry.update(returncode=None, status="timeout")
        except OSError as error:
            entry.update(returncode=None, status="infrastructure_failure", error=str(error))
        entry["wall_seconds"] = time.perf_counter() - start
        entry["finished_at"] = utc()
    return entry


def compress(path):
    raw = path.read_bytes()
    packed = gzip.compress(raw, mtime=0)
    destination = path.with_name(path.name + ".gz")
    with destination.open("xb") as stream:
        stream.write(packed)
    if gzip.decompress(destination.read_bytes()) != raw:
        raise ValueError("Lossless gzip check failed")
    # Only this just-created output is removed after byte-for-byte verification.
    path.unlink()
    return {"path": relative(destination), "sha256": sha(packed), "raw_sha256": sha(raw),
            "raw_bytes": len(raw), "gzip_bytes": len(packed)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline-root", type=Path, required=True)
    p.add_argument("--graphs", type=Path, required=True)
    args = p.parse_args()
    baseline_root, graphs = args.baseline_root.resolve(), args.graphs.resolve()
    runner_commit = git("rev-parse", "HEAD").decode().strip()
    # Every input and every executed source must be frozen before scoring.
    if git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Runner worktree has tracked modifications")
    manifest = json.loads((ROOT / "docs/a/source-manifest.json").read_bytes())
    sources = verify_source(ROOT, SOLVER, ["src/q1_yuanzhifang/construct.py"])
    sources.update(verify_source(ROOT, runner_commit, ["src/q1_yuanzhifang/benchmark_b.py"]))
    baseline_sources = verify_source(baseline_root, BASELINE, ["src/q1/search.py", "src/q1/prototype.py", "src/q1/structure.py"])
    if git("rev-parse", "HEAD", root=baseline_root).decode().strip() != BASELINE:
        raise ValueError("Baseline worktree HEAD changed")
    frozen = official_check(ROOT, manifest)
    assert official_check(baseline_root, manifest) == frozen
    expected = {i["path"]: i["sha256"] for i in manifest["files"]}
    inputs = {}
    for name in ["config.txt", *(f"case_{case}.json" for case in CASES)]:
        inputs[name] = sha((graphs / name).read_bytes())
        if inputs[name] != expected["data/" + name]:
            raise ValueError("Input identity mismatch: " + name)
    if sha((baseline_root / "data/raw/a/official/data/config.txt").read_bytes()) != inputs["config.txt"]:
        raise ValueError("Baseline config mismatch")
    hardware = environment()
    out = ROOT / OUTPUT
    out.mkdir(parents=True, exist_ok=False)
    protocol = {"producer_session": SESSION, "task_url": "https://github.com/huaweibei123/huaweicup2026/issues/98",
                "solver_commit": SOLVER, "baseline_commit": BASELINE, "runner_commit": runner_commit,
                "cases": CASES, "variants": VARIANTS, "cores": 4,
                "source_sha256": sources, "baseline_source_sha256": baseline_sources,
                "official_source_sha256": frozen, "official_code_hash": manifest["official_code_hash"],
                "input_sha256": inputs, "environment": hardware,
                "budget": {"solver": 8, "E0": 8, "E1": 0, "E2": 0, "wall_seconds": 300,
                           "solver_timeout_seconds": 20, "evaluation_timeout_seconds": 40, "workers": 1, "retries": 0},
                "preparation": "Reuse the identical Stage A uv sync --locked environment (initial install 14 packages, reported 43.79s, paid once before Stage A); no training/compilation/case-specific precomputation.",
                "solver_scope": "Outer subprocess.run perf_counter: launch, imports, read graph/config, construct, local scoring if any, validate, write final plan, required diagnostics and exit. New process each time; OS caches not flushed.",
                "evaluation_scope": "Separate unmodified E0 CLI launch through result/trace/log write and process exit; no online full E0/E1/E2 calls.",
                "baseline_internal_work": "fixed64 propose calls official _build_scene_a_tasks once for local Task durations; included in solver wall. It does not call full evaluate_scene_a or an E1/E2 scorer.",
                "argv_note": "Executable normalized to python; exact version above. Relative paths in argv are actual paths used from the runner worktree.",
                "metadata": "Windows: dot_clean unavailable. Output metadata scan recorded at completion."}
    dump(out / "protocol.json", protocol)
    t0, started = time.perf_counter(), utc()
    rows, calls, stop = [], {"solver": 0, "E0": 0, "E1": 0, "E2": 0}, "complete"
    try:
        for variant in VARIANTS:
            for case in CASES:
                if time.perf_counter() - t0 > 235:
                    stop = "batch_budget_reserve"; break
                if shutil.disk_usage(out).free < 100 * 1024 * 1024:
                    stop = "insufficient_disk_headroom"; break
                label = f"{case}-{variant}"
                folder = out / label
                folder.mkdir()
                plan = folder / f"case_{case}_multicore_res.json"
                graph = graphs / f"case_{case}.json"
                if variant == "fixed64-propose":
                    argv = [sys.executable, "-X", "utf8", "-B", relative(baseline_root / "src/q1/search.py"), "propose", relative(graph), relative(plan), "--kind", "fixed64", "--cores", "4", "--seed", "0"]
                else:
                    argv = [sys.executable, "-X", "utf8", "-B", "src/q1_yuanzhifang/construct.py", relative(graph), relative(plan), "--cores", "4", "--variant", variant, "--diagnostics", relative(folder / "diagnostics.json")]
                run = {"case_id": case, "variant": variant, "solver_commit": BASELINE if variant == "fixed64-propose" else SOLVER,
                       "runner_commit": runner_commit, "started_at": utc(), "status": "running", "calls": {"solver": 1, "E0": 0, "E1": 0, "E2": 0}}
                calls["solver"] += 1
                run["solver"] = call(argv, folder, "solver", 20)
                failure_stage = "solver"
                if run["solver"]["status"] == "ok":
                    plan_obj = json.loads(plan.read_bytes())
                    if set(plan_obj) != {"node_to_subgraph", "core_schedules"} or len(plan_obj["core_schedules"]) != 4:
                        raise ValueError("Unexpected solver output contract")
                    run["plan_sha256"] = sha(plan.read_bytes())
                    if not variant == "fixed64-propose":
                        run["diagnostics"] = json.loads((folder / "diagnostics.json").read_bytes())
                    argv = [sys.executable, "-X", "utf8", "-B", "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py", relative(graph), relative(plan), "--config", relative(graphs / "config.txt"), "--output", relative(folder / "result.json"), "--trace-output", relative(folder / "trace.json"), "--log-output", relative(folder / "result.txt")]
                    calls["E0"] += 1; run["calls"]["E0"] = 1
                    run["evaluation"] = call(argv, folder, "evaluation", 40)
                    failure_stage = "evaluation"
                stage = run[failure_stage]
                run["status"] = stage["status"]
                run["failure"] = None
                if stage["status"] != "ok":
                    errors = (folder / f"{failure_stage}.stderr.txt").read_text(encoding="utf-8")
                    run["failure"] = {"stage": failure_stage, "reason": errors or stage.get("error") or stage["status"],
                                      "exit_code": stage["returncode"], "elapsed_seconds": stage["wall_seconds"]}
                    known = any(s in errors.lower() for s in ("cyclic", "cycle", "capacity", "capacity exceeded", "deadlock", "invalid plan", "task dependency", "joint order"))
                    if stage["status"] == "infrastructure_failure" or (stage["status"] == "failed" and not known):
                        stop = "unexpected_supervision_or_process_failure"
                elif (folder / "result.json").exists():
                    result = json.loads((folder / "result.json").read_bytes())
                    assert result["scene"] == "A" and result["num_cores"] == 4
                    run.update(makespan_cycles=result["makespan"], data_movement_bytes=result["data_movement_bytes"], task_count=len(result["step3_by_task"]))
                run["artifacts"] = {}
                for name in ("result.json", "trace.json"):
                    if (folder / name).exists():
                        run["artifacts"][name] = compress(folder / name)
                run["finished_at"] = utc()
                dump(folder / "run.json", run)
                rows.append(run)
                print(json.dumps({"case": case, "variant": variant, "status": run["status"], "cycles": run.get("makespan_cycles"), "solver_s": run["solver"]["wall_seconds"], "e0_s": run.get("evaluation", {}).get("wall_seconds")}), flush=True)
                if stop != "complete":
                    break
            if stop != "complete":
                break
    except Exception as error:
        stop = "supervision_exception"
        dump(out / "supervision-error.json", {"type": type(error).__name__, "message": str(error), "utc": utc(), "calls": calls})
        raise
    finally:
        dump(out / "rows.json", rows)
        metadata = [relative(f) for f in out.rglob("*") if f.is_file() and (f.name.startswith("._") or f.name == ".DS_Store")]
        dump(out / "completion.json", {"status": stop, "started_at": started, "finished_at": utc(), "wall_seconds": time.perf_counter() - t0,
                                      "calls": calls, "records": len(rows), "metadata_scan": metadata, "dot_clean": "unavailable on Windows"})
    if stop != "complete":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
