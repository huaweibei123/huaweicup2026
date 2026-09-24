"""Shared, standard-library-only runtime. Static proposal; not executed yet."""
import ctypes as ct
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
HELPER = HERE.parent / "gate_repair" / "gate_helper.py"
HELPER_SHA256 = "e5af8da2e6cc4288d7066769bb246c68f51da8bc3c2d6da2f4acc45698c88621"
if hashlib.sha256(HELPER.read_bytes()).hexdigest() != HELPER_SHA256:
    raise RuntimeError("frozen gate helper changed")
sys.path.insert(0, str(HELPER.parent))
from gate_helper import WinAPI, ExtendedLimit, close_all, save

SCHEMA = "p2-windows-gated-continuation-v2"
CAPS = {"record": 12, "fixed_e0": 5, "possible_e0": 17, "debug": 0,
        "formal_e0": 0, "wall_seconds": 900, "evaluation_cutoff": 300,
        "preparation_cutoff": 90, "stage_seconds": 120,
        "C_full_stage_seconds": 30, "preflight_stage_seconds": 30,
        "cleanup_seconds": 10, "stage_launch_requests": 8,
        "cli_launch_requests": 5, "adapter_execv_requests": 2,
        "pool_worker_launch_requests_upper": 12,
        "python_launch_requests_upper_including_parent": 28,
        "max_active_processes_per_job": 12,
        "evidence_publication_target_seconds": 600,
        "final_receipt_readback_target_seconds": 750}
STAGES = {"preflight": (0, 0), "C_full": (1, 1), "D_order": (4, 0),
          "D_timeout": (2, 0), "D_rss": (2, 0), "E_search": (3, 0),
          "E_full_valid": (0, 2), "E_full_invalid": (0, 2)}
_API = None


def api():
    global _API
    if _API is None:
        _API = WinAPI()
    return _API


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bundle():
    names = ("gate_runtime.py", "run_gated_continuation.py", "payload.py",
             "launch_once.ps1", "contract.json")
    files = {name: sha((HERE / name).read_bytes()) for name in names}
    files["../gate_repair/gate_helper.py"] = sha(HELPER.read_bytes())
    require(files["../gate_repair/gate_helper.py"] == HELPER_SHA256, "helper changed")
    return {"files": files, "sha256": sha(json.dumps(
        files, sort_keys=True, separators=(",", ":")).encode("ascii"))}


def elapsed(private):
    # This is the OUTER wrapper's immutable T0, before approval preparation/imports.
    state = read(Path(private) / "T0.json")
    utc = (datetime.now(timezone.utc) - datetime.fromisoformat(state["utc"])).total_seconds()
    return max(utc, (api().tick() - state["tick64"]) / 1000)


def stage_seconds(stage):
    if stage == "preflight":
        return CAPS["preflight_stage_seconds"]
    return CAPS["C_full_stage_seconds"] if stage == "C_full" else CAPS["stage_seconds"]


def remaining(private, stage_start, stage):
    limits = read(Path(private) / "gates" / stage / "limits.json")
    return min(CAPS["evaluation_cutoff"] - elapsed(private) - CAPS["cleanup_seconds"],
               stage_seconds(stage) - (time.perf_counter() - stage_start) - CAPS["cleanup_seconds"],
               (limits["work_deadline_tick_ms"] - api().tick()) / 1000)


def wait_for(predicate, deadline, label):
    while api().tick() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.01)
    raise TimeoutError(label)


def configure_payload_job(job):
    # Explicit, separately reviewed integration change: control helper used limit 4.
    # Two Windows worker launcher chains and one CLI chain require more headroom.
    limits = ExtendedLimit()
    limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x8
    limits.BasicLimitInformation.ActiveProcessLimit = CAPS["max_active_processes_per_job"]
    api().check(api().k.SetInformationJobObject(job.value, 9, ct.byref(limits), ct.sizeof(limits)))
    api().events.append({"event": "payload_job_active_limit", "value": 12,
                         "kill_on_close": True, "breakaway": False})
