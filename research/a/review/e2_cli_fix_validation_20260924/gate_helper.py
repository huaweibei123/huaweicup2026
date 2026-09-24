"""Standalone Windows gate primitives. Import alone starts nothing.

STATIC REVIEW ONLY: execution requires a separate approval of the fixed code.
Only Kernel32 is explicitly loaded, and only when WinAPI is constructed.
"""

import ctypes as ct
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import subprocess
import tempfile
import time


DWORD = ct.c_uint32
WORD = ct.c_uint16
BOOL = ct.c_int32
HANDLE = ct.c_void_p
SIZE_T = ct.c_size_t
ULONG_PTR = ct.c_size_t
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
ERROR_ALREADY_EXISTS = 183
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_MORE_DATA = 234
JOB_OBJECT_QUERY = 4
JOB_OBJECT_TERMINATE = 8
CREATE_SUSPENDED = 4
CREATE_NO_WINDOW = 0x08000000
CREATE_UNICODE_ENVIRONMENT = 0x400
EXTENDED_STARTUPINFO_PRESENT = 0x80000
PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
FORCED_CLEANUP_EXIT = 0xE0000001


class BasicLimit(ct.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ct.c_int64),
                ("PerJobUserTimeLimit", ct.c_int64), ("LimitFlags", DWORD),
                ("MinimumWorkingSetSize", SIZE_T), ("MaximumWorkingSetSize", SIZE_T),
                ("ActiveProcessLimit", DWORD), ("Affinity", ULONG_PTR),
                ("PriorityClass", DWORD), ("SchedulingClass", DWORD)]


