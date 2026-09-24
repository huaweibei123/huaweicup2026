"""Run a pinned, explicitly manifested Q3 batch; never propose or retry jobs.

The solver is a fresh child process with an integrated E0 validation. A later
manifest may append jobs with --continue, retaining the original deadline and
call ledger. That flag is an explicit dispatch, not an automatic research gate.
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
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
REPO = "huaweibei123/huaweicup2026"
GUARDED_COMMIT = "6389818b1028ada74c685483dd1cd75fb8e16285"
# Reviewed static/local imports of this frozen entrypoint, including imports in
# main(). Official imports are covered separately by source-manifest.json.
GUARDED_FILES = {f"src/q3/{name}.py" for name in (
    "__init__", "guarded_solve", "safe_solve", "solve", "construct",
    "reduction_tree", "release_tree", "capacity_tree", "pipe_bound")}


def utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if str(path).endswith(".gz") else raw)


def write(path, value):
    """Atomically replace only this runner's own mutable receipt."""
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                         encoding="utf-8", newline="\n")
    temporary.replace(path)


def relative(path, root=ROOT):
    return Path(path).resolve().relative_to(root.resolve()).as_posix()


def artifact(path, root=ROOT):
    return {"path": relative(path, root), "sha256": digest(path)}


def validate_manifest(m):
    required = {"schema", "run_id", "stage_id", "producer_session", "task_url", "solver_commit",
                "solver_module", "algorithm", "runtime_id", "budget", "jobs", "offline_costs"}
    if set(m) not in (required, required | {"execution"}) or m["schema"] != "q3-feedback-benchmark-v1":
        raise ValueError("unexpected manifest fields or schema")
    for field in ("run_id", "stage_id", "runtime_id"):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}", m[field]):
            raise ValueError(f"unsafe {field}")
    if not re.fullmatch(r"[0-9a-f]{40}", m["solver_commit"]):
        raise ValueError("solver_commit must be a full SHA")
    if not re.fullmatch(r"src\.q3\.[a-z_]+", m["solver_module"]):
        raise ValueError("solver_module must be a Q3 module")
    budget = m["budget"]
    if set(budget) != {"max_e0_calls", "total_wall_seconds", "per_job_seconds"}:
        raise ValueError("budget must declare call, whole-batch and per-job limits")
    if type(budget["max_e0_calls"]) is not int or budget["max_e0_calls"] < 1:
        raise ValueError("invalid E0 limit")
    for key in ("total_wall_seconds", "per_job_seconds"):
        if type(budget[key]) not in (int, float) or not 0 < budget[key] < float("inf"):
            raise ValueError("invalid time budget")
    alg = m["algorithm"]
    if set(alg) != {"id", "name", "authors", "method", "references", "upstream"}:
        raise ValueError("algorithm requires stable identity and complete source attribution")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", alg["id"]):
        raise ValueError("invalid algorithm ID")
    if not m["jobs"]:
        raise ValueError("empty job list")
    execution = m.get("execution")
    if execution is not None:
        if set(execution) != {"runner_commit", "output_root", "solver_files", "expected_commit",
                              "memory_limit_bytes", "memory_poll_seconds"}:
            raise ValueError("unexpected verification execution fields")
        if m["solver_commit"] != GUARDED_COMMIT or m["solver_module"] != "src.q3.guarded_solve":
            raise ValueError("separate runner identity currently covers the frozen guarded entrypoint only")
        for key in ("runner_commit", "expected_commit"):
            if not re.fullmatch(r"[0-9a-f]{40}", execution[key]):
                raise ValueError(f"execution.{key} requires a full SHA")
        if execution["output_root"] != "results/a/q3-verification":
            raise ValueError("verification output_root must be results/a/q3-verification")
        if set(execution["solver_files"]) != GUARDED_FILES or any(
                not re.fullmatch(r"[0-9a-f]{64}", value) for value in execution["solver_files"].values()):
            raise ValueError("incomplete frozen guarded dependency hashes")
        if type(execution["memory_limit_bytes"]) is not int or execution["memory_limit_bytes"] <= 0:
            raise ValueError("positive memory_limit_bytes required")
        if type(execution["memory_poll_seconds"]) not in (int, float) or not 0.05 <= execution["memory_poll_seconds"] <= 1:
            raise ValueError("memory_poll_seconds must be 0.05 to 1 second")
    seen = set()
    for j in m["jobs"]:
        fields = {"case_id", "cores", "variant", "solver_args", "parameters", "e0_call_limit"}
        if set(j) != (fields | {"expected"} if execution else fields):
            raise ValueError("unexpected job fields")
        if execution:
            if set(j["expected"]) != {"plan", "result", "receipt"}:
                raise ValueError("expected plan/result/receipt required for every verification job")
            for ref in j["expected"].values():
                if (set(ref) != {"path", "sha256"} or not isinstance(ref["path"], str)
                        or not ref["path"].startswith("results/") or "\\" in ref["path"]
                        or ":" in ref["path"] or ".." in ref["path"].split("/")
                        or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"])):
                    raise ValueError("invalid expected artifact reference")
        if not re.fullmatch(r"00[1-9]|0[1-9][0-9]|100", j["case_id"]):
            raise ValueError("invalid case")
        if type(j["cores"]) is not int or j["cores"] not in range(1, 6):
            raise ValueError("invalid cores")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,69}", j["variant"]):
            raise ValueError("unsafe variant")
        if type(j["e0_call_limit"]) is not int or j["e0_call_limit"] < 1:
            raise ValueError("invalid job call limit")
        if not isinstance(j["parameters"], dict) or not isinstance(j["solver_args"], list):
            raise ValueError("invalid parameters or argv")
        for arg in j["solver_args"]:
            if not isinstance(arg, str) or not arg or arg.startswith(("/", "~")):
                raise ValueError("unsafe solver argument")
            if arg.split("=", 1)[0] in {"--cores", "-o", "--output", "--evidence"}:
                raise ValueError("manifest may not override controlled output arguments")
        key = job_key(j)
        if key in seen:
            raise ValueError("duplicate job; repeated experiments need a distinct run")
        seen.add(key)


