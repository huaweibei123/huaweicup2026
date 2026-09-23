"""Peak process resident memory. Telemetry, never a hard memory cap."""
import ctypes as ct
from functools import lru_cache
import sys


class _ProcessMemoryCounters(ct.Structure):
    # DWORD is 32 bits on both Windows ABIs; SIZE_T follows pointer width.
    _fields_ = [('cb',ct.c_uint32),('PageFaultCount',ct.c_uint32)] + [
        (name,ct.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize',
        'QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage',
        'QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]


@lru_cache(maxsize=1)
def _windows_functions():
    kernel = ct.WinDLL('kernel32',use_last_error=True)
    current = kernel.GetCurrentProcess
    current.argtypes, current.restype = [],ct.c_void_p
    query = kernel.K32GetProcessMemoryInfo
    query.argtypes, query.restype = [ct.c_void_p,ct.POINTER(_ProcessMemoryCounters),ct.c_uint32],ct.c_int
    return current,query


def _windows_peak_rss_bytes():
    current, query = _windows_functions()
    counters = _ProcessMemoryCounters()
    counters.cb = ct.sizeof(counters)
    if not query(current(),ct.byref(counters),counters.cb):
        raise OSError('K32GetProcessMemoryInfo failed')
    return int(counters.PeakWorkingSetSize)


def peak_rss_bytes():
    try:
        if sys.platform == 'win32':
            return _windows_peak_rss_bytes()
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value if sys.platform == 'darwin' else value*1024)
    except (ImportError,AttributeError,OSError):
        return None
