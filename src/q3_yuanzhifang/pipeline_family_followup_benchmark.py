"""Fill only missing pipeline-family cells, reusing two byte-verified P2s."""
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

SOLVER_COMMIT = "6bae8dfa317bc71226068344b59dd65d2612c32b"
HELPER_COMMIT = "39e9c8d8a78e384855ffbfbf41a2dec4d4a7e5a0"
RUNTIME_HELPER_COMMIT = "60477a382514cb6e97bfd8ea1bb560fda1594c06"
OUT = "results/a/q3-yuanzhifang/pipeline-family-followup-20260925"
SOURCE = "results/a/q3-yuanzhifang/pipeline-family-20260925"
SOURCE_COMMIT = "ba3f848492b213d5f3ec93cf12b0da0cc79eea8f"
REUSE = ("044", "046")
CASES = ("044", "046", "067", "073", "083", "092")
VARIANT = "pipeline_stages"
BUDGET = dict(workers=2, cold_solver_limit=4, E0_limit=10, E1_limit=0,
              E2_limit=0, per_call_seconds=30, batch_seconds=300,
              dispatch_until_seconds=270, retries=0)
TEMPLATE = "results/a/q3-yuanzhifang/pilot-20260924/board-feed-20260924T141108Z-unique-plans.json"
DEPENDENCIES = {
    "src/q3_yuanzhifang/pipeline_stages.py": SOLVER_COMMIT,
    "src/q3_yuanzhifang/active_stages.py": "bb7a7e8702b636a0a9dda33d070daad5f4d7c212",
    "src/q3_yuanzhifang/construct.py": "8f8bfce73b0b8e350de1dc40af21f3787c8ac8d6",
    "src/q3_yuanzhifang/baseline.py": "8f8bfce73b0b8e350de1dc40af21f3787c8ac8d6",
}


def source_bytes(path):
    raw = (ROOT / path).read_bytes()
    if raw != git("show", SOURCE_COMMIT + ":" + path):
        raise ValueError("source commit byte mismatch: " + path)
    return raw


def source_ref(ref):
    packed = source_bytes(ref["path"])
    if digest(packed) != ref["sha256"]:
        raise ValueError("source artifact hash mismatch: " + ref["path"])
    if ref["path"].endswith(".gz"):
        raw = gzip.decompress(packed)
        if digest(raw) != ref["raw_sha256"] or len(raw) != ref["raw_bytes"]:
            raise ValueError("source raw-byte mismatch: " + ref["path"])
        return raw
    return packed


