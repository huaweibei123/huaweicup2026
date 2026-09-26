"""Frozen 067 k5 single-tail wave pilot; no online selection."""
from __future__ import annotations

import argparse
from collections import deque
import ctypes
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

from benchmark import (ROOT, OFFICIAL, CONFIG, MANIFEST, Pilot, Stopped, artifact,
                       compress, digest, git, relative, sha, utc, write_json)
from export_feed import baseline
from portable_join_benchmark import live_environment, stop_owned_process

SOLVER_COMMIT = "1b0da8c9f92d868209d0cada77a170eb558c997c"
HELPER_COMMIT = "39e9c8d8a78e384855ffbfbf41a2dec4d4a7e5a0"
RUNTIME_HELPER_COMMIT = "60477a382514cb6e97bfd8ea1bb560fda1594c06"
OUT = "results/a/q3-yuanzhifang/wave-tail-20260925"
CASES = ("067",)
BUDGET = dict(workers=1, cold_solver_limit=1, E0_limit=2, E1_limit=0,
              E2_limit=0, per_call_seconds=60, batch_seconds=180,
              dispatch_until_seconds=120, retries=0)
TEMPLATE = "results/a/q3-yuanzhifang/pilot-20260924/board-feed-20260924T141108Z-unique-plans.json"
DEPENDENCIES = {
    "src/q3_yuanzhifang/wave_tail.py": SOLVER_COMMIT,
    "docs/a/q3-yuanzhifang/WAVE_TAIL.md": SOLVER_COMMIT,
    "src/q3_yuanzhifang/wave_capacity.py": "2cf325fb717077cd902830e7f01c920d27cbf8ec",
    "src/q3_yuanzhifang/active_stages.py": "bb7a7e8702b636a0a9dda33d070daad5f4d7c212",
    "src/q3_yuanzhifang/construct.py": "8f8bfce73b0b8e350de1dc40af21f3787c8ac8d6",
    "src/q3_yuanzhifang/baseline.py": "8f8bfce73b0b8e350de1dc40af21f3787c8ac8d6",
}


def preflight(graph_dir):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    graphs = {f"data/case_{case}.json" for case in CASES}
    verified = []
    for item in manifest["files"]:
        name = item["path"]
        if not (name.startswith("code/") or name == "data/config.txt" or name in graphs):
            continue
        path = graph_dir / Path(name).name if name in graphs else OFFICIAL / name
        raw = path.read_bytes()
        if digest(raw) != item["sha256"] or len(raw) != item["bytes"]:
            raise ValueError("official byte identity mismatch: " + name)
        verified.append(dict(manifest_path=name, actual_path=path.as_posix(),
                             sha256=digest(raw), bytes=len(raw)))
    if {x["manifest_path"] for x in verified if x["manifest_path"] in graphs} != graphs:
        raise ValueError("source manifest does not cover case 067")
    code = "".join(f"{x['path']}\t{x['sha256']}\n" for x in
                   sorted(manifest["files"], key=lambda x: x["path"])
                   if x["path"].startswith("code/"))
    if digest(code.encode()) != manifest["official_code_hash"] or sha(CONFIG) != next(
            x["sha256"] for x in manifest["files"] if x["path"] == "data/config.txt"):
        raise ValueError("official code/config aggregate mismatch")
    implementation = []
    for name, commit in DEPENDENCIES.items():
        raw = Path(name).read_bytes()
        if raw != git("show", commit + ":" + name):
            raise ValueError("frozen candidate/dependency differs: " + name)
        implementation.append(dict(path=name, commit=commit, sha256=digest(raw)))
    for name in ("src/q3_yuanzhifang/benchmark.py", "src/q3_yuanzhifang/export_feed.py"):
        if Path(name).read_bytes() != git("show", HELPER_COMMIT + ":" + name):
            raise ValueError("frozen benchmark/feed helper differs: " + name)
    helper = "src/q3_yuanzhifang/portable_join_benchmark.py"
    if Path(helper).read_bytes() != git("show", RUNTIME_HELPER_COMMIT + ":" + helper):
        raise ValueError("runtime/process cleanup helper differs")
    if Path(TEMPLATE).read_bytes() != git("show", "46c709228c0a83e09c13b008e919d135100b938e:" + TEMPLATE):
        raise ValueError("fixed feed template differs")
    head = git("rev-parse", "HEAD").decode().strip()
    for name in ("src/q3_yuanzhifang/tail_benchmark.py",
                 "src/q3_yuanzhifang/tail_export.py",
                 "docs/a/q3-yuanzhifang/TAIL_MEASUREMENT.md"):
        if Path(name).read_bytes() != git("show", head + ":" + name):
            raise ValueError("batch runner/export/docs must be committed: " + name)
    result = dict(official_code_hash=manifest["official_code_hash"], source_manifest=artifact(MANIFEST),
                  config_sha256=sha(CONFIG), verified_files=verified, implementation=implementation,
                  solver_commit=SOLVER_COMMIT, runner_commit=head, runner_sha256=sha(__file__),
                  helper_commit=HELPER_COMMIT, runtime_helper=dict(commit=RUNTIME_HELPER_COMMIT, **artifact(helper)),
                  export_template=artifact(TEMPLATE))
    result["baseline_refs"] = {case: baseline(case, dict(
        graph_sha256=sha(graph_dir / f"case_{case}.json"), config_sha256=result["config_sha256"],
        official_sha256=result["official_code_hash"])) for case in CASES}
    return result


