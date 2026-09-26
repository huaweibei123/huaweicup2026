"""Frozen cold-setup pipeline: 044 k4, one cold construction and at most two E0s."""
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from benchmark import (ROOT, OFFICIAL, CONFIG, Pilot, Stopped, artifact, compress,
                       git, relative, sha, utc, write_json)
from export_feed import baseline
from portable_join_benchmark import live_environment, stop_owned_process
from benchmark import digest, MANIFEST
import ctypes

SOLVER_COMMIT = "f14e8f0ae38033e83d9f497301595b7568a55cb6"
HELPER_COMMIT = "39e9c8d8a78e384855ffbfbf41a2dec4d4a7e5a0"
OUT = "results/a/q3-yuanzhifang/pipeline-setup-followup-20260924"
CASES = ("044",)
VARIANT = "pipeline_cold_setup"
BUDGET = dict(workers=1, cold_solver_limit=1, E0_limit=2, E1_limit=0,
              E2_limit=0, per_call_seconds=30, batch_seconds=120,
              dispatch_until_seconds=90, retries=0)


CONTROL_COMMIT = "e6b5500dcbf3818034804168ee79d0f65c16706b"
CONTROL_FEED = "results/a/q3-yuanzhifang/pipeline-20260924/board-feed-20260924T155039Z-pipeline.json"
PIPELINE_COMMIT = "6bae8dfa317bc71226068344b59dd65d2612c32b"
RUNTIME_HELPER_COMMIT = "60477a382514cb6e97bfd8ea1bb560fda1594c06"


def fixed_control_artifact(ref, commit):
    path = ROOT / ref["path"]
    raw = path.read_bytes()
    if raw != git("show", commit + ":" + ref["path"]) or digest(raw) != ref["sha256"]:
        raise ValueError("fixed control artifact differs: " + ref["path"])
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
        if ref.get("raw_sha256") and digest(raw) != ref["raw_sha256"]:
            raise ValueError("control raw-byte hash differs: " + ref["path"])
    return raw


def core_ownership(plan):
    if set(plan) != {"node_to_subgraph", "core_schedules"} or len(plan["core_schedules"]) != 4:
        raise ValueError("plan requires exactly two fields and four core entries")
    owners = {}
    for core, order in enumerate(plan["core_schedules"]):
        for subgraph in order:
            if subgraph in owners:
                raise ValueError("subgraph occurs more than once in core schedules")
            owners[subgraph] = core
    mapping = plan["node_to_subgraph"]
    if set(mapping.values()) != set(owners):
        raise ValueError("scheduled subgraph set differs from assigned subgraph set")
    return {op: owners[subgraph] for op, subgraph in mapping.items()}


def control_reference(case, identity, graph_dir):
    feed = json.loads(fixed_control_artifact(artifact(CONTROL_FEED), CONTROL_COMMIT))
    rows = [row for row in feed["records"] if row["case_id"] == case and row["cores"] == 4]
    if len(rows) != 2 or {row["problem"] for row in rows} != {"P2", "P3"}:
        raise ValueError("fixed pipeline control must include both original P2/P3 attempts")
    refs = {}
    plan_hashes = set()
    for row in rows:
        arts = row["artifacts"]
        for ref in arts.values():
            fixed_control_artifact(ref, CONTROL_COMMIT)
        result = json.loads(fixed_control_artifact(arts["result"], CONTROL_COMMIT))
        plan = json.loads(fixed_control_artifact(arts["plan"], CONTROL_COMMIT))
        core_ownership(plan)
        expected = dict(graph_sha256=sha(graph_dir / f"case_{case}.json"),
            config_sha256=identity["config_sha256"], official_sha256=identity["official_code_hash"],
            plan_sha256=arts["plan"]["sha256"])
        if (row["status"] != "ok" or row["evaluator"]["route"] != "E0"
                or row["identity"] != expected or row["metrics"]["makespan_cycles"] != 40927
                or result.get("scene") != "B" or result.get("num_cores") != 4 or result.get("makespan") != 40927):
            raise ValueError("fixed control identity/result mismatch: " + row["problem"])
        if row["problem"] == "P3" and (result.get("problem") != 3 or result.get("cache_mode") != "read_only"):
            raise ValueError("fixed control cache semantics mismatch")
        refs[row["problem"]] = dict(attempt_id=row["attempt_id"], identity=expected,
            makespan_cycles=40927, artifacts=arts)
        plan_hashes.add(arts["plan"]["sha256"])
    if len(plan_hashes) != 1:
        raise ValueError("fixed P2/P3 controls do not share one plan")
    return dict(case_id=case, cores=4, original_commit=CONTROL_COMMIT, package_commit=CONTROL_COMMIT,
        source_feed=artifact(CONTROL_FEED), scenarios=refs, artifacts=refs["P3"]["artifacts"],
        interpretation="Fixed singleton pipeline control; cuts and ownership may differ. No control rerun or latest-best claim.")