def recovered_identity(graph_dir, identity):
    receipt = json.loads(source_bytes(SOURCE + "/export-receipt.json"))
    manifest = json.loads(source_ref(receipt["sealed_manifest"]))
    ledger = json.loads(source_ref(receipt["sealed_call_ledger"]))
    if (manifest["identity"]["runner_commit"] != "63810a050187049357975ac81b7e6009e1d570b3" or
            manifest["identity"]["solver_commit"] != SOLVER_COMMIT or
            manifest["identity"]["config_sha256"] != identity["config_sha256"] or
            manifest["identity"]["official_code_hash"] != identity["official_code_hash"] or
            manifest["calls"] != dict(solver=2, E0=2, E1=0, E2=0)):
        raise ValueError("source batch identity/count mismatch")
    if source_bytes(SOURCE + "/manifest.json") != source_ref(receipt["sealed_manifest"]):
        raise ValueError("source live/sealed manifest differs")
    if source_bytes(SOURCE + "/call-ledger.json") != source_ref(receipt["sealed_call_ledger"]):
        raise ValueError("source live/sealed ledger differs")
    source_bytes(SOURCE + "/board-feed-20260924T190507Z-pipeline-family.json")
    recovered = {}
    for case in REUSE:
        construction = next(c for c in manifest["constructions"] if c["case_id"] == case)
        plan = json.loads(source_ref(construction["plan"]))
        if (set(plan) != {"node_to_subgraph", "core_schedules"} or len(plan["core_schedules"]) != 5 or
                construction["detail"].get("guard") is not True or
                construction["detail"].get("selected") != VARIANT or
                construction["graph_sha256"] != sha(graph_dir / f"case_{case}.json")):
            raise ValueError("recovered plan/guard/graph mismatch: " + case)
        solver, p2 = (next(c for c in ledger if c["call_id"] == cid) for cid in
                      (f"{case}-{VARIANT}", f"{case}-{VARIANT}-P2"))
        for call in (solver, p2):
            if call["status"] != "ok" or call["exit_code"] != 0 or call["wall_seconds"] < 0:
                raise ValueError("source call did not finish successfully: " + case)
            for key in ("stdout", "stderr"):
                source_ref(call[key])
        graph = (graph_dir / f"case_{case}.json").as_posix()
        plan_path = construction["plan"]["path"]
        expected_solver = [relative(sys.executable), "-B", "-m", "src.q3_yuanzhifang.pipeline_stages",
            graph, "--cores", "5", "--config", CONFIG.as_posix(), "--output", plan_path]
        expected_p2 = [relative(sys.executable), "-B", (OFFICIAL / "code/multicore_cut_evaluate_problem_2.py").as_posix(),
            graph, plan_path, "--config", CONFIG.as_posix(), "--output", SOURCE + f"/{case}/{VARIANT}/P2/result.json",
            "--trace-output", SOURCE + f"/{case}/{VARIANT}/P2/trace.json",
            "--log-output", SOURCE + f"/{case}/{VARIANT}/P2/result.log"]
        if solver["argv"] != expected_solver or p2["argv"] != expected_p2:
            raise ValueError("source command identity mismatch: " + case)
        if (json.loads(source_bytes(SOURCE + f"/{case}/{VARIANT}/solver/call.json")) != solver or
                json.loads(source_bytes(SOURCE + f"/{case}/{VARIANT}/P2/call.json")) != p2):
            raise ValueError("source call receipt differs from ledger: " + case)
        refs = {name: next(x for x in manifest["partial_outputs"] if x["path"] ==
            SOURCE + f"/{case}/{VARIANT}/P2/{filename}.gz")
            for name, filename in (("result", "result.json"), ("trace", "trace.json"), ("log", "result.log"))}
        if any(x.get("sealed") is not True for x in refs.values()):
            raise ValueError("source P2 output was not sealed")
        result = json.loads(source_ref(refs["result"]))
        for name in ("trace", "log"):
            source_ref(refs[name])
        # P2 has no `problem` field in the official result. P3 is checked below.
        if (result.get("scene") != "B" or result.get("num_cores") != 5 or
                not isinstance(result.get("makespan"), int) or result["makespan"] <= 0 or
                result.get("bandwidth_bytes_per_cycle") != 60 or
                result.get("capacity_bytes") != {"L1": 524288, "UB": 131072} or
                result.get("cross_core_copy_delay_cycles") != 500 or
                result.get("input_graph") != f"case_{case}.json" or
                result.get("input_plan") != f"case_{case}_multicore_res.json"):
            raise ValueError("source P2 official result identity mismatch: " + case)
        recovered[case] = dict(source_commit=SOURCE_COMMIT, source_run_id=manifest["run_id"],
            construction=construction, P2=dict(evaluation_id=p2["call_id"], call=p2,
                artifacts=refs, makespan_cycles=result["makespan"]))
    return dict(source_manifest=receipt["sealed_manifest"], source_call_ledger=receipt["sealed_call_ledger"],
                cases=recovered)


def result_header(result, problem, cores=5):
    return (result.get("scene") == "B" and result.get("num_cores") == cores and
            isinstance(result.get("makespan"), int) and result["makespan"] > 0 and
            (problem == 2 or (result.get("problem") == 3 and result.get("cache_mode") == "read_only")))


