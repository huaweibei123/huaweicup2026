"""Export completed P123 receipts to board-submission-v1 without evaluating code.

Only new feed files are written. Original plans, results and run receipts are
referenced by their stored-byte SHA256; they are never rewritten or copied.
This is a non-atomic observation of a live directory, not a process monitor.
The receiver's pinned protocol.py --submission remains the admission check.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid

REPO = "huaweibei123/huaweicup2026"
PROTOCOL_COMMIT = "b0937de5b97cb2e85fda68d702c8076457993588"
ARCHIVE_COMMIT = "bd239af75e6a4db6169efe9ddd9011d887447007"
TASK_URL = f"https://github.com/{REPO}/issues/15"
MAX_FEED = 8 * 1024 * 1024
MAX_ARTIFACT = 64 * 1024 * 1024
MAX_RECEIPT = 2 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
PRIVATE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|(?:^|\s)/(?:Users|home|mnt|tmp)/|\\\\[^\\\s]+\\")
METHODS = {
    "P1": ("q1-bounded-search", "Bounded structural candidate search", "search-e1-e0-confirm", "src/q1/search.py", "search"),
    "P2": ("q2-contiguous-baseline", "Topological contiguous-block construction", "contiguous", "src/q2/construct.py", "main"),
    "P3": ("q3-structure-selected", "Structure-guarded selected construction", "unknown", "src/q3/solve.py", "main"),
}
ENTRYPOINTS = {
    "P1": "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py CLI",
    "P2": "data/raw/a/official/code/multicore_cut_evaluate_problem_2.py::evaluate_scene_b",
    "P3": "data/raw/a/official/code/multicore_cut_evaluate_problem_3.py::evaluate_problem_3",
}
EVALUATOR_COMMITS = {
    "P1": "4dff90ef699fd51845cf482951e8477066f5f566",
    "P2": "f27ef37bb76dcf556f35d3f2328e405d92241d9c",
    "P3": "a4e7ee13310d693ec4fb5cc236669ceb3b172d1f",
}
SOURCE_CHECK = "evaluator-source-check-20260924T131820Z.json"


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("receipt timestamp has no timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def private_strings(value):
    if isinstance(value, str):
        return bool(PRIVATE.search(value))
    if isinstance(value, dict):
        return any(private_strings(k) or private_strings(v) for k, v in value.items())
    if isinstance(value, list):
        return any(private_strings(v) for v in value)
    return False


def source(commit, path, entrypoint):
    return {"repo": REPO, "commit": commit, "path": path, "entrypoint": entrypoint}


class Capture:
    """Read each small receipt once; stream hashes without opening evaluators."""

    def __init__(self, repo):
        self.repo = repo.resolve()
        self.bytes = {}
        self.hashes = {}

    def relative(self, path):
        resolved = path.resolve()
        relative = resolved.relative_to(self.repo).as_posix()
        if relative.split("/")[0] not in {"results", "docs", "data", "tasks"}:
            raise ValueError("artifact has a disallowed repository prefix")
        if any(part in {"..", ".git"} for part in relative.split("/")) or ":" in relative or "\\" in relative:
            raise ValueError("unsafe artifact path")
        return relative

    def read(self, path, optional=False):
        if not path.is_file():
            if optional:
                return None
            raise ValueError(f"missing required receipt: {self.relative(path)}")
        if path not in self.bytes:
            if path.stat().st_size > MAX_RECEIPT:
                raise ValueError(f"receipt exceeds small-JSON limit: {self.relative(path)}")
            raw = path.read_bytes()
            if len(raw) > MAX_RECEIPT:
                raise ValueError("receipt grew beyond small-JSON limit")
            self.bytes[path] = raw
            self.hashes[path] = digest(raw)
        return json.loads(self.bytes[path])

    def sha(self, path):
        if path not in self.hashes:
            before = path.stat()
            value = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    value.update(chunk)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError(f"artifact changed while hashing: {self.relative(path)}")
            self.hashes[path] = value.hexdigest()
        return self.hashes[path]

    def artifact(self, path, notes, label, expected=None):
        relative = self.relative(path)
        if not path.is_file():
            notes.append(f"Missing {label}: {relative}")
            return None
        if path.stat().st_size > MAX_ARTIFACT:
            notes.append(f"{label} exceeds 64 MiB stored-byte limit; original retained: {relative}")
            return None
        actual = self.sha(path)
        if expected is not None and actual != expected:
            notes.append(f"{label} does not match its original receipt SHA256; reference withheld: {relative}")
            return None
        return {"path": relative, "sha256": actual}


def load_prior(paths, new_run_id):
    latest = {}
    contents = {}
    for path in paths:
        if path.stat().st_size > MAX_FEED:
            raise ValueError("prior feed exceeds 8 MiB")
        feed = json.loads(path.read_bytes())
        for record in feed["records"]:
            attempt = record["attempt_id"]
            revision = record["revision"]
            if type(revision) is not int or revision < 1:
                raise ValueError("invalid prior revision")
            identity = (record["problem"], record["case_id"], record["cores"],
                        record["algorithm_id"], record["run_id"], record["solver_commit"])
            previous = latest.get(attempt)
            if previous and identity != tuple(previous[k] for k in (
                    "problem", "case_id", "cores", "algorithm_id", "run_id", "solver_commit")):
                raise ValueError("prior attempt identity changed")
            key = (attempt, revision)
            encoded = packed(record)
            if key in contents and contents[key] != encoded:
                raise ValueError("conflicting prior attempt/revision")
            contents[key] = encoded
            if previous is None or revision > previous["revision"]:
                latest[attempt] = record
    cells = {}
    for record in latest.values():
        key = (record["problem"], record["case_id"], record["cores"], record["solver_commit"])
        if key in cells:
            raise ValueError("multiple prior attempts for one cell; explicit reconciliation required")
        cells[key] = record
    # The first imported feed includes six older preflight attempts. Preserve
    # those original IDs/run IDs, while new batch cells use the explicit run.
    current_run = [r for r in latest.values() if r["run_id"] == new_run_id]
    runtimes = {r["runtime_id"] for r in current_run}
    prefixes = set()
    for record in current_run:
        attempt = record["attempt_id"]
        match = re.fullmatch(r"(.+)-P[123]-\d{3}-k[1-5]", attempt)
        if not match:
            raise ValueError("prior attempt IDs do not follow the existing cell-ID convention")
        prefixes.add(match[1])
    if len(runtimes) != 1 or len(prefixes) != 1:
        raise ValueError("selected new-cell run must have one existing runtime/ID convention")
    return cells, new_run_id, runtimes.pop(), prefixes.pop()


def explain_nulls(value, reasons, prefix="provenance"):
    if value is None:
        if not prefix.endswith((".failure", ".selected_algorithm_id", ".selected_solver_commit")):
            reasons.setdefault(prefix, "Not recorded by the original receipt; not inferred during export.")
    elif isinstance(value, dict):
        for key, item in value.items():
            if key != "missing_reasons":
                explain_nulls(item, reasons, prefix + "." + key)


def environment_values(evidence):
    """Validate supplied observations; never probe hardware or infer values."""
    if (not isinstance(evidence, dict)
            or evidence.get("schema") != "p123-environment-evidence-v1"
            or evidence.get("verified") is not True):
        raise ValueError("environment evidence must declare verified observations")
    observed_at = evidence.get("measurement_observed_at")
    if not isinstance(observed_at, str) or not observed_at:
        raise ValueError("environment evidence needs an observation timestamp")
    observed_at = utc(observed_at)
    observation_source = evidence.get("source")
    if not isinstance(observation_source, str) or not observation_source.strip():
        raise ValueError("environment evidence needs its observation source")
    evidence_notes = evidence.get("notes")
    if (not isinstance(evidence_notes, list) or not evidence_notes
            or any(not isinstance(note, str) or not note.strip() for note in evidence_notes)):
        raise ValueError("environment evidence needs notes describing measurement/configuration scope")
    values = {key: evidence.get(key) for key in ("cpu", "ram_bytes", "threads")}
    if values["cpu"] is not None and (not isinstance(values["cpu"], str) or not values["cpu"].strip()):
        raise ValueError("environment CPU must be a nonempty verified description or null")
    for key in ("ram_bytes", "threads"):
        if values[key] is not None and (type(values[key]) is not int or values[key] <= 0):
            raise ValueError(f"environment {key} must be a positive verified integer or null")
    if private_strings(evidence):
        raise ValueError("environment evidence contains a private path")
    metadata = {"measurement_observed_at": observed_at, "source": observation_source,
                "notes": evidence_notes,
                "scope": "Supplementary machine observations/configuration; not per-cell measurements or measured effective OS thread counts."}
    return values, metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--run-dir", type=Path, default=Path("results/a/p123-multicore-20260924"))
    parser.add_argument("--prior-feed", type=Path, action="append", required=True,
                        help="All applicable previous feeds; highest revision is retained")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; never overwrite an export")
    parser.add_argument("--producer-session", required=True)
    parser.add_argument("--new-run-id", default="lyx-p123-multicore-20260924",
                        help="Existing prior-feed run for newly completed batch cells; old preflight IDs remain unchanged")
    parser.add_argument("--source-url", default=TASK_URL)
    parser.add_argument("--environment-evidence", type=Path,
                        help="Optional small verified CPU/RAM/thread evidence JSON inside the repository")
    parser.add_argument("--cell", action="append", help="Exact completed cell, e.g. P1/002/k2; repeat to select multiple cells")
    parser.add_argument("--limit", type=int, help="Finite sample of completed receipts for validation only")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.cell and args.limit is not None:
        parser.error("--cell and --limit cannot be combined")
    if args.cell and any(not re.fullmatch(r"P[123]/(?:00[1-9]|0[1-9][0-9]|100)/k[1-5]", cell) for cell in args.cell):
        parser.error("--cell must be an exact P1/002/k2-style cell identity")
    if not re.fullmatch(r"[a-z0-9-]+/s-[0-9a-f]{32}", args.producer_session):
        parser.error("--producer-session must be the actual registered session address")
    repo = args.repo.resolve()
    run = (repo / args.run_dir).resolve()
    output = args.output_dir.resolve()
    if output.exists():
        parser.error("--output-dir must not already exist")
    capture = Capture(repo)
    capture.relative(run)
    started = utc_now()
    environment = {"cpu": None, "ram_bytes": None, "threads": None}
    environment_metadata = None
    if args.environment_evidence is not None:
        environment_path = (repo / args.environment_evidence).resolve()
        environment_relative = capture.relative(environment_path)
        environment, environment_metadata = environment_values(capture.read(environment_path))
        environment_metadata.update(path=environment_relative, sha256=capture.sha(environment_path))
    prior, run_id, runtime_id, attempt_prefix = load_prior(args.prior_feed, args.new_run_id)
    protocol_path = run / "protocol.json"
    protocol = capture.read(protocol_path)
    manifest_path = repo / "docs/a/source-manifest.json"
    manifest = capture.read(manifest_path)
    if capture.sha(manifest_path) != protocol["official_source_manifest_sha256"]:
        raise ValueError("frozen manifest differs from run protocol")
    frozen = {entry["path"]: entry for entry in manifest["files"]}
    official_hash = manifest["official_code_hash"]
    source_check_path = run / SOURCE_CHECK
    source_check = capture.read(source_check_path)
    verified_evaluators = {item["problem"]: item for item in source_check["evaluators"]}
    if (source_check.get("schema") != "p123-evaluator-source-check-v1"
            or source_check.get("official_code_hash") != official_hash
            or len(source_check["evaluators"]) != 3
            or set(verified_evaluators) != set(METHODS)):
        raise ValueError("official evaluator source identity evidence mismatch")
    for problem, item in verified_evaluators.items():
        if (item.get("source_commit") != EVALUATOR_COMMITS[problem]
                or item.get("entrypoint") != ENTRYPOINTS[problem]
                or item.get("route") != "E0"
                or item.get("official_files_verified") != 10
                or item.get("runtime_bytes_match_manifest_and_git_blobs") is not True):
            raise ValueError("official evaluator source identity was not verified")
    ledger = capture.read(run / "harness/revisions.json")
    if ledger["original_protocol_sha256"] != capture.sha(protocol_path):
        raise ValueError("harness ledger protocol identity mismatch")
    registered = {r["sha256"] for r in ledger["revisions"]}
    legacy = None
    if ledger.get("legacy_evidence"):
        legacy_path = run / ledger["legacy_evidence"]["file"]
        legacy = capture.read(legacy_path)
        if capture.sha(legacy_path) != ledger["legacy_evidence"]["sha256"]:
            raise ValueError("legacy lineage manifest mismatch")
    paths = sorted((run / "cells").glob("P[123]/*/k[1-5]/cell.json"),
                   key=lambda p: (p.parent.parent.name, p.parent.name, p.parent.parent.parent.name))
    if args.cell:
        selected = set(args.cell)
        paths = [path for path in paths if path.parent.relative_to(run / "cells").as_posix() in selected]
        found = {path.parent.relative_to(run / "cells").as_posix() for path in paths}
        if found != selected:
            raise ValueError("selected completed cell receipts are missing: " + ", ".join(sorted(selected - found)))
    if args.limit is not None:
        paths = paths[:args.limit]
    records = []
    revised = 0
    for cell_path in paths:
        cell = capture.read(cell_path)
        row = cell["row"]
        problem, case, cores = row["problem"], row["case"], row["cores"]
        if problem not in METHODS or not re.fullmatch(r"00[1-9]|0[1-9][0-9]|100", case):
            raise ValueError("invalid cell identity")
        if type(cores) is not int or cores not in range(1, 6) or (problem != "P3" and cores == 1):
            raise ValueError("unexpected solver cell, including reused baseline anchor")
        if cell_path.parent != run / "cells" / problem / case / f"k{cores}":
            raise ValueError("receipt path and cell identity disagree")
        commit = protocol["versions"][problem]["commit"]
        if row.get("source_commit") != commit:
            raise ValueError("cell implementation differs from pinned protocol")
        old = prior.get((problem, case, cores, commit))
        method_id, method_name, variant, solver_path, entrypoint = METHODS[problem]
        if old and old["algorithm_id"] != method_id:
            raise ValueError("prior algorithm identity differs from this run")
        notes = ["Export only; no solver, evaluator, retries or result rewriting.",
                 "Complete final receipts only; directory existence is not evidence of a running process.",
                 "Original artifacts must be published with this feed in one Git commit; export is not admission or independent reproduction."]
        if old:
            revised += 1
            notes.append(f"Evidence revision of {old['attempt_id']} revision {old['revision']}; same attempt and run, no rerun.")
        folder = cell_path.parent
        processes = cell.get("processes", [])
        solver_process = processes[0] if processes else {}
        p1 = capture.read(folder / "search/summary.json", optional=True) if problem == "P1" else None
        online = capture.read(folder / "online/receipt.json", optional=True) if problem == "P3" else None
        evaluated = capture.read(folder / "e0/summary.json", optional=True) if problem == "P2" else None
        p1 = p1 or {}
        online = online or {}
        evaluated = evaluated or {}
        harness = cell.get("harness_sha256")
        relative_cell = cell_path.relative_to(run).as_posix()
        lineage = "receipt-declared"
        if not harness and legacy and legacy.get("files", {}).get(relative_cell, {}).get("sha256") == capture.sha(cell_path):
            harness = legacy["harness_sha256"]
            lineage = "legacy-observation-manifest; not retroactive attestation"
        runner_source = None
        if harness in registered:
            archive = run / "harness" / f"p123_run-{harness}.py"
            if capture.sha(archive) != harness:
                raise ValueError("archived runtime harness hash mismatch")
            runner_source = source(ARCHIVE_COMMIT, capture.relative(archive), "main")
        else:
            notes.append("Runtime harness lineage is unavailable; current controller bytes are not substituted.")
        state = row["status"]
        status = "ok" if state == "ok" else "timeout" if state == "timeout" else "failed"
        if status == "ok" and (row.get("makespan_cycles") is None or not cell.get("finished_at")):
            raise ValueError("successful cell lacks final Makespan or finish receipt")
        if problem == "P1" and status == "ok" and not cell.get("p1_search", {}).get("e0_confirms_selected_makespan"):
            raise ValueError("P1 success lacks official final confirmation")
        graph_hash = frozen[f"data/case_{case}.json"]["sha256"]
        config_hash = frozen["data/config.txt"]["sha256"]
        detail = p1 if problem == "P1" else online if problem == "P3" else evaluated
        for key, expected in (("graph_sha256", graph_hash), ("config_sha256", config_hash)):
            if detail.get(key) is not None and detail[key] != expected:
                raise ValueError(f"{relative_cell}: {key} differs from frozen input")
        artifacts = {"manifest": capture.artifact(protocol_path, notes, "protocol")}
        if not private_strings(cell):
            artifacts["run"] = capture.artifact(cell_path, notes, "run receipt")
        else:
            notes.append("Original run receipt contains a private path; reference withheld without altering it.")
        plan_hash = cell.get("plan_sha256")
        if status == "ok":
            plan_ref = capture.artifact(folder / "plan.json", notes, "final plan", expected=plan_hash)
            if plan_ref:
                # Plans are small and must retain the official two-key structure.
                plan = capture.read(folder / "plan.json")
                if set(plan) != {"node_to_subgraph", "core_schedules"}:
                    raise ValueError("final plan has non-official top-level keys")
                plan_hash = plan_ref["sha256"]
                artifacts["plan"] = plan_ref
            result_name = {"P1": "search/e0_best/result.json.gz", "P2": "e0/result.json.gz", "P3": "online/result.json.gz"}[problem]
            expected_result = (cell.get("evidence", {}).get("e0_best/result.json", {}).get("gzip_sha256") if problem == "P1"
                               else online.get("result_sha256") if problem == "P3" else evaluated.get("result_gzip_sha256"))
            result_ref = capture.artifact(folder / result_name, notes, "complete final result", expected=expected_result)
            if result_ref:
                artifacts["result"] = result_ref
        if plan_hash is not None and not SHA256.fullmatch(plan_hash):
            raise ValueError("invalid plan hash in final receipt")
        identity = {"graph_sha256": graph_hash, "config_sha256": config_hash,
                    "official_sha256": official_hash, "plan_sha256": plan_hash}
        baseline = None
        baseline_dir = run / "baselines" / case / "e0"
        single = capture.read(baseline_dir / "summary.json", optional=True) or {}
        if single.get("status") == "ok" and all(single.get(k) == identity[k] for k in ("graph_sha256", "config_sha256")) and single.get("official_code_hash") == official_hash:
            ref = capture.artifact(baseline_dir / "result.json.gz", notes, "local official singlecore result", expected=single.get("result_gzip_sha256"))
            if ref:
                baseline = {k: identity[k] for k in ("graph_sha256", "config_sha256", "official_sha256")}
                baseline.update(route="E0", entrypoint="singlecore_evaluate.evaluate_singlecore", result=ref)
        if baseline is None:
            notes.append("No verified local successful singlecore denominator; captain's shared baseline references are not copied.")
        cache_pair = None
        pair = capture.read(folder / "no_cache/summary.json", optional=True) if problem == "P3" else None
        if pair and status == "ok" and pair.get("status") == "ok":
            keys = ("graph_sha256", "config_sha256", "plan_sha256")
            if all(pair.get(k) == identity[k] for k in keys) and pair.get("official_code_hash") == official_hash and pair.get("num_cores") == cores and pair.get("mode") == "P2":
                ref = capture.artifact(folder / "no_cache/result.json.gz", notes, "same-plan P2 result", expected=pair.get("result_gzip_sha256"))
                if ref:
                    cache_pair = dict(identity, cores=cores, route="E0", result=ref)
            else:
                notes.append("P3 paired P2 receipt identity/core/mode mismatch; cache_pair withheld.")
        if problem == "P3" and cache_pair is None:
            notes.append("No verified successful same-plan/same-core P2 pair; cache gain remains unavailable.")
        movement = row.get("data_movement_bytes")
        movement = json.loads(movement) if isinstance(movement, str) and movement else (movement or {})
        included = problem in {"P1", "P3"}
        parameters = dict(p1.get("parameters") or cell.get("p1_search", {}).get("parameters") or {"cores": cores})
        parameters["solver_process_timeout_seconds"] = solver_process.get("timeout_seconds")
        solver_argv = solver_process.get("argv", [])
        if not private_strings(solver_argv):
            parameters["recorded_solver_argv"] = solver_argv
        if problem == "P1":
            parameters["internal_evaluator"] = {"route": "E1", "commit": protocol["versions"]["E1"]["commit"],
                                                "entrypoint": "src.eval_exact.P1BatchEvaluator", "role": "candidate scoring only; final score confirmed by official E0"}
            parameters["reported_e1_evaluations"] = p1.get("evaluations")
            notes.append("P1 E1 counters are recorded as reported dispatch/evaluation evidence; no universal E1/E0 equivalence is asserted.")
        if problem == "P3":
            variant = online.get("strategy") or cell.get("p3_strategy") or (old or {}).get("variant") or "unknown"
            parameters["structure_selection"] = online.get("selection")
        failure = None
        if status != "ok":
            reason = row.get("error") or f"Original final cell status: {state}"
            if private_strings(reason):
                reason = "Original failure reason contains a private path; inspect retained local receipt."
            failed_process = next((p for p in reversed(processes) if p.get("status") not in {"ok", "reserved"}), {})
            failure = {"stage": "recorded process" if failed_process else "final harness validation",
                       "reason": reason, "exit_code": failed_process.get("returncode"),
                       "elapsed_seconds": cell.get("cell_wall_seconds")}
        timing_note = cell.get("timing_note") or "Original detailed solver timing scope was not recorded."
        scope = ("Included final/stub official confirmation component; not independent evaluation wall."
                 if problem == "P1" else "One online P3 E0 included in solver wall; same-plan P2 is separate experimental work."
                 if problem == "P3" else "Independent final official P2 evaluator subprocess, including process overhead.")
        calls = {"solver": 1 if type(solver_process.get("pid")) is int and solver_process.get("started_at") else None,
                 "E0": None, "E1": None, "E2": None}
        if problem == "P2" and type(evaluated.get("official_calls")) is int:
            calls["E0"] = evaluated["official_calls"]
        elif problem == "P3" and type(online.get("official_e0_calls")) is int and pair and type(pair.get("official_calls")) is int:
            calls["E0"] = online["official_e0_calls"] + pair["official_calls"]
        elif problem == "P1":
            confirms = [p1.get(name, {}) for name in ("e0_best", "e0_baseline")]
            if all(c.get("status") == "ok" and c.get("returncode") == 0 for c in confirms):
                calls["E0"] = 2
        reasons = {}
        provenance = {
            "producer_session": args.producer_session, "task_url": TASK_URL,
            "solver": {"source": source(commit, solver_path, entrypoint), "authors": (old or {}).get("provenance", {}).get("solver", {}).get("authors", []),
                       "method": method_name, "references": [args.source_url], "upstream": [],
                       "selected_algorithm_id": None, "selected_solver_commit": None},
            "runner": {"source": runner_source, "argv": [], "working_directory": None},
            "environment": {"os": protocol.get("platform"), "cpu": environment["cpu"], "gpu": None, "ram_bytes": environment["ram_bytes"],
                            "python": protocol.get("python"), "dependencies": "uv.lock SHA256 " + protocol["uv_lock_sha256"],
                            "threads": environment["threads"], "workers": protocol.get("workers"), "peak_rss_bytes": None},
            "measurement": {"started_at": utc(cell.get("started_at")), "finished_at": utc(cell.get("finished_at")),
                            "seed": parameters.get("seed"), "repeat_index": 0, "cold_start": None,
                            "solver_scope": timing_note, "evaluation_scope": scope,
                            "budget": {"wall_seconds": parameters.get("budget_seconds") if problem == "P1" else solver_process.get("timeout_seconds"),
                                       "candidate_limit": parameters.get("candidates") if problem == "P1" else None, "stop_reason": None},
                            "calls": calls, "offline_costs": None, "failure": failure},
            "missing_reasons": reasons,
        }
        reasons["provenance.runner.working_directory"] = "Controller cwd was not preserved; role-placeholder child cwd is not the controller cwd."
        if problem == "P2":
            reasons["provenance.measurement.budget.candidate_limit"] = "Not applicable to the contiguous-block constructor; no candidate-search limit."
        explain_nulls(provenance, reasons)
        notes += ["Controller argv and author attribution were not fully recorded; empty arrays do not assert absence.",
                  "Runner source points to a later published byte-identical runtime archive, not to the export-time controller or a claimed historical checkout HEAD.",
                  "Evaluator commit identifies official source bytes checked against the frozen manifest and fixed Git blobs; it is not an inferred process checkout timestamp or export-time HEAD.",
                  scope]
        record = {
            "attempt_id": old["attempt_id"] if old else f"{attempt_prefix}-{problem}-{case}-k{cores}",
            "revision": old["revision"] + 1 if old else 1, "run_id": old["run_id"] if old else run_id,
            "algorithm_id": method_id, "algorithm_name": (old or {}).get("algorithm_name", method_name),
            "variant": variant, "solver_commit": commit, "parameters": parameters,
            "problem": problem, "case_id": case, "cores": cores, "status": status,
            "runtime_id": (old or {}).get("runtime_id", runtime_id), "observed_at": utc(cell.get("finished_at")),
            "source_url": args.source_url, "notes": notes,
            "metrics": {"makespan_cycles": row.get("makespan_cycles") if status == "ok" else None,
                        "solver_wall_seconds": row.get("solver_wall_seconds"),
                        "evaluation_wall_seconds": None if included else row.get("e0_wall_seconds"),
                        "ddr_bytes": movement.get("scheduled_copy_bytes"), "extra_ddr_bytes": movement.get("added_copy_bytes"),
                        "spill_bytes": movement.get("spill_added_copy_bytes"), "cache_hit_rate": row.get("cache_hit_rate")},
            "timing": {"solver_includes_evaluation": included, "evaluation_precision": None, "utc": "UTC",
                       "source_e0_component_seconds": row.get("e0_wall_seconds"), "source_cell_wall_seconds": cell.get("cell_wall_seconds"),
                       "source_pair_wall_seconds": processes[1].get("wall_seconds") if problem == "P3" and len(processes) > 1 else None},
            "evaluator": {"route": "E0", "commit": EVALUATOR_COMMITS[problem], "entrypoint": ENTRYPOINTS[problem]},
            "identity": identity, "artifacts": {k: v for k, v in artifacts.items() if v is not None},
            "baseline": baseline, "cache_pair": cache_pair, "provenance": provenance,
            "reported_source": {"protocol_commit": PROTOCOL_COMMIT, "protocol_sha256": capture.sha(protocol_path),
                                "manifest_sha256": capture.sha(manifest_path), "harness_sha256": harness,
                                "lineage": lineage, "wrapper_sha256": protocol["source_sha256"]["p123_evaluate.py"],
                                "evaluator_source_check": {"path": capture.relative(source_check_path), "sha256": capture.sha(source_check_path)},
                                "receipt_path": capture.relative(cell_path), "receipt_sha256": capture.sha(cell_path)},
        }
        if environment_metadata is not None:
            record["reported_source"]["environment_evidence"] = environment_metadata
            notes.append("Supplementary environment evidence observed at " + environment_metadata["measurement_observed_at"]
                         + " from " + environment_metadata["source"] + "; not a per-cell hardware/resource measurement.")
            notes.extend(environment_metadata["notes"])
        for path, value in (("timing.evaluation_precision", None),
                            ("metrics.evaluation_wall_seconds", record["metrics"]["evaluation_wall_seconds"]),
                            ("baseline", baseline), ("cache_pair", cache_pair)):
            if value is None:
                reasons[path] = "Unknown, unavailable or not an independent measurement; see notes and original receipts."
        for key, value in record.items():
            explain_nulls(value, reasons, key)
        records.append(record)
    finished = utc_now()
    snapshot_note = f"Non-atomic live capture {started} to {finished}; no assertion that processes remain online."
    for record in records:
        record["notes"].append(snapshot_note)
        if private_strings(record):
            raise ValueError("export contains an absolute/private path; refusing to publish")
    if not records:
        raise ValueError("no completed cell receipts selected")
    # Bound shards by encoded bytes, rather than assuming a per-record size.
    prefix = b'{"schema_version":1,"submission_version":1,"records":['
    suffix = b']}\n'
    shards, current, size = [], [], len(prefix) + len(suffix)
    for record in records:
        raw = packed(record)
        if len(raw) + len(prefix) + len(suffix) > MAX_FEED:
            raise ValueError("one record exceeds the feed byte limit")
        extra = len(raw) + bool(current)
        if size + extra > MAX_FEED or len(current) >= 5000:
            shards.append(prefix + b','.join(current) + suffix)
            current, size = [], len(prefix) + len(suffix)
        current.append(raw)
        size += len(raw) + (1 if len(current) > 1 else 0)
    if current:
        shards.append(prefix + b','.join(current) + suffix)
    output.mkdir(parents=True, exist_ok=False)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    unique = uuid.uuid4().hex[:12]
    emitted = []
    for number, raw in enumerate(shards, 1):
        name = f"board-feed-{stamp}-{unique}-{number:03d}.json"
        with (output / name).open("xb") as stream:
            stream.write(raw)
        emitted.append({"file": name, "bytes": len(raw), "sha256": digest(raw)})
    print(json.dumps({"records": len(records), "revised": revised, "new": len(records) - revised,
                      "status": dict(Counter(r["status"] for r in records)), "feeds": emitted,
                      "capture_started_at": started, "capture_finished_at": finished,
                      "scope": "export only; receiver validation and same-commit artifact publication still required"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, TypeError) as error:
        # Do not echo OS exceptions containing private absolute paths.
        message = str(error)
        if PRIVATE.search(message):
            message = "Local path/IO validation failed; no source artifacts were modified."
        print(json.dumps({"exported": False, "error": message}), file=sys.stderr)
        raise SystemExit(1)
