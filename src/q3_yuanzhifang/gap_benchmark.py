"""Frozen 069 k5 gap-list pilot: one cold construction, at most two external E0s."""
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
                       git, preflight as pilot_preflight, relative, sha, utc, write_json)
from export_feed import baseline
from portable_join_benchmark import live_environment, stop_owned_process
from benchmark import digest

SOLVER_COMMIT = "a37eb931a22fb7df7e0d00d193538ce5289ae045"
HELPER_COMMIT = "39e9c8d8a78e384855ffbfbf41a2dec4d4a7e5a0"
OUT = "results/a/q3-yuanzhifang/gap-list-20260924"
CASES = ("069",)
VARIANT = "dag_join_gap_list"
BUDGET = dict(workers=1, cold_solver_limit=1, E0_limit=2, E1_limit=0,
              E2_limit=0, per_call_seconds=30, batch_seconds=120,
              dispatch_until_seconds=90, retries=0)


CONTROLS = {
    "release": dict(commit="b4f3f2895f52975cb6275ea85b89bf5a4a76ef7b",
        manifest="results/a/q3-yuanzhifang/release-order-20260924/manifest.json",
        feed="results/a/q3-yuanzhifang/release-order-20260924/board-feed-20260924T164524Z-release-order.json"),
    "join": dict(commit="ef80a88ed04b26e70465d56a54c373b0dcc5d00f",
        manifest="results/a/q3-yuanzhifang/join-list-20260924/manifest.json",
        feed="results/a/q3-yuanzhifang/join-list-20260924/board-feed-20260924T160841Z-join-list.json"),
}
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
        if ref.get("raw_bytes") is not None and len(raw) != ref["raw_bytes"]:
            raise ValueError("control raw-byte size differs: " + ref["path"])
    return raw


def control_reference(identity, graph_dir, fixed):
    commit = fixed["commit"]
    old = json.loads(fixed_control_artifact(artifact(fixed["manifest"]), commit))
    feed = json.loads(fixed_control_artifact(artifact(fixed["feed"]), commit))
    if old["status"] != "ok" or old["identity"]["config_sha256"] != identity["config_sha256"] or old["identity"]["official_code_hash"] != identity["official_code_hash"]:
        raise ValueError("frozen control configuration/source/status mismatch")
    c = next(x for x in old["constructions"] if x["case_id"] == "069")
    if c["graph_sha256"] != sha(graph_dir / "case_069.json") or c["cores"] != 5:
        raise ValueError("frozen control graph/core mismatch")
    value = json.loads(fixed_control_artifact(c["plan"], commit))
    if set(value) != {"node_to_subgraph", "core_schedules"} or len(value["core_schedules"]) != 5:
        raise ValueError("frozen control plan malformed")
    evaluations = {}
    for e in old["evaluations"]:
        if e["case_id"] != "069":
            continue
        for ref in e["artifacts"].values():
            fixed_control_artifact(ref, commit)
        result = json.loads(fixed_control_artifact(e["artifacts"]["result"], commit))
        if e["call"]["status"] != "ok" or result["scene"] != "B" or result["num_cores"] != 5 or result["makespan"] != e["makespan_cycles"]:
            raise ValueError("frozen control result identity mismatch")
        if e["problem"] == "P3" and (result.get("problem") != 3 or result.get("cache_mode") != "read_only"):
            raise ValueError("frozen P3 control identity mismatch")
        row = next(x for x in feed["records"] if x["case_id"] == "069" and x["problem"] == e["problem"])
        if row["identity"]["plan_sha256"] != c["plan"]["sha256"] or row["artifacts"]["result"]["sha256"] != e["artifacts"]["result"]["sha256"]:
            raise ValueError("frozen control feed points to different bytes")
        evaluations[e["problem"]] = dict(evaluation_id=e["evaluation_id"], attempt_id=row["attempt_id"],
            makespan_cycles=e["makespan_cycles"], original_call=e["call"], artifacts=e["artifacts"])
    if set(evaluations) != {"P2", "P3"}:
        raise ValueError("frozen control requires both frozen P2/P3 results")
    return dict(commit=commit, manifest=artifact(fixed["manifest"]), feed=artifact(fixed["feed"]),
                run_id=old["run_id"], construction_id=c["construction_id"], plan=c["plan"], evaluations=evaluations)


