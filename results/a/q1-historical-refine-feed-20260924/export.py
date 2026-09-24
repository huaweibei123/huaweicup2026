"""Export existing profile-refine evidence; never execute submitted code."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
ORIGIN = "909f6f1f29fc7f2557395fae98f0f68a853f4c4b"
OLD = "results/a/q1-profile-refine-20260924"
REPO = "huaweibei123/huaweicup2026"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def raw(path):
    return subprocess.check_output(["git", "show", f"{ORIGIN}:{path}"], cwd=ROOT)


def source(path, entrypoint, commit=ORIGIN):
    return {"repo": REPO, "commit": commit, "path": path, "entrypoint": entrypoint}


def save(path, data):
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != data:
            raise ValueError(f"Refuse to overwrite different bytes: {path}")
    else:
        target.write_bytes(data)
    return {"path": target.relative_to(ROOT).as_posix(), "sha256": sha(data)}


def dump(path, obj):
    return save(path, (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode())


def main():
    protocol = json.loads(raw(f"{OLD}/protocol.json"))
    original_head = protocol["code_base_commit"]
    for name, digest in protocol["source_hashes"].items():
        assert sha(raw(f"{OLD}/source/{name}")) == digest
    official = json.loads(raw("docs/a/source-manifest.json"))["official_code_hash"]
    assert sha(raw("data/raw/a/official/data/config.txt")) == protocol["config_sha256"]
    records, evidence = [], []
    for case, expected in (("002", 88188), ("044", 114443), ("051", 336057)):
        prefix = f"{OLD}/case{case}"
        summary_raw = raw(f"{prefix}/summary.json")
        summary = json.loads(summary_raw)
        supervisor = json.loads(raw(f"{prefix}/supervisor.json"))
        plan = raw(f"{prefix}/confirmed_plan.json")
        seed = raw(f"{prefix}/seed.json")
        assert sha(plan) == summary["confirmed_plan_sha256"]
        assert sha(seed) == summary["seed_sha256"]
        parent_path = f"results/a/q1-guided-moves-20260924/case{case}/guided/best_plan.json"
        assert raw(parent_path) == seed
        assert summary["status"] == supervisor["status"] == "ok"
        assert summary["final_confirms_provisional"] and summary["e0_final"]["returncode"] == 0
        manifest = json.loads(raw(f"{prefix}/execution-evidence.manifest.json"))
        archive = raw(f"{prefix}/execution-evidence.tar.xz")
        assert sha(archive) == manifest["sha256"]
        member = "e0_final/result.json"
        expected_member = next(x for x in manifest["members"] if x["path"] == member)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:xz") as bundle:
            result_raw = bundle.extractfile(member).read()
        assert sha(result_raw) == expected_member["sha256"]
        result = json.loads(result_raw)
        assert result["makespan"] == summary["confirmed_result"]["makespan"] == expected
        assert result["num_cores"] == 4 and result["scene"] == "A"
        assert len(json.loads(plan)["core_schedules"]) == 4
        movement = result["data_movement_bytes"]
        artifacts = {"plan": save(f"{case}/plan.json", plan),
                     "result": save(f"{case}/result.json", result_raw),
                     "run": save(f"{case}/run.json", summary_raw)}
        save(f"{case}/seed.json", seed)
        stage = {"case": case, "source_commit": ORIGIN, "source_directory": prefix,
                 "plan_sha256": sha(plan), "seed_sha256": sha(seed),
                 "result_archive_sha256": sha(archive), "result_member": member,
                 "result_member_sha256": sha(result_raw),
                 "parent_plan_path": parent_path,
                 "supervised_refinement_wall_seconds": supervisor["wall_seconds"],
                 "refinement_function_seconds": summary["total_seconds"],
                 "search_phase_seconds": summary["search_seconds"],
                 "final_e0_confirmation_seconds": summary["e0_final"]["seconds"],
                 "raw_to_final_solver_wall_seconds": None,
                 "timing_scope": "Refinement from existing guided-moves seed only; excludes seed production. Supervisor includes process launch/reaping; function total starts inside refine(). Final E0 is within refinement.",
                 "historical_calls": {"solver": 1, "E0": 2, "E1": summary["evaluations"], "E2": 0},
                 "historical_local_profile_builds": len(summary["rounds"])}
        evidence.append(stage)
        missing = {
            "metrics.solver_wall_seconds": "Full raw-graph-to-plan time absent; only refinement-stage time exists, excluding historical seed production.",
            "timing.solver_includes_evaluation": "No complete solver wall is reported. Historical final E0 is included in the separately retained refinement-stage wall.",
            "timing.utc": "Original receipts contain monotonic elapsed durations, no run UTC timestamps.",
            "provenance.runner.argv": "Exact runtime argv was not retained; source constructs commands but this export does not fabricate an observed invocation.",
            "provenance.runner.working_directory": "Actual inherited working directory was not recorded.",
            "provenance.environment.cpu": "Original protocol records OS/architecture, not CPU model.",
            "provenance.environment.gpu": "Original protocol does not record GPU or its absence.",
            "provenance.environment.ram_bytes": "Machine RAM was not recorded; RSS budget is not machine RAM.",
            "provenance.environment.threads": "Thread count was not recorded; workers=1 is not a thread count.",
            "provenance.measurement.started_at": "No original UTC timestamp; Git timestamps and mtimes are not substituted.",
            "provenance.measurement.finished_at": "No original UTC timestamp; Git timestamps and mtimes are not substituted.",
            "provenance.measurement.seed": "This refinement uses deterministic priorities/ID ties and an existing plan, not an integer random seed.",
            "provenance.measurement.cold_start": "Original run does not classify cold/warm start.",
        }
        provenance = {
            "producer_session": "nikolastarx/s-6607cb2735304751b36662035723372b",
            "task_url": f"https://github.com/{REPO}/issues/33",
            "solver": {"source": source(f"{OLD}/source/profile_refine.py", "refine(args), exact as-run archived bytes"),
                       "authors": ["NikolaStarx"],
                       "method": "Two-round local partition refinement of an existing guided-moves plan. Actual Task profiles prioritize split/cover-merge candidates; E1 selects and original E0 confirms. Not a general raw-graph solver.",
                       "references": [f"https://github.com/{REPO}/blob/{ORIGIN}/{OLD}/protocol.json"],
                       "upstream": [source(parent_path, "fixed historical seed plan"),
                                    source(f"{OLD}/source/profile_candidates.py", "candidates")],
                       "selected_algorithm_id": None, "selected_solver_commit": None},
            "runner": {"source": source(f"{OLD}/source/profile_refine.py", "experiment -> run_guarded -> refine"),
                       "argv": [], "working_directory": None},
            "environment": {"os": protocol["platform"], "cpu": None, "gpu": None, "ram_bytes": None,
                            "python": protocol["python"], "dependencies": "uv.lock sha256=" + protocol["uv_lock_sha256"],
                            "threads": None, "workers": protocol["workers"],
                            "peak_rss_bytes": supervisor["sampled_group_peak_rss_bytes"]},
            "measurement": {"started_at": None, "finished_at": None, "seed": None,
                            "repeat_index": 0, "cold_start": None,
                            "solver_scope": stage["timing_scope"],
                            "evaluation_scope": "Historical final E0 confirmation subprocess phase, measured by confirm() using time.monotonic; included in refinement stage. Export runs no evaluation.",
                            "budget": {"wall_seconds": protocol["outer_case_wall_seconds"], "candidate_limit": 8,
                                       "stop_reason": "Two prescribed rounds completed; 8 new candidates plus one E1 seed score, final E0 confirmation succeeded."},
                            "calls": stage["historical_calls"],
                            "offline_costs": "Existing guided-moves seed generation and earlier search cost excluded and not aggregated here; no new training/compilation/benchmark performed by export.",
                            "failure": None},
            "missing_reasons": missing,
        }
        records.append({
            "attempt_id": f"nikolastarx-q1-profile-refine-20260924-P1-{case}-k4", "revision": 1,
            "run_id": "q1-profile-refine-20260924", "algorithm_id": "q1-profile-refine",
            "algorithm_name": "P1 历史种子计划的局部剖面改进", "variant": "two-round-profile-e1-e0-confirm-refinement-only",
            "solver_commit": ORIGIN,
            "parameters": {**{k: protocol[k] for k in ("rounds", "new_candidates_per_round", "max_e1_calls_per_case", "search_budget_seconds", "proposal_timeout_seconds", "e1_timeout_seconds", "worker_startup_timeout_seconds", "e0_timeout_seconds", "outer_case_wall_seconds", "sampled_process_group_rss_stop_bytes", "workers", "cache_bytes", "max_merge_ops", "objective", "failure_policy")},
                           "seed_plan_sha256": sha(seed), "seed_plan_path": parent_path,
                           "as_run_base_head": original_head, "as_run_source_hashes": protocol["source_hashes"],
                           "internal_evaluator_commit": protocol["evaluator_commit"], "local_profile_builds": len(summary["rounds"])},
            "problem": "P1", "case_id": case, "cores": 4, "status": "ok",
            "metrics": {"makespan_cycles": result["makespan"], "solver_wall_seconds": None,
                        "evaluation_wall_seconds": summary["e0_final"]["seconds"],
                        "ddr_bytes": movement["scheduled_copy_bytes"], "extra_ddr_bytes": movement["added_copy_bytes"],
                        "spill_bytes": movement["spill_added_copy_bytes"], "cache_hit_rate": None},
            "evaluator": {"route": "E0", "commit": original_head,
                          "entrypoint": "multicore_cut_evaluate_problem_1.evaluate_scene_a"},
            "identity": {"graph_sha256": summary["graph_sha256"], "config_sha256": protocol["config_sha256"],
                         "official_sha256": official, "plan_sha256": sha(plan)},
            "artifacts": artifacts, "runtime_id": "historical-q1-profile-refine-20260924-recorded-environment",
            "observed_at": None,
            "timing": {"solver_includes_evaluation": None, "evaluation_precision": "time.monotonic float seconds; display precision is not measurement accuracy", "utc": None},
            "provenance": provenance, "baseline": None, "cache_pair": None,
            "source_url": f"https://github.com/{REPO}/issues/33",
            "notes": ["Historical original attempt exported without rerun; run_id/attempt_id label the existing case receipt, not a new experiment.",
                      "repeat_index=0 denotes the sole receipt for this case in the original experiment's one-pass CASES loop, not a rerun or guessed timestamp.",
                      f"solver_commit={ORIGIN} identifies the exact archived as-run source path, not the post-run hardened src/q1/profile_refine.py. Runtime base HEAD was {original_head} with recorded source hashes.",
                      "Full solver wall, runtime UTC, CPU/RAM/GPU and cold/warm classification are unknown. Refinement-only wall remains in provenance-summary.json and must not populate solver_wall_seconds.",
                      "Original plan/result/run bytes copied unchanged; archive and payload hashes checked. This export is not an independent E0 rerun or scientific acceptance.",
                      "Historical counters include 2 complete E0 confirmations and 9 E1 calls; two additional local Task profile compilations are recorded separately."]})
    dump("provenance-summary.json", {"origin_commit": ORIGIN, "runtime_base_head": original_head,
        "as_run_source_hashes": protocol["source_hashes"], "cases": evidence,
        "export_calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}})
    dump("board-feed-historical-refine.json", {"schema_version": 1, "submission_version": 1, "records": records})
    print(json.dumps({"records": len(records), "source_commit": ORIGIN, "export_calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0}}))


if __name__ == "__main__":
    main()
