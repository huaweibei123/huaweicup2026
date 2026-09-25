"""Serial subprocess supervision with Windows sampled working-set accounting."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import time


def working_set(pid: int) -> int:
    """Read one process. Fail closed outside the validated Windows runtime."""
    if os.name != "nt":
        raise OSError("stage A working-set monitor currently supports Windows only")

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE,
                                          ctypes.POINTER(Counters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x0400 | 0x0010, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return counters.WorkingSetSize
    finally:
        kernel.CloseHandle(handle)


def supervise(command: list[str], *, cwd: Path, folder: Path,
              deadline: float, memory_limit: int = 4 * 1024**3,
              interval: float = 0.25, sampler=working_set) -> dict:
    """Monitor this controller plus its sole direct child; no worker descendants.

    The frozen CLI and stub are single Python processes. Working sets can double
    count shared pages and miss between-sample peaks. This is not a hard limit.
    """
    folder.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    record = {"status": "error", "launched": False, "samples": 0,
              "sampled_working_set_peak_bytes": 0, "sample_interval_seconds": interval,
              "memory_limit_bytes": memory_limit, "returncode": None}
    process = None
    try:
        first = sampler(os.getpid())
        record["samples"] += 1
        record["sampled_working_set_peak_bytes"] = first
        if first >= memory_limit:
            record["status"] = "resource_limit"
            return record
        if time.monotonic() >= deadline:
            record["status"] = "timeout"
            return record
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
        with (folder / "stdout.txt").open("wb") as out, (folder / "stderr.txt").open("wb") as err:
            process = subprocess.Popen(command, cwd=cwd, env=env, stdout=out, stderr=err)
            record["launched"] = True
            record["child_pid"] = process.pid
            while True:
                parent_rss = sampler(os.getpid())
                child_rss = 0
                if process.poll() is None:
                    try:
                        child_rss = sampler(process.pid)
                    except OSError:
                        if process.poll() is None:
                            raise
                record["samples"] += 1
                record["sampled_working_set_peak_bytes"] = max(
                    record["sampled_working_set_peak_bytes"], parent_rss + child_rss)
                if parent_rss + child_rss >= memory_limit:
                    record["status"] = "resource_limit"
                    break
                if process.poll() is not None:
                    record["status"] = "completed"
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    record["status"] = "timeout"
                    break
                time.sleep(min(interval, remaining))
    except (OSError, ValueError) as error:
        record.update(status="monitor_error", error_type=type(error).__name__,
                      error=str(error))
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            record["returncode"] = process.wait()
        record["wall_seconds"] = time.monotonic() - started
        record["deadline_overshoot_seconds"] = max(0.0, time.monotonic() - deadline)
    return record
