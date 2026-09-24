"""One approved Windows window. Code is an unexecuted preparation artifact."""
import ctypes as ct
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time

# -I removes the script directory. Bind only this already hash-pinned directory.
_DRIVER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_DRIVER_DIR))
import common as _common
if Path(_common.__file__).resolve() != _DRIVER_DIR / "common.py":
    raise RuntimeError("unexpected common module origin")
from common import HERE, ROOT, PLAN, SCHEMA, read, save, require, digest, contract, matrix, source_identity, expected_stdin, route_line, fake_argv, wait_record
from win_support import API, Census
from gate_helper import OwnedHandle, close_all


def locate(label, runtime_home):
    kind, relative = label.split(":", 1)
    base = {"root": ROOT, "runtime": runtime_home, "venv": ROOT / ".venv"}[kind]
    path = (base / relative).resolve()
    require(path.is_relative_to(base.resolve()), "manifest path escapes root")
    return path


def elapsed(api, outer):
    return (api.qpc() - outer["outer_t0_qpc"]) / outer["qpc_frequency"]


def failure_capture(api, job):
    """The controller waits <=100ms; a slow read-only OS call cannot delay kill.

    A timed-out daemon owns only temporary observer/snapshot handles, never Job
    mutation rights. Its observations are not merged into the live Census.
    """
    box = {}
    def collect():
        local = []
        try:
            until = time.monotonic() + 0.09
            listing = api.pids(job)
            parents = api.parents(until)
            rows = []
            for pid in listing["pids"]:
                require(time.monotonic() < until, "failure identity collection deadline")
                handle = api.observer(pid)
                local.append(handle)
                rows.append(api.identity(pid, handle, parents.get(pid)))
            box["value"] = {"listing": listing, "identities": rows}
        except BaseException as exc:
            box["error"] = repr(exc)
        finally:
            try:
                close_all(local)
            except BaseException as exc:
                box["close_error"] = repr(exc)
    thread = threading.Thread(target=collect, daemon=True)
    thread.start()
    thread.join(0.1)
    if thread.is_alive():
        return {"error": "capture deadline; OS collector still pending", "complete": False}
    return {**box, "complete": "value" in box and "close_error" not in box}


def command(row, case, python):
    bindings = {"${ROOT}": str(ROOT), "${PY}": str(python),
                "${INPUT}": str(case / "input"), "${CASE}": str(case)}
    result = []
    for token in row["argv_tokens"]:
        for variable, value in bindings.items():
            token = token.replace(variable, value)
        require("${" not in token, "unresolved command token")
        result.append(token)
    return result