def resource_gate(out):
    gate = dict(checked_at=utc(), available_phys_bytes=None, free_disk_bytes=None,
                minimum_phys_bytes=2 * 1024**3, minimum_disk_bytes=2 * 1024**3,
                passed=False, memory_method="Windows GlobalMemoryStatusEx", disk_method="shutil.disk_usage")
    if os.name != "nt":
        gate["reason"] = "This frozen batch requires Windows available-RAM query."
        return gate
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in ("total_phys", "avail_phys", "total_page",
            "avail_page", "total_virtual", "avail_virtual", "avail_extended")]
    state = MemoryStatus()
    state.length = ctypes.sizeof(state)
    try:
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
            gate["available_phys_bytes"] = state.avail_phys
        gate["free_disk_bytes"] = shutil.disk_usage(out).free
    except OSError as exc:
        gate["reason"] = type(exc).__name__
    gate["passed"] = (gate["available_phys_bytes"] is not None and
                      gate["available_phys_bytes"] >= gate["minimum_phys_bytes"] and
                      gate["free_disk_bytes"] is not None and gate["free_disk_bytes"] >= gate["minimum_disk_bytes"])
    return gate


def audit_p3(graph, result, detail):
    """Read-only post-E0 audit; IDs and bytes come from the frozen original graph."""
    original = json.loads(graph.read_bytes())
    eligible = {o["id"] for o in original["ops"] if o["op"] not in ("COPY_IN", "COPY_OUT")}
    tensors = {t["id"]: t for t in original["tensors"]}
    writers, readers = {t: set() for t in tensors}, {t: set() for t in tensors}
    for edge in original["edges"]:
        a, b = edge["source"], edge["target"]
        if a in eligible and b in tensors:
            writers[b].add(a)
        if a in tensors and b in eligible:
            readers[a].add(b)
    shared = {t for t in tensors if not writers[t] and len(readers[t]) > 1}
    bytes_by_id = {t: 0 for t in shared}
    covered = set()
    all_read_bytes = 0
    events = result.get("cache_events")
    if not isinstance(events, list):
        raise Stopped("P3 cache_events missing or not a list")
    for event in events:
        if event.get("event") not in ("hit", "miss"):
            continue
        size = event.get("size_bytes")
        if event.get("op") != "COPY_IN" or type(size) is not int or size < 0:
            raise Stopped("invalid P3 cache read event")
        all_read_bytes += size
        tid = event.get("tensor_id")
        if tid in bytes_by_id:
            if event.get("size_bytes") != tensors[tid]["size"]:
                raise Stopped("shared cache event size differs from original tensor")
            bytes_by_id[tid] += event["size_bytes"]
            covered.add((event.get("core_id"), tid))
    measured = sum(bytes_by_id.values())
    cross = result.get("cross_core_transfers")
    stats = result.get("cache_stats", {})
    checks = dict(
        shared_identity_bytes=sum(tensors[t]["size"] for t in shared) == sum(map(sum, detail["W"].values())),
        cache_accounting=all_read_bytes == stats.get("hit_bytes", -1) + stats.get("miss_bytes", -1),
        cross_core_transfer_list_present=isinstance(cross, list),
        compute_work_lower_bound=result.get("makespan", -1) >= detail["minimax_compute_work_cycles"],
    )
    audit = dict(shared_tensor_count=len(shared), shared_read_bytes=measured,
                 by_tensor_id=bytes_by_id,
                 shared_core_tensor_pairs=len(covered), all_read_bytes=all_read_bytes,
                 checks=checks, passed=all(checks.values()),
                 cross_core_transfer_count=len(cross) if isinstance(cross, list) else None,
                 cross_core_transfer_review="preserved raw; tail logical/direct-edge ownership requires separate read-only review",
                 event_policy="Only hit/miss events count; logical original tensor IDs and original byte sizes")
    return audit


