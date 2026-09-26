"""Portable fixed join candidate handoff. Check-only never constructs or evaluates."""
from __future__ import annotations

import argparse
import gzip
import json
import os
import ctypes
import platform
import re
import signal
from pathlib import Path
import subprocess
import sys
import time

from benchmark import (ROOT, OFFICIAL, CONFIG, Pilot, Stopped, artifact, compress,
                       git, MANIFEST, digest, relative, sha, utc, write_json)
from export_feed import baseline

SOLVER_COMMIT = "071d538ddae05ceda519d3b1b0844e987da908d5"
HELPER_COMMIT = "39e9c8d8a78e384855ffbfbf41a2dec4d4a7e5a0"
CASES = ("069", "071", "005", "086")
VARIANT = "dag_join_list"
BUDGET = dict(workers=1, cold_solver_limit=4, E0_limit=8, E1_limit=0,
              E2_limit=0, solver_seconds=30, E0_seconds=60, batch_seconds=600,
              dispatch_until_seconds=540, retries=0)


def preflight(graph_dir):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    needed_graphs = {f"data/case_{case}.json" for case in CASES}
    verified = []
    for item in manifest["files"]:
        name = item["path"]
        if not (name.startswith("code/") or name == "data/config.txt" or name in needed_graphs):
            continue
        path = graph_dir / Path(name).name if name in needed_graphs else OFFICIAL / name
        raw = path.read_bytes()
        if digest(raw) != item["sha256"] or len(raw) != item["bytes"]:
            raise ValueError("official input/source mismatch: " + name)
        verified.append(dict(manifest_path=name, actual_path=path.as_posix(), sha256=digest(raw), bytes=len(raw)))
    if {x["manifest_path"] for x in verified if x["manifest_path"] in needed_graphs} != needed_graphs:
        raise ValueError("source manifest does not cover all four cases")
    code = "".join(f"{x['path']}\t{x['sha256']}\n" for x in sorted(manifest["files"], key=lambda x:x["path"])
                   if x["path"].startswith("code/"))
    if digest(code.encode()) != manifest["official_code_hash"]:
        raise ValueError("official aggregate mismatch")
    result = dict(official_code_hash=manifest["official_code_hash"], source_manifest=artifact(MANIFEST),
                  config_sha256=sha(CONFIG), verified_files=verified, implementation=[])
    for name in ("src/q3_yuanzhifang/join_list.py", "src/q3_yuanzhifang/dag_list.py",
                 "src/q3_yuanzhifang/active_stages.py", "src/q3_yuanzhifang/construct.py",
                 "src/q3_yuanzhifang/baseline.py",
                 "docs/a/q3-yuanzhifang/JOIN_LIST.md"):
        if Path(name).read_bytes() != git("show", SOLVER_COMMIT + ":" + name):
            raise ValueError("join-aware DAG source/spec differs from frozen commit: " + name)
        result["implementation"].append(dict(path=name, sha256=sha(name)))
    for name in ("src/q3_yuanzhifang/benchmark.py", "src/q3_yuanzhifang/export_feed.py"):
        if Path(name).read_bytes() != git("show", HELPER_COMMIT + ":" + name):
            raise ValueError("frozen helper changed: " + name)
    template = "results/a/q3-yuanzhifang/pilot-20260924/board-feed-20260924T141108Z-unique-plans.json"
    if Path(template).read_bytes() != git("show", "46c709228c0a83e09c13b008e919d135100b938e:" + template):
        raise ValueError("fixed export template missing or changed")
    result["export_template"] = artifact(template)
    head = git("rev-parse", "HEAD").decode().strip()
    for name in ("src/q3_yuanzhifang/portable_join_benchmark.py", "src/q3_yuanzhifang/portable_join_export.py"):
        if Path(name).read_bytes() != git("show", head + ":" + name):
            raise ValueError("join-aware DAG runner/exporter must be committed: " + name)
    result.update(solver_commit=SOLVER_COMMIT, runner_commit=head,
                  runner_sha256=sha(__file__), helper_commit=HELPER_COMMIT,
                  helper_sha256=sha("src/q3_yuanzhifang/benchmark.py"))
    result["baseline_refs"] = {case: baseline(case, dict(
        graph_sha256=sha(graph_dir / f"case_{case}.json"),
        config_sha256=result["config_sha256"], official_sha256=result["official_code_hash"]))
        for case in CASES}
    return result