class IOCounters(ct.Structure):
    _fields_ = [(name, ct.c_uint64) for name in
                ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                 "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class ExtendedLimit(ct.Structure):
    _fields_ = [("BasicLimitInformation", BasicLimit), ("IoInfo", IOCounters),
                ("ProcessMemoryLimit", SIZE_T), ("JobMemoryLimit", SIZE_T),
                ("PeakProcessMemoryUsed", SIZE_T), ("PeakJobMemoryUsed", SIZE_T)]


class Accounting(ct.Structure):
    _fields_ = [("TotalUserTime", ct.c_int64), ("TotalKernelTime", ct.c_int64),
                ("ThisPeriodTotalUserTime", ct.c_int64),
                ("ThisPeriodTotalKernelTime", ct.c_int64),
                ("TotalPageFaultCount", DWORD), ("TotalProcesses", DWORD),
                ("ActiveProcesses", DWORD), ("TotalTerminatedProcesses", DWORD)]


class StartupInfo(ct.Structure):
    _fields_ = [("cb", DWORD), ("lpReserved", ct.c_wchar_p),
                ("lpDesktop", ct.c_wchar_p), ("lpTitle", ct.c_wchar_p),
                ("dwX", DWORD), ("dwY", DWORD), ("dwXSize", DWORD),
                ("dwYSize", DWORD), ("dwXCountChars", DWORD),
                ("dwYCountChars", DWORD), ("dwFillAttribute", DWORD),
                ("dwFlags", DWORD), ("wShowWindow", WORD), ("cbReserved2", WORD),
                ("lpReserved2", ct.c_void_p), ("hStdInput", HANDLE),
                ("hStdOutput", HANDLE), ("hStdError", HANDLE)]


class StartupInfoEx(ct.Structure):
    _fields_ = [("StartupInfo", StartupInfo), ("lpAttributeList", ct.c_void_p)]


class ProcessInfo(ct.Structure):
    _fields_ = [("hProcess", HANDLE), ("hThread", HANDLE),
                ("dwProcessId", DWORD), ("dwThreadId", DWORD)]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_identity(directory):
    names = ("gate_helper.py", "control_runner.py", "contract.json")
    files = {name: sha256(Path(directory) / name) for name in names}
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("ascii")
    return {"files": files, "sha256": hashlib.sha256(encoded).hexdigest()}


def save(path, value, exclusive=False):
    """Atomic JSON; initial gate/ready/ACK cannot replace an earlier file on Windows."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=True, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.rename(temporary, path)  # Windows refuses an existing destination.
        else:
            os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class OwnedHandle:
    def __init__(self, api, value, kind):
        if not value:
            raise ValueError("null owned handle: " + kind)
        self.api, self.value, self.kind = api, value, kind
        self.closed = False

    def close(self):
        if self.closed:
            return
        ok = bool(self.api.k.CloseHandle(self.value))
        error = ct.get_last_error() if not ok else 0
        self.api.events.append({"event": "close_handle", "kind": self.kind,
                                "success": ok, "error": error})
        if not ok:
            raise ct.WinError(error)
        self.closed = True


def close_all(handles):
    """Attempt every close, retaining failure instead of masking later releases."""
    failures = []
    for handle in reversed(handles):
        try:
            handle.close()
        except Exception as exc:
            failures.append(repr(exc))
    if failures:
        raise RuntimeError("handle close failures: " + repr(failures))


class WinAPI:
    def __init__(self):
        if os.name != "nt":
            raise RuntimeError("Windows only")
        self.events = []
        self.k = ct.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "GetCurrentProcess": ([], HANDLE),
            "GetTickCount64": ([], ct.c_uint64),
            "CloseHandle": ([HANDLE], BOOL),
            "GetHandleInformation": ([HANDLE, ct.POINTER(DWORD)], BOOL),
            "CreateJobObjectW": ([ct.c_void_p, ct.c_wchar_p], HANDLE),
            "OpenJobObjectW": ([DWORD, BOOL, ct.c_wchar_p], HANDLE),
            "SetInformationJobObject": ([HANDLE, ct.c_int, ct.c_void_p, DWORD], BOOL),
            "QueryInformationJobObject": ([HANDLE, ct.c_int, ct.c_void_p, DWORD,
                                            ct.POINTER(DWORD)], BOOL),
            "IsProcessInJob": ([HANDLE, HANDLE, ct.POINTER(BOOL)], BOOL),
            "AssignProcessToJobObject": ([HANDLE, HANDLE], BOOL),
            "TerminateJobObject": ([HANDLE, DWORD], BOOL),
            "TerminateProcess": ([HANDLE, DWORD], BOOL),
            "OpenProcess": ([DWORD, BOOL, DWORD], HANDLE),
            "WaitForSingleObject": ([HANDLE, DWORD], DWORD),
            "GetExitCodeProcess": ([HANDLE, ct.POINTER(DWORD)], BOOL),
            "ResumeThread": ([HANDLE], DWORD),
            "DuplicateHandle": ([HANDLE, HANDLE, HANDLE, ct.POINTER(HANDLE),
                                  DWORD, BOOL, DWORD], BOOL),
            "InitializeProcThreadAttributeList": ([ct.c_void_p, DWORD, DWORD,
                                                    ct.POINTER(SIZE_T)], BOOL),
            "UpdateProcThreadAttribute": ([ct.c_void_p, DWORD, ULONG_PTR,
                                           ct.c_void_p, SIZE_T, ct.c_void_p,
                                           ct.c_void_p], BOOL),
            "DeleteProcThreadAttributeList": ([ct.c_void_p], None),
            "CreateProcessW": ([ct.c_wchar_p, ct.c_void_p, ct.c_void_p, ct.c_void_p,
                                 BOOL, DWORD, ct.c_void_p, ct.c_wchar_p,
                                 ct.POINTER(StartupInfoEx), ct.POINTER(ProcessInfo)], BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.k, name)
            function.argtypes, function.restype = arguments, result

    @staticmethod
    def check(result):
        if not result:
            raise ct.WinError(ct.get_last_error())
        return result

    def tick(self):
        return int(self.k.GetTickCount64())

    def inherit(self, handle, expected=False):
        flags = DWORD()
        self.check(self.k.GetHandleInformation(handle.value, ct.byref(flags)))
        actual = bool(flags.value & 1)
        self.events.append({"event": "inheritance", "kind": handle.kind,
                            "inheritable": actual, "expected": expected})
        if actual != expected:
            raise RuntimeError("unexpected handle inheritance: " + handle.kind)

    def job(self, name):
        ct.set_last_error(0)
        value = self.k.CreateJobObjectW(None, name)
        error = ct.get_last_error()
        self.check(value)
        handle = OwnedHandle(self, value, "job")
        if error == ERROR_ALREADY_EXISTS:
            handle.close()  # No limits, termination or other mutation of existing Job.
            raise RuntimeError("job_name_collision")
        try:
            self.inherit(handle)
            limits = ExtendedLimit()
            limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x8
            limits.BasicLimitInformation.ActiveProcessLimit = 4
            self.check(self.k.SetInformationJobObject(value, 9, ct.byref(limits),
                                                      ct.sizeof(limits)))
            return handle
        except BaseException:
            handle.close()
            raise

    def exact_membership(self, name):
        query = OwnedHandle(self, self.check(self.k.OpenJobObjectW(
            JOB_OBJECT_QUERY, False, name)), "child_job_query")
        result = BOOL()
        record = {"api_success": False, "member": False, "query_closed": False}
        try:
            self.inherit(query)
            success = bool(self.k.IsProcessInJob(self.k.GetCurrentProcess(),
                                                query.value, ct.byref(result)))
            record.update(api_success=success, member=bool(result.value))
            self.check(success)
        finally:
            query.close()
            record["query_closed"] = query.closed
        return record

    def pids(self, job):
        for capacity in (8, 16, 32, 64):
            class PIDList(ct.Structure):
                _fields_ = [("assigned", DWORD), ("listed", DWORD),
                            ("ids", ULONG_PTR * capacity)]
            listing = PIDList()
            returned = DWORD()
            success = bool(self.k.QueryInformationJobObject(
                job.value, 3, ct.byref(listing), ct.sizeof(listing), ct.byref(returned)))
            error = ct.get_last_error() if not success else 0
            if not success and error != ERROR_MORE_DATA:
                raise ct.WinError(error)
            if success and listing.assigned == listing.listed <= capacity:
                ids = [int(listing.ids[i]) for i in range(listing.listed)]
                if len(set(ids)) != len(ids) or any(pid <= 0 for pid in ids):
                    raise RuntimeError("invalid complete PID list")
                return {"assigned": listing.assigned, "listed": listing.listed,
                        "pids": ids, "capacity": capacity, "complete": True}
        raise RuntimeError("complete PID list unavailable")

    def accounting(self, job):
        record = Accounting()
        self.check(self.k.QueryInformationJobObject(
            job.value, 1, ct.byref(record), ct.sizeof(record), None))
        return {name: int(getattr(record, name)) for name in
                ("TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses")}

    def observer(self, pid):
        handle = OwnedHandle(self, self.check(self.k.OpenProcess(
            0x00100000 | 0x1000, False, pid)), "process_observer")
        try:
            self.inherit(handle)
            return handle
        except BaseException:
            handle.close()
            raise

    def exited(self, process):
        result = self.k.WaitForSingleObject(process.value, 0)
        if result not in (WAIT_OBJECT_0, WAIT_TIMEOUT):
            raise ct.WinError(ct.get_last_error())
        return result == WAIT_OBJECT_0

    def exit_code(self, process):
        code = DWORD()
        self.check(self.k.GetExitCodeProcess(process.value, ct.byref(code)))
        return code.value

    def terminate_job(self, job):
        self.check(self.k.TerminateJobObject(job.value, FORCED_CLEANUP_EXIT))
        self.events.append({"event": "terminate_job", "kind": job.kind})

    def reopen_for_cleanup(self, name):
        value = self.k.OpenJobObjectW(JOB_OBJECT_QUERY | JOB_OBJECT_TERMINATE, False, name)
        if not value:
            error = ct.get_last_error()
            if error == 2:  # The last close may already have deleted the Job.
                return None
            raise ct.WinError(error)
        handle = OwnedHandle(self, value, "cleanup_job_query_terminate")
        try:
            self.inherit(handle)
            return handle
        except BaseException:
            handle.close()
            raise

    def launch_assigned(self, executable, arguments, environment, directory, job,
                        receipt, cleanup_deadline, launch_deadline_ns):
        """The sole controlled creation site; suspended -> assigned -> one resume.

        STARTUPINFOEX HANDLE_LIST contains only three duplicate stdio handles.
        Original file handles, Job, process and thread handles are not inherited.
        The caller has already durably reserved this case's one launch request.
        """
        files, duplicates, owned = [], [], []
        attribute_list = None
        process = thread = None
        assigned = False
        try:
            files.append(open(os.devnull, "rb"))
            files.append(open(Path(directory) / "stdout.raw", "xb"))
            files.append(open(Path(directory) / "stderr.raw", "xb"))
            current = self.k.GetCurrentProcess()  # Pseudo handle, never closed/inherited.
            for stream in files:
                original = msvcrt.get_osfhandle(stream.fileno())
                if os.get_inheritable(stream.fileno()):
                    raise RuntimeError("original stdio descriptor is inheritable")
                duplicate = HANDLE()
                self.check(self.k.DuplicateHandle(current, original, current,
                                                  ct.byref(duplicate), 0, True, 2))
                handle = OwnedHandle(self, duplicate.value, "stdio_duplicate")
                duplicates.append(handle)
                self.inherit(handle, expected=True)
            size = SIZE_T()
            ct.set_last_error(0)
            first = self.k.InitializeProcThreadAttributeList(None, 1, 0, ct.byref(size))
            if first or ct.get_last_error() != ERROR_INSUFFICIENT_BUFFER or not size.value:
                raise RuntimeError("attribute-list sizing failed")
            storage = ct.create_string_buffer(size.value)
            self.check(self.k.InitializeProcThreadAttributeList(storage, 1, 0, ct.byref(size)))
            attribute_list = storage
            whitelist = (HANDLE * 3)(*(h.value for h in duplicates))
            self.check(self.k.UpdateProcThreadAttribute(
                attribute_list, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                ct.cast(whitelist, ct.c_void_p), ct.sizeof(whitelist), None, None))
            startup = StartupInfoEx()
            startup.StartupInfo.cb = ct.sizeof(startup)
            startup.StartupInfo.dwFlags = 0x100  # STARTF_USESTDHANDLES
            startup.StartupInfo.hStdInput = duplicates[0].value
            startup.StartupInfo.hStdOutput = duplicates[1].value
            startup.StartupInfo.hStdError = duplicates[2].value
            startup.lpAttributeList = ct.cast(attribute_list, ct.c_void_p)
            command = ct.create_unicode_buffer(subprocess.list2cmdline(
                [str(executable), *map(str, arguments)]))
            environment_block = ct.create_unicode_buffer("\0".join(
                f"{key}={value}" for key, value in sorted(environment.items(),
                                                        key=lambda item: item[0].upper())) + "\0\0")
            info = ProcessInfo()
            flags = (CREATE_SUSPENDED | CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT |
                     EXTENDED_STARTUPINFO_PRESENT)
            if (self.tick() >= cleanup_deadline - 5000 or
                    time.monotonic_ns() >= launch_deadline_ns):
                raise TimeoutError("no launch after case work/global launch deadline")
            receipt.update(create_process_attempted=True, flags=flags,
                           inherited_handle_kinds=["stdin", "stdout", "stderr"])
            self.check(self.k.CreateProcessW(str(executable), command, None, None, True,
                                             flags, environment_block, str(directory),
                                             ct.byref(startup), ct.byref(info)))
            process = OwnedHandle(self, info.hProcess, "launcher_process")
            thread = OwnedHandle(self, info.hThread, "launcher_primary_thread")
            owned.extend([process, thread])
            receipt.update(created=True, launcher_pid=info.dwProcessId,
                           primary_thread_id=info.dwThreadId)
            self.inherit(process)
            self.inherit(thread)
            self.check(self.k.AssignProcessToJobObject(job.value, process.value))
            assigned = True
            receipt["assigned_before_resume"] = True
            previous_count = self.k.ResumeThread(thread.value)
            receipt["resume_previous_count"] = previous_count
            if previous_count != 1:
                raise RuntimeError("ResumeThread must return exactly 1")
            thread.close()
            # Release the attribute list while whitelist/storage still exist.
            self.k.DeleteProcThreadAttributeList(attribute_list)
            attribute_list = None
            close_all(duplicates)
            for stream in files:
                stream.close()
            return process
        except BaseException:
            if process is not None:
                try:
                    if assigned:
                        self.terminate_job(job)
                    else:
                        self.check(self.k.TerminateProcess(process.value, FORCED_CLEANUP_EXIT))
                    remaining = max(0, cleanup_deadline - self.tick())
                    receipt["failed_launch_wait"] = int(self.k.WaitForSingleObject(
                        process.value, min(5000, remaining)))
                    receipt["failed_launch_exited"] = self.exited(process)
                    receipt["failed_launch_exit_code"] = self.exit_code(process)
                    if not receipt["failed_launch_exited"]:
                        raise RuntimeError("failed-launch process still active after cleanup")
                except BaseException as exc:
                    receipt["failed_launch_cleanup_error"] = repr(exc)
                    raise
                finally:
                    close_all(owned)
            raise
        finally:
            # Even failure of one release must not skip remaining release attempts.
            if attribute_list is not None:
                self.k.DeleteProcThreadAttributeList(attribute_list)
            try:
                close_all(duplicates)
            finally:
                for stream in files:
                    stream.close()
