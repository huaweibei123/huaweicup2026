"""New, unexecuted observation and limit policy around immutable gate primitives."""
import ctypes as ct
from ctypes import wintypes as wt
import time
from common import require
from gate_helper import WinAPI, OwnedHandle, ExtendedLimit, DWORD, HANDLE


class ProcessEntry(ct.Structure):
    _fields_ = [("dwSize", DWORD), ("cntUsage", DWORD), ("pid", DWORD),
                ("heap", ct.c_size_t), ("module", DWORD), ("threads", DWORD),
                ("parent", DWORD), ("priority", ct.c_long), ("flags", DWORD),
                ("exe", ct.c_wchar * 260)]


class MemoryStatus(ct.Structure):
    _fields_ = [("length", DWORD), ("load", DWORD)] + [
        (n, ct.c_uint64) for n in ("total_phys", "avail_phys", "total_page",
                                  "avail_page", "total_virtual", "avail_virtual",
                                  "avail_extended")]


class ProcessMemory(ct.Structure):
    _fields_ = [("cb", DWORD), ("faults", DWORD)] + [
        (n, ct.c_size_t) for n in ("peak_working_set", "working_set", "peak_paged",
                                  "paged", "peak_nonpaged", "nonpaged", "pagefile",
                                  "peak_pagefile", "private_bytes")]


