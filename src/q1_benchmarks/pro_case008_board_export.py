"""Export one existing lawful regression; zero solver/evaluator calls."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
DATA = "3dd923a86ce97480c37edf749806255eab33a6e9"
DATA_PATH = "results/a/review/p1-pro-case008-e0-20260924/20260924T1720Z-pro008-auto"
SINGLECORE = "6fcec11ccc472a1a652b21feb6fccf85a4555598"
SINGLECORE_PATH = "results/benchmark-board/official-singlecore-20260924/008"
REPO = "huaweibei123/huaweicup2026"
SESSION = "nikolastarx/s-6607cb2735304751b36662035723372b"
TASK = "https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5815486806"


def blob(commit, path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def source(commit, path, entry):
    return {"repo": REPO, "commit": commit, "path": path, "entrypoint": entry}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    output = args.output
    if output.is_absolute() or ".." in output.parts or not output.as_posix().startswith("results/"):
        raise ValueError("Use a fresh repo-relative results directory")
    out = ROOT / output
    out.mkdir(parents=True, exist_ok=False)
    run = json.loads(blob(DATA, f"{DATA_PATH}/run.json"))
    manifest = json.loads(blob(DATA, f"{DATA_PATH}/manifest.json"))
    result = json.loads(blob(DATA, f"{DATA_PATH}/result.json"))
    diagnostics = json.loads(blob(DATA, f"{DATA_PATH}/diagnostics.json"))
    assert run["status"] == "ok" and run["calls"] == {"solver": 1, "E0": 1, "E1": 0, "E2": 0, "baseline_E0": 0}
    single_run_raw = blob(SINGLECORE, f"{SINGLECORE_PATH}/run.json")
    single_run = json.loads(single_run_raw)
    single_raw = blob(SINGLECORE, f"{SINGLECORE_PATH}/result.json.gz")
    single = json.loads(gzip.decompress(single_raw))
    assert single_run["entrypoint"] == "singlecore_evaluate.evaluate_singlecore"
    assert single_run["status"] == "ok" and single_run["returncode"] == 0
    assert single["scene"] == "A" and single["num_cores"] == 1
    assert single["makespan"] == single_run["makespan_cycles"] == 487605
    assert sha(single_raw) == single_run["artifacts"]["result.json"]["sha256"]
    identity = {"graph_sha256": manifest["input"]["sha256"], "config_sha256": manifest["config_sha256"],
                "official_sha256": manifest["official_code_hash"], "plan_sha256": run["plan"]["sha256"]}
    for current, prior in (("graph_sha256", "graph_sha256"), ("config_sha256", "config_sha256"), ("official_sha256", "official_code_hash")):
        assert identity[current] == single_run[prior]
    references = out / "references"
    references.mkdir()
    single_result_path = references / "official-singlecore-008-result.json.gz"
    single_result_path.write_bytes(single_raw)
    (references / "official-singlecore-008-run.json").write_bytes(single_run_raw)
    def artifact(path):
        path = Path(path)
        return {"path": path.as_posix(), "sha256": sha((ROOT / path).read_bytes())}
    artifacts = {}
    for key, name in (("plan", "plan.json"), ("result", "result.json"), ("run", "run.json"),
                      ("trace", "trace.json"), ("log", "official.log"), ("manifest", "manifest.json")):
        path = f"{DATA_PATH}/{name}"
        raw = blob(DATA, path)
        assert (ROOT / path).read_bytes() == raw
        artifacts[key] = {"path": path, "sha256": sha(raw)}
    env = manifest["environment"]
    source_commit = manifest["source_commit"]
    source_path = f"{manifest['material_git_root']}/p1_phase_cut.py"
    model = diagnostics["model"]
    movement = result["data_movement_bytes"]
    record = {
        "attempt_id": f"nikolastarx-{run['run_id']}-P1-008-k4-r0", "revision": 1, "run_id": run["run_id"],
        "algorithm_id": "q1-one-cut-return-rotation-candidate",
        "algorithm_name": "单切返程错位包：直接 auto 候选实验", "variant": "auto-candidate-without-adoption-gate",
        "solver_commit": source_commit, "problem": "P1", "case_id": "008", "cores": 4, "status": "ok",
        "parameters": {"cores": 4, "mode": "auto", "actual_derived_packet": diagnostics["packet"],
            "actual_derived_cut_chains": diagnostics["cut_chains"], "actual_derived_whole_packet": diagnostics["whole_packet"],
            "conservative_dominance_certificate": diagnostics["conservative_dominance_certificate"],
            "integration_fallback_called": False, "production_adopted": False, "candidate_limit": 1,
            "constructor_timeout_seconds_including_cleanup": 30, "evaluation_timeout_seconds_including_cleanup": 60,
            "batch_timeout_seconds": 120, "cleanup_reserve_per_child_seconds": 1, "workers": 1, "retries": 0,
            "scoring_backend": "Analytical proxy in author CLI; no internal E0/E1/E2, one external final E0",
            "policy": "One preauthorized offline candidate even when dominance certificate is false; no parameter sweep"},
        "metrics": {"makespan_cycles": result["makespan"], "solver_wall_seconds": run["solver"]["wall_seconds"],
            "evaluation_wall_seconds": run["evaluation"]["wall_seconds"], "ddr_bytes": movement["scheduled_copy_bytes"],
            "extra_ddr_bytes": movement["added_copy_bytes"], "spill_bytes": movement["spill_added_copy_bytes"]},
        "evaluator": {"route": "E0", "commit": run["runner_commit"], "entrypoint": "multicore_cut_evaluate_problem_1.evaluate_scene_a"},
        "identity": identity, "artifacts": artifacts,
        "runtime_id": "nikolastarx-m5pro-macos-py312-20260924", "observed_at": run["finished_at"],
        "timing": {"solver_includes_evaluation": False, "evaluation_precision": "time.perf_counter elapsed seconds, preserved without rounding",
            "utc": "Original controller and subprocess timestamps are UTC; export time is not observation time"},
        "provenance": {"producer_session": SESSION, "task_url": TASK,
            "solver": {"source": source(source_commit, source_path, "main (--mode auto; choose_and_construct)"),
                "authors": ["nikolastarx"], "method": "ChatGPT Pro supplied a strict M-V+-M chain candidate: analytically choose packet/cut counts, rotate next prefixes with prior returns inside Tasks; direct auto CLI, not integrate_construct/fallback.",
                "references": [f"https://github.com/{REPO}/blob/{source_commit}/{quote(manifest['material_git_root'] + '/RESEARCH_NOTE.md')}",
                    "https://chatgpt.com/g/g-p-6ab2d820c86081918067a0c6d5eb1ab6-huaweicup/c/6ab54526-3220-83e8-9dca-f2f924c91d69"],
                "upstream": [], "selected_algorithm_id": None, "selected_solver_commit": None},
            "runner": {"source": source(run["runner_commit"], "src/q1_benchmarks/pro_case008_e0.py", "run"),
                "argv": [".venv/bin/python", "-B", "src/q1_benchmarks/pro_case008_e0.py", "run", run["run_id"]], "working_directory": "."},
            "environment": {"os": env["platform"], "cpu": env["cpu"], "gpu": "none", "ram_bytes": env["ram_bytes"],
                "python": env["python"], "dependencies": f"uv sync --locked --python 3.12; uv.lock SHA256={manifest['uv_lock_sha256']}",
                "threads": None, "workers": 1, "peak_rss_bytes": None},
            "measurement": {"started_at": run["started_at"], "finished_at": run["finished_at"],
                "seed": None, "repeat_index": 0, "cold_start": True,
                "solver_scope": "Fresh CLI interpreter startup, graph read, analytical construction and model diagnostics, plan/diagnostics publication through process exit. External E0 excluded. OS page caches not flushed.",
                "evaluation_scope": "One fresh unmodified official P1 E0 CLI through complete result/trace/log write and exit; external final check, no online selection. Controller source/legality/hash checks and archival separate.",
                "budget": {"wall_seconds": 30, "candidate_limit": 1, "stop_reason": "One authorized constructor and external E0 completed; legal regression preserved; execution gate closed"},
                "calls": {key: run["calls"][key] for key in ("solver", "E0", "E1", "E2")},
                "offline_costs": "No training or compiled preprocessing. Locked environment and exact ZIP-member extraction in preparation; prior Pro theory/model experiments are separate author research, not local scoring. This export adds 0 calls; official singlecore and bounded comparison reused from fixed originals.",
                "failure": None},
            "missing_reasons": {"provenance.environment.threads": "Not sampled; child OMP/OPENBLAS/MKL environment variables each set to 1",
                "provenance.environment.peak_rss_bytes": "Only cumulative Darwin RUSAGE_CHILDREN maximum recorded; not a separately isolated per-attempt peak",
                "provenance.measurement.seed": "Deterministic construction; no RNG"}},
        "notes": [
            "Real official graph 008, four simulated cores; legal E0 regression kept for history/feedback. Six synthetic micrographs are excluded from this feed.",
            "Against prior bounded P1/k4 plan: 123060 -> 162326 cycles, +39266 (+31.908012351698357%). That optimized historical plan is not the official singlecore denominator.",
            "Dominance certificate=false. Model conditional_exact_model=false and DDR intervals disjoint=false; model115736 is not the official162326. Conservative envelope224551 still contains the observation.",
            "112 Tasks, official MEMORY dependency count0 and spill0; extra DDR3244032B. Observed M/V overlap97272 cycles equals model. No causal decomposition or generalization claim.",
            "Author code attributed to ChatGPT Pro research; authors login identifies the owning captain session. This algorithm ID is the direct experimental candidate, not the default production solver or integration fallback.",
            f"Executed source={source_commit}; runner={run['runner_commit']}; original data={DATA}; export commit is not substituted for any execution identity.",
            f"Official singlecore denominator487605 from {SINGLECORE}:{SINGLECORE_PATH}/result.json.gz, same graph/config/official identity; 0 baseline reruns.",
            "Root coordinated P2/P3 release before this attempt. Both owned subprocess groups exited; shared host, no exclusive timing or controlled speedup claim."],
        "source_url": "https://github.com/huaweibei123/huaweicup2026/pull/128",
        "baseline": {key: identity[key] for key in ("graph_sha256", "config_sha256", "official_sha256")}}
    record["baseline"].update(route="E0", entrypoint="singlecore_evaluate.evaluate_singlecore",
                              result=artifact(single_result_path.relative_to(ROOT)))
    feed_name = "board-feed-20260924T1730Z-pro008.json"
    write(out / feed_name, {"schema_version": 1, "submission_version": 1, "records": [record]})
    write(out / "export-receipt.json", {"exported_at": datetime.now(timezone.utc).isoformat(),
        "export_only": True, "new_calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
        "source_commit": source_commit, "runner_commit": run["runner_commit"], "original_data_commit": DATA,
        "original_source_branch": "codex/p1-pro-evidence-source-20260925", "entry_sha256": manifest["entry_sha256"],
        "singlecore_source": {"commit": SINGLECORE, "path": SINGLECORE_PATH, "result_sha256": sha(single_raw),
            "run_sha256": sha(single_run_raw), "makespan_cycles": single["makespan"]},
        "derived_official_singlecore_speedup": single["makespan"] / result["makespan"],
        "feed": artifact((out / feed_name).relative_to(ROOT)),
        "exporter_sha256": sha(Path(__file__).read_bytes()),
        "registration": "New algorithm identity declared with source/authors/method; protocol registry is not a whitelist. Owner registers on receipt; no central edits made."})
    print(json.dumps({"feed": str(output / feed_name), "records": 1, "new_solver_E0_calls": 0,
                      "official_singlecore": single["makespan"], "official_result": result["makespan"]}))


if __name__ == "__main__":
    main()
