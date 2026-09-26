"""Export measured P2 attempts to immutable board-submission-v1 snapshots.

No solver, evaluator, network access or central board writes occur here.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .measure import EVALUATOR, REPO, ROOT, RUNNER, SOLVER, artifact, digest, read_json, relative, repo_path, save_json, utc


def source(commit, path, entrypoint):
    subprocess.check_output(["git", "cat-file", "-e", f"{commit}:{path}"], cwd=ROOT, stderr=subprocess.PIPE)
    return {"repo": REPO, "commit": commit, "path": path, "entrypoint": entrypoint}


def checked_artifact(item):
    if artifact(repo_path(item["path"])) != item:
        raise ValueError("recorded artifact bytes changed: " + item["path"])
    return item


def baseline_for(case, identity):
    base = ROOT / "results/benchmark-board/official-singlecore-20260924" / case
    run_path = base / "run.json"
    if not run_path.exists():
        return None
    receipt = read_json(run_path)
    for receipt_key, key in (("graph_sha256", "graph_sha256"), ("config_sha256", "config_sha256"),
                             ("official_code_hash", "official_sha256")):
        if receipt[receipt_key] != identity[key]:
            raise ValueError("baseline frozen identity mismatch: " + case)
    if receipt["status"] != "ok" or receipt["entrypoint"] != "singlecore_evaluate.evaluate_singlecore":
        raise ValueError("baseline receipt is not a successful official singlecore run")
    item = receipt["artifacts"]["result.json"]
    reference = checked_artifact({"path": item["path"], "sha256": item["sha256"]})
    result = read_json(repo_path(item["path"]))
    if result["makespan"] != receipt["makespan_cycles"]:
        raise ValueError("baseline result/receipt makespan mismatch")
    return {key: identity[key] for key in ("graph_sha256", "config_sha256", "official_sha256")} | {
        "route": "E0", "entrypoint": "singlecore_evaluate.evaluate_singlecore", "result": reference}


def null_reasons(value, prefix="provenance"):
    reasons = {}
    for key, child in value.items():
        path = prefix + "." + key
        if key in ("selected_algorithm_id", "selected_solver_commit", "missing_reasons") or (key == "failure" and child is None):
            continue
        if isinstance(child, dict):
            reasons.update(null_reasons(child, path))
        elif child is None:
            reasons[path] = "Actual measurement did not collect this item; no value inferred."
    return reasons


def record_for(run_path, spec, ledger, ledger_artifact):
    run = read_json(run_path)
    method, stages = run["method"], run["stages"]
    if run["solver_commit"] != spec["solver_commit"] or run["runner_commit"] != spec["runner_commit"]:
        raise ValueError("actual code commit differs from frozen spec")
    if run["evaluator_commit"] != spec["evaluator_commit"]:
        raise ValueError("actual evaluator commit differs from frozen spec")
    artifacts = {key: checked_artifact(item) for key, item in run["artifacts"].items()}
    artifacts.update(run=artifact(run_path), manifest=ledger_artifact)
    # A timed-out E0 may leave a partial JSON; retain its bytes without treating
    # it as a complete result or preventing the failure record from exporting.
    result = read_json(repo_path(artifacts["result"]["path"])) if run["status"] == "ok" and "result" in artifacts else None
    if "plan" in artifacts and artifacts["plan"]["sha256"] != run["identity"]["plan_sha256"]:
        raise ValueError("plan identity differs from recorded stored bytes")
    metrics = {"makespan_cycles": None,
               "solver_wall_seconds": stages.get("solver", {}).get("wall_seconds"),
               "evaluation_wall_seconds": stages.get("E0", {}).get("wall_seconds"),
               "ddr_bytes": None, "extra_ddr_bytes": None, "spill_bytes": None, "cache_hit_rate": None}
    if run["status"] == "ok":
        if result is None or result["scene"] != "B" or result["num_cores"] != run["cores"]:
            raise ValueError("successful attempt lacks matching P2 E0 output")
        if result["makespan"] != run["metrics"]["makespan_cycles"]:
            raise ValueError("result/receipt makespan mismatch")
        movement = result["data_movement_bytes"]
        if movement != run["metrics"]["data_movement_bytes"]:
            raise ValueError("result/receipt movement mismatch")
        metrics.update(makespan_cycles=result["makespan"], ddr_bytes=movement["scheduled_copy_bytes"],
                       extra_ddr_bytes=movement["added_copy_bytes"], spill_bytes=movement["spill_added_copy_bytes"])
    params = {"strategy": method["variant"], "solver_args": method["args"], "seed": 0,
              "repeat_index": 0, "cores": run["cores"], "workers": 1,
              "budget": spec["budget"], "expected_unsupported_cases": method.get("expected_unsupported_cases", []),
              "selection_policy": "one fixed direct construction; no online E0 selection; post-hoc development comparison only",
              "batch_preparation": ledger["preparation"],
              "python_hash_seed": 0, "thread_environment": {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}}
    # Successful solver stdout contains structure-derived W, lag or lookahead;
    # retain these actual decisions without treating them as pre-timed tuning.
    stdout = run_path.parent / "solver.stdout.txt"
    if stdout.exists():
        try:
            params["solver_report"] = json.loads(stdout.read_text(encoding="utf-8"))
        except ValueError:
            pass
    provenance = {
        "producer_session": spec["producer_session"], "task_url": spec["task_url"],
        "solver": {
            "source": source(run["solver_commit"], SOLVER, "python -X utf8 -B -m src.q2.feedback.construct"),
            "authors": spec.get("authors", ["yuanzhifang30-sudo"]), "method": method["description"],
            "references": method["references"], "upstream": method["upstream"],
            "selected_algorithm_id": None, "selected_solver_commit": None},
        "runner": {
            "source": source(run["runner_commit"], RUNNER, "python -X utf8 -B -m src.q2.feedback.measure"),
            "argv": ledger["runner_argv"], "working_directory": "."},
        "environment": run["environment"],
        "measurement": {
            "started_at": run["started_at"], "finished_at": run["finished_at"], "seed": 0,
            "repeat_index": 0, "cold_start": True,
            "solver_scope": "External perf_counter: before spawning a fresh Python solver through process exit after graph load, contraction/indexing, direct construction, official structural derivation checks and final two-field plan write; no E0 or online candidate comparison. Parent startup observation and durable dispatch bookkeeping are included. Fresh process; OS filesystem caches are uncontrolled.",
            "evaluation_scope": "Separate fresh unmodified official P2 CLI process after solver exit, including imports, input/plan/config reads, complete evaluation, full result/trace/log writes and process exit. This time is not included in solver wall.",
            "budget": {"wall_seconds": spec["budget"]["solver_timeout_seconds"], "candidate_limit": 1,
                       "stop_reason": run.get("stop_reason")},
            "calls": run["calls"], "offline_costs": spec["offline_costs"], "failure": run["failure"]},
        "missing_reasons": {}}
    provenance["missing_reasons"] = null_reasons(provenance)
    provenance["missing_reasons"]["provenance.environment.peak_rss_bytes"] = "Peak RSS not sampled by this runner; CPU/RAM inventory and single worker/thread configuration are recorded."
    baseline = baseline_for(run["case_id"], run["identity"])
    notes = [
        "Fixed finite development comparison, not an online portfolio or a full 100-case/1..5-core algorithm result.",
        "All declared method attempts are retained, including worse results and predeclared unsupported structures; no retry.",
        "Makespan is simulated cycles; solver wall and separate external E0 wall are real seconds. The official 5–10 minute guidance is not a 600-second disqualification rule.",
        "Fresh Python process for each attempt; OS/filesystem caches were not cleared. Threads=1 is the configured solver/BLAS limit, not a hardware inventory or OS-thread measurement.",
        "Result and trace gzip files preserve complete original bytes; raw and compressed hashes are recorded in run.json.",
        "Code/source and artifact checks are not independent scientific validation or final algorithm acceptance."]
    notes.append("Frozen-byte/Git preflight is recorded separately as batch_preparation before the batch budget T0; it is not algorithm preprocessing. The batch envelope includes serial receipt/compression work, which is not solver wall.")
    if baseline is None:
        notes.append("No matching shared official singlecore artifact available; baseline remains unknown; no baseline rerun.")
    return {
        "attempt_id": run["attempt_id"], "revision": 1, "run_id": run["run_id"],
        "algorithm_id": method["algorithm_id"], "algorithm_name": method["algorithm_name"],
        "variant": method["variant"], "solver_commit": run["solver_commit"], "parameters": params,
        "problem": "P2", "case_id": run["case_id"], "cores": run["cores"], "status": run["status"],
        "metrics": metrics,
        "evaluator": {"route": "E0", "commit": run["evaluator_commit"], "entrypoint": EVALUATOR},
        "identity": run["identity"], "artifacts": artifacts, "runtime_id": spec["runtime_id"],
        "observed_at": run["started_at"],
        "timing": {"solver_includes_evaluation": False, "evaluation_precision": "time.perf_counter wall seconds; external process lifecycle",
                   "utc": "UTC from datetime.now(timezone.utc); start and finish recorded at execution"},
        "provenance": provenance, "notes": notes, "source_url": spec["source_url"],
        "baseline": baseline, "cache_pair": None}


def export(batch, output):
    spec = read_json(batch / "spec.json")
    ledger_path = batch / "ledger.json"
    ledger = read_json(ledger_path)
    if ledger["state"] == "running":
        raise ValueError("do not export a batch while its ledger is changing")
    ledger_artifact = artifact(ledger_path)
    records = [record_for(repo_path(name), spec, ledger, ledger_artifact) for name in ledger["attempts"]]
    totals = {key: sum(row["provenance"]["measurement"]["calls"][key] for row in records) for key in ("solver", "E0", "E1", "E2")}
    if totals != ledger["charged_calls"]:
        raise ValueError("attempt call totals differ from durable ledger")
    feed = {"schema_version": 1, "submission_version": 1, "records": records}
    # Use the site's existing schema checker without any production service import.
    from src.benchmark_board.protocol import validate_feed
    validate_feed(feed, submission=True)
    save_json(output, feed)
    command = [sys.executable, "-X", "utf8", "-B", "src/benchmark_board/protocol.py", relative(output), "--submission"]
    check = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
    validation = {"checked_at": utc(), "command": ["python", *command[1:]], "returncode": check.returncode,
                  "stdout": check.stdout, "stderr": check.stderr, "feed": artifact(output),
                  "scope": "read-only schema and artifact preflight; zero solver/E0/E1/E2 calls; no network or central writes"}
    save_json(output.with_name(output.stem + "-preflight.json"), validation)
    if check.returncode:
        raise ValueError("board protocol preflight failed; see immutable preflight receipt")
    print(check.stdout.strip())
    return feed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    batch = args.batch.resolve()
    if not batch.is_relative_to(ROOT / "results/a/q2-yuanzhifang/feedback-20260924"):
        raise ValueError("batch is outside the assigned output directory")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = args.output.resolve() if args.output else batch / f"board-feed-{stamp}.json"
    if not output.is_relative_to(batch):
        raise ValueError("feed must be saved in the measured batch directory")
    export(batch, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