class API(WinAPI):
    def __init__(self):
        super().__init__()
        signatures = {
            "GetProcessTimes": ([HANDLE, ct.POINTER(wt.FILETIME), ct.POINTER(wt.FILETIME),
                                 ct.POINTER(wt.FILETIME), ct.POINTER(wt.FILETIME)], wt.BOOL),
            "QueryFullProcessImageNameW": ([HANDLE, DWORD, wt.LPWSTR, ct.POINTER(DWORD)], wt.BOOL),
            "CreateToolhelp32Snapshot": ([DWORD, DWORD], HANDLE),
            "Process32FirstW": ([HANDLE, ct.POINTER(ProcessEntry)], wt.BOOL),
            "Process32NextW": ([HANDLE, ct.POINTER(ProcessEntry)], wt.BOOL),
            "CreateEventW": ([ct.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR], HANDLE),
            "OpenEventW": ([DWORD, wt.BOOL, wt.LPCWSTR], HANDLE),
            "SetEvent": ([HANDLE], wt.BOOL),
            "GlobalMemoryStatusEx": ([ct.POINTER(MemoryStatus)], wt.BOOL),
            "QueryPerformanceCounter": ([ct.POINTER(ct.c_int64)], wt.BOOL),
            "QueryPerformanceFrequency": ([ct.POINTER(ct.c_int64)], wt.BOOL),
        }
        for name, (args, restype) in signatures.items():
            f = getattr(self.k, name)
            f.argtypes, f.restype = args, restype
        self.ps = ct.WinDLL("psapi", use_last_error=True)
        self.ps.GetProcessMemoryInfo.argtypes = [HANDLE, ct.POINTER(ProcessMemory), DWORD]
        self.ps.GetProcessMemoryInfo.restype = wt.BOOL

    def qpc(self):
        value = ct.c_int64()
        self.check(self.k.QueryPerformanceCounter(ct.byref(value)))
        return value.value

    def configure(self, job):
        info = ExtendedLimit()
        info.BasicLimitInformation.LimitFlags = 0x2000 | 0x8 | 0x100 | 0x200
        info.BasicLimitInformation.ActiveProcessLimit = 14
        info.ProcessMemoryLimit = 512 * 1024**2
        info.JobMemoryLimit = 2 * 1024**3
        self.check(self.k.SetInformationJobObject(job.value, 9, ct.byref(info), ct.sizeof(info)))
        got = ExtendedLimit()
        self.check(self.k.QueryInformationJobObject(job.value, 9, ct.byref(got), ct.sizeof(got), None))
        require(got.BasicLimitInformation.LimitFlags == info.BasicLimitInformation.LimitFlags
                and got.BasicLimitInformation.ActiveProcessLimit == 14
                and got.ProcessMemoryLimit == info.ProcessMemoryLimit
                and got.JobMemoryLimit == info.JobMemoryLimit, "Job limit readback")

    def memory(self, process):
        info = ProcessMemory()
        info.cb = ct.sizeof(info)
        self.check(self.ps.GetProcessMemoryInfo(process.value, ct.byref(info), ct.sizeof(info)))
        return {"private_bytes": info.private_bytes,
                "peak_working_set_bytes": info.peak_working_set}

    def available(self):
        info = MemoryStatus()
        info.length = ct.sizeof(info)
        self.check(self.k.GlobalMemoryStatusEx(ct.byref(info)))
        return info.avail_phys

    def parents(self, deadline):
        value = self.k.CreateToolhelp32Snapshot(2, 0)
        require(value != ct.c_void_p(-1).value and value, "process snapshot")
        handle = OwnedHandle(self, value, "process_snapshot")
        result = {}
        try:
            row = ProcessEntry()
            row.dwSize = ct.sizeof(row)
            ok = self.k.Process32FirstW(handle.value, ct.byref(row))
            while ok:
                require(time.monotonic() < deadline, "snapshot collection deadline")
                result[int(row.pid)] = int(row.parent)
                ok = self.k.Process32NextW(handle.value, ct.byref(row))
            return result
        finally:
            handle.close()

    def identity(self, pid, handle, parent):
        times = [wt.FILETIME() for _ in range(4)]
        self.check(self.k.GetProcessTimes(handle.value, *(ct.byref(t) for t in times)))
        size = DWORD(32768)
        name = ct.create_unicode_buffer(size.value)
        self.check(self.k.QueryFullProcessImageNameW(handle.value, 0, name, ct.byref(size)))
        return {"pid": pid, "parent_pid": parent, "parent_source": "Toolhelp32",
                "internal_parent_edge_status": "unknown" if parent is None else "reported_not_creation_bound",
                "creation_filetime": (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
                "image": name.value, "observed_qpc": self.qpc(), "handle_inheritable": False}

    def event(self, name, create=False):
        if create:
            ct.set_last_error(0)
            value = self.k.CreateEventW(None, True, False, name)
            error = ct.get_last_error()
            self.check(value)
            handle = OwnedHandle(self, value, "release_event_owner")
            if error == 183:
                handle.close()
                raise RuntimeError("event collision")
        else:
            handle = OwnedHandle(self, self.check(self.k.OpenEventW(0x100000, False, name)),
                                 "release_event_reader")
        self.inherit(handle)
        return handle


class Census:
    def __init__(self, api, job, allowed_images):
        self.api, self.job, self.allowed = api, job, allowed_images
        self.handles, self.rows, self.errors = {}, {}, []
        self.sampled_peak = 0

    def sample(self, seconds=0.1):
        deadline = time.monotonic() + seconds
        listing = self.api.pids(self.job)
        require(len(listing["pids"]) <= 14, "active cap")
        self.sampled_peak = max(self.sampled_peak, len(listing["pids"]))
        parents = self.api.parents(deadline)
        for pid in listing["pids"]:
            require(time.monotonic() < deadline, "PID capture deadline")
            if pid in self.handles and self.api.exited(self.handles[pid]):
                raise RuntimeError("PID reused while old handle retained")
            if pid not in self.handles:
                handle = self.api.observer(pid)
                self.handles[pid] = handle
                row = self.api.identity(pid, handle, parents.get(pid))
                self.rows[pid] = row
                require(row["image"].casefold() in self.allowed, "unidentified process image")
        return listing

    def final(self):
        for pid, handle in self.handles.items():
            row = self.rows.setdefault(pid, {"pid": pid})
            row["signaled"] = self.api.exited(handle)
            row["raw_exit_dword"] = self.api.exit_code(handle)
            row["raw_exit_hex"] = hex(row["raw_exit_dword"])
            try:
                row.update(self.api.memory(handle))
            except OSError as exc:
                row["memory_error"] = repr(exc)
        info = ExtendedLimit()
        self.api.check(self.api.k.QueryInformationJobObject(
            self.job.value, 9, ct.byref(info), ct.sizeof(info), None))
        return {"processes": list(self.rows.values()), "sampled_peak_active_lower_bound": self.sampled_peak,
                "exact_peak_active": None, "hard_active_cap": 14,
                "peak_job_commit_bytes": info.PeakJobMemoryUsed,
                "accounting": self.api.accounting(self.job), "capture_errors": self.errors}