def live_environment():
    """Acquire this host's public hardware description, without credentials/hostnames."""
    cpu, ram = platform.processor().strip() or None, None
    reasons = {"provenance.environment.peak_rss_bytes": "Peak RSS was not instrumented; not inferred from total RAM."}
    try:
        if os.name == "nt":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                cpu = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip() or None

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                    (name, ctypes.c_ulonglong) for name in (
                        "total_phys", "avail_phys", "total_page", "avail_page",
                        "total_virtual", "avail_virtual", "avail_extended")]
            value = MemoryStatus()
            value.length = ctypes.sizeof(value)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
                ram = value.total_phys
        elif sys.platform == "darwin":
            def sysctl(name):
                return subprocess.check_output(["sysctl", "-n", name], timeout=3,
                                               stderr=subprocess.DEVNULL).decode().strip()
            try:
                cpu = sysctl("machdep.cpu.brand_string") or cpu
            except (OSError, subprocess.SubprocessError):
                pass
            ram = int(sysctl("hw.memsize"))
        else:
            info = Path("/proc/cpuinfo")
            if info.exists():
                for line in info.read_text(errors="replace").splitlines():
                    if line.split(":", 1)[0].strip() in ("model name", "Hardware"):
                        cpu = line.split(":", 1)[1].strip() or cpu
                        break
            try:
                ram = int(os.sysconf("SC_PHYS_PAGES")) * int(os.sysconf("SC_PAGE_SIZE"))
            except (AttributeError, OSError, ValueError):
                pass
    except (OSError, ValueError, subprocess.SubprocessError):
        # Unavailable inventory remains unknown; it never becomes fake zero.
        pass
    if cpu is None:
        reasons["provenance.environment.cpu"] = "Live platform inventory did not provide a CPU model."
    if ram is None or ram <= 0:
        ram = None
        reasons["provenance.environment.ram_bytes"] = "Live physical RAM query was unavailable on this host."
    env = dict(os=platform.platform(), cpu=cpu,
               gpu="none used; installed adapters not inventoried",
               ram_bytes=ram, python=platform.python_version(),
               dependencies="Python standard library solver/E0; project environment prepared with uv sync --locked; "
                            "uv.lock sha256=" + sha("uv.lock"),
               threads=1, workers=1, peak_rss_bytes=None)
    return env, reasons


def stop_owned_process(process):
    """Terminate only this call's process tree/group and expose cleanup failure."""
    receipt = dict(ok=False, mechanism="taskkill /T /F" if os.name == "nt" else "own POSIX process group SIGKILL")
    try:
        if os.name == "nt":
            killed = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                    capture_output=True, timeout=5)
            receipt["tool_exit_code"] = killed.returncode
            process.wait(timeout=3)
            receipt["ok"] = killed.returncode == 0
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=3)
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                receipt["ok"] = True
            else:
                receipt["failure"] = "Owned process group still exists after termination; no new dispatch."
    except (OSError, subprocess.SubprocessError) as exc:
        receipt["failure_type"] = type(exc).__name__
    finally:
        if process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=2)
            except (OSError, subprocess.SubprocessError) as exc:
                receipt["root_cleanup_failure_type"] = type(exc).__name__
        receipt["root_exit_code"] = process.returncode
    return receipt