def validate_result(row, case, run, census):
    result = read(case / "bootstrap.result.json")
    rc = result["returncode"]
    if row["kind"] == "fake_contract":
        require(read(case / "wrapper.ready.json")["subprocess_real"] is True, "real subprocess evidence")
        attempts = read(case / "helper-create-attempt.json")
        require(len(attempts) == 1 and attempts[0]["env_is_none"]
                and attempts[0]["cwd"] is None, "helper launch semantics")
        executable = str(case / "missing interpreter.exe") if row["id"] == "F-startfail" else str(ROOT / ".venv/Scripts/python.exe")
        expected_tokens = [executable, str(case / "目标 空间" /
                           f"multicore_cut_evaluate_problem_{row['problem']}.py"), *fake_argv(row)]
        require(attempts[0]["raw_executable"] is None and attempts[0]["raw_executable_type"] == "NoneType" and
                attempts[0]["expected_image_token"] == expected_tokens[0] and
                attempts[0]["expected_tokens"] == expected_tokens and
                attempts[0]["command_line_type"] == "str" and
                attempts[0]["command_line"] == subprocess.list2cmdline(expected_tokens), "raw Windows command line")
        if row["id"] == "F-startfail":
            error = read(case / "wrapper.start_error.json")
            require(rc != 0 and error["create_attempts"] == 1 and error["winerror"] in (2, 3),
                    "genuine CreateProcess not-found failure")
            require(not (case / "target.ready.json").exists(), "startup failure launched target")
        else:
            expected = row["expected_ordinary_exit_code"]
            require(rc == expected, "wrapper ordinary code")
            require(read(case / "wrapper.exit.json")["SystemExit_code"] == expected, "SystemExit evidence")
            target = read(case / "target.ready.json")
            require(target["argv"] == expected_tokens[1:], "actual target argv tokens")
            observed = census.rows[target["pid"]]
            require(observed.get("signaled") and observed["raw_exit_dword"] == expected,
                    "real target raw exit status")
            if row["id"] != "F2":
                require(read(case / "target.final.json")["exit_code_requested"] == expected,
                        "target final marker")
            if row["id"] == "F1":
                require((case / "case.stdout.raw").read_bytes() == b"O" * (256 * 1024), "PIPE stdout bytes")
                stderr = (case / "case.stderr.raw").read_bytes().replace(b"\r\n", b"\n")
                require(stderr == route_line(row["problem"]) + b"E" * (256 * 1024), "PIPE stderr bytes")
        return {"observed_returncode": rc, "completed_e0": 0}
    require(rc == row["expected_ordinary_exit_code"], "real CLI return code")
    valid = "-invalid-" not in row["id"]
    artifacts = [case / n for n in ("result.json", "trace.json", "official.log")]
    require(all(p.is_file() for p in artifacts) if valid else not any(p.exists() for p in artifacts),
            "immediate official artifact presence")
    compare = {"observed_returncode": rc, "potential_e0_retained": 1,
               "actual_function_entries": None, "complete_success": valid,
               "normalizations": []}
    if row["route"] == "adapter":
        reference = run / "cases" / row["paired_reference_case"]
        for artifact in artifacts:
            if valid:
                require(artifact.read_bytes() == (reference / artifact.name).read_bytes(),
                        "full artifact bytes: " + artifact.name)
        left = (reference / "case.stdout.raw").read_bytes()
        right = (case / "case.stdout.raw").read_bytes()
        if valid:
            old = str(reference / "result.json").encode("utf-8")
            new = str(case / "result.json").encode("utf-8")
            require(left.count(old) == 1 and right.count(new) == 1, "stdout path occurrence")
            right = right.replace(new, old, 1)
            compare["normalizations"].append({"kind": "single_output_path", "from": new.decode(), "to": old.decode()})
        require(right == left, "stdout comparison")
        stderr = (case / "case.stderr.raw").read_bytes()
        prefix = route_line(row["problem"]).replace(b"\n", b"\r\n")
        if not stderr.startswith(prefix):
            prefix = route_line(row["problem"])
        require(stderr.startswith(prefix), "exact route prefix")
        require(stderr[len(prefix):] == (reference / "case.stderr.raw").read_bytes(), "stderr comparison")
        compare["normalizations"].append({"kind": "one_route_prefix", "bytes_hex": prefix.hex()})
    return compare


