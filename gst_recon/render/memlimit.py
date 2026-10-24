"""Per-worker memory cap that fails one case instead of taking down a shared host.

Linux: RLIMIT_DATA (private anonymous memory; RLIMIT_AS breaks rust/openblas thread pools).
Windows: a Job Object with a per-process commit limit, via ctypes (no extra dependency).
macOS and anything else: not enforced.
"""

from __future__ import annotations

import sys

_JOBS: list = []  # keep Job Object handles alive for the life of the process


def _rlimit_cap(max_gb: float) -> str:
    try:
        import resource

        lim = int(max_gb * 2**30)
        resource.setrlimit(resource.RLIMIT_DATA, (lim, lim))
    except (ImportError, ValueError, OSError):
        return "unsupported"
    return "rlimit_data"


def _job_object_cap(max_gb: float) -> str:
    import ctypes
    from ctypes import wintypes

    class _Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class _Io(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in ("ro", "wo", "oo", "rb", "wb", "ob")]

    class _Extended(ctypes.Structure):
        _fields_ = [("Basic", _Basic), ("Io", _Io), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    # without argtypes ctypes passes 64-bit handles as C int and raises OverflowError
    k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = k32.CreateJobObjectW(None, None)
    if not job:
        return "unsupported"
    info = _Extended()
    info.Basic.LimitFlags = 0x100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY
    info.ProcessMemoryLimit = int(max_gb * 2**30)
    ok = k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)) and \
        k32.AssignProcessToJobObject(job, k32.GetCurrentProcess())
    if not ok:
        return "unsupported"
    _JOBS.append(job)
    return "job_object"


def apply_memory_cap(max_gb: float, platform: str | None = None) -> str:
    """Cap this process; returns the mechanism used ('off', 'rlimit_data', 'job_object', 'unsupported')."""
    if max_gb <= 0:
        return "off"
    plat = platform or sys.platform
    if plat.startswith("win"):
        return _job_object_cap(max_gb)
    if plat == "darwin":
        return "unsupported"  # RLIMIT_DATA is not enforced on macOS
    return _rlimit_cap(max_gb)
