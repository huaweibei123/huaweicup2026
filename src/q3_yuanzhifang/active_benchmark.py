"""One resource-selected active-core 044/k4 candidate: one cold construction, two external E0s."""
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path
import sys
import time

from benchmark import (ROOT, OFFICIAL, CONFIG, Pilot, Stopped, artifact, compress,
                       git, preflight as pilot_preflight, relative, sha, utc)

SOLVER_COMMIT = "bb7a7e8702b636a0a9dda33d070daad5f4d7c212"
HELPER_COMMIT = "39e9c8d8a78e384855ffbfbf41a2dec4d4a7e5a0"
OUT = "results/a/q3-yuanzhifang/active-20260924"
BUDGET = dict(workers=1, cold_solver_limit=1, E0_limit=2, E1_limit=0,
              E2_limit=0, per_call_seconds=30, batch_seconds=120,
              dispatch_until_seconds=90, retries=0)


def preflight(graph_dir):
    result = pilot_preflight(graph_dir)
    name = "src/q3_yuanzhifang/active_stages.py"
    if Path(name).read_bytes() != git("show", SOLVER_COMMIT + ":" + name):
        raise ValueError("stage solver bytes differ from fixed commit")
    helper = "src/q3_yuanzhifang/benchmark.py"
    if Path(helper).read_bytes() != git("show", HELPER_COMMIT + ":" + helper):
        raise ValueError("frozen pilot helper changed")
    head = git("rev-parse", "HEAD").decode().strip()
    for name in ("src/q3_yuanzhifang/active_benchmark.py", "src/q3_yuanzhifang/active_export.py"):
        if Path(name).read_bytes() != git("show", head + ":" + name):
            raise ValueError("stage runner/exporter must be committed")
    result["implementation"].append(dict(path="src/q3_yuanzhifang/active_stages.py",
                                        sha256=sha("src/q3_yuanzhifang/active_stages.py")))
    result.update(solver_commit=SOLVER_COMMIT, runner_commit=head,
                  runner_sha256=sha(__file__), helper_commit=HELPER_COMMIT,
                  helper_sha256=sha(helper))
    return result