def preflight(graph_dir):
    result = pilot_preflight(graph_dir)
    for name in ("src/q3_yuanzhifang/gap_list.py", "src/q3_yuanzhifang/gap_calendar.py", "src/q3_yuanzhifang/dag_list.py",
                 "src/q3_yuanzhifang/active_stages.py",
                 "docs/a/q3-yuanzhifang/GAP_LIST.md"):
        if Path(name).read_bytes() != git("show", SOLVER_COMMIT + ":" + name):
            raise ValueError("gap-list source/spec differs from frozen commit: " + name)
        result["implementation"].append(dict(path=name, sha256=sha(name)))
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
    for name in ("src/q3_yuanzhifang/gap_benchmark.py", "src/q3_yuanzhifang/gap_export.py"):
        if Path(name).read_bytes() != git("show", head + ":" + name):
            raise ValueError("gap-list runner/exporter must be committed: " + name)
    result.update(solver_commit=SOLVER_COMMIT, runner_commit=head,
                  runner_sha256=sha(__file__), helper_commit=HELPER_COMMIT,
                  helper_sha256=sha("src/q3_yuanzhifang/benchmark.py"))
    result["baseline_refs"] = {case: baseline(case, dict(
        graph_sha256=sha(graph_dir / f"case_{case}.json"),
        config_sha256=result["config_sha256"], official_sha256=result["official_code_hash"]))
        for case in CASES}
    result["controls"] = {name: control_reference(result, graph_dir, fixed) for name, fixed in CONTROLS.items()}
    return result


class GapPilot(Pilot):
    def __init__(self, args):
        super().__init__(args)
        (self.out / ".gitattributes").write_bytes(b"# Preserve exact process output and receipt bytes.\n* -text\n")
        self.info.update(schema="q3-gap-list-v1", run_id="yuanzhifang-q3-gap-list-20260924",
                         budget=BUDGET,
                         argv=[relative(sys.executable), "-B", relative(__file__),
                               "--graph-dir", args.graph_dir.as_posix(), "--output", args.output.as_posix()],
                         offline_costs="No training, compilation or precomputed candidate plan. Parent reports three "
                         "synthetic tests: 180 integer-time oracle reservations, persistent versions/overlap rejection, "
                         "and a long-short diamond with an independently released operation. These and prior results "
                         "are separately recorded development costs. The cold solver includes graph/chain indexing, "
                         "persistent per-pipe AVL calendars, at most k^2 arithmetic joint placements, start-order sorting, "
                         "validation and output. uv sync --locked preceded this batch; preparation wall unrecorded.")


    def invoke(self, kind, call_id, argv, folder):
        elapsed = time.perf_counter() - self.started
        limit = BUDGET["cold_solver_limit" if kind == "solver" else "E0_limit"]
        if elapsed >= BUDGET["dispatch_until_seconds"]:
            raise Stopped("gap-list dispatch cutoff reached; no new call")
        if sum(call["kind"] == kind for call in self.calls) >= limit:
            raise Stopped("gap-list call cap reached; no new call")
        folder.mkdir(parents=True, exist_ok=True)
        stdout, stderr = folder / "stdout.txt", folder / "stderr.txt"
        call = dict(call_id=call_id, kind=kind, argv=argv, working_directory=".",
                    started_at=utc(), batch_elapsed_at_dispatch=elapsed, status="running",
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
            self.info["environment_inventory_source"] = dict(acquired_at=utc(),
                scope="Live hardware inventory in this batch; no previous process timing reused. Peak RSS unmeasured.")
            self.save()
            for case in CASES:
                folder = self.out / case / VARIANT
                graph = self.args.graph_dir / f"case_{case}.json"
                plan = folder / f"case_{case}_multicore_res.json"
                cid = f"{case}-{VARIANT}"
                argv = [relative(sys.executable), "-B", "-m", "src.q3_yuanzhifang.gap_list",
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
                    raise Stopped("gap-list guard failed; no E0 on fallback")
                c["control_comparisons"] = []
                for name, control in self.info["identity"]["controls"].items():
                    old_plan = fixed_control_artifact(control["plan"], control["commit"])
                    comparison = dict(control_name=name, bytes_equal=plan.read_bytes() == old_plan,
                        full_two_field_json_equal=value == json.loads(old_plan), control_commit=control["commit"],
                        control_plan=control["plan"], rule="Complete parsed mapping and ordered per-core schedules; no proxy comparison.")
                    c["control_comparisons"].append(comparison)
                    if comparison["full_two_field_json_equal"] and c["alias_of"] is None:
                        c["alias_of"] = dict(commit=control["commit"], run_id=control["run_id"],
                                             construction_id=control["construction_id"], control_name=name)
                        c["reused_evaluations"] = control["evaluations"]
                self.save()
                if c["alias_of"] is not None:
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
            reason = ("one cold construction; identical frozen control plan reused with zero new E0s"
                      if any(c["alias_of"] for c in self.constructions)
                      else "one guarded gap-list construction and two external E0s completed")
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
    args = ap.parse_args()
    os.chdir(ROOT)
    if args.output.is_absolute() or args.graph_dir.is_absolute() or ".." in args.output.parts:
        ap.error("use project-relative input and in-project output")
    if args.check_only:
        identity = preflight(args.graph_dir)
        print(json.dumps(dict(verified_files=len(identity["verified_files"]), solver_commit=SOLVER_COMMIT,
                              runner_commit=identity["runner_commit"], baselines=list(identity["baseline_refs"]),
                              planned_calls=dict(solver=1, E0=2, E1=0, E2=0), calls_executed=0,
                              controls={name: dict(commit=value["commit"], problems=list(value["evaluations"]))
                                        for name, value in identity["controls"].items()})))
        return 0
    return GapPilot(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