def official_identity(graph_dir):
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
            raise ValueError("frozen official input/source mismatch: " + name)
        verified.append(dict(manifest_path=name, actual_path=path.as_posix(), sha256=digest(raw), bytes=len(raw)))
    if {x["manifest_path"] for x in verified if x["manifest_path"] in graphs} != graphs:
        raise ValueError("source manifest does not cover the registered case")
    code = "".join(f"{x['path']}\t{x['sha256']}\n" for x in sorted(manifest["files"], key=lambda x:x["path"]) if x["path"].startswith("code/"))
    if digest(code.encode()) != manifest["official_code_hash"]:
        raise ValueError("official aggregate mismatch")
    return dict(official_code_hash=manifest["official_code_hash"], source_manifest=artifact(MANIFEST),
                config_sha256=sha(CONFIG), verified_files=verified, implementation=[])


def memory_gate():
    value = dict(checked_at=utc(), available_phys_bytes=None, minimum_bytes=1073741824,
                 passed=False, method="Windows GlobalMemoryStatusEx")
    if os.name != "nt":
        value["reason"] = "This local batch's available-memory gate is implemented for Windows only."
        return value
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in ("total_phys", "avail_phys", "total_page", "avail_page", "total_virtual", "avail_virtual", "avail_extended")]
    state = MemoryStatus()
    state.length = ctypes.sizeof(state)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
        value.update(available_phys_bytes=state.avail_phys, total_phys_bytes=state.total_phys,
                     passed=state.avail_phys >= value["minimum_bytes"])
    else:
        value["reason"] = "Available-memory query failed; no child may be dispatched."
    return value


def preflight(graph_dir):
    result = official_identity(graph_dir)
    for name in ("src/q3_yuanzhifang/pipeline_setup.py", "src/q3_yuanzhifang/pipeline_stages.py",
                 "src/q3_yuanzhifang/active_stages.py", "src/q3_yuanzhifang/construct.py",
                 "src/q3_yuanzhifang/baseline.py", "docs/a/q3-yuanzhifang/PIPELINE_SETUP.md"):
        if Path(name).read_bytes() != git("show", SOLVER_COMMIT + ":" + name):
            raise ValueError("cold-setup pipeline source/spec differs from frozen commit: " + name)
        result["implementation"].append(dict(path=name, commit=SOLVER_COMMIT, sha256=sha(name)))
    pipeline = "src/q3_yuanzhifang/pipeline_stages.py"
    if Path(pipeline).read_bytes() != git("show", PIPELINE_COMMIT + ":" + pipeline):
        raise ValueError("underlying pipeline split differs from the original frozen implementation")
    result["pipeline_dependency"] = dict(commit=PIPELINE_COMMIT, **artifact(pipeline))
    for name in ("src/q3_yuanzhifang/benchmark.py", "src/q3_yuanzhifang/export_feed.py"):
        if Path(name).read_bytes() != git("show", HELPER_COMMIT + ":" + name):
            raise ValueError("frozen helper changed: " + name)
    runtime_helper = "src/q3_yuanzhifang/portable_join_benchmark.py"
    if Path(runtime_helper).read_bytes() != git("show", RUNTIME_HELPER_COMMIT + ":" + runtime_helper):
        raise ValueError("live inventory/process cleanup helper changed")
    result["runtime_helper"] = dict(commit=RUNTIME_HELPER_COMMIT, **artifact(runtime_helper))
    template = "results/a/q3-yuanzhifang/pilot-20260924/board-feed-20260924T141108Z-unique-plans.json"
    if Path(template).read_bytes() != git("show", "46c709228c0a83e09c13b008e919d135100b938e:" + template):
        raise ValueError("fixed feed template changed")
    result["export_template"] = artifact(template)
    head = git("rev-parse", "HEAD").decode().strip()
    for name in ("src/q3_yuanzhifang/pipeline_setup_followup_benchmark.py", "src/q3_yuanzhifang/pipeline_setup_followup_export.py",
                 "docs/a/q3-yuanzhifang/PIPELINE_SETUP_FOLLOWUP.md"):
        if Path(name).read_bytes() != git("show", head + ":" + name):
            raise ValueError("pipeline-setup runner/exporter must be committed: " + name)
    result.update(solver_commit=SOLVER_COMMIT, runner_commit=head,
                  runner_sha256=sha(__file__), helper_commit=HELPER_COMMIT,
                  helper_sha256=sha("src/q3_yuanzhifang/benchmark.py"))
    result["baseline_refs"] = {case: baseline(case, dict(
        graph_sha256=sha(graph_dir / f"case_{case}.json"),
        config_sha256=result["config_sha256"], official_sha256=result["official_code_hash"]))
        for case in CASES}
    result["controls"] = {case: control_reference(case, result, graph_dir) for case in CASES}
    return result