def one_case(row, run, approval, manifest, api, outer, python, allowed_images):
    case = run / "cases" / row["id"]
    case.mkdir()
    for name in ("input", "工作 空间", "目标 空间"):
        (case / name).mkdir()
    for name in ("E_full_valid.graph.json", "E_full_valid.plan.json", "invalid-plan.json"):
        (case / "input" / name).write_bytes((PLAN / name).read_bytes())
    (case / "stdin.bin").write_bytes(expected_stdin(row) if row["kind"] == "fake_contract" else b"")
    for n in (2, 3):
        (case / "目标 空间" / f"multicore_cut_evaluate_problem_{n}.py").write_bytes((HERE / "fixture.py").read_bytes())
    job_name = "Local\\e2-cli-" + secrets.token_hex(24)
    event_name = "Local\\e2-cli-release-" + secrets.token_hex(24)
    start_tick = api.tick()
    deadline = start_tick + 35000
    request = {"schema": SCHEMA, "case": row, "case_directory": str(case),
               "run_directory": str(run), "job": job_name, "release_event": event_name,
               "nonce": secrets.token_hex(32), "bundle": manifest["driver_bundle_sha256"],
               "helper_sha256": matrix()["production_helper_sha256"], "work_deadline_tick": deadline,
               "argv": command(row, case, python) if row["kind"] == "real_cli" else None}
    save(case / "request.private.json", request, exclusive=True)
    handles = []
    census = None
    job = process = event = None
    record = {"id": row["id"], "passed": False, "forced_cleanup": False,
              "expected_cancel": row["id"] == "F-cancel", "error": None, "cleanup_errors": []}
    shared_cleanup_end = None
    try:
        job = api.job(job_name)
        handles.append(job)
        api.configure(job)
        event = api.event(event_name, create=True)
        handles.append(event)
        census = Census(api, job, allowed_images)
        env = dict(os.environ)
        env.update(E2_CASE_DIR=str(case), E2_CASE_NONCE=request["nonce"], E2_DRIVER_DIR=str(HERE),
                   E2_SENTINEL="环境 sentinel λ", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8:strict",
                   PYTHONUTF8="1")
        receipt = {}
        launch_started = time.monotonic()
        try:
            # Conservative single cleanup allowance: fixed primitive's failed-
            # launch wait and our finally share this deadline, never 5s + 10s.
            process = api.launch_assigned(python, ["-I", "-B", "-X", "utf8", HERE / "bootstrap.py"], env, case, job,
                                         receipt, api.tick() + 10000, time.monotonic_ns() + 5000000000)
        except BaseException:
            shared_cleanup_end = launch_started + 10
            raise
        handles.append(process)
        save(case / "bootstrap-launch.json", receipt, exclusive=True)
        acked = released = cancelled = False
        while api.tick() < deadline and elapsed(api, outer) < 660:
            listing = census.sample()
            accounting = api.accounting(job)
            require(accounting["TotalProcesses"] <= contract()["aggregate_policy"]["case_cumulative_limits"][row["id"]],
                    "case aggregate process policy exceeded")
            ready_path = case / "bootstrap.ready.json"
            if not acked and ready_path.is_file():
                boot = read(ready_path)
                require(boot["bundle"] == request["bundle"] and boot["nonce_sha256"] ==
                        hashlib.sha256(request["nonce"].encode()).hexdigest(), "bootstrap identity")
                require(boot["pid"] in listing["pids"] and len(listing["pids"]) <= 3, "bootstrap launch chain")
                proof = boot["membership"]
                require(proof["api_success"] and proof["member"] and proof["query_closed"], "exact Job proof")
                save(case / "ack.private.json", {"pid": boot["pid"], "nonce": request["nonce"],
                     "bundle": request["bundle"], "complete_ready_pids": listing["pids"]}, exclusive=True)
                acked = True
            target_path = case / "target.ready.json"
            if acked and not released and target_path.is_file():
                target = read(target_path)
                wrapper = read(case / "wrapper.ready.json")
                for pid in (target["pid"], wrapper["pid"]):
                    require(pid in census.handles and not api.exited(census.handles[pid]), "wait ownership/alive")
                if row["id"] == "F-cancel":
                    grand = case / "grandchild.ready.json"
                    if not grand.is_file():
                        time.sleep(0.005)
                        continue
                    descendant = read(grand)
                    require(descendant["pid"] in census.handles and
                            not api.exited(census.handles[descendant["pid"]]), "grandchild live handle")
                    handle = OwnedHandle(api, api.check(api.k.OpenProcess(0x1 | 0x100000 | 0x1000,
                                                                         False, wrapper["pid"])), "wrapper_terminate")
                    try:
                        api.inherit(handle)
                        require(api.identity(wrapper["pid"], handle, wrapper["ppid"])["creation_filetime"] ==
                                census.rows[wrapper["pid"]]["creation_filetime"], "cancel PID identity")
                        api.check(api.k.TerminateProcess(handle.value, 0xE0000002))
                    finally:
                        handle.close()
                    record["cancel_snapshot"] = census.sample(0.1)
                    require(not api.exited(census.handles[target["pid"]]) and
                            not api.exited(census.handles[descendant["pid"]]), "retained descendants before Job cleanup")
                    cancelled = True
                    break
                # An actual wait timeout demonstrates liveness while release is withheld.
                require(api.k.WaitForSingleObject(census.handles[wrapper["pid"]].value, 50) == 258,
                        "wrapper returned before target release")
                require(not api.exited(census.handles[target["pid"]]), "target vanished before release")
                record["waiting_proof"] = {"wrapper_pid": wrapper["pid"], "target_pid": target["pid"],
                                           "withheld_release_wait_timeout_ms": 50, "qpc": api.qpc()}
                api.check(api.k.SetEvent(event.value))
                released = True
            if (case / "bootstrap.result.json").is_file() or api.exited(process):
                require(acked, "bootstrap exited before admission")
                break
            time.sleep(0.005)
        require(cancelled or (case / "bootstrap.result.json").is_file(), "case/global work deadline")
        if not cancelled:
            work_result = read(case / "bootstrap.result.json")
            require(work_result["work_finished_tick"] <= deadline, "work exceeded 35 seconds")
            close_deadline = min(work_result["work_finished_tick"] + 3000,
                                 start_tick + 38000,
                                 api.tick() + int(max(0, 660 - elapsed(api, outer)) * 1000))
            while api.tick() < close_deadline:
                census.sample()
                if api.exited(process) and api.accounting(job)["ActiveProcesses"] == 0:
                    break
                time.sleep(0.005)
            record["normal_close_seconds"] = (api.tick() - work_result["work_finished_tick"]) / 1000
            require(0 <= record["normal_close_seconds"] <= 3 and api.exited(process), "normal close deadline")
            require(api.exit_code(process) == 0, "bootstrap failed")
            require(api.accounting(job)["ActiveProcesses"] == 0, "normal completion left descendants")
            census.final()
            record["validation"] = validate_result(row, case, run, census)
            require(len(census.handles) == api.accounting(job)["TotalProcesses"], "incomplete process census")
            require(all(r.get("signaled") for r in census.rows.values()), "unexited member")
            record["passed"] = True
        else:
            record["planned_cancel_observed"] = True
    except BaseException as exc:
        record["error"] = repr(exc)
        if shared_cleanup_end is None:
            shared_cleanup_end = time.monotonic() + 10
    finally:
        cleanup_start = time.monotonic()
        cleanup_end = min(shared_cleanup_end or cleanup_start + 10,
                          time.monotonic() + max(0, 670 - elapsed(api, outer)))
        if job is not None:
            try:
                if api.accounting(job)["ActiveProcesses"]:
                    capture_start = time.monotonic()
                    record["failure_pid_snapshot"] = failure_capture(api, job)
                    if not record["failure_pid_snapshot"]["complete"]:
                        record["failure_capture_error"] = record["failure_pid_snapshot"].get("error", "incomplete")
                    record["failure_capture_wall_seconds"] = time.monotonic() - capture_start
                    api.terminate_job(job)
                    record["forced_cleanup"] = True
                    while api.accounting(job)["ActiveProcesses"] and time.monotonic() < cleanup_end:
                        time.sleep(0.005)
                require(api.accounting(job)["ActiveProcesses"] == 0, "cleanup_incomplete")
                if census:
                    record["census"] = census.final()
                    require(all(r.get("signaled") for r in census.rows.values()), "cleanup handle unsignaled")
                    require(len(census.handles) == api.accounting(job)["TotalProcesses"], "missing lifecycle identity")
                    require(api.accounting(job)["TotalProcesses"] <= contract()["aggregate_policy"]["case_cumulative_limits"][row["id"]],
                            "final case aggregate policy")
                    known = {"bootstrap_launcher": receipt["launcher_pid"]}
                    if (case / "bootstrap.ready.json").exists():
                        known["bootstrap_actual"] = read(case / "bootstrap.ready.json")["pid"]
                    if (case / "case-launcher.json").exists():
                        known["case_launcher"] = read(case / "case-launcher.json")["pid"]
                    for name in ("wrapper", "target", "grandchild"):
                        if (case / (name + ".ready.json")).exists():
                            known[name + "_actual"] = read(case / (name + ".ready.json"))["pid"]
                    require(all(pid in census.rows for pid in known.values()), "known PID association incomplete")
                    record["known_identity_associations"] = [
                        {"role": role, "pid": pid, "creation_filetime": census.rows[pid]["creation_filetime"]}
                        for role, pid in known.items()]
                if record.get("planned_cancel_observed") and record["error"] is None:
                    require(record["forced_cleanup"] and not record.get("failure_capture_error"), "cancel cleanup proof")
                    record["passed"] = True
            except BaseException as exc:
                record["cleanup_errors"].append(repr(exc))
                record["passed"] = False
            finally:
                if census:
                    try:
                        close_all(list(census.handles.values()))
                    except BaseException as exc:
                        record["cleanup_errors"].append(repr(exc))
                        record["passed"] = False
        try:
            close_all(handles)
        except BaseException as exc:
            record["cleanup_errors"].append(repr(exc))
            record["passed"] = False
        record["cleanup_wall_seconds"] = time.monotonic() - cleanup_start
        if record["cleanup_wall_seconds"] > 10:
            record["cleanup_errors"].append("cleanup exceeded 10 seconds")
            record["passed"] = False
        if time.monotonic() > cleanup_end:
            record["cleanup_errors"].append("shared first-failure cleanup deadline exceeded")
            record["passed"] = False
        record["handle_events"] = api.events
        api.events = []
        record["end_elapsed_seconds"] = elapsed(api, outer)
        save(case / "controller.json", record, exclusive=True)
    return record