def header_regression(recovered):
    p2 = json.loads(source_ref(recovered["cases"]["044"]["P2"]["artifacts"]["result"]))
    p3_path = "results/a/q3-yuanzhifang/pipeline-20260924/044/pipeline_stages/P3/result.json.gz"
    packed = (ROOT / p3_path).read_bytes()
    if packed != git("show", "e6b5500dcbf3818034804168ee79d0f65c16706b:" + p3_path):
        raise ValueError("fixed P3 regression sample differs")
    p3 = json.loads(gzip.decompress(packed))
    if "problem" in p2 or not result_header(p2, 2) or not result_header(p3, 3, cores=4) or result_header(p2, 3):
        raise ValueError("P2/P3 header regression failed")


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
        raise ValueError("source manifest does not cover all six graphs")
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
    for name in ("src/q3_yuanzhifang/pipeline_family_benchmark.py",
                 "src/q3_yuanzhifang/pipeline_family_export.py",
                 "docs/a/q3-yuanzhifang/PIPELINE_FAMILY.md"):
        if Path(name).read_bytes() != git("show", SOURCE_COMMIT + ":" + name):
            raise ValueError("original batch code differs from source commit: " + name)
    for name in ("src/q3_yuanzhifang/pipeline_family_followup_benchmark.py",
                 "src/q3_yuanzhifang/pipeline_family_followup_export.py",
                 "docs/a/q3-yuanzhifang/PIPELINE_FAMILY_FOLLOWUP.md"):
        if Path(name).read_bytes() != git("show", head + ":" + name):
            raise ValueError("followup runner/export/docs must be committed: " + name)
    result = dict(official_code_hash=manifest["official_code_hash"], source_manifest=artifact(MANIFEST),
                  config_sha256=sha(CONFIG), verified_files=verified, implementation=implementation,
                  solver_commit=SOLVER_COMMIT, runner_commit=head, runner_sha256=sha(__file__),
                  helper_commit=HELPER_COMMIT, runtime_helper=dict(commit=RUNTIME_HELPER_COMMIT, **artifact(helper)),
                  export_template=artifact(TEMPLATE))
    result["baseline_refs"] = {case: baseline(case, dict(
        graph_sha256=sha(graph_dir / f"case_{case}.json"), config_sha256=result["config_sha256"],
        official_sha256=result["official_code_hash"])) for case in CASES}
    result["recovered"] = recovered_identity(graph_dir, result)
    header_regression(result["recovered"])
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


