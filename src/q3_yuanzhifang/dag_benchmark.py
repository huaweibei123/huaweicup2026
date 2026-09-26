"""Frozen 069/071 k5 DAG pilot: two cold constructions, four external E0s."""
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

SOLVER_COMMIT = "20fbf33b310b6e9959e45d67361f580601f5959f"
HELPER_COMMIT = "39e9c8d8a78e384855ffbfbf41a2dec4d4a7e5a0"
OUT = "results/a/q3-yuanzhifang/dag-list-20260924"
CASES = ("069", "071")
VARIANT = "dag_chain_list"
BUDGET = dict(workers=1, cold_solver_limit=2, E0_limit=4, E1_limit=0,
              E2_limit=0, per_call_seconds=30, batch_seconds=180,
              dispatch_until_seconds=150, retries=0)


def preflight(graph_dir):
    result = pilot_preflight(graph_dir)
    for name in ("src/q3_yuanzhifang/dag_list.py", "src/q3_yuanzhifang/active_stages.py",
                 "docs/a/q3-yuanzhifang/DAG_LIST.md"):
        if Path(name).read_bytes() != git("show", SOLVER_COMMIT + ":" + name):
            raise ValueError("DAG source/spec differs from frozen commit: " + name)
        result["implementation"].append(dict(path=name, sha256=sha(name)))
    for name in ("src/q3_yuanzhifang/benchmark.py", "src/q3_yuanzhifang/export_feed.py"):
        if Path(name).read_bytes() != git("show", HELPER_COMMIT + ":" + name):
            raise ValueError("frozen helper changed: " + name)
    head = git("rev-parse", "HEAD").decode().strip()
    for name in ("src/q3_yuanzhifang/dag_benchmark.py", "src/q3_yuanzhifang/dag_export.py"):
        if Path(name).read_bytes() != git("show", head + ":" + name):
            raise ValueError("DAG runner/exporter must be committed: " + name)
    result.update(solver_commit=SOLVER_COMMIT, runner_commit=head,
                  runner_sha256=sha(__file__), helper_commit=HELPER_COMMIT,
                  helper_sha256=sha("src/q3_yuanzhifang/benchmark.py"))
    result["baseline_refs"] = {case: baseline(case, dict(
        graph_sha256=sha(graph_dir / f"case_{case}.json"),
        config_sha256=result["config_sha256"], official_sha256=result["official_code_hash"]))
        for case in CASES}
    return result


class DagPilot(Pilot):
    def __init__(self, args):
        super().__init__(args)
        (self.out / ".gitattributes").write_bytes(b"# Preserve exact process output and receipt bytes.\n* -text\n")
        self.info.update(schema="q3-dag-list-v1", run_id="yuanzhifang-q3-dag-list-20260924",
                         budget=BUDGET,
                         argv=[relative(sys.executable), "-B", relative(__file__),
                               "--graph-dir", args.graph_dir.as_posix(), "--output", args.output.as_posix()],
                         offline_costs="No training, compilation or precomputed plans. Parent developed a direct DAG "
                         "constructor and reports ten synthetic structure tests before freeze. Existing 100-graph "
                         "structure analysis (22.365 s) and lower-bound analysis (49.296 s parent report) informed "
                         "development case selection, not per-input online selection. These are separate development "
                         "costs. uv sync --locked preceded all batches; environment preparation wall unrecorded.")

    def invoke(self, kind, call_id, argv, folder):
        elapsed = time.perf_counter() - self.started
        limit = BUDGET["cold_solver_limit" if kind == "solver" else "E0_limit"]
        if elapsed >= BUDGET["dispatch_until_seconds"]:
            raise Stopped("DAG dispatch cutoff reached; no new call")
        if sum(call["kind"] == kind for call in self.calls) >= limit:
            raise Stopped("DAG call cap reached; no new call")
        folder.mkdir(parents=True, exist_ok=True)
        stdout, stderr = folder / "stdout.txt", folder / "stderr.txt"
        call = dict(call_id=call_id, kind=kind, argv=argv, working_directory=".",
                    started_at=utc(), batch_elapsed_at_dispatch=elapsed, status="running",
                    timeout_seconds=min(BUDGET["per_call_seconds"], BUDGET["batch_seconds"] - elapsed))
        self.calls.append(call)
        self.save()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
                   PYTHONHASHSEED="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                   MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
        start = time.perf_counter()
        try:
            with stdout.open("wb") as out, stderr.open("wb") as err:
                process = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=out, stderr=err)
                call["pid"] = process.pid
                try:
                    call["exit_code"] = process.wait(timeout=call["timeout_seconds"])
                    call["status"] = "ok" if call["exit_code"] == 0 else "failed"
                except subprocess.TimeoutExpired:
                    # A Windows venv launcher can have an interpreter child.
                    # Only terminate this owned process tree, never another batch.
                    if os.name == "nt":
                        killed = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                                capture_output=True, timeout=5)
                        call["tree_kill_exit_code"] = killed.returncode
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    call.update(status="timeout", exit_code=process.returncode)
        except OSError as exc:
            call.update(status="failed", exit_code=None, failure_type=type(exc).__name__)
        finally:
            call.update(wall_seconds=time.perf_counter() - start, finished_at=utc())
            call["stdout"] = compress(stdout)
            call["stderr"] = compress(stderr)
            write_json(folder / "call.json", call)
            self.save()
        print(json.dumps({k: call[k] for k in ("call_id", "status", "wall_seconds")}), flush=True)
        if call["status"] != "ok":
            raise Stopped("first unsuccessful call: " + call_id)
        return call

    def run(self):
        try:
            self.info["identity"] = preflight(self.args.graph_dir)
            old_path = Path("results/a/q3-yuanzhifang/pilot-20260924/manifest.json")
            old = json.loads(old_path.read_text(encoding="utf-8"))
            self.info["environment"] = dict(old["environment"])
            self.info["environment_inventory_source"] = dict(
                **artifact(old_path), acquired_between=[old["started_at"], old["finished_at"]],
                scope="Same-host static hardware inventory reused; all new process times measured here. Peak RSS unmeasured.")
            if self.info["environment"]["python"] != sys.version.split()[0]:
                raise Stopped("Python version differs from recorded inventory")
            self.save()
            for case in CASES:
                folder = self.out / case / VARIANT
                graph = self.args.graph_dir / f"case_{case}.json"
                plan = folder / f"case_{case}_multicore_res.json"
                cid = f"{case}-{VARIANT}"
                argv = [relative(sys.executable), "-B", "-m", "src.q3_yuanzhifang.dag_list",
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
                    raise Stopped("DAG guard failed; no E0 on fallback")
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
            self.info.update(status="ok", stop_reason="two guarded DAG constructions and four external E0s completed")
        except Exception as exc:
            self.info.update(status="stopped", stop_reason=str(exc), failure_type=type(exc).__name__)
        finally:
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
                              planned_calls=dict(solver=2, E0=4, E1=0, E2=0))))
        return 0
    return DagPilot(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