class TailPilot(Pilot):
    def __init__(self, args):
        super().__init__(args)
        (self.out / ".gitattributes").write_bytes(b"# Preserve exact process/receipt bytes.\n* -text\n")
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.queue = deque(CASES)
        self.info.update(schema="q3-wave-tail-v1", run_id="yuanzhifang-q3-wave-tail-20260925",
                         budget=BUDGET, argv=[relative(sys.executable), "-B", relative(__file__),
                         "--graph-dir", args.graph_dir.as_posix(), "--output", args.output.as_posix(),
                         "--concurrent-work", args.concurrent_work],
                         resource_context=dict(concurrent_work=args.concurrent_work, workers=1,
                         exclusive_host_claim=False, process_priority="BELOW_NORMAL_PRIORITY_CLASS",
                         dispatch_gate="global lock; >=2 GiB available RAM and >=2 GiB free output disk"),
                         resource_checks=[], concurrent_case_workers=1,
                         offline_costs="No training, compilation or case-specific precomputation in this batch. "
                         "Prior algorithm development and environment preparation are outside measured cold calls. "
                         "The fresh Python solver call includes graph read/indexing, strict guard, two-pass tail DP, construction, validation and plan write. "
                         "No online E0 selection. Prior pipeline 067 P2/P3 at c514edf0 is historical only.")

    def save(self):
        with self.lock:
            super().save()

    def invoke(self, kind, call_id, argv, folder):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONHASHSEED="0",
                   OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
        with self.lock:
            elapsed = time.perf_counter() - self.started
            limit = BUDGET["cold_solver_limit" if kind == "solver" else "E0_limit"]
            if self.stop.is_set() or elapsed >= BUDGET["dispatch_until_seconds"] or elapsed >= BUDGET["batch_seconds"]:
                raise Stopped("global stop or dispatch deadline reached")
            if sum(x["kind"] == kind for x in self.calls) >= limit:
                raise Stopped("call cap reached: " + kind)
            gate = resource_gate(self.out)
            gate.update(kind=kind, call_id=call_id, batch_elapsed_at_check=elapsed)
            self.info["resource_checks"].append(gate)
            self.save()
            if not gate["passed"]:
                self.stop.set()
                raise Stopped("RAM/disk below 2 GiB or unknown; no child dispatched")
            folder.mkdir(parents=True, exist_ok=False)
            stdout, stderr = folder / "stdout.txt", folder / "stderr.txt"
            call = dict(call_id=call_id, kind=kind, argv=argv, working_directory=".",
                        started_at=utc(), batch_elapsed_at_dispatch=elapsed, status="running",
                        timeout_seconds=min(BUDGET["per_call_seconds"], BUDGET["batch_seconds"] - elapsed))
            if self.stop.is_set():
                raise Stopped("global stop before spawn")
            self.calls.append(call)
            self.save()
            # Gate, final stop check and actual spawn form one dispatch transaction.
            # No second worker can reuse the same pre-spawn resource snapshot.
            start = time.perf_counter()
            process = None
            try:
                with stdout.open("wb") as out, stderr.open("wb") as err:
                    process = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=out, stderr=err,
                        creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 0,
                        start_new_session=os.name != "nt")
                    call["pid"] = process.pid
            except (OSError, Stopped, KeyboardInterrupt, SystemExit) as exc:
                call.update(status="failed", exit_code=None, failure_type=type(exc).__name__)
                self.stop.set()
        try:
            if process is not None:
                try:
                    call["exit_code"] = process.wait(timeout=call["timeout_seconds"])
                    call["status"] = "ok" if call["exit_code"] == 0 else "failed"
                except subprocess.TimeoutExpired:
                    call["status"] = "timeout"
                    call["cleanup"] = stop_owned_process(process)
                    call["exit_code"] = process.returncode
                    if not call["cleanup"]["ok"]:
                        call["cleanup_failure"] = True
        except (OSError, KeyboardInterrupt, SystemExit) as exc:
            call.update(status="failed", failure_type=type(exc).__name__)
            if process is not None and process.poll() is None:
                call["cleanup"] = stop_owned_process(process)
                call["cleanup_failure"] = not call["cleanup"]["ok"]
            call["exit_code"] = process.returncode if process else None
        finally:
            call.update(wall_seconds=time.perf_counter() - start, finished_at=utc())
            if call["status"] != "ok":
                with self.lock:
                    self.stop.set()
            if call.get("cleanup_failure"):
                call["unsealed_outputs"] = [relative(p) for p in (stdout, stderr) if p.exists()]
            else:
                try:
                    call["stdout"], call["stderr"] = compress(stdout), compress(stderr)
                except (OSError, ValueError) as exc:
                    call.update(status="failed", preservation_failure_type=type(exc).__name__)
                    with self.lock:
                        self.stop.set()
                    call["unsealed_outputs"] = [relative(p) for p in (stdout, stderr) if p.exists()]
            with self.lock:
                write_json(folder / "call.json", call)
                self.save()
        if call["status"] != "ok":
            raise Stopped("first unsuccessful call: " + call_id)
        return call

    def case(self, case):
        cid = f"{case}-wave_tail"
        folder = self.out / case / "wave_tail"
        graph = self.args.graph_dir / f"case_{case}.json"
        plan = folder / f"case_{case}_multicore_res.json"
        python = relative(sys.executable)
        solver_argv = [python, "-B", "-m", "src.q3_yuanzhifang.wave_tail", graph.as_posix(),
                       "--cores", "5", "--config", CONFIG.as_posix(),
                       "--output", plan.as_posix()]
        call = self.invoke("solver", cid, solver_argv, folder / "solver")
        value = json.loads(plan.read_bytes())
        if set(value) != {"node_to_subgraph", "core_schedules"} or len(value["core_schedules"]) != 5:
            raise Stopped("invalid plan fields/core count: " + cid)
        detail = json.loads(gzip.decompress((ROOT / call["stdout"]["path"]).read_bytes()))
        construction = dict(construction_id=cid, case_id=case, variant="wave_tail",
            cores=5, requested_cores=5,
            active_cores=sum(bool(s) for s in value["core_schedules"]), graph_sha256=sha(graph),
            plan=artifact(plan), solver=call, detail=detail, alias_of=None, evaluation_ids=[])
        with self.lock:
            self.constructions.append(construction)
            self.save()
        if not detail.get("guard") or detail.get("selected") != "wave_tail":
            raise Stopped("tail structural guard failed; no E0 on fallback: " + cid)
        owners = {}
        for core, seq in enumerate(value["core_schedules"]):
            for subgraph in seq:
                if subgraph in owners:
                    raise Stopped("duplicate subgraph in core schedules")
                owners[subgraph] = core
        if (len(set(value["node_to_subgraph"].values())) != len(value["node_to_subgraph"]) or
                set(owners) != set(value["node_to_subgraph"].values())):
            raise Stopped("singleton coverage mismatch")
        from src.q3_yuanzhifang.construct import SharingIndex
        index = SharingIndex(json.loads(graph.read_bytes()))
        jobs = index.components
        if (len(jobs) % 5 != 1 or detail.get("jobs") != len(jobs) or
                detail.get("full_jobs_per_core") != 14 or detail.get("tail_job_id") != len(jobs) - 1 or
                len(jobs) != 71 or detail.get("active_cores") != 5):
            raise Stopped("067 single-tail job identity mismatch")
        for core in range(5):
            assigned = [j for j, job in enumerate(jobs[:-1])
                        if {owners[value["node_to_subgraph"][str(u)]] for u in job} == {core}]
            if assigned != list(range(core, 70, 5)):
                raise Stopped("complete-job owner/count mismatch")
        cuts = detail.get("cuts")
        if (not isinstance(cuts, list) or len(cuts) != 6 or cuts[0] != 0 or
                cuts[-1] != len(jobs[-1]) or any(a >= b for a, b in zip(cuts, cuts[1:]))):
            raise Stopped("invalid tail cuts")
        for core, (a, b) in enumerate(zip(cuts, cuts[1:])):
            if any(owners[value["node_to_subgraph"][str(jobs[-1][p])]] != core
                   for p in range(a, b)):
                raise Stopped("tail owner interval mismatch")
        m = [index.ops[u]["cycles"] if index.ops[u]["pipe"] == "PIPE_M" else 0 for u in jobs[0]]
        v = [index.ops[u]["cycles"] if index.ops[u]["pipe"] == "PIPE_V" else 0 for u in jobs[0]]
        expected_work = [dict(M=14 * sum(m) + sum(m[a:b]), V=14 * sum(v) + sum(v[a:b]))
                         for a, b in zip(cuts, cuts[1:])]
        if (detail.get("per_core_compute_work_cycles") != expected_work or
                detail.get("minimax_compute_work_cycles") != max(max(x.values()) for x in expected_work)):
            raise Stopped("compute-work metadata mismatch")
        for problem in (2, 3):
            destination = folder / f"P{problem}"
            paths = dict(result=destination / "result.json", trace=destination / "trace.json",
                         log=destination / "result.log")
            argv = [python, "-B", (OFFICIAL / f"code/multicore_cut_evaluate_problem_{problem}.py").as_posix(),
                    graph.as_posix(), plan.as_posix(), "--config", CONFIG.as_posix(),
                    "--output", paths["result"].as_posix(), "--trace-output", paths["trace"].as_posix(),
                    "--log-output", paths["log"].as_posix()]
            eval_call = self.invoke("E0", f"{cid}-P{problem}", argv, destination)
            result = json.loads(paths["result"].read_bytes())
            if (result.get("scene") != "B" or (problem == 3 and result.get("problem") != 3) or
                    result.get("num_cores") != 5 or result.get("makespan", 0) <= 0 or
                    (problem == 3 and result.get("cache_mode") != "read_only")):
                raise Stopped("official E0 result identity mismatch: " + cid)
            evaluation = dict(evaluation_id=eval_call["call_id"], construction_id=cid, case_id=case,
                variant="wave_tail", problem=f"P{problem}", makespan_cycles=result["makespan"],
                call=eval_call, artifacts={name: compress(path) for name, path in paths.items()})
            with self.lock:
                self.evaluations.append(evaluation)
                construction["evaluation_ids"].append(evaluation["evaluation_id"])
                self.save()
            if problem == 3:
                evaluation["p3_audit"] = audit_p3(graph, result, detail)
                with self.lock:
                    self.save()
                if not evaluation["p3_audit"]["passed"]:
                    raise Stopped("P3 cache/workload audit failed: " + json.dumps(evaluation["p3_audit"]))

    def worker(self):
        while True:
            with self.lock:
                if self.stop.is_set() or not self.queue:
                    return
                case = self.queue.popleft()
                self.info["active_case_ids"] = [case]
                self.save()
            try:
                self.case(case)
            except Exception as exc:
                with self.lock:
                    self.stop.set()
                    self.info.setdefault("failures", []).append(dict(case_id=case, type=type(exc).__name__, reason=str(exc)))
                    self.save()
            finally:
                with self.lock:
                    self.info["active_case_ids"].remove(case)
                    self.save()

    def run(self):
        threads = []
        try:
            self.info["identity"] = preflight(self.args.graph_dir)
            self.info["environment"], self.info["environment_missing_reasons"] = live_environment()
            self.info["environment"]["workers"] = 1
            self.info["environment_inventory_source"] = dict(acquired_at=utc(), scope="live host inventory")
            self.save()
            threads = [threading.Thread(target=self.worker, name="tail-worker")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            if self.info.get("failures") or self.queue or len(self.constructions) != 1 or len(self.evaluations) != 2:
                self.info.update(status="stopped", stop_reason=self.info.get("failures", [{}])[0].get(
                    "reason", "batch ended before all prescribed calls"))
            else:
                self.info.update(status="ok", stop_reason="one guarded tail plan and two external E0s completed")
        except (Exception, KeyboardInterrupt, SystemExit) as exc:
            with self.lock:
                self.stop.set()
            for thread in threads:
                if thread.ident is not None and thread.is_alive():
                    thread.join()
            self.info.update(status="stopped", stop_reason=str(exc), failure_type=type(exc).__name__)
        finally:
            # Preserve every completed result/trace/log even when its sibling failed.
            self.info["partial_outputs"] = []
            unsafe_cases = {c["call_id"][:3] for c in self.calls if c.get("cleanup_failure")}
            for name in ("result.json", "trace.json", "result.log"):
                for path in sorted(self.out.rglob(name)):
                    if path.relative_to(self.out).parts[0] in unsafe_cases:
                        self.info["partial_outputs"].append(dict(path=relative(path), sealed=False,
                            reason="owned child cleanup was not confirmed"))
                    else:
                        try:
                            self.info["partial_outputs"].append(dict(**compress(path), sealed=True))
                        except (OSError, ValueError) as exc:
                            self.info["partial_outputs"].append(dict(path=relative(path), sealed=False,
                                failure_type=type(exc).__name__))
                            self.info.update(status="stopped", stop_reason="partial output preservation failed")
            referenced = {a["path"] for e in self.evaluations for a in e["artifacts"].values()}
            referenced.update(a["path"] for a in self.info["partial_outputs"])
            for name in ("result.json.gz", "trace.json.gz", "result.log.gz"):
                for path in sorted(self.out.rglob(name)):
                    if relative(path) in referenced:
                        continue
                    try:
                        raw = gzip.decompress(path.read_bytes())
                        self.info["partial_outputs"].append(dict(**artifact(path), raw_sha256=digest(raw),
                            raw_bytes=len(raw), gzip_bytes=path.stat().st_size, sealed=True))
                    except (OSError, ValueError, EOFError) as exc:
                        self.info["partial_outputs"].append(dict(path=relative(path), sealed=False,
                            failure_type=type(exc).__name__))
                        self.info.update(status="stopped", stop_reason="partial archive verification failed")
            if time.perf_counter() - self.started > BUDGET["batch_seconds"]:
                self.info.update(status="stopped", stop_reason="batch wall cap exceeded; no further calls")
            self.info["finished_at"] = utc()
            self.save()
        print(json.dumps(dict(status=self.info["status"], calls=self.info["calls"],
            elapsed_seconds=self.info["elapsed_seconds"], stop_reason=self.info["stop_reason"])), flush=True)
        return 0 if self.info["status"] == "ok" else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graph-dir", type=Path, default=Path("../huaweicup2026/data/raw/a/official-cases/data"))
    ap.add_argument("--output", type=Path, default=Path(OUT))
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--concurrent-work", choices=("P2", "P1", "P1+P2", "none-reported", "unknown"))
    args = ap.parse_args()
    os.chdir(ROOT)
    if (args.output.is_absolute() or args.graph_dir.is_absolute() or ".." in args.output.parts or
            not args.output.parts or args.output.parts[0] != "results" or
            not args.output.resolve().is_relative_to((ROOT / "results").resolve())):
        ap.error("use project-relative graph directory and new in-project results output")
    if args.check_only:
        identity = preflight(args.graph_dir)
        print(json.dumps(dict(verified_files=len(identity["verified_files"]), solver_commit=SOLVER_COMMIT,
            runner_commit=identity["runner_commit"], baselines=list(identity["baseline_refs"]),
            planned_calls=dict(solver=1, E0=2, E1=0, E2=0), calls_executed=0)))
        return 0
    if args.concurrent_work is None:
        ap.error("actual run requires --concurrent-work")
    return TailPilot(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