class PortableJoin(Pilot):
    def __init__(self, args):
        self.args, self.out = args, args.output
        self.out.mkdir(parents=True, exist_ok=False)
        self.started = time.perf_counter()
        self.calls, self.constructions, self.evaluations = [], [], []
        (self.out / ".gitattributes").write_bytes(b"# Preserve exact raw outputs and receipts.\n* -text\n")
        run_id = args.producer_session.replace("/", "-") + "-portable-join-" + args.run_label
        self.info = dict(schema="q3-portable-join-v1", run_id=run_id,
                         producer_session=args.producer_session, run_label=args.run_label,
                         runtime_id="portable-join-" + digest(run_id.encode())[:20],
                         started_at=utc(), budget=BUDGET, working_directory=".", status="running",
                         argv=[relative(sys.executable), "-B", relative(__file__),
                               "--graph-dir", args.graph_dir.as_posix(), "--output", args.output.as_posix(),
                               "--producer-session", args.producer_session, "--run-label", args.run_label],
                         cold_start_definition="Fresh Python process per call; OS file cache not flushed",
                         offline_costs="Fixed candidate developed and tested in prior separately preserved Windows batches. "
                         "No training, compilation, precomputed plan or internal evaluator is part of this method. "
                         "Each measured solver includes graph indexing, chain condensation and arithmetic join placements. "
                         "Environment preparation via uv sync --locked occurs before this batch; its duration is not measured here.")


    def invoke(self, kind, call_id, argv, folder):
        elapsed = time.perf_counter() - self.started
        limit = BUDGET["cold_solver_limit" if kind == "solver" else "E0_limit"]
        if elapsed >= BUDGET["dispatch_until_seconds"]:
            raise Stopped("join-aware DAG dispatch cutoff reached; no new call")
        if sum(call["kind"] == kind for call in self.calls) >= limit:
            raise Stopped("join-aware DAG call cap reached; no new call")
        folder.mkdir(parents=True, exist_ok=True)
        stdout, stderr = folder / "stdout.txt", folder / "stderr.txt"
        call = dict(call_id=call_id, kind=kind, argv=argv, working_directory=".",
                    started_at=utc(), batch_elapsed_at_dispatch=elapsed, status="running",
                    timeout_seconds=min(BUDGET["solver_seconds" if kind == "solver" else "E0_seconds"],
                                        BUDGET["batch_seconds"] - elapsed - 10))
        self.calls.append(call)
        self.save()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
                   PYTHONHASHSEED="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                   MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
        start = time.perf_counter()
        try:
            with stdout.open("wb") as out, stderr.open("wb") as err:
                process = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=out, stderr=err,
                                           start_new_session=os.name != "nt")
                call["pid"] = process.pid
                try:
                    call["exit_code"] = process.wait(timeout=call["timeout_seconds"])
                    call["status"] = "ok" if call["exit_code"] == 0 else "failed"
                except subprocess.TimeoutExpired:
                    call["status"] = "timeout"
                    call["cleanup"] = stop_owned_process(process)
                    call["exit_code"] = process.returncode
                    if not call["cleanup"]["ok"]:
                        call["cleanup_failure"] = True
                except (KeyboardInterrupt, SystemExit) as exc:
                    call.update(status="failed", failure_type=type(exc).__name__)
                    call["cleanup"] = stop_owned_process(process)
                    call["exit_code"] = process.returncode
                    if not call["cleanup"]["ok"]:
                        call["cleanup_failure"] = True

        except OSError as exc:
            call.update(status="failed", exit_code=None, failure_type=type(exc).__name__)
        finally:
            call.update(wall_seconds=time.perf_counter() - start, finished_at=utc())
            if call.get("cleanup_failure"):
                # A surviving child may still have these handles. Retain raw
                # files without claiming a stable hash or deleting them.
                call["unsealed_outputs"] = [relative(stdout), relative(stderr)]
            else:
                try:
                    call["stdout"] = compress(stdout)
                    call["stderr"] = compress(stderr)
                except OSError as exc:
                    call.update(status="failed", preservation_failure_type=type(exc).__name__)
                    call["unsealed_outputs"] = [relative(p) for p in (stdout, stderr) if p.exists()]
            write_json(folder / "call.json", call)
            self.save()
        print(json.dumps({k: call[k] for k in ("call_id", "status", "wall_seconds")}), flush=True)
        if call["status"] != "ok":
            raise Stopped("first unsuccessful call: " + call_id)
        return call

    def run(self):
        try:
            self.info["identity"] = preflight(self.args.graph_dir)
            self.info["environment"], self.info["environment_missing_reasons"] = live_environment()
            self.info["environment_inventory_source"] = dict(acquired_at=utc(), scope="Live acquisition in this batch; no prior host inventory reused")
            self.save()
            for case in CASES:
                folder = self.out / case / VARIANT
                graph = self.args.graph_dir / f"case_{case}.json"
                plan = folder / f"case_{case}_multicore_res.json"
                cid = f"{case}-{VARIANT}"
                argv = [relative(sys.executable), "-B", "-m", "src.q3_yuanzhifang.join_list",
                        graph.as_posix(), "--cores", "5", "--config", CONFIG.as_posix(), "--output", plan.as_posix()]
                call = self.invoke("solver", cid, argv, folder / "solver")
                value = json.loads(plan.read_bytes())
                if set(value) != {"node_to_subgraph", "core_schedules"} or len(value["core_schedules"]) != 5:
                    raise Stopped("invalid plan fields/core count")
                detail = json.loads(gzip.decompress((ROOT / call["stdout"]["path"]).read_bytes()))
                c = dict(construction_id=cid, case_id=case, variant=VARIANT, cores=5, requested_cores=5,
                         active_cores=sum(bool(s) for s in value["core_schedules"]),
                         graph_sha256=sha(graph), plan=artifact(plan), solver=call, detail=detail,
                         alias_of=None, evaluation_ids=[])
                self.constructions.append(c)
                self.save()
                if not detail.get("guard") or detail.get("selected") != VARIANT:
                    raise Stopped("join-aware DAG guard failed; no E0 on fallback")
                for problem in (2, 3):
                    destination = folder / f"P{problem}"
                    paths = dict(result=destination / "result.json", trace=destination / "trace.json",
                                 log=destination / "result.log")
                    argv = [relative(sys.executable), "-B",
                            (OFFICIAL / f"code/multicore_cut_evaluate_problem_{problem}.py").as_posix(),
                            graph.as_posix(), plan.as_posix(), "--config", CONFIG.as_posix(),
                            "--output", paths["result"].as_posix(), "--trace-output", paths["trace"].as_posix(),
                            "--log-output", paths["log"].as_posix()]
                    call = self.invoke("E0", f"{cid}-P{problem}", argv, destination)
                    result = json.loads(paths["result"].read_bytes())
                    if result.get("scene") != "B" or result.get("num_cores") != 5 or result["makespan"] <= 0:
                        raise Stopped("official result identity mismatch")
                    if problem == 3 and (result.get("problem") != 3 or result.get("cache_mode") != "read_only"):
                        raise Stopped("P3 cache identity mismatch")
                    e = dict(evaluation_id=call["call_id"], construction_id=cid, case_id=case,
                             variant=VARIANT, problem=f"P{problem}", makespan_cycles=result["makespan"],
                             call=call, artifacts={name: compress(path) for name, path in paths.items()})
                    self.evaluations.append(e)
                    c["evaluation_ids"].append(e["evaluation_id"])
                    self.save()
            self.info.update(status="ok", stop_reason="four guarded join-aware DAG constructions and eight external E0s completed")
        except Exception as exc:
            self.info.update(status="stopped", stop_reason=str(exc), failure_type=type(exc).__name__)
        finally:
            self.info["partial_outputs"] = []
            for name in ("result.json", "trace.json", "result.log"):
                for path in sorted(self.out.rglob(name)):
                    if any(c.get("cleanup_failure") for c in self.calls):
                        self.info["partial_outputs"].append(dict(path=relative(path), sealed=False,
                            reason="Subprocess cleanup not confirmed; preserve raw file without a stable-hash claim."))
                    else:
                        try:
                            self.info["partial_outputs"].append(compress(path))
                        except OSError as exc:
                            self.info["partial_outputs"].append(dict(path=relative(path), sealed=False,
                                failure_type=type(exc).__name__))
                            self.info.update(status="stopped", stop_reason="partial output preservation failed")
            if time.perf_counter() - self.started > BUDGET["batch_seconds"]:
                self.info.update(status="stopped", stop_reason="batch wall cap exceeded during final preservation; no new call")
            self.info["finished_at"] = utc()
            self.save()
        print(json.dumps(dict(status=self.info["status"], calls=self.info["calls"],
                              started_at=self.info["started_at"], finished_at=self.info["finished_at"],
                              elapsed_seconds=self.info["elapsed_seconds"], stop_reason=self.info["stop_reason"])), flush=True)
        return 0 if self.info["status"] == "ok" else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graph-dir", type=Path, default=Path("data/raw/a/official/data"))
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--producer-session", required=True, help="Actual executing session, login/s-ID")
    ap.add_argument("--run-label", required=True, help="Fresh human-readable identifier; reuse is forbidden")
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()
    os.chdir(ROOT)
    if (args.output.is_absolute() or ".." in args.output.parts or not args.output.parts
            or args.output.parts[0] != "results" or args.graph_dir.is_absolute()
            or not args.output.resolve().is_relative_to((ROOT / "results").resolve())):
        ap.error("output must be a new project-relative results path; graph-dir must be project-relative")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*/s-[a-z0-9-]+", args.producer_session) or len(args.producer_session)>100:
        ap.error("producer-session must identify the actual lowercase login/s-ID, at most 100 characters")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,39}", args.run_label):
        ap.error("run-label must be a new alphanumeric/hyphen/underscore label, at most 40 characters")
    if args.output.exists():
        ap.error("output already exists; never overwrite or resume a batch")
    if args.check_only:
        identity = preflight(args.graph_dir)
        print(json.dumps(dict(verified_files=len(identity["verified_files"]), solver_commit=SOLVER_COMMIT,
                              runner_commit=identity["runner_commit"], baselines=list(identity["baseline_refs"]),
                              planned_calls=dict(solver=4, E0=8, E1=0, E2=0), calls_executed=0,
                              environment_acquisition="deferred to actual run on executing host")))
        return 0
    return PortableJoin(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
