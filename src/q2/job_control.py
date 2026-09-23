"""Windows job supervision for complete, gated solver processes and descendants.

API contract: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
The job kills descendants on close; memory is sampled, never a hard limit.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as W
import os
from pathlib import Path
import subprocess
import time

from .monitor import working_set


class Job:
    def __init__(self):
        if os.name != "nt":
            raise OSError("Windows job control is required")
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, W.LPCWSTR], W.HANDLE),
            "SetInformationJobObject": ([W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD], W.BOOL),
            "QueryInformationJobObject": ([W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD, ctypes.c_void_p], W.BOOL),
            "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
            "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
            "OpenProcess": ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
            "CloseHandle": ([W.HANDLE], W.BOOL),
        }
        for name, (args, returns) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, returns

        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                        ("flags", W.DWORD), ("min_ws", ctypes.c_size_t),
                        ("max_ws", ctypes.c_size_t), ("active", W.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", W.DWORD),
                        ("scheduling", W.DWORD)]

        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", ctypes.c_uint64 * 6),
                        ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                        ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]

        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def assign(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def pids(self):
        class Ids(ctypes.Structure):
            _fields_ = [("assigned", W.DWORD), ("count", W.DWORD),
                        ("ids", ctypes.c_size_t * 64)]
        ids = Ids()
        if not self.api.QueryInformationJobObject(self.handle, 3, ctypes.byref(ids), ctypes.sizeof(ids), None):
            raise ctypes.WinError(ctypes.get_last_error())
        if ids.count > 64:
            raise OSError("unexpected process count")
        return list(ids.ids[:ids.count])

    def terminate(self):
        if not self.api.TerminateJobObject(self.handle, 124):
            raise ctypes.WinError(ctypes.get_last_error())

    def open_wait_handle(self, pid):
        handle = self.api.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle and pid in self.pids():
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    def wait_process(self, handle, milliseconds):
        if self.api.WaitForSingleObject(handle,milliseconds) != 0:
            raise OSError('process termination did not signal within cleanup deadline')

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def run_job(command, *, cwd: Path, folder: Path, started: float, deadline: float,
            sampler=working_set, memory_limit=4 * 1024**3, interval=0.25):
    """Child MUST await a GO line before spawning children or doing solver work.

    All input-sensitive work, including final hashing, runs inside this job.
    Parent control receipt writing is separately timed by the caller.
    """
    job, process = None, None
    wait_handles = {}
    record = {"status": "monitor_error", "launched": False, "samples": 0,
              "peak_working_set_bytes": 0, "max_job_processes": 0,
              "interval_seconds": interval, "memory_limit_bytes": memory_limit}
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "controller-samples.jsonl").open("w", encoding="utf-8", newline="\n") as samples, \
                (folder / "worker-stdout.txt").open("wb") as stdout, \
                (folder / "worker-stderr.txt").open("wb") as stderr:
            initial = sampler(os.getpid())
            record["peak_working_set_bytes"] = initial
            if initial >= memory_limit:
                record["status"] = "resource_limit"
                return record
            if time.monotonic() >= deadline:
                record["status"] = "timeout"
                return record
            job = Job()
            process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE,
                                       stdout=stdout, stderr=stderr,
                                       env=dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1"))
            record.update(launched=True, pid=process.pid)
            job.assign(process)
            process.stdin.write(b"GO\n")
            process.stdin.close()
            while True:
                pids = job.pids()
                for pid in pids:
                    if pid not in wait_handles:
                        handle = job.open_wait_handle(pid)
                        if handle:
                            wait_handles[pid] = handle
                rss = sampler(os.getpid())
                for pid in pids:
                    try:
                        rss += sampler(pid)
                    except OSError:
                        # A process may exit between listing and sampling.
                        if pid in job.pids():
                            raise
                now = time.monotonic()
                record["samples"] += 1
                record["max_job_processes"] = max(record["max_job_processes"], len(pids))
                record["peak_working_set_bytes"] = max(record["peak_working_set_bytes"], rss)
                samples.write(f'{{"elapsed":{now-started},"working_set_bytes":{rss},"processes":{pids}}}\n')
                samples.flush()
                if rss >= memory_limit:
                    record["status"] = "resource_limit"
                    break
                if now >= deadline:
                    record["status"] = "timeout"
                    break
                if process.poll() is not None:
                    # A crashed worker must not leave a generator/evaluator running.
                    pids = job.pids()
                    record["worker_exit_with_descendants"] = bool(pids)
                    record["status"] = "completed" if process.returncode == 0 and not pids else "worker_error"
                    break
                time.sleep(min(interval, max(0, deadline - now)))
    except Exception as error:
        record.update(status="monitor_error", error_type=type(error).__name__, error=str(error))
    finally:
        cleanup_started = time.monotonic()
        cleanup_deadline = cleanup_started + 10
        record.update(waited_process_handles=0,closed_wait_handles=0)
        try:
            if process is not None and process.stdin is not None and not process.stdin.closed:
                process.stdin.close()  # Assignment failure never reached the GO-gate close.
            if job is not None:
                for pid in job.pids():
                    if pid not in wait_handles:
                        handle = job.open_wait_handle(pid)
                        if handle:
                            wait_handles[pid] = handle
                job.terminate()
            if process is not None:
                # Also kill the gated child if assignment itself failed.
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=max(0,cleanup_deadline-time.monotonic()))
            if job is not None:
                # TerminateJobObject/TerminateProcess initiate asynchronous exits.
                # Active PID accounting alone does not wait for handle cleanup.
                for pid, handle in wait_handles.items():
                    milliseconds = max(0, int((cleanup_deadline-time.monotonic())*1000))
                    job.wait_process(handle,milliseconds)
                    record['waited_process_handles'] += 1
                # Waiting for only the immediate child is insufficient.
                while job.pids() and time.monotonic() < cleanup_deadline:
                    time.sleep(0.01)
                record["remaining_job_pids"] = job.pids()
                if record["remaining_job_pids"]:
                    record["status"] = "monitor_error"
        except Exception as error:
            record.update(status="monitor_error", cleanup_error=str(error))
            if process is not None and process.poll() is None:
                process.kill()
                try:
                    process.wait(timeout=max(0,cleanup_deadline-time.monotonic()))
                except subprocess.TimeoutExpired:
                    record['cleanup_error'] += '; immediate child still unsignaled at cleanup deadline'
        finally:
            if job is not None:
                for handle in wait_handles.values():
                    if job.api.CloseHandle(handle):
                        record['closed_wait_handles'] += 1
                    else:
                        record.update(status='monitor_error',cleanup_error='failed to close process wait handle')
                job.close()  # KILL_ON_JOB_CLOSE remains the last fail-safe.
            if process is not None:
                process._handle.Close()
                record['closed_popen_process_handle'] = True
        record["returncode"] = process.returncode if process is not None else None
        record["cleanup_seconds"] = time.monotonic() - cleanup_started
        record["wall_through_job_cleanup"] = time.monotonic() - started
        record["overshoot_seconds"] = max(0, time.monotonic() - deadline)
    return record