class ActivePilot(Pilot):
    def __init__(self, args):
        super().__init__(args)
        (self.out / ".gitattributes").write_bytes(b"# Preserve exact process output and receipt bytes.\n* -text\n")
        self.info.update(schema="q3-active-stages-v1", run_id="yuanzhifang-q3-active-20260924",
                         budget=BUDGET,
                         argv=[relative(sys.executable), "-B", relative(__file__),
                               "--graph-dir", args.graph_dir.as_posix(), "--output", args.output.as_posix()],
                         offline_costs="No training, compilation or precomputation for the live input. "
                         "Parent performed static chain/signature/resource-formula checks and six synthetic structure tests "
                         "before fixing the algorithm; these are separate development costs. "
                         "Environment was prepared by uv sync --locked before this batch; preparation wall unrecorded.")

    def invoke(self, kind, call_id, argv, folder):
        # The inherited primitive has looser pilot limits. Apply this stage's
        # stricter limits before it can dispatch: 90+30 <= the 120 second cap.
        if time.perf_counter() - self.started >= 90:
            raise Stopped("stage dispatch cutoff reached; no new call")
        limit = 1 if kind == "solver" else 2
        if sum(call["kind"] == kind for call in self.calls) >= limit:
            raise Stopped("stage call cap reached; no new call")
        return super().invoke(kind, call_id, argv, folder)

    def run(self):
        try:
            self.info["identity"] = preflight(self.args.graph_dir)
            # Static machine inventory was obtained minutes earlier by this same
            # worker. Explicitly retain its acquisition time rather than re-run
            # slow CIM while another local worker waits for this reserved slot.
            old_path = Path("results/a/q3-yuanzhifang/pilot-20260924/manifest.json")
            previous = json.loads(old_path.read_text(encoding="utf-8"))
            self.info["environment"] = dict(previous["environment"])
            self.info["environment_inventory_source"] = dict(
                **artifact(old_path), acquired_between=[previous["started_at"], previous["finished_at"]],
                scope="Reuse same-host static CPU/RAM/GPU inventory only; timing is newly measured, peak RSS remains unmeasured")
            if self.info["environment"]["python"] != sys.version.split()[0]:
                raise Stopped("Python version changed from recorded inventory")
            self.save()
            folder = self.out / "044" / "active_stages"
            graph = self.args.graph_dir / "case_044.json"
            plan = folder / "case_044_multicore_res.json"
            argv = [relative(sys.executable), "-B", "-m", "src.q3_yuanzhifang.active_stages",
                    graph.as_posix(), "--cores", "4", "--config", CONFIG.as_posix(), "--output", plan.as_posix()]
            call = self.invoke("solver", "044-active_stages", argv, folder / "solver")
            if set(json.loads(plan.read_bytes())) != {"node_to_subgraph", "core_schedules"}:
                raise Stopped("invalid plan fields")
            detail = json.loads(gzip.decompress((ROOT / call["stdout"]["path"]).read_bytes()))
            c = dict(construction_id="044-active_stages", case_id="044", variant="active_stages", cores=4,
                     requested_cores=4, active_cores=detail.get("active_cores"),
                     graph_sha256=sha(graph), plan=artifact(plan), solver=call, detail=detail,
                     alias_of=None, evaluation_ids=[])
            self.constructions.append(c)
            self.save()
            if not detail.get("guard") or detail.get("selected") != "active_stages":
                raise Stopped("044 stage guard unexpectedly failed; do not spend E0 on a fallback")
            schedules = json.loads(plan.read_bytes())["core_schedules"]
            if (detail.get("requested_cores") != 4 or len(schedules) != 4 or
                    sum(bool(sequence) for sequence in schedules) != detail.get("active_cores")):
                raise Stopped("requested/active core count mismatch; no E0 dispatched")
            for problem in (2, 3):
                destination = folder / f"P{problem}"
                paths = dict(result=destination / "result.json", trace=destination / "trace.json",
                             log=destination / "result.log")
                argv = [relative(sys.executable), "-B",
                        (OFFICIAL / f"code/multicore_cut_evaluate_problem_{problem}.py").as_posix(),
                        graph.as_posix(), plan.as_posix(), "--config", CONFIG.as_posix(),
                        "--output", paths["result"].as_posix(), "--trace-output", paths["trace"].as_posix(),
                        "--log-output", paths["log"].as_posix()]
                call = self.invoke("E0", f"044-active_stages-P{problem}", argv, destination)
                result = json.loads(paths["result"].read_bytes())
                if result.get("scene") != "B" or result.get("num_cores") != 4 or result["makespan"] <= 0:
                    raise Stopped("official result identity mismatch")
                if problem == 3 and (result.get("problem") != 3 or result.get("cache_mode") != "read_only"):
                    raise Stopped("P3 cache identity mismatch")
                e = dict(evaluation_id=call["call_id"], construction_id=c["construction_id"],
                         case_id="044", variant="active_stages", problem=f"P{problem}",
                         makespan_cycles=result["makespan"], call=call,
                         artifacts={name: compress(path) for name, path in paths.items()})
                self.evaluations.append(e)
                c["evaluation_ids"].append(e["evaluation_id"])
                self.save()
            self.info.update(status="ok", stop_reason="one guarded stage construction and its P2/P3 pair completed")
        except Exception as exc:
            self.info.update(status="stopped", stop_reason=str(exc), failure_type=type(exc).__name__)
        finally:
            self.info["finished_at"] = utc()
            self.save()
        print(json.dumps(dict(status=self.info["status"], calls=self.info["calls"],
                              elapsed_seconds=self.info["elapsed_seconds"], stop_reason=self.info["stop_reason"])), flush=True)
        return 0 if self.info["status"] == "ok" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-dir", type=Path, default=Path("../huaweicup2026/data/raw/a/official-cases/data"))
    parser.add_argument("--output", type=Path, default=Path(OUT))
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.output.is_absolute() or args.graph_dir.is_absolute() or ".." in args.output.parts:
        parser.error("use project-relative input and in-project output")
    if args.check_only:
        identity = preflight(args.graph_dir)
        print(json.dumps(dict(verified_files=len(identity["verified_files"]),
                              solver_commit=SOLVER_COMMIT, runner_commit=identity["runner_commit"],
                              planned_calls=dict(solver=1, E0=2, E1=0, E2=0))))
        return 0
    return ActivePilot(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
