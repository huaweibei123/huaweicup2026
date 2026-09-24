"""Four standalone control cases. No evaluator imports, builds or evaluations.

NOT RUN during implementation. A fixed-code execution approval is required.
The approved future command uses the existing venv launcher with -I -S -B.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sys
import time

# -I -S excludes site/user imports; add only this exact helper's directory.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gate_helper import (WinAPI, close_all, save, sha256, source_identity)


CAPS = {
    "launch_requests": 4,
    "wall_seconds_including_delivery": 300,
    "preparation_seconds": 45,
    "launch_cutoff_seconds": 150,
    "case_seconds": 20,
    "cleanup_seconds": 5,
    "gate_seconds": 5,
    "ack_seconds": 5,
    "g4_ack_seconds": 15,
    "g4_minimum_self_exit_margin_seconds": 6,
    "g4_observation_seconds": 2,
    "max_active_processes_per_job": 4,
    "E0": 0, "E2": 0, "BC_DLL": 0, "debug": 0,
}
CASES = ("G1", "G2", "G3", "G4")
EXIT = {"ok": 0, "nonce_mismatch": 21, "not_in_expected_job": 22,
        "gate_timeout": 23, "ack_timeout": 24, "identity_mismatch": 25,
        "unexpected_exception": 26}


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def wait_for(api, predicate, deadline, label):
    while api.tick() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.01)
    raise TimeoutError(label)


def current_head(root):
    """Read only Git administrative text. No extra git subprocess is launched."""
    git = root / ".git"
    if git.is_file():
        pointer = git.read_text(encoding="utf-8").strip()
        require(pointer.startswith("gitdir: "), "invalid gitdir pointer")
        git = (root / pointer[8:]).resolve()
    common_pointer = git / "commondir"
    common = ((git / common_pointer.read_text(encoding="utf-8").strip()).resolve()
              if common_pointer.exists() else git)
    head = (git / "HEAD").read_text(encoding="ascii").strip()
    if head.startswith("ref: "):
        name = head[5:]
        require(name.startswith("refs/heads/") and ".." not in name, "unexpected Git ref")
        for base in (git, common):
            ref = base / name
            if ref.is_file():
                return ref.read_text(encoding="ascii").strip()
        packed = common / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="ascii").splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1] == name:
                    return parts[0]
        raise RuntimeError("unresolved Git HEAD")
    return head


def child(directory):
    api = WinAPI()
    expected = {key: os.environ["CODEX_GATE_" + key.upper()]
                for key in ("nonce", "job", "case", "code_hash")}
    case = expected["case"]
    final_deadline = int(os.environ["CODEX_GATE_FINAL_TICK"])
    work_deadline = final_deadline - 5000
    record = {"case": case, "pid": os.getpid(), "ppid": os.getppid(),
              "start_tick_ms": api.tick(), "payload_reached": False,
              "nonce_sha256": digest(expected["nonce"]),
              "expected_job_sha256": digest(expected["job"]),
              "code_hash": expected["code_hash"]}
    save(directory / "child.boot.json", record, exclusive=True)

    def finish(reason):
        record.update(reason=reason, exit_code=EXIT[reason], end_tick_ms=api.tick(),
                      handle_events=api.events)
        save(directory / "child.final.json", record, exclusive=True)
        return EXIT[reason]

    try:
        require(case in CASES, "unknown case")
        require(source_identity(HERE)["sha256"] == expected["code_hash"], "source identity")
        gate_path = directory / "gate.private.json"
        try:
            wait_for(api, gate_path.exists, min(api.tick() + 5000, work_deadline), "gate")
        except TimeoutError:
            return finish("gate_timeout")
        gate = load(gate_path)
        record["launcher_pid"] = gate.get("launcher_pid")
        # Save actual PID/PPID and launcher observation before checking gate identity.
        save(directory / "child.observed.json", record, exclusive=True)
        if not isinstance(gate.get("nonce"), str) or not hmac.compare_digest(
                gate["nonce"], expected["nonce"]):
            return finish("nonce_mismatch")
        if any(gate.get(key) != expected[key] for key in ("case", "job", "code_hash")):
            return finish("identity_mismatch")
        record["membership"] = api.exact_membership(expected["job"])
        if not record["membership"]["member"]:
            return finish("not_in_expected_job")
        require(record["membership"]["api_success"] and
                record["membership"]["query_closed"], "query must succeed and close")
        ready_tick = api.tick()
        # G4 deliberately remains waiting much longer than the parent's 2 s observation.
        ack_deadline = min(ready_tick + (15000 if case == "G4" else 5000),
                           final_deadline if case == "G4" else work_deadline)
        record.update(ready_tick_ms=ready_tick, ack_self_exit_deadline_tick_ms=ack_deadline,
                      clock="GetTickCount64")
        save(directory / "ready.json", {**record, "handle_events": api.events}, exclusive=True)
        ack_path = directory / "ack.private.json"
        try:
            wait_for(api, ack_path.exists, ack_deadline, "ACK")
        except TimeoutError:
            return finish("ack_timeout")
        ack = load(ack_path)
        if (ack.get("pid") != os.getpid() or ack.get("case") != case or
                ack.get("code_hash") != expected["code_hash"] or
                not isinstance(ack.get("nonce"), str) or
                not hmac.compare_digest(ack["nonce"], expected["nonce"])):
            return finish("identity_mismatch")
        # Sole payload: a marker. G2/G3 must reject, G4 must be forcibly terminated.
        require(case == "G1", "ACK/payload forbidden for this case")
        record["payload_reached"] = True
        save(directory / "payload.json", {"control_payload_reached": True,
                                          "pid": os.getpid(), "tick_ms": api.tick()},
             exclusive=True)
        return finish("ok")
    except BaseException as exc:
        record["exception"] = repr(exc)
        return finish("unexpected_exception")


def verify_ready(ready, case, nonce, expected_job, identity):
    require(ready.get("case") == case and ready.get("code_hash") == identity["sha256"],
            "ready code/stage mismatch")
    require(ready.get("nonce_sha256") == digest(nonce) and
            ready.get("expected_job_sha256") == digest(expected_job), "ready binding mismatch")
    require(ready.get("membership") == {"api_success": True, "member": True,
                                       "query_closed": True}, "ready membership proof")
    require(type(ready.get("pid")) is int and ready["pid"] > 0, "ready actual PID")
    require(ready.get("clock") == "GetTickCount64", "ready clock mismatch")


def one_case(api, case, directory, executable, identity, ledger, ledger_path, launch_deadline_ns):
    start = api.tick()
    work_deadline, final_deadline = start + 15000, start + 20000
    receipt = {"case": case, "start_tick_ms": start, "work_deadline_tick_ms": work_deadline,
               "final_deadline_tick_ms": final_deadline, "passed": False,
               "launch_request_reserved": 1, "create_process_attempted": False,
               "created": False, "cleanup_forced": False}
    ledger["requests"].append({"case": case, "reserved_tick_ms": start, "count": 1})
    save(ledger_path, ledger)  # Reservation precedes Job creation and the sole launch.
    directory.mkdir(exist_ok=False)
    save(directory / "reservation.json", receipt, exclusive=True)
    handles, observers = [], {}
    job = empty = process = None
    job_name = "Local\\CodexE2Gate-" + secrets.token_hex(24)
    nonce = secrets.token_hex(32)
    event_start = len(api.events)
    try:
        job = api.job(job_name)
        handles.append(job)
        expected_job = job_name
        if case == "G3":
            expected_job = "Local\\CodexE2Gate-" + secrets.token_hex(24)
            empty = api.job(expected_job)
            handles.append(empty)
            receipt["empty_job_before"] = api.pids(empty)
            require(not receipt["empty_job_before"]["pids"], "negative target not empty")
        child_nonce = (("0" if nonce[0] != "0" else "1") + nonce[1:]
                       if case == "G2" else nonce)
        environment = dict(os.environ)
        for key in list(environment):
            if key.upper().startswith("CODEX_GATE_"):
                del environment[key]
        environment.update(CODEX_GATE_NONCE=child_nonce, CODEX_GATE_JOB=expected_job,
                           CODEX_GATE_CASE=case, CODEX_GATE_CODE_HASH=identity["sha256"],
                           CODEX_GATE_FINAL_TICK=str(final_deadline))
        require(api.tick() < work_deadline, "case preparation deadline")
        process = api.launch_assigned(executable,
            ["-I", "-S", "-B", HERE / "control_runner.py", "--child", directory],
            environment, directory, job, receipt, final_deadline, launch_deadline_ns)
        handles.append(process)
        receipt["pid_list_after_resume"] = api.pids(job)
        receipt["accounting_after_resume"] = api.accounting(job)
        save(directory / "launch.json", receipt, exclusive=True)
        save(directory / "gate.private.json", {"case": case, "nonce": nonce,
             "job": expected_job, "code_hash": identity["sha256"],
             "launcher_pid": receipt["launcher_pid"]}, exclusive=True)
        if case in ("G2", "G3"):
            wait_for(api, lambda: (directory / "child.final.json").exists(),
                     work_deadline, "negative result")
            final = load(directory / "child.final.json")
            expected_reason = "nonce_mismatch" if case == "G2" else "not_in_expected_job"
            require(final.get("reason") == expected_reason and
                    final.get("exit_code") == EXIT[expected_reason], "wrong negative reason")
            require(final.get("case") == case and
                    final.get("code_hash") == identity["sha256"] and
                    final.get("nonce_sha256") == digest(child_nonce) and
                    final.get("expected_job_sha256") == digest(expected_job), "negative identity")
            require(not (directory / "ready.json").exists(), "negative reached ready")
            require(not (directory / "payload.json").exists() and
                    final.get("payload_reached") is False, "negative reached payload")
            if case == "G3":
                require(final.get("membership") == {"api_success": True, "member": False,
                                                     "query_closed": True}, "G3 exact rejection")
                receipt["empty_job_after"] = api.pids(empty)
                require(not receipt["empty_job_after"]["pids"], "G3 target gained processes")
            wait_for(api, lambda: api.exited(process) and
                     api.accounting(job)["ActiveProcesses"] == 0, work_deadline, "negative exit")
            receipt["launcher_exit_code"] = api.exit_code(process)
            require(receipt["launcher_exit_code"] == EXIT[expected_reason], "negative exit code")
            receipt["actual_script_pid"] = final["pid"]
        else:
            def ready_or_failure():
                if (directory / "child.final.json").exists():
                    raise RuntimeError("child exited before ACK: " + repr(load(directory / "child.final.json")))
                return (directory / "ready.json").exists()
            wait_for(api, ready_or_failure, work_deadline, "ready")
            ready = load(directory / "ready.json")
            verify_ready(ready, case, nonce, expected_job, identity)
            listing = api.pids(job)
            receipt.update(complete_pid_list=listing, actual_script_pid=ready["pid"],
                           script_parent_pid=ready["ppid"])
            require(ready["pid"] in listing["pids"] and
                    receipt["launcher_pid"] in listing["pids"], "actual/launcher not in exact Job")
            require(1 <= len(listing["pids"]) <= 4, "unexpected live process count")
            for pid in listing["pids"]:
                observer = api.observer(pid)
                handles.append(observer)
                observers[pid] = observer
                require(not api.exited(observer), "member exited before parent decision")
            receipt["accounting_before_decision"] = api.accounting(job)
            save(directory / "parent.membership.json", receipt, exclusive=True)
            if case == "G1":
                save(directory / "ack.private.json", {"case": case, "nonce": nonce,
                     "pid": ready["pid"], "code_hash": identity["sha256"]}, exclusive=True)
                wait_for(api, lambda: all(api.exited(h) for h in observers.values()) and
                         api.accounting(job)["ActiveProcesses"] == 0, work_deadline, "positive exit")
                final = load(directory / "child.final.json")
                require(final.get("reason") == "ok" and final.get("payload_reached") is True and
                        load(directory / "payload.json")["control_payload_reached"] is True,
                        "positive payload/final missing")
                receipt["exit_codes"] = {str(pid): api.exit_code(h) for pid, h in observers.items()}
                require(all(code == 0 for code in receipt["exit_codes"].values()), "positive exit code")
            else:
                deadline = ready.get("ack_self_exit_deadline_tick_ms")
                require(type(deadline) is int and deadline <= final_deadline, "G4 child deadline")
                receipt["g4_last_pid_list"] = api.pids(job)
                require(set(receipt["g4_last_pid_list"]["pids"]) == set(observers),
                        "G4 membership changed before last close")
                require(all(not api.exited(h) for h in observers.values()),
                        "G4 tracked process exited before close")
                before = api.tick()
                require(deadline - before >= 6000, "G4 requires >=6s self-exit margin")
                require(work_deadline - before >= 2000, "G4 requires 2s observation before cleanup")
                require(not (directory / "child.final.json").exists(), "G4 already self-exited")
                receipt["g4"] = {"expected_exit": "forced_by_last_job_handle_close",
                    "child_self_exit_deadline_tick_ms": deadline,
                    "before_last_close_tick_ms": before,
                    "self_exit_margin_ms": deadline - before,
                    "observation_deadline_tick_ms": before + 2000, "ack_sent": False}
                # Process observer handles do not keep a Job alive. Child query is closed.
                job.close()
                receipt["g4"]["after_last_close_tick_ms"] = api.tick()
                wait_for(api, lambda: all(api.exited(h) for h in observers.values()),
                         before + 2000, "G4 last-close exit within 2s")
                after = api.tick()
                receipt["g4"].update(all_tracked_exited_tick_ms=after,
                    observation_wall_ms=after - before,
                    remaining_until_child_self_exit_ms=deadline - after,
                    exit_codes={str(pid): api.exit_code(h) for pid, h in observers.items()})
                require(after - before <= 2000 and deadline - after >= 4000,
                        "G4 insufficient separation from normal self-exit")
                require(not (directory / "child.final.json").exists() and
                        not (directory / "payload.json").exists(), "G4 normal exit/payload found")
                require(all(code != EXIT["ack_timeout"] for code in
                            receipt["g4"]["exit_codes"].values()), "G4 ACK-timeout exit code")
                # Win32 does not promise a particular kill-on-close exit code.
                # Forced-exit evidence is the time-separated handshake, not code!=0.
                require(receipt["g4"]["exit_codes"][str(ready["pid"])] not in
                        {21, 22, 23, 24, 25, 26}, "G4 child reported a normal rejection")
                receipt["g4"]["active_zero_basis"] = "complete tracked PID set exited; Job handle closed"
        if not job.closed:
            receipt["final_accounting"] = api.accounting(job)
            require(receipt["final_accounting"]["ActiveProcesses"] == 0, "active processes remain")
        require(api.tick() <= work_deadline, "case work exceeded 15s")
        receipt["passed"] = True
    except BaseException as exc:
        receipt["error"] = repr(exc)
    finally:
        cleanup_errors = []
        try:
            if job is not None and not job.closed:
                if api.accounting(job)["ActiveProcesses"]:
                    receipt["cleanup_forced"] = True
                    api.terminate_job(job)
                wait_for(api, lambda: api.accounting(job)["ActiveProcesses"] == 0,
                         final_deadline, "Job cleanup")
                receipt["cleanup_accounting"] = api.accounting(job)
            elif job is not None and any(not api.exited(h) for h in observers.values()):
                receipt["cleanup_forced"] = True
                cleanup_job = api.reopen_for_cleanup(job_name)
                if cleanup_job is not None:
                    handles.append(cleanup_job)
                    api.terminate_job(cleanup_job)
                    wait_for(api, lambda: api.accounting(cleanup_job)["ActiveProcesses"] == 0,
                             final_deadline, "reopened Job cleanup")
                    receipt["cleanup_accounting"] = api.accounting(cleanup_job)
            if process is not None:
                wait_for(api, lambda: api.exited(process) and
                         all(api.exited(h) for h in observers.values()), final_deadline, "tracked cleanup")
        except BaseException as exc:
            cleanup_errors.append(repr(exc))
        try:
            close_all(handles)
        except BaseException as exc:
            cleanup_errors.append(repr(exc))
        receipt.update(end_tick_ms=api.tick(), handle_events=api.events[event_start:],
                       cleanup_errors=cleanup_errors)
        receipt["wall_ms"] = receipt["end_tick_ms"] - start
        if cleanup_errors or receipt["cleanup_forced"] or receipt["wall_ms"] > 20000:
            receipt["passed"] = False
        save(directory / "result.json", receipt, exclusive=True)
        ledger["results"].append(receipt)
        save(ledger_path, ledger)
    return receipt


def parent(args, t0_ns, t0_utc):
    # T0 was captured before arguments, approvals, source/launcher checks and API preparation.
    root = HERE.parents[4]
    approval = load(args.approval)
    contract = load(HERE / "contract.json")
    identity = source_identity(HERE)
    require(approval.get("approved") is True and
            approval.get("scope") == "four_windows_gate_controls_only", "missing control approval")
    require(isinstance(approval.get("approval_reference"), str) and
            approval["approval_reference"].strip(), "missing approval source")
    require(contract["caps"] == CAPS and contract["cases"] == list(CASES), "caps/matrix changed")
    require(approval.get("caps") == CAPS and approval.get("source_identity") == identity,
            "approval does not match exact source/caps")
    require(current_head(root) == approval.get("head"), "HEAD changed")
    executable = root / ".venv" / "Scripts" / "python.exe"
    require(Path(sys.executable).resolve() == executable.resolve(), "must use original venv launcher")
    require(sys.version.split()[0] == contract["python_version"], "Python version changed")
    require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode,
            "required interpreter flags: -I -S -B")
    require(sha256(executable) == contract["venv_launcher_sha256"], "launcher changed")
    directory = Path(args.output).resolve()
    private_root = (Path(os.environ["LOCALAPPDATA"]) / "CodexEvidence").resolve()
    require(directory.is_relative_to(private_root) and directory != private_root and
            not directory.is_relative_to(root) and not directory.exists(),
            "output must be fresh under LOCALAPPDATA/CodexEvidence, outside repository")
    directory.mkdir(parents=True, exist_ok=False)
    api = WinAPI()
    ledger = {"schema": contract["schema"], "t0_utc": t0_utc, "t0_monotonic_ns": t0_ns,
              "clock_sample": {"tick_ms": api.tick(), "monotonic_ns": time.monotonic_ns()},
              "head": approval["head"], "approval_reference": approval["approval_reference"],
              "approval_sha256": sha256(args.approval), "identity": identity,
              "launcher_sha256": sha256(executable), "caps": CAPS,
              "requests": [], "results": [], "E0": 0, "E2": 0, "BC_DLL": 0,
              "debug": 0, "formal": 0, "passed": False}
    ledger_path = directory / "ledger.json"
    save(ledger_path, ledger, exclusive=True)
    try:
        require((time.monotonic_ns() - t0_ns) / 1e9 <= 45, "preparation exceeded 45s")
        for case in CASES:
            # Reserve a whole 20s before the 150s cutoff; no automatic retries.
            require((time.monotonic_ns() - t0_ns) / 1e9 + 20 <= 150, "launch cutoff")
            require(source_identity(HERE) == identity, "source changed between cases")
            result = one_case(api, case, directory / case, executable, identity, ledger, ledger_path,
                              t0_ns + 150_000_000_000)
            if not result["passed"]:
                raise RuntimeError("first unexpected failure: " + case)
        ledger["passed"] = True
    except BaseException as exc:
        ledger["error"] = repr(exc)
    finally:
        ledger["controls_end_utc"] = datetime.now(timezone.utc).isoformat()
        ledger["controls_end_monotonic_ns"] = time.monotonic_ns()
        ledger["controls_wall_seconds"] = (ledger["controls_end_monotonic_ns"] - t0_ns) / 1e9
        ledger["launch_requests_reserved"] = len(ledger["requests"])
        ledger["create_process_attempts"] = sum(bool(r["create_process_attempted"]) for r in ledger["results"])
        ledger["created_launchers"] = sum(bool(r["created"]) for r in ledger["results"])
        ledger["actual_os_process_counts"] = {
            r["case"]: (r.get("final_accounting") or r.get("accounting_before_decision") or
                        r.get("cleanup_accounting") or r.get("accounting_after_resume") or
                        {}).get("TotalProcesses")
            for r in ledger["results"]}
        ledger["delivery_deadline_monotonic_ns"] = t0_ns + 300_000_000_000
        ledger["delivery_included_in_300s"] = True
        if ledger["controls_wall_seconds"] > 150:
            ledger["passed"] = False
        save(ledger_path, ledger)
    return 0 if ledger["passed"] else 1


def main():
    t0_ns = time.monotonic_ns()
    t0_utc = datetime.now(timezone.utc).isoformat()
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.child is not None:
        require(args.approval is None and args.output is None, "invalid child arguments")
        return child(args.child.resolve())
    require(args.approval is not None and args.output is not None, "approval and output required")
    return parent(args, t0_ns, t0_utc)


if __name__ == "__main__":
    raise SystemExit(main())
