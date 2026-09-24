"""Review-only C/D/E integration; no execution without a new fixed-code approval."""
import argparse
from datetime import datetime, timezone
import hmac
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gate_runtime import (ROOT, CAPS, STAGES, SCHEMA, api, bundle, close_all,
                          configure_payload_job, elapsed, read, remaining,
                          require, save, sha, stage_seconds, wait_for)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, timeout=10)


def handshake(stage, private):
    """No evaluation imports before exact membership, query-close and parent ACK."""
    directory = private / "gates" / stage
    expected = {key: os.environ["CODEX_P2C_" + key.upper()]
                for key in ("nonce", "job", "stage", "bundle")}
    boot = {"stage": stage, "pid": os.getpid(), "ppid": os.getppid(),
            "bundle": bundle()["sha256"], "nonce_sha256": sha(expected["nonce"].encode()),
            "expected_job_sha256": sha(expected["job"].encode()), "payload_imported": False}
    save(directory / "child.boot.json", boot, exclusive=True)
    limits = read(directory / "limits.json")
    try:
        require(expected["stage"] == stage and boot["bundle"] == expected["bundle"], "child identity")
        wait_for((directory / "gate.private.json").exists,
                 min(api().tick() + 5000, limits["work_deadline_tick_ms"]), "gate")
        gate = read(directory / "gate.private.json")
        boot["launcher_pid"] = gate.get("launcher_pid")
        save(directory / "child.observed.json", boot, exclusive=True)
        require(isinstance(gate.get("nonce"), str) and
                hmac.compare_digest(gate["nonce"], expected["nonce"]), "nonce mismatch")
        require(all(gate.get(k) == expected[k] for k in ("stage", "job", "bundle")), "gate identity")
        boot["membership"] = api().exact_membership(expected["job"])
        require(boot["membership"] == {"api_success": True, "member": True,
                                       "query_closed": True}, "exact Job proof")
        boot["handle_events"] = list(api().events)
        save(directory / "ready.json", boot, exclusive=True)
        wait_for((directory / "ack.private.json").exists,
                 min(api().tick() + 5000, limits["work_deadline_tick_ms"]), "ACK")
        ack = read(directory / "ack.private.json")
        require(ack.get("pid") == os.getpid() and ack.get("stage") == stage and
                ack.get("bundle") == expected["bundle"] and isinstance(ack.get("nonce"), str) and
                hmac.compare_digest(ack["nonce"], expected["nonce"]), "ACK identity")
        require(remaining(private, time.perf_counter(), stage) > 0, "no evaluation time after ACK")
        boot["ack_verified"] = True
        save(directory / "child.admitted.json", boot, exclusive=True)
    except BaseException as error:
        save(directory / "child.gate_failure.json", {**boot, "error": repr(error),
                                                     "handle_events": api().events}, exclusive=True)
        raise


def child(stage, private):
    handshake(stage, private)
    # This import is standard-library-only; E2 itself is inside run_stage.
    from payload import run_stage
    return run_stage(stage, private)


