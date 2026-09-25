"""One-shot Q2 semantic checkpoint. Maximum twelve official Q2 CLI invocations."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone

from .construct import ROOT, OFFICIAL
from .monitor import supervise, working_set

PRO_REF = "3a4505d4101e23d54580d15560da3820e02d05da"
PRO_BASE = "results/a/pro-research-20260924/"
CONFIG = ROOT / "data/raw/a/official/data/config.txt"
# Windows venv python.exe is a redirector with another process underneath it.
# All launched tools here are stdlib-only; use the real, same-version interpreter
# so the monitored PID is the evaluator itself and kill/wait cannot orphan it.
INTERPRETER = getattr(sys, "_base_executable", sys.executable)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def selected_pro_inputs(output: Path):
    manifest = json.loads(git("show", f"{PRO_REF}:{PRO_BASE}pro3-r2.manifest.json"))
    payload = git("show", f"{PRO_REF}:{PRO_BASE}pro3-r2.tar.xz")
    if hashlib.sha256(payload).hexdigest() != manifest["archive_sha256"]:
        raise ValueError("Pro3 archive identity mismatch")
    selected = [r for r in manifest["members"]
                if any(f"/counterexamples/{name}/" in r["path"]
                       for name in ("head_blocking", "fork"))
                and Path(r["path"]).name in
                {"graph.json", "plan0.json", "plan1.json", "plan_0.json", "plan_1.json"}]
    if len(selected) != 6:
        raise ValueError("Expected exactly six static Pro3 inputs")
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:xz") as archive:
        for row in selected:
            raw = archive.extractfile(row["path"]).read()
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError(f"Pro3 member identity mismatch: {row['path']}")
            parts = Path(row["path"]).parts
            destination = output / parts[-2] / parts[-1]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)  # Never execute or extract archive paths.
    return {"ref": PRO_REF, "archive_sha256": manifest["archive_sha256"],
            "selected_members": selected}


class Budget:
    def __init__(self, folder: Path, max_calls: int, seconds: float):
        self.folder = folder
        self.max_calls = max_calls
        self.started = time.monotonic()
        self.deadline = self.started + seconds
        self.calls = []
        self.persist()

    def persist(self):
        write_json(self.folder / "budget.json", {
            "max_q2_invocations": self.max_calls, "reserved_invocations": len(self.calls),
            "wall_limit_seconds": self.deadline - self.started,
            "elapsed_seconds": time.monotonic() - self.started, "calls": self.calls})

    def reserve(self, label):
        if len(self.calls) >= self.max_calls or time.monotonic() >= self.deadline:
            raise RuntimeError("stage A evaluation budget exhausted")
        self.calls.append({"label": label, "reserved_at_seconds": time.monotonic() - self.started})
        self.persist()  # Charge before launch, including interruptions and launch failures.


def evaluate_job(job, output, budget, per_call):
    label, graph, plan, expected, domain = job
    budget.reserve(label)
    folder = output / "evaluations" / label
    folder.mkdir(parents=True, exist_ok=False)
    command = [INTERPRETER, "-B", relative(OFFICIAL / "multicore_cut_evaluate_problem_2.py"),
               relative(graph), relative(plan), "--config", relative(CONFIG),
               "-o", relative(folder / "result.json"),
               "--trace-output", relative(folder / "trace.json"),
               "--log-output", relative(folder / "summary.txt")]
    record = {"label": label, "graph": relative(graph), "plan": relative(plan),
              "graph_sha256": digest(graph), "plan_sha256": digest(plan),
              "config_sha256": digest(CONFIG), "command": ["python", *command[1:]],
              "expected": expected, "domain": domain}
    monitored = supervise(command, cwd=ROOT, folder=folder,
                           deadline=min(budget.deadline, time.monotonic() + per_call))
    record.update(monitored)
    error_text = (folder / "stderr.txt").read_text(encoding="utf-8") if (folder / "stderr.txt").exists() else ""
    if record["status"] == "completed":
        if record["returncode"] == 0 and all((folder / name).is_file()
                                             for name in ("result.json", "trace.json", "summary.txt")):
            result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
            record.update(status="ok", makespan_cycles=result["makespan"],
                          movement_bytes=result["data_movement_bytes"],
                          memory_peak_by_core=result["memory_peak_by_core"],
                          task_count=result["task_count"])
        else:
            known = ("dependency order violation", "subgraph priority order violates",
                     "dependency cycle", "[STEP2 ERROR] no spill victim")
            record["status"] = "rejected" if any(s in error_text for s in known) else "error"
    record["expected_status_met"] = record["status"] == expected
    record["evidence"] = {p.name: digest(p) for p in folder.iterdir() if p.is_file()}
    write_json(folder / "run.json", record)
    budget.calls[-1].update(status=record["status"], launched=record["launched"],
                            wall_seconds=record["wall_seconds"])
    budget.persist()
    print(json.dumps({k: record.get(k) for k in
                      ("label", "status", "makespan_cycles", "wall_seconds")}), flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-calls", type=int, default=12)
    parser.add_argument("--wall-seconds", type=float, default=1800)
    parser.add_argument("--per-call-seconds", type=float, default=120)
    args = parser.parse_args()
    if not (1 <= args.max_calls <= 12 and 0 < args.wall_seconds <= 1800
            and 0 < args.per_call_seconds <= 120):
        parser.error("approved stage A ceilings: 12 invocations / 1800 s / 120 s per call")
    output = args.output.resolve()
    output.relative_to(ROOT / "results/a/q2-yuanzhifang")
    output.mkdir(parents=True, exist_ok=False)  # No restart that resets an existing run's ledger.
    budget = Budget(output, args.max_calls, args.wall_seconds)
    code_files = sorted((ROOT / "src/q2").glob("*.py")) + [ROOT / "tests/q2/fixtures.py"]
    metadata = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                "stage": "A", "code_head": git("rev-parse", "HEAD").decode().strip(),
                "code_sha256": {relative(p): digest(p) for p in code_files},
                "python": platform.python_version(), "platform": platform.platform(),
                "machine": platform.machine(), "seed": 0, "workers": 1,
                "child_interpreter": "sys._base_executable; same Python version; stdlib-only child tools",
                "dependencies": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
                "uv_lock_sha256": digest(ROOT / "uv.lock"),
                "official_code_hash": json.loads((ROOT / "docs/a/source-manifest.json").read_text(encoding="utf-8"))["official_code_hash"],
                "memory_accounting": "250 ms sum of controller + sole direct child working sets; sampled, not hard limit",
                "budget_scope": "preparation below + all proposals/evaluations/output within this invocation",
                "outer_preparation": "uv sync --locked and a_materials --extract recorded separately"}
    write_json(output / "run.json", metadata)
    rows, checks = [], {}
    try:
        if working_set(os.getpid()) >= 4 * 1024**3:
            raise RuntimeError("controller already at sampled memory limit")
        inputs = output / "inputs"
        metadata["provenance"] = selected_pro_inputs(inputs / "pro3")
        fixture_path = ROOT / "tests/q2/fixtures.py"
        spec = importlib.util.spec_from_file_location("q2_fixtures", fixture_path)
        fixtures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixtures)
        jobs = []

        def synthetic(label, pair, expected="ok", domain="synthetic within stated graph constraints"):
            graph, plan = pair
            folder = inputs / label
            write_json(folder / "graph.json", graph)
            write_json(folder / "plan.json", plan)
            jobs.append((label, folder / "graph.json", folder / "plan.json", expected, domain))

        synthetic("01-pdf-minimal-empty-core", fixtures.minimal())
        case = ROOT / "data/raw/a/official/data/case_002.json"
        stub = inputs / "case002-stub-plan.json"
        stub_record = supervise(
            [INTERPRETER, "-B", relative(OFFICIAL / "stub_multicore_cut_and_schedule.py"),
             relative(case), "-n", "4", "--seed", "0", "-o", relative(stub)],
            cwd=ROOT, folder=output / "stub-generation",
            deadline=min(budget.deadline, time.monotonic() + args.per_call_seconds))
        metadata["stub_generation"] = stub_record
        if stub_record["status"] != "completed" or stub_record["returncode"] != 0:
            raise RuntimeError("stub generation failed; see recorded supervision")
        jobs.append(("02-case002-stub", case, stub, "ok", "official public development case"))
        baseline_path = inputs / "case002-contiguous-plan.json"
        proposal = supervise(
            [INTERPRETER, "-B", "-m", "src.q2.construct", relative(case),
             "--cores", "4", "--output", relative(baseline_path)],
            cwd=ROOT, folder=output / "baseline-generation",
            deadline=min(budget.deadline, time.monotonic() + args.per_call_seconds))
        metadata["baseline_generation"] = proposal
        if proposal["status"] != "completed" or proposal["returncode"] != 0:
            raise RuntimeError("baseline generation failed; see recorded supervision")
        jobs.append(("03-case002-contiguous", case, baseline_path, "ok", "official public development case"))
        for label, example, plan_name in (
                ("04-fifo-blocked", "head_blocking", "plan_0.json"),
                ("05-fifo-reordered", "head_blocking", "plan_1.json"),
                ("06-fork-coarse", "fork", "plan0.json"),
                ("07-fork-fine", "fork", "plan1.json")):
            folder = inputs / "pro3" / example
            jobs.append((label, folder / "graph.json", folder / plan_name, "ok", "Pro3 published synthetic input, independently evaluated"))
        reverse_graph = json.loads((inputs / "pro3/head_blocking/graph.json").read_text(encoding="utf-8"))
        reverse_plan = {"node_to_subgraph": {"2": 0, "3": 1, "6": 2},
                        "core_schedules": [[1, 0], [2]]}
        synthetic("08-intra-core-reverse", (reverse_graph, reverse_plan), "rejected")
        synthetic("09-global-fifo-cycle", fixtures.global_cycle(), "rejected")
        synthetic("10-op-capacity-rejection", fixtures.minimal(131072), "rejected",
                  "outside official single-op input+output capacity guarantee; diagnostic negative")
        synthetic("11-legal-memory-pressure", fixtures.pressure())
        metadata["planned_jobs"] = [j[0] for j in jobs] + ["12-case002-incumbent-confirmation"]
        write_json(output / "run.json", metadata)
        for job in jobs:
            if len(budget.calls) >= budget.max_calls or time.monotonic() >= budget.deadline:
                break
            record = evaluate_job(job, output, budget, args.per_call_seconds)
            rows.append(record)
            if record["status"] in {"resource_limit", "monitor_error"}:
                break
        safe = not rows or rows[-1]["status"] not in {"resource_limit", "monitor_error"}
        candidates = [r for r in rows if r["label"].startswith(("02-", "03-")) and r["status"] == "ok"]
        if safe and candidates and len(budget.calls) < budget.max_calls and time.monotonic() < budget.deadline:
            incumbent = min(candidates, key=lambda r: r["makespan_cycles"])
            final_plan = inputs / "case002-incumbent-plan.json"
            shutil.copyfile(ROOT / incumbent["plan"], final_plan)
            metadata["incumbent_source"] = incumbent["label"]
            rows.append(evaluate_job(("12-case002-incumbent-confirmation", case, final_plan,
                                      "ok", "official public development case"),
                                     output, budget, args.per_call_seconds))
        by_label = {r["label"]: r for r in rows}

        def result(label):
            return json.loads((output / "evaluations" / label / "result.json").read_text(encoding="utf-8"))

        checks["expected_statuses"] = all(r["expected_status_met"] for r in rows) and len(rows) == 12
        for label, marker in (
                ("08-intra-core-reverse", "dependency order violation on core"),
                ("09-global-fifo-cycle", "global execution (core, op): dependency cycle"),
                ("10-op-capacity-rejection", "[STEP2 ERROR] no spill victim")):
            stderr = output / "evaluations" / label / "stderr.txt"
            checks[label + "-expected-rejection-stage"] = stderr.exists() and marker in stderr.read_text(encoding="utf-8")
        if by_label.get("01-pdf-minimal-empty-core", {}).get("status") == "ok":
            minimal = result("01-pdf-minimal-empty-core")
            checks["pdf_minimal_6_cycles_empty_core"] = minimal["makespan"] == 6 and minimal["per_core_timeline"][1]["ops"] == []
        for name, left, right in (("fifo", "04-fifo-blocked", "05-fifo-reordered"),
                                  ("fork", "06-fork-coarse", "07-fork-fine")):
            if all(by_label.get(label, {}).get("status") == "ok" for label in (left, right)):
                a, b = result(left), result(right)
                checks[name] = {"left_cycles": a["makespan"], "right_cycles": b["makespan"],
                                "same_movement": a["data_movement_bytes"] == b["data_movement_bytes"],
                                "observed_difference": a["makespan"] != b["makespan"]}
        if by_label.get("11-legal-memory-pressure", {}).get("status") == "ok":
            pressure = result("11-legal-memory-pressure")
            checks["pressure"] = {"spill_bytes": pressure["data_movement_bytes"]["spill_added_copy_bytes"],
                                  "local_peaks_within_capacity": all(
                                      peak[pos] <= pressure["capacity_bytes"][pos]
                                      for peak in pressure["memory_peak_by_core"].values() for pos in peak)}
        if by_label.get("12-case002-incumbent-confirmation", {}).get("status") == "ok":
            original, confirmed = result(metadata["incumbent_source"]), result("12-case002-incumbent-confirmation")
            original.pop("input_plan", None)
            confirmed.pop("input_plan", None)
            checks["incumbent_full_repeat_equal_excluding_input_plan_filename"] = original == confirmed
        checks["mechanisms_verified"] = all((
            checks.get("pdf_minimal_6_cycles_empty_core", False),
            checks.get("fifo", {}).get("observed_difference", False),
            checks.get("fork", {}).get("observed_difference", False),
            checks.get("pressure", {}).get("spill_bytes", 0) > 0,
            checks.get("pressure", {}).get("local_peaks_within_capacity", False),
            checks.get("incumbent_full_repeat_equal_excluding_input_plan_filename", False),
            *(checks.get(label + "-expected-rejection-stage", False) for label in
              ("08-intra-core-reverse", "09-global-fifo-cycle", "10-op-capacity-rejection")),
        ))
    except Exception as error:
        metadata["failure"] = {"type": type(error).__name__, "message": str(error)}
        print(json.dumps(metadata["failure"]), file=sys.stderr, flush=True)
    finally:
        budget.persist()
        metadata.update(checks=checks, completed_evaluations=len(rows),
                        experiment_wall_seconds=time.monotonic() - budget.started,
                        deadline_overshoot_seconds=max(0.0, time.monotonic() - budget.deadline),
                        actual_q2_launches=sum(bool(c.get("launched")) for c in budget.calls),
                        results=[{k: r.get(k) for k in ("label", "status", "makespan_cycles", "wall_seconds",
                                                        "sampled_working_set_peak_bytes", "expected_status_met")} for r in rows])
        write_json(output / "run.json", metadata)
        with (output / "metrics.csv").open("w", newline="", encoding="utf-8") as stream:
            fields = ["label", "status", "makespan_cycles", "wall_seconds", "sampled_working_set_peak_bytes", "expected_status_met"]
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(metadata["results"])
        write_json(output / "artifacts.json", {p.relative_to(output).as_posix(): {
            "sha256": digest(p), "bytes": p.stat().st_size}
            for p in sorted(output.rglob("*")) if p.is_file() and p.name != "artifacts.json"})
    return 0 if checks.get("expected_statuses") and checks.get("mechanisms_verified") and "failure" not in metadata else 1


if __name__ == "__main__":
    raise SystemExit(main())