def job_key(job):
    return f"{job['case_id']}-k{job['cores']}-{job['variant']}"


def verify_source(commit, cases, root=ROOT):
    """Verify as-run code and frozen inputs; no evaluator imports."""
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                    cwd=root, text=True)
    if actual != commit or dirty:
        raise RuntimeError("pinned source HEAD differs or tracked files are dirty")
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "src"],
                                        cwd=root, text=True).splitlines()
    if any(p.endswith(".py") for p in untracked):
        raise RuntimeError("untracked source files would invalidate fixed source identity")
    manifest = read(root / "docs/a/source-manifest.json")
    hashes = {}
    for item in manifest["files"]:
        name = item["path"]
        if (name.startswith("code/") or name == "data/config.txt"
                or name in {f"data/case_{case}.json" for case in cases}):
            path = root / "data/raw/a/official" / name
            if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
                raise RuntimeError(f"frozen identity differs: {name}")
            hashes[relative(path, root)] = item["sha256"]
    for path in sorted((root / "src/q3").glob("*.py")):
        hashes[relative(path, root)] = digest(path)
    hashes["uv.lock"] = digest(root / "uv.lock")
    return manifest["official_code_hash"], hashes


def git_bytes(root, commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=root)


def verify_manifest_source(manifest, cases, root):
    execution = manifest.get("execution")
    if not execution:
        return verify_source(manifest["solver_commit"], cases, root)
    official, hashes = verify_source(execution["runner_commit"], cases, root)
    for name, expected in execution["solver_files"].items():
        frozen = hashlib.sha256(git_bytes(root, manifest["solver_commit"], name)).hexdigest()
        if frozen != expected or digest(root / name) != expected:
            raise RuntimeError(f"frozen algorithm dependency differs: {name}")
    # src is a namespace package in the frozen checkout. A new initializer could
    # execute unrelated code before the verified q3 entrypoint.
    if (root / "src/__init__.py").exists():
        raise RuntimeError("unexpected src package initializer")
    for name in ("uv.lock", "pyproject.toml", "docs/a/source-manifest.json"):
        if (root / name).read_bytes() != git_bytes(root, manifest["solver_commit"], name):
            raise RuntimeError(f"frozen dependency/input contract differs: {name}")
    return official, hashes


