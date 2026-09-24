"""Explicit, reviewed-artifact loader for the experimental P1 replay ABI.

Importing this module never loads a library, NumPy, or the replay bridge. There
is no compiler, PATH/env search, or automatic artifact discovery. The caller
must supply a reviewed manifest; its provenance is an attestation, not a proof
that arbitrary machine code implements the declared source or ABI.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import platform
import sys

ABI = "huaweicup-p1-replay-v0.1-cdecl-64le"
KERNEL_SHA256 = "77b814a1fbf58bad0d07a630eab0ce5b4e5f357a74ab6dccc94f8ad6c7bb6ad6"
SOURCE_COMMIT = "03f02e79de4b4bd6f55241385664b154f4332454"
_REQUIRED_FLAGS = frozenset(("-std=c++17", "-O3", "-fno-fast-math", "-ffp-contract=off"))
_ALLOWED_FLAGS = _REQUIRED_FLAGS | frozenset((
    "-fPIC", "-shared", "-dynamiclib", "-Wall", "-Wextra",
    "-Wl,--export-all-symbols",
))


class BackendUnavailable(RuntimeError):
    """A missing/unsupported backend may use the existing complete E1 path."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


class BackendManifestError(ValueError):
    """An invalid identity/ABI declaration is an error, never native success."""


@dataclass(frozen=True)
class BackendSpec:
    binary: Path
    binary_sha256: str
    manifest_sha256: str


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require(condition, message):
    if not condition:
        raise BackendManifestError(message)


def discover_backend(manifest_path):
    """Check one explicit manifest/artifact without loading native code.

    Missing files and a different host target are unavailable. Malformed or
    changed artifacts, unknown ABI and unsafe/unreviewed build recipes fail
    closed. No manifest is inferred from a neighboring .so/.dll file.
    """
    path = Path(manifest_path).resolve()
    try:
        raw = path.read_bytes()
    except FileNotFoundError as error:
        raise BackendUnavailable("manifest-missing") from error
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise BackendManifestError("invalid manifest JSON") from error
    _require(type(value) is dict, "manifest must be an object")
    _require(set(value) == {"version", "abi", "source_commit", "kernel_sha256",
                           "target", "build", "binary", "binary_sha256"},
             "unexpected manifest fields")
    _require(type(value["version"]) is int and value["version"] == 1, "unknown manifest version")
    _require(value["abi"] == ABI, "unknown replay ABI")
    _require(value["source_commit"] == SOURCE_COMMIT and value["kernel_sha256"] == KERNEL_SHA256,
             "unreviewed kernel source identity")
    target = value["target"]
    _require(type(target) is dict and set(target) == {"platform", "machine", "pointer_bits", "byteorder"},
             "invalid target declaration")
    _require(type(target["pointer_bits"]) is int and target["pointer_bits"] == 64
             and target["byteorder"] == "little", "only the 64-bit little-endian ABI is declared")
    host = dict(platform=sys.platform, machine=platform.machine().lower(),
                pointer_bits=ctypes.sizeof(ctypes.c_void_p) * 8, byteorder=sys.byteorder)
    if target != host:
        raise BackendUnavailable("target-mismatch")
    suffixes = {"win32": (".dll",), "darwin": (".dylib", ".so"), "linux": (".so",)}
    if sys.platform not in suffixes:
        raise BackendUnavailable("platform-unsupported")
    build = value["build"]
    _require(type(build) is dict and set(build) == {"compiler", "compiler_version", "flags"},
             "invalid build declaration")
    _require(build["compiler"] in ("clang", "gcc") and type(build["compiler_version"]) is str
             and bool(build["compiler_version"].strip()), "unreviewed compiler recipe")
    flags = build["flags"]
    _require(type(flags) is list and all(type(flag) is str for flag in flags), "invalid build flags")
    _require(_REQUIRED_FLAGS <= set(flags) <= _ALLOWED_FLAGS, "unsafe or undeclared build flags")
    name = value["binary"]
    _require(type(name) is str and name not in ("", ".", "..")
             and not any(char in name for char in ("/", "\\", ":")),
             "artifact must be a filename next to the manifest")
    _require(Path(name).suffix.lower() in suffixes[sys.platform], "wrong artifact suffix for target")
    binary = (path.parent / name).resolve()
    _require(binary.parent == path.parent, "artifact must stay in its reviewed directory")
    expected = value["binary_sha256"]
    _require(type(expected) is str and len(expected) == 64
             and all(char in "0123456789abcdef" for char in expected), "invalid artifact SHA-256")
    try:
        actual = _digest(binary)
    except FileNotFoundError as error:
        raise BackendUnavailable("artifact-missing") from error
    _require(actual == expected, "artifact SHA-256 mismatch")
    return BackendSpec(binary, expected, hashlib.sha256(raw).hexdigest())


@dataclass(frozen=True)
class LoadedBackend:
    spec: BackendSpec
    bridge: object
    library: object


def load_backend(manifest_path):
    """Explicitly load a separately reviewed artifact; never compile one.

    Files and dependencies must remain under the caller's trusted control. A
    SHA and symbol check do not attest a binary's behavior or dependent DLLs.
    This first increment has no native ABI query function or build driver.
    """
    spec = discover_backend(manifest_path)
    try:
        from . import _native_replay as bridge
    except ModuleNotFoundError as error:
        if error.name != "numpy":
            raise
        raise BackendUnavailable("numpy-missing") from error
    expected_input = (0, 4, 8, *range(16, 144, 8), 144, 152, 160, 168)
    expected_output = tuple(range(0, 56, 8))
    _require(ctypes.sizeof(bridge.Input) == 176 and ctypes.sizeof(bridge.Output) == 56
             and tuple(getattr(bridge.Input, name).offset for name, _ in bridge.Input._fields_) == expected_input
             and tuple(getattr(bridge.Output, name).offset for name, _ in bridge.Output._fields_) == expected_output,
             "ctypes layout differs from the reviewed ABI")
    # Recheck after bridge import, before CDLL can execute native constructors.
    try:
        actual = _digest(spec.binary)
    except FileNotFoundError as error:
        raise BackendUnavailable("artifact-missing") from error
    _require(actual == spec.binary_sha256, "artifact changed before loading")
    try:
        library = ctypes.CDLL(str(spec.binary))  # replay is cdecl, including on Windows.
    except OSError as error:
        raise BackendUnavailable("library-load-failed") from error
    try:
        function = library.replay
    except AttributeError as error:
        raise BackendManifestError("artifact does not export the declared replay symbol") from error
    function.argtypes = [ctypes.POINTER(bridge.Input), ctypes.POINTER(bridge.Output)]
    function.restype = ctypes.c_int
    return LoadedBackend(spec, bridge, library)