class PipelineFamilyPilot(Pilot):
    def __init__(self, args):
        super().__init__(args)
        (self.out / ".gitattributes").write_bytes(b"# Preserve exact process/receipt bytes.\n* -text\n")
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.queue = deque(CASES)
        self.info.update(schema="q3-pipeline-family-followup-v1", run_id="yuanzhifang-q3-pipeline-family-followup-20260925",
                         budget=BUDGET, argv=[relative(sys.executable), "-B", relative(__file__),
                         "--graph-dir", args.graph_dir.as_posix(), "--output", args.output.as_posix(),
                         "--concurrent-work", args.concurrent_work],
                         resource_context=dict(concurrent_work=args.concurrent_work, workers=2,
                         exclusive_host_claim=False, process_priority="BELOW_NORMAL_PRIORITY_CLASS",
                         dispatch_gate="global lock; >=2 GiB available RAM and >=2 GiB free output disk"),
                         resource_checks=[], concurrent_case_workers=2,
                         offline_costs="044/046 cold plans and P2 evaluations are verified reuse from frozen prior batch; "
                         "no new calls for those cells. No training, compilation or case-specific precomputation in this batch. "
                         "Prior algorithm development and environment preparation are outside measured cold calls. "
                         "Each fresh Python solver call includes graph read/indexing, construction, validation and plan write.")

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
        cid = f"{case}-{VARIANT}"
        folder = self.out / case / VARIANT
        graph = self.args.graph_dir / f"case_{case}.json"
        reused = case in REUSE
        plan = (Path(self.info["identity"]["recovered"]["cases"][case]["construction"]["plan"]["path"])
                if reused else folder / f"case_{case}_multicore_res.json")
        python = relative(sys.executable)
        if reused:
            prior = self.info["identity"]["recovered"]["cases"][case]
            construction = dict(prior["construction"], reused_from=SOURCE_COMMIT,
                                evaluation_ids=[prior["P2"]["evaluation_id"]])
            with self.lock:
                self.info.setdefault("reused_constructions", []).append(construction)
                self.info.setdefault("reused_evaluations", []).append(prior["P2"])
                self.save()
        else:
            solver_argv = [python, "-B", "-m", "src.q3_yuanzhifang.pipeline_stages", graph.as_posix(),
                           "--cores", "5", "--config", CONFIG.as_posix(), "--output", plan.as_posix()]
            call = self.invoke("solver", cid, solver_argv, folder / "solver")
            value = json.loads(plan.read_bytes())
            if set(value) != {"node_to_subgraph", "core_schedules"} or len(value["core_schedules"]) != 5:
                raise Stopped("invalid plan fields/core count: " + cid)
            detail = json.loads(gzip.decompress((ROOT / call["stdout"]["path"]).read_bytes()))
            construction = dict(construction_id=cid, case_id=case, variant=VARIANT, cores=5,
                requested_cores=5, active_cores=sum(bool(s) for s in value["core_schedules"]),
                graph_sha256=sha(graph), plan=artifact(plan), solver=call, detail=detail,
                alias_of=None, evaluation_ids=[])
            with self.lock:
                self.constructions.append(construction)
                self.save()
            if not detail.get("guard") or detail.get("selected") != VARIANT:
                raise Stopped("pipeline structural guard failed; no E0 on fallback: " + cid)
        for problem in ((3,) if reused else (2, 3)):
            destination = folder / f"P{problem}"
            paths = dict(result=destination / "result.json", trace=destination / "trace.json",
                         log=destination / "result.log")
            argv = [python, "-B", (OFFICIAL / f"code/multicore_cut_evaluate_problem_{problem}.py").as_posix(),
                    graph.as_posix(), plan.as_posix(), "--config", CONFIG.as_posix(),
                    "--output", paths["result"].as_posix(), "--trace-output", paths["trace"].as_posix(),
                    "--log-output", paths["log"].as_posix()]
            eval_call = self.invoke("E0", f"{cid}-P{problem}", argv, destination)
            result = json.loads(paths["result"].read_bytes())
            if not result_header(result, problem):
                raise Stopped("official E0 result identity mismatch: " + cid)
            evaluation = dict(evaluation_id=eval_call["call_id"], construction_id=cid, case_id=case,
                variant=VARIANT, problem=f"P{problem}", makespan_cycles=result["makespan"],
                call=eval_call, artifacts={name: compress(path) for name, path in paths.items()})
            with self.lock:
                self.evaluations.append(evaluation)
                construction["evaluation_ids"].append(evaluation["evaluation_id"])
                self.save()

    def worker(self):
        while True:
            with self.lock:
                if self.stop.is_set() or not self.queue:
                    return
                case = self.queue.popleft()
                self.info["active_case_ids"] = sorted(set(self.info.get("active_case_ids", [])) | {case})
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
            self.info["environment"]["workers"] = 2
            self.info["environment_inventory_source"] = dict(acquired_at=utc(), scope="live host inventory")
            self.save()
            threads = [threading.Thread(target=self.worker, name=f"case-worker-{n}") for n in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            if (self.info.get("failures") or self.queue or len(self.evaluations) != 10 or
                    len(self.constructions) != 4 or len(self.info.get("reused_evaluations", [])) != 2):
                self.info.update(status="stopped", stop_reason=self.info.get("failures", [{}])[0].get(
                    "reason", "batch ended before all prescribed calls"))
            else:
                self.info.update(status="ok", stop_reason="four new cold plans, ten new E0s, two verified P2 reuses completed")
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
            recovered_cases=list(identity["recovered"]["cases"]),
            planned_calls=dict(solver=4, E0=10, E1=0, E2=0), calls_executed=0)))
        return 0
    if args.concurrent_work is None:
        ap.error("actual run requires --concurrent-work")
    return PipelineFamilyPilot(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