def load_expected(manifest, root):
    """Read all fixed control bytes before any child is dispatched; never score."""
    execution = manifest.get("execution")
    if not execution:
        return {}
    expected = {}
    for job in manifest["jobs"]:
        values = {}
        for name, ref in job["expected"].items():
            raw = git_bytes(root, execution["expected_commit"], ref["path"])
            if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
                raise ValueError("fixed expected artifact hash differs: " + ref["path"])
            values[name] = json.loads(gzip.decompress(raw) if ref["path"].endswith(".gz") else raw)
        expected[job_key(job)] = values
    return expected


def typed_differences(left, right, path="$", limit=20):
    """Compare decoded values and number types; only mapping order is ignored."""
    differences = []
    def visit(a, b, p):
        if len(differences) >= limit:
            return
        if type(a) is not type(b):
            differences.append({"path": p, "reason": "type", "expected": type(a).__name__, "actual": type(b).__name__})
        elif isinstance(a, dict):
            if set(a) != set(b):
                differences.append({"path": p, "reason": "keys", "expected": sorted(a), "actual": sorted(b)})
            for key in sorted(a.keys() & b.keys()):
                visit(a[key], b[key], p + "." + key)
        elif isinstance(a, list):
            if len(a) != len(b):
                differences.append({"path": p, "reason": "length", "expected": len(a), "actual": len(b)})
            for i, (x, y) in enumerate(zip(a, b)):
                visit(x, y, f"{p}[{i}]")
        elif a != b:
            differences.append({"path": p, "reason": "value", "expected": a, "actual": b})
    visit(left, right, path)
    return differences


def compare_expected(expected, folder, result, receipt, job):
    keys = ("official_e0_calls", "selected_strategy", "makespan")
    candidate_keys = ("name", "strategy", "status", "makespan", "certified_lower_bound_cycles",
                      "unscored_plan_sha256")
    def semantics(value):
        return {**{key: value.get(key) for key in keys}, "candidates": [
            {key: item.get(key) for key in candidate_keys} for item in value.get("candidates", [])]}
    comparisons = {
        "plan": typed_differences(expected["plan"], read(folder / f"case_{job['case_id']}_multicore_res.json")),
        "result": typed_differences(expected["result"], result),
        "receipt_semantics": typed_differences(semantics(expected["receipt"]), semantics(receipt)),
    }
    # Plan bytes are part of the reproducibility contract, unlike gzip container
    # metadata. Full decoded result values/types are compared without exclusions.
    if digest(folder / f"case_{job['case_id']}_multicore_res.json") != job["expected"]["plan"]["sha256"]:
        comparisons["plan"].append({"path": "$", "reason": "plan bytes SHA256 differs"})
    return {"matched": not any(comparisons.values()), "differences": comparisons,
            "scope": "Exact plan bytes; full decoded official JSON values/types; receipt decisions/calls, excluding wall timers and gzip container metadata."}


def environment(root=ROOT):
    cpu = platform.processor() or platform.machine()
    if sys.platform == "darwin":
        cpu = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
    try:
        ram = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        ram = None
    return {"os": platform.platform(), "cpu": cpu, "gpu": "none used (CPU-only solver)",
            "ram_bytes": ram, "python": sys.version, "dependencies": "uv.lock sha256=" + digest(root / "uv.lock"),
            "threads": None, "workers": 1, "peak_rss_bytes": None}


