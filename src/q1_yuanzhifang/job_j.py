"""Windows Job supervisor copied from Stage I fixed 7993bafe; no graph semantics."""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[2]
GATE_CODE = ("import os,runpy,sys,time;" "gate=os.environ['Q1_JOB_GATE'];entry=os.environ['Q1_JOB_ENTRY'];" "\nwhile not os.path.exists(gate): time.sleep(.01)" "\nsys.path.insert(0,os.path.dirname(entry));runpy.run_path(entry,run_name='__main__')")

def job_api():
    """Return Win32 Job functions with verified pointer-sized structure layout."""
    from ctypes import c_size_t, c_longlong, c_uint32, c_uint64, c_void_p

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", c_longlong),
                    ("PerJobUserTimeLimit", c_longlong), ("LimitFlags", c_uint32),
                    ("MinimumWorkingSetSize", c_size_t), ("MaximumWorkingSetSize", c_size_t),
                    ("ActiveProcessLimit", c_uint32), ("Affinity", c_size_t),
                    ("PriorityClass", c_uint32), ("SchedulingClass", c_uint32)]

    class Io(ctypes.Structure):
        _fields_ = [(name, c_uint64) for name in
                    ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                     "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", Io),
                    ("ProcessMemoryLimit", c_size_t), ("JobMemoryLimit", c_size_t),
                    ("PeakProcessMemoryUsed", c_size_t), ("PeakJobMemoryUsed", c_size_t)]

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateJobObjectW.argtypes = (c_void_p, wintypes.LPCWSTR)
    api.CreateJobObjectW.restype = c_void_p
    api.SetInformationJobObject.argtypes = (c_void_p, ctypes.c_int, c_void_p, c_uint32)
    api.SetInformationJobObject.restype = wintypes.BOOL
    api.AssignProcessToJobObject.argtypes = (c_void_p, c_void_p)
    api.AssignProcessToJobObject.restype = wintypes.BOOL
    api.CloseHandle.argtypes = (c_void_p,)
    api.CloseHandle.restype = wintypes.BOOL
    class Accounting(ctypes.Structure):
        _fields_ = [(name, c_longlong) for name in
                    ("TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime")]
        _fields_ += [(name, c_uint32) for name in
                     ("TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses")]

    api.QueryInformationJobObject.argtypes = (c_void_p, ctypes.c_int, c_void_p, c_uint32, c_void_p)
    api.QueryInformationJobObject.restype = wintypes.BOOL
    api.TerminateJobObject.argtypes = (c_void_p, c_uint32)
    api.TerminateJobObject.restype = wintypes.BOOL
    return api, Extended, Accounting


def managed_process(entry, args, cell_dir, label, timeout):
    """Run one owned tree; verify Job active count is zero before returning."""
    api, Extended, Accounting = job_api()
    gate = cell_dir / f"{label}.gate"
    stdout = cell_dir / f"{label}.stdout.jsonl"
    stderr = cell_dir / f"{label}.stderr.txt"
    env = os.environ.copy()
    env.update(Q1_JOB_GATE=str(gate), Q1_JOB_ENTRY=str(entry))
    command = [sys.executable, "-u", "-c", GATE_CODE, *map(str, args)]
    job = api.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = Extended()
    limits.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
    if not api.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        error = ctypes.WinError(ctypes.get_last_error())
        api.CloseHandle(job)
        raise error
    proc = None
    timed_out = False
    assigned = False
    try:
        with stdout.open("xb") as out, stderr.open("xb") as err:
            start = time.perf_counter()
            proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=out, stderr=err,
                                    stdin=subprocess.DEVNULL, close_fds=True)
            if not api.AssignProcessToJobObject(job, int(proc._handle)):
                # The child is still held at the gate and cannot spawn workers.
                raise ctypes.WinError(ctypes.get_last_error())
            assigned = True
            gate.write_text("assigned\n", encoding="utf-8")
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
    finally:
        supervision_error = None
        try:
            if assigned:
                if timed_out and not api.TerminateJobObject(job, 1):
                    supervision_error = "TerminateJobObject failed"
                end = time.monotonic() + 10
                while True:
                    accounting = Accounting()
                    if not api.QueryInformationJobObject(job, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
                        supervision_error = "Job active-process query failed"
                        break
                    if accounting.ActiveProcesses == 0:
                        break
                    if time.monotonic() >= end:
                        api.TerminateJobObject(job, 1)
                        supervision_error = f"Job still has {accounting.ActiveProcesses} active processes"
                        break
                    time.sleep(.05)
            elif proc is not None:
                # Assignment failed: this gated process is not owned by the Job.
                proc.kill()
            if proc is not None:
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    supervision_error = "parent did not exit after cleanup"
        finally:
            api.CloseHandle(job)
        if supervision_error:
            raise RuntimeError(f"{label} supervision failure: {supervision_error}")
    return dict(command=command, pid=proc.pid, returncode=proc.returncode,
                timeout=timed_out, wall_seconds=time.perf_counter() - start,
                stdout=str(stdout.relative_to(cell_dir)), stderr=str(stderr.relative_to(cell_dir)))