class PipelineSetupPilot(Pilot):
    def __init__(self, args):
        super().__init__(args)
        (self.out / ".gitattributes").write_bytes(b"# Preserve exact process output and receipt bytes.\n* -text\n")
        self.info.update(schema="q3-pipeline-setup-v1", run_id="yuanzhifang-q3-pipeline-setup-followup-20260924",
                         budget=BUDGET,
                         argv=[relative(sys.executable), "-B", relative(__file__),
                               "--graph-dir", args.graph_dir.as_posix(), "--output", args.output.as_posix(),
                               "--concurrent-work", args.concurrent_work],
                         resource_context=dict(concurrent_work=args.concurrent_work, workers=1,
                             exclusive_host_claim=False, source="Actual run CLI declaration after coordinated START",
                             memory_gate="at least 1 GiB immediately before each child dispatch",
                             child_priority="Windows BELOW_NORMAL_PRIORITY_CLASS via process creation flag; driver priority not instrumented"),
                         memory_checks=[],
                         offline_costs="No training, precomputed plan or real-graph construction during preparation. "
                         "Parent reports four synthetic tests, including 100 independent event-recursion/full-cut "
                         "oracle examples, changed cuts for late setup, legal coverage and guard fallback. "
                         "These are development costs, not official results. Cold solver includes graph/chain "
                         "indexing, one O(k L^2) cold-setup flowshop DP, singleton plan construction, "
                         "official static validation, output and exit. No internal E0. "
                         "uv sync --locked preceded this batch; preparation wall unrecorded.")



    def invoke(self, kind, call_id, argv, folder):
        elapsed = time.perf_counter() - self.started
        limit = BUDGET["cold_solver_limit" if kind == "solver" else "E0_limit"]
        if elapsed >= BUDGET["dispatch_until_seconds"]:
            raise Stopped("pipeline-setup dispatch cutoff reached; no new call")
        if sum(call["kind"] == kind for call in self.calls) >= limit:
            raise Stopped("pipeline-setup call cap reached; no new call")
        memory = memory_gate()
        memory.update(kind=kind, call_id=call_id)
        self.info["memory_checks"].append(memory)
        self.save()
        if not memory["passed"]:
            raise Stopped("available RAM below 1 GiB or unknown; no child dispatched")
        folder.mkdir(parents=True, exist_ok=True)
        stdout, stderr = folder / "stdout.txt", folder / "stderr.txt"
        call = dict(call_id=call_id, kind=kind, argv=argv, working_directory=".",
                    started_at=utc(), batch_elapsed_at_dispatch=elapsed, status="running",
                    priority_request="Windows BELOW_NORMAL_PRIORITY_CLASS",
                    timeout_seconds=min(BUDGET["per_call_seconds"],
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
                                           start_new_session=os.name != "nt",
                                           creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 0)
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
            self.info["environment_inventory_source"] = dict(acquired_at=utc(),
                scope="Live hardware inventory in this batch; no previous process timing reused. Peak RSS unmeasured.")
            self.save()
            for case in CASES:
                self.info["active_case_id"] = case
                folder = self.out / case / VARIANT
                graph = self.args.graph_dir / f"case_{case}.json"
                plan = folder / f"case_{case}_multicore_res.json"
                cid = f"{case}-{VARIANT}"
                argv = [relative(sys.executable), "-B", "-m", "src.q3_yuanzhifang.pipeline_setup",
                        graph.as_posix(), "--cores", "4", "--config", CONFIG.as_posix(), "--output", plan.as_posix()]
                call = self.invoke("solver", cid, argv, folder / "solver")
                value = json.loads(plan.read_bytes())
                if set(value) != {"node_to_subgraph", "core_schedules"} or len(value["core_schedules"]) != 4:
                    raise Stopped("invalid plan fields/core count")
                detail = json.loads(gzip.decompress((ROOT / call["stdout"]["path"]).read_bytes()))
                c = dict(construction_id=cid, case_id=case, variant=VARIANT, cores=4, requested_cores=4,
                         active_cores=sum(bool(s) for s in value["core_schedules"]),
                         graph_sha256=sha(graph), plan=artifact(plan), solver=call, detail=detail,
                         alias_of=None, evaluation_ids=[])
                self.constructions.append(c)
                self.save()
                if not detail.get("guard") or detail.get("selected") != VARIANT:
                    raise Stopped("pipeline-setup guard failed; no E0 on fallback")
                control = self.info["identity"]["controls"][case]
                old_plan = fixed_control_artifact(control["artifacts"]["plan"], control["package_commit"])
                old_value = json.loads(old_plan)
                old_owners, new_owners = core_ownership(old_value), core_ownership(value)
                missing_ops = sorted(set(old_owners) - set(new_owners))
                extra_ops = sorted(set(new_owners) - set(old_owners))
                singleton = len(set(value["node_to_subgraph"].values())) == len(new_owners)
                changed_owners = sorted(op for op in set(old_owners) & set(new_owners)
                                        if old_owners[op] != new_owners[op])
                c["historical_control_comparison"] = dict(bytes_equal=plan.read_bytes() == old_plan,
                    full_two_field_json_equal=value == old_value, control_commit=CONTROL_COMMIT,
                    control_attempts={p: r["attempt_id"] for p, r in control["scenarios"].items()},
                    exact_compute_coverage=not missing_ops and not extra_ops and len(new_owners)==1364,
                    operations_checked=len(new_owners), missing_ops=missing_ops, extra_ops=extra_ops,
                    singleton=singleton, changed_core_ownership_count=len(changed_owners),
                    ownership_sha256=digest(json.dumps(new_owners, sort_keys=True, separators=(",", ":")).encode()),
                    operations_by_core=[sum(core == k for core in new_owners.values()) for k in range(4)],
                    subgraphs=len(set(value["node_to_subgraph"].values())),
                    quotient_static_validation=dict(passed=True, scope="inside successful cold solver before plan write",
                        function="derive_multicore_plan", source="data/raw/a/official/code/stub_multicore_cut_and_schedule.py",
                        source_sha256=sha(OFFICIAL / "code/stub_multicore_cut_and_schedule.py")),
                    note="Expected 1364 original compute ops established by fixed valid control. "
                         "Cuts and per-op core ownership may change. No second build/derive/control evaluation. "
                         "Static legality and abstract model do not establish official quality or capacity.")
                self.save()
                if not c["historical_control_comparison"]["exact_compute_coverage"] or not singleton:
                    raise Stopped("expected 1364 compute ops and singleton mapping; no E0")
                if c["historical_control_comparison"]["bytes_equal"]:
                    c["alias_of"] = dict(commit=CONTROL_COMMIT, plan=control["artifacts"]["plan"],
                                         attempts={p:r["attempt_id"] for p,r in control["scenarios"].items()})
                    c["reused_evaluations"] = control["scenarios"]
                    self.save()
                    continue
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
                    if result.get("scene") != "B" or result.get("num_cores") != 4 or result["makespan"] <= 0:
                        raise Stopped("official result identity mismatch")
                    if problem == 3 and (result.get("problem") != 3 or result.get("cache_mode") != "read_only"):
                        raise Stopped("P3 cache identity mismatch")
                    e = dict(evaluation_id=call["call_id"], construction_id=cid, case_id=case,
                             variant=VARIANT, problem=f"P{problem}", makespan_cycles=result["makespan"],
                             call=call, artifacts={name: compress(path) for name, path in paths.items()})
                    self.evaluations.append(e)
                    c["evaluation_ids"].append(e["evaluation_id"])
                    self.save()
            reason = ("one cold construction; plan bytes equal frozen pipeline control, reused with zero new E0"
                      if any(c["alias_of"] for c in self.constructions)
                      else "one guarded cold-setup pipeline construction and two external E0s completed")
            self.info.update(status="ok", stop_reason=reason)
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
                            self.info["partial_outputs"].append(dict(**compress(path), sealed=True))
                        except (OSError, ValueError) as exc:
                            self.info["partial_outputs"].append(dict(path=relative(path), sealed=False,
                                failure_type=type(exc).__name__))
                            self.info.update(status="stopped", stop_reason="partial output preservation failed")
            # A preceding multi-artifact compression may have sealed one file
            # before another failed. Retain references to those orphan archives.
            referenced = {a["path"] for e in self.evaluations for a in e["artifacts"].values()}
            referenced.update(a["path"] for a in self.info["partial_outputs"])
            for name in ("result.json.gz", "trace.json.gz", "result.log.gz"):
                for path in sorted(self.out.rglob(name)):
                    if relative(path) in referenced:
                        continue
                    try:
                        raw = gzip.decompress(path.read_bytes())
                        self.info["partial_outputs"].append(dict(**artifact(path), sealed=True,
                            raw_sha256=digest(raw), raw_bytes=len(raw), gzip_bytes=path.stat().st_size))
                    except (OSError, ValueError, EOFError) as exc:
                        self.info["partial_outputs"].append(dict(path=relative(path), sealed=False,
                            failure_type=type(exc).__name__))
                        self.info.update(status="stopped", stop_reason="partial archive verification failed")
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
    ap.add_argument("--graph-dir", type=Path, default=Path("../huaweicup2026/data/raw/a/official-cases/data"))
    ap.add_argument("--output", type=Path, default=Path(OUT))
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--concurrent-work", choices=("P2", "P1", "P1+P2", "none-reported", "unknown"))
    args = ap.parse_args()
    os.chdir(ROOT)
    if (args.output.is_absolute() or args.graph_dir.is_absolute() or ".." in args.output.parts
            or not args.output.parts or args.output.parts[0] != "results"
            or not args.output.resolve().is_relative_to((ROOT / "results").resolve())):
        ap.error("use project-relative input and a new in-project results output")
    if args.check_only:
        identity = preflight(args.graph_dir)
        print(json.dumps(dict(verified_files=len(identity["verified_files"]), solver_commit=SOLVER_COMMIT,
                              runner_commit=identity["runner_commit"], baselines=list(identity["baseline_refs"]),
                              planned_calls=dict(solver=1, E0=2, E1=0, E2=0), calls_executed=0,
                              controls={case: dict(commit=value["original_commit"], P2=value["scenarios"]["P2"]["makespan_cycles"], P3=value["scenarios"]["P3"]["makespan_cycles"])
                                        for case, value in identity["controls"].items()})))
        return 0
    if args.concurrent_work is None:
        ap.error("actual run requires --concurrent-work from the current coordinated window")
    return PipelineSetupPilot(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