class WindowsJob:
    """Native job ownership: descendants cannot outlive timeout/parent cleanup.

    The gated launcher is assigned before it can spawn the solver. Unsupported
    nested-job/host policies fail closed before releasing that gate.
    """
    def __init__(self):
        import ctypes as c
        from ctypes import wintypes as w
        self.c, self.w = c, w
        self.api = c.WinDLL("kernel32", use_last_error=True)
        class Basic(c.Structure):
            _fields_ = [("process_time", c.c_int64), ("job_time", c.c_int64), ("flags", w.DWORD),
                        ("min_ws", c.c_size_t), ("max_ws", c.c_size_t), ("active_limit", w.DWORD),
                        ("affinity", c.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]
        class Extended(c.Structure):
            _fields_ = [("basic", Basic), ("io", c.c_uint64 * 6), ("process_memory", c.c_size_t),
                        ("job_memory", c.c_size_t), ("peak_process", c.c_size_t), ("peak_job", c.c_size_t)]
        class Memory(c.Structure):
            _fields_ = [("cb", w.DWORD), ("faults", w.DWORD), ("peak_ws", c.c_size_t),
                        ("working_set", c.c_size_t), ("peak_paged", c.c_size_t), ("paged", c.c_size_t),
                        ("peak_nonpaged", c.c_size_t), ("nonpaged", c.c_size_t),
                        ("pagefile", c.c_size_t), ("peak_pagefile", c.c_size_t)]
        self.Memory = Memory
        signatures = {
            "CreateJobObjectW": ([c.c_void_p, w.LPCWSTR], w.HANDLE),
            "SetInformationJobObject": ([w.HANDLE, c.c_int, c.c_void_p, w.DWORD], w.BOOL),
            "QueryInformationJobObject": ([w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p], w.BOOL),
            "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
            "TerminateJobObject": ([w.HANDLE, w.UINT], w.BOOL),
            "CloseHandle": ([w.HANDLE], w.BOOL),
            "OpenProcess": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            "K32GetProcessMemoryInfo": ([w.HANDLE, c.c_void_p, w.DWORD], w.BOOL),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.api, name)
            fn.argtypes, fn.restype = args, result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise c.WinError(c.get_last_error())
        info = Extended()
        info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, c.byref(info), c.sizeof(info)):
            error = c.WinError(c.get_last_error())
            self.close()
            raise error

    def attach(self, proc):
        if not self.api.AssignProcessToJobObject(self.handle, int(proc._handle)):
            raise self.c.WinError(self.c.get_last_error())

    def rss(self):
        c, w = self.c, self.w
        count = 16
        for _ in range(5):
            class Pids(c.Structure):
                _fields_ = [("assigned", w.DWORD), ("count", w.DWORD), ("pids", c.c_size_t * count)]
            info = Pids()
            if self.api.QueryInformationJobObject(self.handle, 3, c.byref(info), c.sizeof(info), None):
                break
            error = c.get_last_error()
            if error != 234:  # ERROR_MORE_DATA
                raise c.WinError(error)
            count = max(count * 2, info.assigned)
        else:
            raise RuntimeError("cannot obtain stable Windows job process list")
        total = 0
        for pid in info.pids[:info.count]:
            handle = self.api.OpenProcess(0x0400 | 0x0010, False, pid)
            if not handle:
                if c.get_last_error() == 87:  # process exited between snapshots
                    continue
                raise c.WinError(c.get_last_error())
            try:
                memory = self.Memory()
                memory.cb = c.sizeof(memory)
                if not self.api.K32GetProcessMemoryInfo(handle, c.byref(memory), memory.cb):
                    raise c.WinError(c.get_last_error())
                total += memory.working_set
            finally:
                self.api.CloseHandle(handle)
        return total

    def kill(self):
        if self.handle and not self.api.TerminateJobObject(self.handle, 1):
            raise self.c.WinError(self.c.get_last_error())

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def group_rss(pid):
    # ps is queried by process-group ID, so subprocess descendants count too.
    text = subprocess.check_output(["ps", "-A", "-o", "pgid=,rss="], text=True,
                                   encoding="utf-8", timeout=2)
    return sum(int(rss) * 1024 for group, rss in (line.split() for line in text.splitlines() if line.strip())
               if int(group) == pid)


