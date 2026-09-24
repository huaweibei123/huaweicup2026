"""Export the two Stage L raw cells as a submission-v1 feed; never score."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from src.q1_yuanzhifang.benchmark_l import ROOT, OUT, SOURCE, CELLS, sha

REPO = "huaweibei123/huaweicup2026"
BASELINE = "6fcec11ccc472a1a652b21feb6fccf85a4555598"
BASE = "results/benchmark-board/official-singlecore-20260924/044"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def artifact(path):
    return dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path))


def source(commit, path, entrypoint):
    git("cat-file", "-e", f"{commit}:{path}")
    return dict(repo=REPO, commit=commit, path=path, entrypoint=entrypoint)


def baseline(folder, manifest):
    target = folder / "baseline" / "044"
    target.mkdir(parents=True, exist_ok=True)
    originals = {name: git("show", f"{BASELINE}:{BASE}/{name}") for name in ("run.json", "result.json.gz")}
    for name, raw in originals.items():
        file = target / name
        if file.exists():
            if file.read_bytes() != raw:
                raise ValueError("baseline copy differs from fixed Git source")
        else:
            file.write_bytes(raw)
    run = json.loads(originals["run.json"])
    result_raw = gzip.decompress(originals["result.json.gz"])
    result = json.loads(result_raw)
    if (run["case_id"] != "044" or run["status"] != "ok" or run["official_calls"] != 1
            or run["graph_sha256"] != manifest["graph_sha256"]
            or run["config_sha256"] != manifest["config_sha256"]
            or run["official_code_hash"] != manifest["official_code_hash"]
            or run["artifacts"]["result.json"]["sha256"] != hashlib.sha256(originals["result.json.gz"]).hexdigest()
            or run["artifacts"]["result.json"]["raw_sha256"] != hashlib.sha256(result_raw).hexdigest()
            or result.get("scene") != "A" or result.get("num_cores") != 1
            or result.get("makespan") != run["makespan_cycles"]):
        raise ValueError("official singlecore baseline identity mismatch")
    return dict(graph_sha256=run["graph_sha256"], config_sha256=run["config_sha256"],
                official_sha256=run["official_code_hash"], route="E0",
                entrypoint="singlecore_evaluate.evaluate_singlecore",
                result=artifact(target / "result.json.gz")), result["makespan"]


def export(run_dir, feed):
    manifest = json.loads((run_dir / "batch_manifest.json").read_bytes())
    receipt = json.loads((run_dir / "batch_receipt.json").read_bytes())
    if manifest["solver_commit"] != SOURCE or not manifest.get("producer_session"):
        raise ValueError("solver/session identity mismatch")
    if (receipt["calls"]["solver"] > 2 or receipt["calls"]["E0"] > 2
            or receipt["calls"]["E1"] or receipt["calls"]["E2"] or receipt["retries"]):
        raise ValueError("batch exceeded Stage L budget")
    code = ROOT / "data/raw/a/official/code"
    signature = "".join(f"code/{p.name}\t{sha(p)}\n" for p in sorted(code.iterdir()) if p.is_file())
    if hashlib.sha256(signature.encode()).hexdigest() != manifest["official_code_hash"]:
        raise ValueError("full official source differs")
    if sha(ROOT / "data/raw/a/official/data/config.txt") != manifest["config_sha256"]:
        raise ValueError("config differs")
    verified_baseline, baseline_cycles = baseline(run_dir.parent, manifest)
    records = []
    for cores in CELLS:
        cell = run_dir / f"044-k{cores}"
        run = json.loads((cell / "run.json").read_bytes())
        if run["case"] != "044" or run["cores"] != cores or run["graph_sha256"] != manifest["graph_sha256"]:
            raise ValueError("cell identity differs")
        paths = dict(plan=cell / "case_044_multicore_res.json", result=cell / "e0_result.json",
                     trace=cell / "e0_trace.json", log=cell / "e0_log.txt",
                     diagnostics=cell / "diagnostics.json")
        artifacts = dict(run=artifact(cell / "run.json"), manifest=artifact(run_dir / "batch_manifest.json"))
        for key, path in paths.items():
            if key == "diagnostics":
                continue  # Board artifact schema permits only official artifact keys.
            if path.is_file():
                artifacts[key] = artifact(path)
        success = run["status"] == "success"
        result = None
        if success:
            if not all(path.is_file() for path in paths.values()):
                raise ValueError("successful cell lacks raw plan/diagnostics/E0 original")
            plan = json.loads(paths["plan"].read_bytes())
            result = json.loads(paths["result"].read_bytes())
            diagnostic = json.loads(paths["diagnostics"].read_bytes())
            if (set(plan) != {"node_to_subgraph", "core_schedules"}
                    or diagnostic.get("algorithm_id") != "q1-shared-packet-pipeline"
                    or diagnostic.get("graph_sha256") != manifest["graph_sha256"]
                    or result.get("scene") != "A" or result.get("num_cores") != cores
                    or result.get("makespan") != run["makespan_cycles"]
                    or any(run[f"e0_{key}_sha256"] != artifacts[key]["sha256"] for key in ("result", "trace", "log"))
                    or run["plan_sha256"] != artifacts["plan"]["sha256"]):
                raise ValueError("successful raw cell hash/content differs")
        status = ("ok" if success else "not_run" if run["status"] in
                  {"deadline-before-solver", "deadline-before-e0", "not-started-after-supervision-failure",
                   "ram-insufficient-before-cell"}
                  else "timeout" if run.get("solver", {}).get("timeout") or run.get("e0", {}).get("timeout")
                  else "failed")
        solver, e0 = run.get("solver", {}), run.get("e0", {})
        movement = result["data_movement_bytes"] if success else {}
        missing = {"provenance.environment.gpu": "No GPU was measured.",
                   "provenance.environment.ram_bytes": "Only startup available RAM was checked, not total RAM.",
                   "provenance.environment.threads": "OS threads were not instrumented.",
                   "provenance.environment.peak_rss_bytes": "Peak RSS was not instrumented.",
                   "provenance.measurement.seed": "Deterministic graph-derived DP has no RNG seed."}
        if not success:
            for key in ("makespan_cycles", "ddr_bytes", "extra_ddr_bytes", "spill_bytes"):
                missing[f"metrics.{key}"] = f"No accepted E0 result: {run['status']}"
        if "wall_seconds" not in solver:
            missing["metrics.solver_wall_seconds"] = "No completed owned solver wall recorded."
        if "wall_seconds" not in e0:
            missing["metrics.evaluation_wall_seconds"] = "No completed external E0 wall recorded."
        failure = None if success else dict(stage="E0" if run["calls"]["E0"] else "solver",
                                            reason=run["status"] + (": " + run["message"] if run.get("message") else ""),
                                            exit_code=(e0 or solver).get("returncode"),
                                            elapsed_seconds=(e0 or solver).get("wall_seconds"))
        if failure and failure["exit_code"] is None:
            missing["provenance.measurement.failure.exit_code"] = "No exit code observed."
        if failure and failure["elapsed_seconds"] is None:
            missing["provenance.measurement.failure.elapsed_seconds"] = "No child process wall observed."
        records.append(dict(
            attempt_id=f"fang-q1-stage-l-mem512-20260925-044-k{cores}-r0", revision=1,
            run_id="fang-q1-stage-l-mem512-20260925", algorithm_id="q1-shared-packet-pipeline",
            algorithm_name="Shared-input packet pipeline", variant="graph-derived-rectangle",
            solver_commit=SOURCE,
            parameters=dict(cores=cores, capacity_bytes={"L1": 524288, "UB": 131072},
                            bandwidth_bytes_per_cycle=60, same_wait_cycles=100,
                            cross_wait_cycles=1000, baseline_commit=BASELINE,
                            batch_budget=manifest["budget"], batch_actual_calls=receipt["calls"]),
            problem="P1", case_id="044", cores=cores, status=status,
            metrics=dict(makespan_cycles=result["makespan"] if success else None,
                         solver_wall_seconds=solver.get("wall_seconds"),
                         evaluation_wall_seconds=e0.get("wall_seconds"),
                         ddr_bytes=movement.get("scheduled_copy_bytes"),
                         extra_ddr_bytes=movement.get("added_copy_bytes"),
                         spill_bytes=movement.get("spill_added_copy_bytes"), cache_hit_rate=None),
            evaluator=dict(route="E0", commit=SOURCE,
                           entrypoint="data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"),
            identity=dict(graph_sha256=manifest["graph_sha256"], config_sha256=manifest["config_sha256"],
                          official_sha256=manifest["official_code_hash"],
                          plan_sha256=artifacts.get("plan", {}).get("sha256")),
            artifacts=artifacts, runtime_id="fang-windows-q1-stage-l-mem512-20260925",
            observed_at=run["finished_at"],
            timing=dict(solver_includes_evaluation=False,
                        evaluation_precision="Cold solver/DP and unchanged external E0 Job walls measured separately",
                        utc="UTC ISO8601 Z"),
            provenance=dict(producer_session=manifest["producer_session"],
                            task_url="https://github.com/huaweibei123/huaweicup2026/issues/98",
                            solver=dict(source=source(SOURCE, "src/q1_yuanzhifang/shared_packet_model.py", "construct"),
                                        authors=["yuanzhifang30-sudo"],
                                        method="Graph-derived shared-input repeated-job packet/interval DP; one actual rectangle plan, proxy is not an official score.",
                                        references=["https://github.com/huaweibei123/huaweicup2026/issues/98"],
                                        upstream=[], selected_algorithm_id=None, selected_solver_commit=None),
                            runner=dict(source=source(manifest["runner_head"], "src/q1_yuanzhifang/benchmark_l.py", "main"),
                                        argv=solver.get("command", []), working_directory="."),
                            environment=dict(os=manifest["platform"], cpu=manifest["cpu"] or "unavailable",
                                             gpu=None, ram_bytes=None, python=manifest["python"],
                                             dependencies="uv.lock sha256 " + sha(ROOT / "uv.lock"),
                                             threads=None, workers=1, peak_rss_bytes=None),
                            measurement=dict(started_at=run["started_at"], finished_at=run["finished_at"],
                                             seed=None, repeat_index=0, cold_start=True,
                                             solver_scope="External process launch through owned Job process cleanup; model DP included",
                                             evaluation_scope="Independent unchanged official E0 CLI through Job cleanup",
                                             budget=dict(wall_seconds=300, candidate_limit=1,
                                                         stop_reason=run["status"] + "; 0 retries"),
                                             calls=run["calls"], offline_costs="No current-case offline model or score selection.",
                                             failure=failure), missing_reasons=missing),
            notes=["Two exposed 044/k3,k4 cells only; no full matrix or blind mean.",
                   f"Official singlecore denominator {baseline_cycles} cycles from fixed {BASELINE}; 0 reruns.",
                   "Model proxy is not official E0 Makespan and does not choose by historical score."],
            source_url="https://github.com/huaweibei123/huaweicup2026/issues/98",
            baseline=verified_baseline, cache_pair=None))
    if feed.exists():
        raise FileExistsError(feed)
    feed.parent.mkdir(parents=True, exist_ok=True)
    feed.write_text(json.dumps(dict(schema_version=1, submission_version=1, records=records),
                               indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(records)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", type=Path, default=OUT)
    p.add_argument("--feed", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(dict(records=export(a.run_dir.resolve(), a.feed.resolve()), feed=str(a.feed.resolve()))))


if __name__ == "__main__":
    main()