def controlled(stage, private, identity):
    start = api().tick()
    final_deadline = min(start + stage_seconds(stage) * 1000,
                         start + int(max(0, CAPS["evaluation_cutoff"] - elapsed(private)) * 1000))
    work_deadline = final_deadline - CAPS["cleanup_seconds"] * 1000
    require(work_deadline - start >= 10000, "insufficient handshake/work/cleanup time")
    directory = private / "gates" / stage
    directory.mkdir(parents=True, exist_ok=False)
    save(directory / "limits.json", {"stage": stage, "start_tick_ms": start,
         "work_deadline_tick_ms": work_deadline, "final_deadline_tick_ms": final_deadline}, exclusive=True)
    record = {"stage": stage, "passed": False, "forced_cleanup": False,
              "create_process_attempted": False, "created": False,
              "stage_budget_seconds": stage_seconds(stage), "cleanup_reserve_seconds": 10,
              "max_active_job_processes": 12, "start_tick_ms": start}
    handles, observers = [], {}
    job = process = None
    event_start = len(api().events)
    nonce, job_name = secrets.token_hex(32), "Local\\CodexP2C-" + secrets.token_hex(24)
    try:
        job = api().job(job_name)
        handles.append(job)
        configure_payload_job(job)
        environment = {k: v for k, v in os.environ.items() if not k.upper().startswith("CODEX_P2C_")}
        environment.update(CODEX_P2C_NONCE=nonce, CODEX_P2C_JOB=job_name,
                           CODEX_P2C_STAGE=stage, CODEX_P2C_BUNDLE=identity["sha256"],
                           PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        # The helper uses final-5s internally; passing work+5s makes its launch
        # guard exactly this stage's work deadline, while our cleanup reserves 10s.
        process = api().launch_assigned(ROOT / ".venv/Scripts/python.exe",
            ["-I", "-B", HERE / "run_gated_continuation.py", "--private", private, "--child", stage],
            environment, directory, job, record, work_deadline + 5000,
            time.monotonic_ns() + int(max(0, (work_deadline - api().tick()) / 1000) * 1e9))
        handles.append(process)
        save(directory / "launch.json", record, exclusive=True)
        save(directory / "gate.private.json", {"stage": stage, "nonce": nonce, "job": job_name,
             "bundle": identity["sha256"], "launcher_pid": record["launcher_pid"]}, exclusive=True)
        def ready():
            require(not (directory / "child.gate_failure.json").exists(), "child rejected gate")
            require(not api().exited(process), "launcher exited before ready")
            return (directory / "ready.json").exists()
        wait_for(ready, min(api().tick() + 10000, work_deadline), "child ready")
        proof = read(directory / "ready.json")
        require(proof.get("stage") == stage and proof.get("bundle") == identity["sha256"] and
                proof.get("nonce_sha256") == sha(nonce.encode()) and
                proof.get("expected_job_sha256") == sha(job_name.encode()) and
                proof.get("membership") == {"api_success": True, "member": True, "query_closed": True},
                "ready identity/member/closed proof")
        listing = api().pids(job)
        require(type(proof.get("pid")) is int and proof["pid"] in listing["pids"] and
                record["launcher_pid"] in listing["pids"], "actual and launcher PID must be in exact Job")
        record.update(actual_script_pid=proof["pid"], script_ppid=proof["ppid"], complete_ready_pid_list=listing)
        for pid in listing["pids"]:
            handle = api().observer(pid)
            handles.append(handle)
            observers[pid] = handle
            require(not api().exited(handle), "ready member already exited")
        save(directory / "parent.membership.json", record, exclusive=True)
        save(directory / "ack.private.json", {"stage": stage, "nonce": nonce,
             "pid": proof["pid"], "bundle": identity["sha256"]}, exclusive=True)
        def ended():
            if not api().exited(process):
                return False
            record["returncode"] = api().exit_code(process)
            require(record["returncode"] == 0, "payload exited with error; clean up now")
            return api().accounting(job)["ActiveProcesses"] == 0
        wait_for(ended, work_deadline, "payload and all descendants exit")
        record["returncode"] = api().exit_code(process)
        record["ready_process_exit_codes"] = {str(pid): api().exit_code(h) for pid, h in observers.items()}
        record["final_accounting"] = api().accounting(job)
        require(record["returncode"] == 0 and all(api().exited(h) for h in observers.values()), "payload failure")
        record["passed"] = True
    except BaseException as error:
        record["error"] = repr(error)
    finally:
        errors = []
        try:
            if job is not None and not job.closed:
                record["active_before_cleanup"] = api().accounting(job)["ActiveProcesses"]
                if record["active_before_cleanup"]:
                    record["forced_cleanup"] = True
                    api().terminate_job(job)
                wait_for(lambda: api().accounting(job)["ActiveProcesses"] == 0,
                         final_deadline, "Job cleanup")
                record["cleanup_accounting"] = api().accounting(job)
                record["active_after_cleanup"] = record["cleanup_accounting"]["ActiveProcesses"]
            if process is not None:
                wait_for(lambda: api().exited(process) and all(api().exited(h) for h in observers.values()),
                         final_deadline, "tracked cleanup")
        except BaseException as error:
            errors.append(repr(error))
        try:
            close_all(handles)
        except BaseException as error:
            errors.append(repr(error))
        record.update(cleanup_errors=errors, handle_events=api().events[event_start:],
                      end_tick_ms=api().tick(), wall_since_outer_t0=elapsed(private))
        record["wall_ms"] = record["end_tick_ms"] - start
        if errors or record["forced_cleanup"] or record["end_tick_ms"] > final_deadline:
            record["passed"] = False
        save(private / (stage + ".controller.json"), record, exclusive=True)
    return record


def parent(private, approval_path, outer_path):
    approval, outer = read(approval_path), read(outer_path)
    identity, contract = bundle(), read(HERE / "contract.json")
    require(approval.get("execute_approved") is True and approval.get("schema") == SCHEMA and
            approval.get("caps") == CAPS and approval.get("reference") and
            approval.get("source_bundle_sha256") == identity["sha256"], "new exact approval required")
    require(contract["caps"] == CAPS and contract["stages"] == {k: list(v) for k, v in STAGES.items()},
            "contract mismatch")
    require(os.name == "nt" and sys.flags.isolated and sys.dont_write_bytecode and not sys.flags.optimize,
            "requires Windows original venv -I -B with site enabled")
    require(Path(sys.executable).resolve() == (ROOT / ".venv/Scripts/python.exe").resolve(), "wrong launcher")
    require(sha(Path(sys.executable).read_bytes()) == contract["venv_launcher_sha256"], "launcher changed")
    require(not private.exists() and private.parent == outer_path.resolve().parent,
            "fresh run directory beside outer.json required")
    require(private.is_relative_to((Path(os.environ["LOCALAPPDATA"]) / "CodexEvidence").resolve()),
            "private output must be outside Git workspaces")
    require(outer["authorized_commit"] == approval["authorized_commit"] and
            outer["approval_reference"] == approval["reference"], "outer identity mismatch")
    private.mkdir()
    save(private / "T0.json", {"utc": outer["outer_t0_utc"], "tick64": outer["outer_t0_tick64_ms"],
         "stopwatch": outer["outer_t0_stopwatch"], "stopwatch_frequency": outer["stopwatch_frequency"],
         "origin": "launch_once.ps1 before approval preparation and parent launch"}, exclusive=True)
    save(private / "approval.json", approval, exclusive=True)
    ledger = {"schema": SCHEMA, "source_bundle": identity, "stages": [], "stage_launch_reserved": 0,
              "record_reserved": 0, "fixed_e0_reserved": 0, "possible_e0_reserved": 0,
              "formal_e0": 0, "debug": 0, "execution_state": "preparing"}
    try:
        head = git("rev-parse", "HEAD").decode().strip()
        require(head == approval["authorized_commit"], "unapproved HEAD")
        require(not git("status", "--porcelain").strip(), "dirty working tree")
        ledger["as_run_head"] = head
        from payload import frozen_inputs
        frozen_inputs(private)
        stdlib_identity = {}
        for relative, wanted in contract["stdlib_sha256"].items():
            actual = sha((Path(sys.base_prefix) / relative).read_bytes())
            require(actual == wanted, "stdlib spawn source changed: " + relative)
            stdlib_identity[relative] = actual
        save(private / "STDLIB_IDENTITY.json", stdlib_identity, exclusive=True)
        require(elapsed(private) < CAPS["preparation_cutoff"], "outer preparation deadline")
        for stage, (records, direct) in STAGES.items():
            require(bundle() == identity, "source changed between stages")
            require(elapsed(private) < (90 if stage in ("preflight", "C_full") else 280), "stage launch cutoff")
            ledger["stage_launch_reserved"] += 1
            ledger["record_reserved"] += records
            ledger["fixed_e0_reserved"] += direct
            ledger["possible_e0_reserved"] += records + direct
            require(ledger["stage_launch_reserved"] <= 8 and ledger["record_reserved"] <= 12 and
                    ledger["fixed_e0_reserved"] <= 5 and ledger["possible_e0_reserved"] <= 17, "global caps")
            item = {"stage": stage, "record_reserved": records, "fixed_e0_reserved": direct,
                    "possible_e0_reserved": records + direct, "status": "reserved"}
            ledger["stages"].append(item)
            save(private / "ledger.json", ledger)
            result = controlled(stage, private, identity)
            item.update(status="returned", controller=result)
            save(private / "ledger.json", ledger)
            require(result["passed"], "first unexpected stage failure; no later stage or retry")
        ledger["execution_state"] = "matrix_completed_pending_review"
    except BaseException as error:
        ledger.update(execution_state="stopped", error=repr(error))
        traceback.print_exc()
    finally:
        ledger["execution_end_outer_wall"] = elapsed(private)
        ledger["execution_end_utc"] = datetime.now(timezone.utc).isoformat()
        save(private / "ledger.json", ledger)
    return 0 if ledger["execution_state"] == "matrix_completed_pending_review" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--child", choices=list(STAGES))
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--outer", type=Path)
    args = parser.parse_args()
    if args.child:
        return child(args.child, args.private.resolve())
    require(args.approval is not None and args.outer is not None, "outer wrapper and new approval required")
    return parent(args.private.resolve(), args.approval.resolve(), args.outer.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