def kill_tree(proc, job=None):
    if job is not None:
        job.kill()
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_child(argv, timeout, folder, root=ROOT, memory_limit_bytes=None, memory_poll_seconds=0.1):
    """Full process wall; optional sampled group RSS tripwire, never a hard cap."""
    start = time.perf_counter()
    job = None
    proc = None
    stdout = stderr = b""
    status, reason, peak = "ok", None, None
    env = dict(os.environ)
    # Do not read stale bytecode from the algorithm checkout. -B also prevents
    # writes; the newly reserved job directory makes this prefix initially empty.
    cache = folder / "unused-pycache"
    if cache.exists():
        raise FileExistsError("bytecode isolation prefix already exists")
    env.update(PYTHONPYCACHEPREFIX=str(cache), PYTHONUTF8="1")
    try:
        if os.name == "nt":
            job = WindowsJob()
            gate = "import subprocess,sys; token=sys.stdin.buffer.read(1); sys.exit(subprocess.call(sys.argv[1:]) if token==b'1' else 125)"
            proc = subprocess.Popen([sys.executable, "-I", "-c", gate, *argv], cwd=root, env=env,
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            job.attach(proc)
            proc.stdin.write(b"1")
            proc.stdin.flush()
            proc.stdin.close()
            proc.stdin = None
        else:
            proc = subprocess.Popen(argv, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True)
        while True:
            remaining = timeout - (time.perf_counter() - start)
            if remaining <= 0:
                status, reason = "timeout", "per-job or original batch deadline"
                break
            if memory_limit_bytes is not None:
                try:
                    rss = job.rss() if job else group_rss(proc.pid)
                except Exception as error:
                    status, reason = "failed", f"memory_monitor_error: {type(error).__name__}: {error}"
                    break
                peak = max(peak or 0, rss)
                if rss > memory_limit_bytes:
                    status, reason = "failed", "memory_limit_exceeded"
                    break
            remaining = timeout - (time.perf_counter() - start)
            if remaining <= 0:
                status, reason = "timeout", "per-job or original batch deadline"
                break
            try:
                stdout, stderr = proc.communicate(timeout=min(remaining, memory_poll_seconds) if memory_limit_bytes else remaining)
                if proc.returncode:
                    status, reason = "failed", "nonzero exit"
                break
            except subprocess.TimeoutExpired:
                continue
        if status != "ok":
            kill_tree(proc, job)
            stdout, stderr = proc.communicate(timeout=10)
    except BaseException:
        if proc is not None:
            # Assignment can fail before the gate opens: kill that gated process
            # directly too, because it may not belong to the job yet.
            try:
                kill_tree(proc, job)
            finally:
                if proc.poll() is None:
                    proc.kill()
                stdout, stderr = proc.communicate(timeout=10)
        raise
    finally:
        if job is not None:
            job.close()  # also removes descendants after a successful root exit
        elif proc is not None:
            kill_tree(proc)
        for name, raw in (("stdout.txt", stdout), ("stderr.txt", stderr)):
            (folder / name).write_bytes(raw.replace(str(root).encode(), b"<repo>")
                                       .replace(sys.executable.encode(), b"<python>"))
    return {"status": status, "reason": reason, "exit_code": proc.returncode,
            "wall_seconds": time.perf_counter() - start, "argv": ["python", *map(str, argv[1:])],
            "process_tree_cleanup": "Windows kill-on-close Job Object with gated launcher" if job else "POSIX process group",
            "memory": {"limit_bytes": memory_limit_bytes, "sampled_peak_rss_bytes": peak,
                       "poll_seconds": memory_poll_seconds if memory_limit_bytes else None,
                       "scope": "sum of process-group RSS / Windows job WorkingSetSize; sampled tripwire, not OS hard limit; shared pages may be counted more than once"},
            "log_derivation": "stdout/stderr preserve bytes except repository and interpreter absolute paths replaced by markers"}


def validate_result(folder, job, root=ROOT):
    plan_path = folder / f"case_{job['case_id']}_multicore_res.json"
    result_path = folder / "evidence/result.json.gz"
    receipt_path = folder / "evidence/receipt.json"
    plan, result, receipt = read(plan_path), read(result_path), read(receipt_path)
    if set(plan) != {"node_to_subgraph", "core_schedules"}:
        raise ValueError("plan is not official two-field format")
    if (result.get("scene") != "B" or type(result.get("problem")) is not int
            or result["problem"] != 3 or result.get("cache_mode") != "read_only"
            or result.get("num_cores") != job["cores"]):
        raise ValueError("P3 result scene/problem/cache/core identity differs")
    count = receipt["official_e0_calls"]
    if type(count) is not int or not 1 <= count <= job["e0_call_limit"]:
        raise ValueError("actual E0 call count exceeds fixed job reservation")
    makespan = result["makespan"]
    if (type(makespan) not in (int, float) or not 0 < makespan < float("inf")
            or type(receipt["makespan"]) is not type(makespan) or receipt["makespan"] != makespan):
        raise ValueError("receipt/result Makespan value or numeric type differs")
    expected = {"plan_sha256": digest(plan_path), "result_sha256": digest(result_path),
                "graph_sha256": digest(root / f"data/raw/a/official/data/case_{job['case_id']}.json"),
                "config_sha256": digest(root / "data/raw/a/official/data/config.txt")}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("receipt does not bind graph/config/final plan/full result bytes")
    if "candidates" in receipt:
        successful = []
        for candidate in receipt["candidates"]:
            if candidate["status"] != "ok":
                if candidate["status"] not in {"unsupported", "duplicate", "rejected", "bound_pruned"} or candidate["makespan"] is not None:
                    raise ValueError("unrecognized candidate status or fabricated failed score")
                if candidate["status"] == "bound_pruned":
                    lower = candidate.get("certified_lower_bound_cycles")
                    if type(lower) is not int or lower < receipt["makespan"]:
                        raise ValueError("pruned candidate lacks an adequate lower bound")
                    unscored = candidate.get("unscored_plan")
                    if not isinstance(unscored, dict):
                        raise ValueError("pruned candidate lacks its unscored plan")
                    payload = (json.dumps(unscored, separators=(",", ":")) + "\n").encode()
                    if hashlib.sha256(payload).hexdigest() != candidate.get("unscored_plan_sha256"):
                        raise ValueError("pruned candidate plan hash differs")
                continue
            refs = candidate["artifacts"]
            for ref in refs.values():
                path = (folder / "evidence" / ref["path"]).resolve()
                if not path.is_relative_to((folder / "evidence").resolve()) or digest(path) != ref["sha256"]:
                    raise ValueError("candidate artifact hash/path differs")
            candidate_result = read(folder / "evidence" / refs["result"]["path"])
            if (candidate_result.get("scene") != "B" or candidate_result.get("problem") != 3
                    or candidate_result.get("cache_mode") != "read_only" or candidate_result.get("num_cores") != job["cores"]
                    or type(candidate_result["makespan"]) is not type(candidate["makespan"])
                    or candidate_result["makespan"] != candidate["makespan"]):
                raise ValueError("candidate score/identity disagrees with full E0 bytes")
            successful.append(candidate)
        # Stable min preserves the first (seed) candidate on exact score ties.
        if not successful or successful[0].get("name") != "seed":
            raise ValueError("confirmed seed missing")
        chosen = min(successful, key=lambda c: c["makespan"])
        if (chosen["artifacts"]["plan"]["sha256"] != expected["plan_sha256"]
                or chosen["artifacts"]["result"]["sha256"] != expected["result_sha256"]
                or chosen["strategy"] != receipt["selected_strategy"]):
            raise ValueError("published plan does not follow strict-improvement/seed-on-tie rule")
        evaluations = read(folder / "evidence/evaluations.json")
        if len(evaluations) != count or any(e["status"] not in {"ok", "failed"} for e in evaluations):
            raise ValueError("actual evaluation ledger disagrees with completed solver receipt")
    return result, receipt, {"plan": artifact(plan_path, root), "result": artifact(result_path, root),
                             "trace": artifact(receipt_path, root)}


def same_batch(old, manifest):
    for key in ("run_id", "producer_session", "task_url", "solver_commit", "solver_module", "algorithm",
                "runtime_id", "budget", "offline_costs"):
        if old[key] != manifest[key]:
            raise ValueError(f"continuation cannot change {key}")
    if old.get("execution") != manifest.get("execution"):
        raise ValueError("continuation cannot change execution policy")
    if old["status"] not in ("stage_complete",):
        raise ValueError("only a completed successful stage may be explicitly continued")
    if manifest["stage_id"] in [stage["stage_id"] for stage in old["stages"]]:
        raise ValueError("stage already attempted; no implicit retry")
    if {job_key(j) for j in manifest["jobs"]} & {r["job_key"] for r in old["records"]}:
        raise ValueError("job already attempted; no implicit retry")


def execute(manifest, output, continuing=False, root=ROOT, runner_argv=None):
    validate_manifest(manifest)
    root = Path(root).resolve()
    output = Path(output).resolve()
    execution = manifest.get("execution", {})
    declared_area = root / execution.get("output_root", "results/a/q3-nikolastarx")
    write_area = declared_area.resolve()
    if write_area != declared_area or not output.is_relative_to(write_area) or output == write_area:
        raise ValueError("batch must be in the Q3 result write area")
    meta_path = output / "batch.json"
    if continuing:
        batch = read(meta_path)
        same_batch(batch, manifest)
    else:
        if output.exists():
            raise FileExistsError("batch exists; no overwrite or automatic resume")
        batch = {key: value for key, value in manifest.items() if key not in ("jobs", "stage_id")}
        batch.update(started_at=utc(), status="prepared", stages=[], records=[], e0_budget_used=0)
    code_hash, hashes = verify_manifest_source(manifest, [j["case_id"] for j in manifest["jobs"]], root)
    expected = load_expected(manifest, root)
    env = environment(root)
    if continuing and env != batch["environment"]:
        raise ValueError("continuation environment changed")
    batch.update(environment=env, official_sha256=code_hash)
    output.mkdir(parents=True, exist_ok=continuing)
    snapshot = output / f"manifest-{manifest['stage_id']}.json"
    if snapshot.exists():
        raise FileExistsError("manifest snapshot exists")
    write(snapshot, manifest)
    stage = {"stage_id": manifest["stage_id"], "started_at": utc(), "manifest": artifact(snapshot, root),
             "source_input_sha256": hashes, "status": "running", "runner_argv": runner_argv or []}
    batch["stages"].append(stage)
    batch["status"] = "running"
    write(meta_path, batch)
    deadline_utc = datetime.fromisoformat(batch["started_at"].replace("Z", "+00:00")).timestamp() + batch["budget"]["total_wall_seconds"]
    deadline = time.monotonic() + deadline_utc - time.time()
    for job in manifest["jobs"]:
        key = job_key(job)
        remaining = deadline - time.monotonic()
        if remaining <= 0 or batch["e0_budget_used"] + job["e0_call_limit"] > batch["budget"]["max_e0_calls"]:
            batch["status"] = stage["status"] = "stopped_before_dispatch"
            batch["stop_reason"] = "original deadline or global E0 reservation cap reached"
            break
        # Detect concurrent code changes before every dispatch. No calls made by this check.
        try:
            _, fresh_hashes = verify_manifest_source(manifest, [job["case_id"]], root)
            if any(fresh_hashes[k] != v for k, v in hashes.items() if k in fresh_hashes):
                raise RuntimeError("source bytes changed between jobs")
        except Exception as error:
            batch["status"] = stage["status"] = "stopped_before_dispatch"
            batch["stop_reason"] = f"source preflight failed: {type(error).__name__}: {error}".replace(str(root), "<repo>")
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            batch["status"] = stage["status"] = "stopped_before_dispatch"
            batch["stop_reason"] = "original deadline reached during source preflight"
            break
        folder = output / "cells" / key
        folder.mkdir(parents=True, exist_ok=False)
        record = {**job, "job_key": key, "stage_id": manifest["stage_id"], "started_at": utc(),
                  "status": "running", "calls": {"solver": 0, "E0": None, "E1": 0, "E2": 0},
                  "e0_reserved": job["e0_call_limit"], "artifacts": {}, "run_path": relative(folder / "run.json", root),
                  "failure": None, "solver_process": None, "identity": {
                      "graph_sha256": digest(root / f"data/raw/a/official/data/case_{job['case_id']}.json"),
                      "config_sha256": digest(root / "data/raw/a/official/data/config.txt"),
                      "official_sha256": code_hash, "plan_sha256": None}}
        batch["records"].append(record)
        batch["e0_budget_used"] += job["e0_call_limit"]
        write(folder / "run.json", record)
        write(meta_path, batch)  # reserve BEFORE a child can enter E0
        argv = [sys.executable, "-B", "-m", manifest["solver_module"],
                f"data/raw/a/official/data/case_{job['case_id']}.json", "--cores", str(job["cores"]),
                "-o", relative(folder / f"case_{job['case_id']}_multicore_res.json", root),
                "--evidence", relative(folder / "evidence", root), *job["solver_args"]]
        try:
            record["calls"]["solver"] = 1
            limits = ({"memory_limit_bytes": execution["memory_limit_bytes"],
                       "memory_poll_seconds": execution["memory_poll_seconds"]} if execution else {})
            record["solver_process"] = run_child(argv, min(remaining, batch["budget"]["per_job_seconds"]), folder, root, **limits)
            process = record["solver_process"]
            if process["status"] != "ok":
                record["status"] = process["status"]
                raise RuntimeError("solver child did not complete; no retry; " + str(process.get("reason", "unknown")))
            verify_manifest_source(manifest, [job["case_id"]], root)
            result, receipt, refs = validate_result(folder, job, root)
            record.update(artifacts=refs, makespan_cycles=result["makespan"],
                          data_movement_bytes=result.get("data_movement_bytes"), cache_stats=result.get("cache_stats"),
                          solver_receipt=receipt)
            record["identity"]["plan_sha256"] = refs["plan"]["sha256"]
            record["calls"]["E0"] = receipt["official_e0_calls"]
            if execution:
                comparison = compare_expected(expected[key], folder, result, receipt, job)
                comparison_path = folder / "expected-comparison.json"
                write(comparison_path, comparison)
                record["expected_comparison"] = artifact(comparison_path, root)
                if not comparison["matched"]:
                    raise ValueError("fixed expected evidence differs; stop before next job")
            record["status"] = "ok"
            # Successful receipts prove unused reservations; failures/unknowns never refund.
            batch["e0_budget_used"] -= job["e0_call_limit"] - receipt["official_e0_calls"]
            if any(c["status"] == "rejected" for c in receipt.get("candidates", [])):
                record["research_stop"] = "tree candidate rejected by E0; confirmed seed preserved, no further dispatch"
                batch["status"] = stage["status"] = "stopped_on_candidate_rejection"
        except BaseException as error:
            if record["status"] == "running":
                record["status"] = "failed"
            process = record["solver_process"] or {}
            record["failure"] = {"stage": "solver_or_evidence", "reason": f"{type(error).__name__}: {error}".replace(str(root), "<repo>"),
                                 "exit_code": process.get("exit_code"), "elapsed_seconds": process.get("wall_seconds")}
            batch["status"] = stage["status"] = "stopped_on_failure"
        finally:
            ledger = folder / "evidence/evaluations.json"
            if ledger.exists():
                record["evaluation_ledger"] = artifact(ledger, root)
            record["finished_at"] = utc()
            write(folder / "run.json", record)
            write(meta_path, batch)
        if record["status"] != "ok" or batch["status"] == "stopped_on_candidate_rejection":
            break
    else:
        batch["status"] = stage["status"] = "stage_complete"
    stage["finished_at"] = batch["finished_at"] = utc()
    batch["elapsed_wall_seconds"] = time.time() - datetime.fromisoformat(batch["started_at"].replace("Z", "+00:00")).timestamp()
    write(meta_path, batch)
    return batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--continue", action="store_true", dest="continuing")
    args = parser.parse_args()
    invocation = ["python", "-m", "src.q3.feedback_benchmark", *sys.argv[1:]]
    invocation = [value.replace(str(ROOT), "<repo>") for value in invocation]
    batch = execute(read(args.manifest), args.output, args.continuing, runner_argv=invocation)
    print(json.dumps({"status": batch["status"], "attempts": len(batch["records"]),
                      "e0_budget_used": batch["e0_budget_used"], "elapsed_wall_seconds": batch["elapsed_wall_seconds"]}))
    return 0 if batch["status"] == "stage_complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
