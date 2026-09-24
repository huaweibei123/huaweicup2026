"""Load the frozen official evaluator without trusting ambient imports."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import threading
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType, ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_ROOT = REPO_ROOT / "data" / "raw" / "a" / "official"
OFFICIAL_CODE_DIR = OFFICIAL_ROOT / "code"
OFFICIAL_CODE_HASH = "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0"
PROBLEM1_SHA256 = "2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f"

_SUPPORT_MODULES = (
    "contest_io",
    "evaluation_validation",
    "schedule_step1",
    "schedule_step2",
    "schedule_step3",
    "stub_multicore_cut_and_schedule",
)
_LOAD_LOCK = threading.RLock()
_MISSING = object()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_official_code_hash() -> str:
    """Recompute the source-manifest hash over every frozen ``code/*`` file."""
    rows = []
    for path in sorted(OFFICIAL_CODE_DIR.iterdir(), key=lambda item: item.name):
        if path.is_file():
            relative = path.relative_to(OFFICIAL_ROOT).as_posix()
            rows.append(f"{relative}\t{_sha256(path)}\n")
    return hashlib.sha256("".join(rows).encode("utf-8")).hexdigest()


def verify_official_code() -> None:
    actual = compute_official_code_hash()
    if actual != OFFICIAL_CODE_HASH:
        raise RuntimeError(
            "frozen official code hash mismatch: "
            f"expected {OFFICIAL_CODE_HASH}, got {actual}"
        )


def _load_file(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load frozen evaluator module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def load_problem1_bundle(
    alias: str,
) -> tuple[ModuleType, Mapping[str, ModuleType]]:
    """Load P1 plus private, byte-verified copies of all local imports.

    Official sources use absolute imports such as ``schedule_step1``. During the
    load those names point to fresh modules from the frozen source directory;
    the caller's module table, including ``alias``, is restored afterwards. A
    preloaded same-name module therefore cannot contaminate either side of a
    differential run, and a private alias cannot leak into later imports.
    """
    if not alias or alias in _SUPPORT_MODULES:
        raise ValueError("problem-1 alias must be a non-empty private module name")

    with _LOAD_LOCK:
        verify_official_code()
        temporary_names = (*_SUPPORT_MODULES, alias)
        saved_modules = {
            name: sys.modules.get(name, _MISSING) for name in temporary_names
        }
        saved_path = list(sys.path)
        loaded: dict[str, ModuleType] = {}
        try:
            sys.path.insert(0, str(OFFICIAL_CODE_DIR))
            for name in _SUPPORT_MODULES:
                sys.modules.pop(name, None)
            for name in _SUPPORT_MODULES:
                loaded[name] = _load_file(name, OFFICIAL_CODE_DIR / f"{name}.py")
            problem1_path = OFFICIAL_CODE_DIR / "multicore_cut_evaluate_problem_1.py"
            if _sha256(problem1_path) != PROBLEM1_SHA256:
                raise RuntimeError("frozen problem-1 evaluator hash mismatch")
            module = _load_file(alias, problem1_path)

            # This official function imports its reader when called. Bind the
            # verified dependency now so a later ambient import cannot win.
            read_required_settings = loaded[
                "evaluation_validation"
            ].read_required_settings

            def read_scene_a_config(config_path):
                return read_required_settings(
                    config_path,
                    "multicore_scene_a",
                    (
                        "task_cross_core_wait_cycles",
                        "task_same_core_wait_cycles",
                    ),
                )

            module.read_scene_a_config = read_scene_a_config
        finally:
            sys.path[:] = saved_path
            for name, previous in saved_modules.items():
                if previous is _MISSING:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = previous

    return module, MappingProxyType(loaded)


def load_problem1(alias: str) -> ModuleType:
    """Load a private P1 evaluator and retain its verified dependencies."""
    module, _ = load_problem1_bundle(alias)
    return module
