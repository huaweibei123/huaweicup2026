"""Host-side, single-use Colab controller for an admitted 014/K1 differential.

Do not invoke before the total scheduler grants an exclusive CPU Standard
window. This creates one CPU session and never retries the preparation.
"""

import argparse
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys
import time
import zipfile


CAPSULE_SHA256 = "9a41bc000814f180d99433d8cb5cf645dc134c564c98ad19d63fcfcb5648a3af"
VM_SECONDS = 600


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def run_logged(command, log_file, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("independent VM deadline reached")
    with log_file.open("wb") as output:
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT,
                                timeout=min(remaining, 550), check=False)
    return result.returncode


def stop_proven(receipt):
    """Require successful stop and successful, explicit absence on readback."""
    return (receipt.get("stop_exit_code") == 0
            and receipt.get("sessions_readback_exit_code") == 0
            and receipt.get("named_session_still_active") is False
            and "stop_error" not in receipt
            and "sessions_readback_error" not in receipt)


def final_status(workload_completed, receipt):
    return "completed" if workload_completed and stop_proven(receipt) else "failed_or_unknown"


def release_watchdog_if_proven(watchdog, receipt):
    """Keep the independent stop request alive whenever stop is unproven."""
    receipt["watchdog_termination_skipped"] = not stop_proven(receipt)
    receipt["watchdog_already_exited"] = watchdog.poll() is not None
    if not stop_proven(receipt):
        return
    watchdog.terminate()
    try:
        watchdog.wait(timeout=3)
    except subprocess.TimeoutExpired:
        watchdog.kill()
        watchdog.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--admitted", action="store_true", help="total scheduler granted the exclusive CPU window")
    parser.add_argument("--capsule", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()
    if not args.admitted:
        parser.error("refusing to create a VM without --admitted")
    actual = hashlib.sha256(args.capsule.read_bytes()).hexdigest()
    if actual != CAPSULE_SHA256:
        parser.error(f"capsule hash mismatch: {actual}")
    args.out.mkdir(parents=True, exist_ok=False)
    session = "q2-rank-014-s55-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    receipt = {"schema": "q2-rank-014-host-v1", "session": session,
               "vm_t0_utc": utc_now(), "capsule_sha256": actual,
               "admitted_flag": True, "preparation_attempts": 0,
               "planned_e0_calls": 0, "planned_native_replays": 0,
               "retry_count": 0,
               "status": "setup_failed"}
    deadline = time.monotonic() + VM_SECONDS
    # The separate process survives a controller crash. The controller also
    # enforces the deadline and always tries to stop/read back in finally.
    watchdog = subprocess.Popen(["/bin/sh", "-c",
                                 'sleep 600; colab stop --session "$1"',
                                 "watchdog", session],
                                stdout=(args.out / "watchdog.log").open("wb"),
                                stderr=subprocess.STDOUT, start_new_session=True)
    try:
        if run_logged(["colab", "new", "--session", session], args.out / "new.log", deadline):
            raise RuntimeError("colab new failed")
        if run_logged(["colab", "upload", "--session", session,
                       str(args.capsule), "/content/q2-rank-014-capsule.zip"],
                      args.out / "upload.log", deadline):
            raise RuntimeError("colab upload failed")
        cell = pathlib.Path(__file__).with_name("q2_rank_prep_colab_cell.py")
        receipt["preparation_attempts"] = 1
        receipt["cell_dispatch_utc"] = utc_now()
        cell_timeout = min(540, max(1, int(deadline - time.monotonic() - 30)))
        code = run_logged(["colab", "exec", "--session", session,
                           "--file", str(cell), "--timeout", str(cell_timeout)],
                          args.out / "exec.log", deadline)
        receipt["exec_exit_code"] = code
        # Preserve failure/partial evidence too. A missing archive leaves the
        # attempt's actual call count unknown, never zero by inference.
        try:
            receipt["download_exit_code"] = run_logged(
                ["colab", "download", "--session", session,
                 "/content/q2-rank-014-result.zip", str(args.out / "result.zip")],
                args.out / "download.log", deadline)
        except (TimeoutError, subprocess.TimeoutExpired) as error:
            receipt["download_error"] = str(error)
        result_path = args.out / "result.zip"
        if result_path.exists():
            try:
                with zipfile.ZipFile(result_path) as archive:
                    cell_receipt = json.loads(archive.read("cell-receipt.json"))
                receipt["cell_status"] = cell_receipt.get("status")
                receipt["cell_preparation_attempts"] = cell_receipt.get("preparation_attempts")
                receipt["cell_runner_report_status"] = cell_receipt.get("runner_report", {}).get("status")
            except (OSError, KeyError, ValueError, zipfile.BadZipFile) as error:
                receipt["cell_receipt_error"] = str(error)
        receipt["workload_completed"] = bool(
            code == 0 and receipt.get("download_exit_code") == 0
            and receipt.get("cell_status") == "completed"
            and receipt.get("cell_preparation_attempts") == 1
        )
    except Exception as error:
        receipt["error"] = f"{type(error).__name__}: {error}"
        if receipt["preparation_attempts"]:
            receipt["status"] = "failed_or_unknown"
    finally:
        receipt["stop_requested_utc"] = utc_now()
        try:
            receipt["stop_exit_code"] = run_logged(["colab", "stop", "--session", session],
                                                   args.out / "stop.log", time.monotonic() + 45)
        except Exception as error:
            receipt["stop_error"] = str(error)
        try:
            receipt["sessions_readback_exit_code"] = run_logged(
                ["colab", "sessions"], args.out / "sessions-after.log", time.monotonic() + 45)
            if receipt["sessions_readback_exit_code"] == 0:
                receipt["named_session_still_active"] = session in (args.out / "sessions-after.log").read_text()
        except Exception as error:
            receipt["sessions_readback_error"] = str(error)
        receipt["stop_proven"] = stop_proven(receipt)
        receipt["status"] = final_status(receipt.get("workload_completed") is True, receipt)
        release_watchdog_if_proven(watchdog, receipt)
        receipt["host_finished_utc"] = utc_now()
        if not (args.out / "result.zip").exists():
            receipt["calls_if_no_cell_report"] = "unknown; do not infer zero"
        (args.out / "host-receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2))
    return 0 if receipt["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
