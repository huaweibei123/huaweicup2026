"""Private, hash-verified P2/P3 bundles. No changes to the frozen sources."""
from types import MappingProxyType
import sys

from src.eval_exact._official import (
    _LOAD_LOCK, _MISSING, _SUPPORT_MODULES, _load_file,
    OFFICIAL_CODE_DIR, verify_official_code,
)


def load_bundle(problem):
    if type(problem) is not int or problem not in (2, 3):
        raise ValueError("problem must be 2 or 3")
    names = (*_SUPPORT_MODULES, "multicore_cut_evaluate_problem_1",
             f"multicore_cut_evaluate_problem_{problem}")
    with _LOAD_LOCK:
        verify_official_code()
        saved = {name: sys.modules.get(name, _MISSING) for name in names}
        old_path = list(sys.path)
        modules = {}
        try:
            sys.path.insert(0, str(OFFICIAL_CODE_DIR))
            for name in names:
                sys.modules.pop(name, None)
            for name in names:
                modules[name] = _load_file(name, OFFICIAL_CODE_DIR / f"{name}.py")
            runtime = modules[names[-1]]
            # Config functions lazily import; use the bound reader below instead.
            return runtime, MappingProxyType(modules)
        finally:
            sys.path[:] = old_path
            for name, value in saved.items():
                if value is _MISSING:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value


def read_config(path, *, problem=1):
    if type(problem) is not int or problem not in (1, 2, 3):
        raise ValueError("problem must be 1, 2 or 3")
    from src.eval_exact import read_config as read_p1
    if problem == 1:
        return read_p1(path)
    _, support = load_bundle(problem)
    validation = support["evaluation_validation"]
    base = validation.read_evaluation_config(str(path))
    capacity, bandwidth = base["capacity"], base["bandwidth"]
    b = validation.read_required_settings(
        path, "multicore_scene_b", ("cross_core_copy_delay_cycles",))
    result = dict(capacity=capacity, bandwidth=bandwidth,
                  cross_core_copy_delay=b["cross_core_copy_delay_cycles"])
    if problem == 3:
        c = validation.read_required_settings(
            path, "problem_3", ("cache_capacity_bytes", "cache_bandwidth_bytes_per_cycle"))
        result.update(c)
    return result