def main():
    require(len(sys.argv) == 2, "one private run directory required")
    run = Path(sys.argv[1]).resolve()
    approval = read(run / "approval.json")
    require(approval.get("approved") is True and approval.get("execution_enabled") is True, "not approved")
    settings = contract()
    require(settings["execution_blockers"] == [], "driver checkpoint still has static execution blockers")
    require(approval["limits"] == settings["limits"], "approved limits mismatch")
    require(approval.get("runtime_review_closed") is True and approval.get("approval_reference"), "runtime review unresolved")
    manifest = source_identity()
    require(approval["driver_bundle_sha256"] == manifest["driver_bundle_sha256"], "approved bundle")
    require(digest(HERE / "sources.json") == approval["sources_sha256"], "approved source manifest")
    require(sys.flags.isolated and sys.dont_write_bytecode and sys.flags.utf8_mode == 1 and os.name == "nt",
            "Windows -I -B -X utf8 required")
    api = API()
    outer = read(run / "outer.json")
    require(outer["driver_commit"] == approval["driver_commit"], "outer commit")
    outer_proof = api.exact_membership(outer["root_job_name"])
    require(outer_proof["api_success"] and outer_proof["member"] and outer_proof["query_closed"], "outer Job membership")
    require(elapsed(api, outer) < 90, "preparation cutoff")
    require(api.available() >= 3 * 1024**3, "available physical memory")
    require(not os.environ.get("PYTHONHOME") and not os.environ.get("PYTHONPATH"), "ambient Python path contamination")
    cfg = dict(line.split(" = ", 1) for line in (ROOT / ".venv/pyvenv.cfg").read_text().splitlines() if " = " in line)
    runtime_home = Path(cfg["home"]).resolve()
    for label, expected in manifest["environment_files"].items():
        require(elapsed(api, outer) < 90, "preparation cutoff during environment reads")
        require(digest(locate(label, runtime_home)) == expected, "pinned environment: " + label)
    official = ROOT / "data/raw/a/official/code"
    official_rows = "".join(f"code/{path.name}\t{digest(path)}\n" for path in
                            sorted(official.iterdir(), key=lambda p: p.name) if path.is_file())
    require(hashlib.sha256(official_rows.encode()).hexdigest() ==
            "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0", "official directory aggregate")
    python = ROOT / ".venv/Scripts/python.exe"
    require(Path(sys.executable).resolve() == python.resolve(), "interpreter path")
    allowed_images = {str(locate(label, runtime_home)).casefold() for label in manifest["allowed_image_labels"]}
    me = api.observer(os.getpid())
    try:
        info = api.identity(os.getpid(), me, os.getppid())
        require(api.memory(me)["private_bytes"] <= 256 * 1024**2, "controller memory budget")
        save(run / "controller.boot.json", {**info, "outer_nonce": outer["outer_nonce"]}, exclusive=True)
    finally:
        me.close()
    require(elapsed(api, outer) < 90, "preparation cutoff after identities")
    ack_deadline = api.tick() + int(max(0, 90 - elapsed(api, outer)) * 1000)
    outer_ack = wait_record(run / "controller.ack.private.json", ack_deadline, api)
    require(outer_ack["outer_nonce"] == outer["outer_nonce"] and outer_ack["controller_pid"] == os.getpid()
            and outer_ack["driver_bundle_sha256"] == manifest["driver_bundle_sha256"], "controller admission ACK")
    controller_count = outer_ack["controller_os_count"]
    require(1 <= controller_count <= 3 and len(set(outer_ack["complete_pids"])) == controller_count
            and os.getpid() in outer_ack["complete_pids"], "independent controller <=3 policy")
    (run / "cases").mkdir()
    ledger = {"logical_reserved": 1, "potential_e0_reserved": 0, "cases": [], "state": "running",
              "controller_OS_count": controller_count, "case_OS_total": 0, "case_OS_accounting_complete": True}
    save(run / "ledger.json", ledger, exclusive=True)
    for row in matrix()["cases"]:
        require(elapsed(api, outer) + 35 + 3 + 10 <= 670, "no complete case budget left")
        require(controller_count + ledger["case_OS_total"] +
                settings["aggregate_policy"]["case_cumulative_limits"][row["id"]] <= 126,
                "whole-window cumulative admission policy")
        ledger["logical_reserved"] += row["process_model"]["logical_create_requests"]
        ledger["potential_e0_reserved"] += row["potential_e0_reserved"]
        require(ledger["logical_reserved"] <= 43 and ledger["potential_e0_reserved"] <= 8, "reservation cap")
        ledger["cases"].append({"id": row["id"], "reserved": True, "state": "admitted"})
        save(run / "ledger.json", ledger)
        result = one_case(row, run, approval, manifest, api, outer, python, allowed_images)
        ledger["cases"][-1]["state"] = "passed" if result["passed"] else "stopped"
        counted = result.get("census", {}).get("accounting", {}).get("TotalProcesses")
        ledger["cases"][-1]["actual_OS_cumulative"] = counted
        if counted is None:
            ledger["case_OS_accounting_complete"] = False
        else:
            ledger["case_OS_total"] += counted
        require(ledger["case_OS_total"] <= 123, "case cumulative total policy")
        ledger["state"] = "running" if result["passed"] else "stopped"
        save(run / "ledger.json", ledger)
        save(run / "final.accounting.json", {"controller_os_count": controller_count,
             "case_OS_total": ledger["case_OS_total"], "case_records": ledger["cases"],
             "complete": ledger["case_OS_accounting_complete"], "state": ledger["state"],
             "exact_peak_active": None})
        if not result["passed"]:
            return 1
    ledger["state"] = "matrix_passed_pending_evidence_review"
    save(run / "ledger.json", ledger)
    save(run / "final.accounting.json", {"controller_os_count": controller_count,
         "case_OS_total": ledger["case_OS_total"], "case_records": ledger["cases"],
         "complete": ledger["case_OS_accounting_complete"], "state": ledger["state"],
         "exact_peak_active": None})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) == 2 and Path(sys.argv[1]).is_dir():
            save(Path(sys.argv[1]) / "controller.error.json", {"error": repr(error)})
        raise
