"""One fixed 014/K1 E2 preparation, compared with the archived 603b snapshot.

No evaluate_record, E0 evaluation, native library load or native replay occurs.
The caller supplies a freshly unpacked, hash-checked capsule and a new output
directory. The coordinator owns the VM watchdog and termination readback.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pickle
import pickletools
import platform
import resource
import signal
import sys
import time
import zipfile


EXPECTED_SOURCE = "5f3c1f536dc9c63aefdbc1762fbd023e8a6aea57"
EXPECTED_OLD_SOURCE = "603b0741e21c449d3db652ebd67c94f2dc014cc9"
EXPECTED_OLD_ARCHIVE = "bdc28f73c3001ec4385143a48a80538f1147067812471a1ddce6d9d4b13148ca"
EXPECTED_OLD_PREPARED = "4c8569591c245a8c14b290368fc694ecacb9690159ba2ef550a8b0a754787af7"
UNSAFE_PICKLE_OPS = {"GLOBAL", "STACK_GLOBAL", "REDUCE", "BUILD", "OBJ", "INST",
                     "NEWOBJ", "NEWOBJ_EX", "EXT1", "EXT2", "EXT4", "PERSID", "BINPERSID"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def save(path: Path, value: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def first_difference(old, new, path="root"):
    if type(old) is not type(new):
        return f"{path}: {type(old).__name__} != {type(new).__name__}"
    if isinstance(old, dict):
        if list(old) != list(new):
            return f"{path}: dict key/order mismatch"
        for key in old:
            found = first_difference(old[key], new[key], f"{path}[{key!r}]")
            if found:
                return found
        return None
    if isinstance(old, (list, tuple)):
        if len(old) != len(new):
            return f"{path}: length {len(old)} != {len(new)}"
        for i, (a, b) in enumerate(zip(old, new)):
            found = first_difference(a, b, f"{path}[{i}]")
            if found:
                return found
        return None
    if old != new:
        return f"{path}: value mismatch ({type(old).__name__})"
    return None


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: q2_rank_prep_differential.py CAPSULE_ROOT NEW_OUTPUT_DIR")
    root = Path(sys.argv[1]).resolve(strict=True)
    output = Path(sys.argv[2]).resolve()
    if output == root or root in output.parents:
        raise ValueError("output must be outside the immutable capsule")
    output.mkdir(parents=True, exist_ok=False)
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 << 20, 64 << 20))
    resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))
    started = time.perf_counter()
    report = {"status": "checking", "source_commit": EXPECTED_SOURCE,
              "old_source_commit": EXPECTED_OLD_SOURCE,
              "limits": {"preparations": 1, "E0": 0, "native": 0, "workers": 1,
                         "internal_seconds": 150, "external_seconds": 180,
                         "address_space_bytes": 4 << 30, "retries": 0},
              "python": sys.version, "platform": platform.platform()}
    save(output / "report.json", report)

    def alarm(_signum, _frame):
        raise TimeoutError("150-second preparation/differential limit")

    signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, 150)
    try:
        manifest_raw = (root / "manifest.json").read_bytes()
        manifest = json.loads(manifest_raw)
        if manifest.get("source_commit") != EXPECTED_SOURCE or manifest.get("old_source_commit") != EXPECTED_OLD_SOURCE:
            raise ValueError("capsule source identity mismatch")
        for relative, expected in manifest["files"].items():
            rel = Path(relative)
            if rel.is_absolute() or ".." in rel.parts or digest((root / rel).read_bytes()) != expected:
                raise ValueError("capsule file drift: " + relative)
        old_archive = (root / "old-results.zip").read_bytes()
        if digest(old_archive) != EXPECTED_OLD_ARCHIVE:
            raise ValueError("old profile archive identity mismatch")
        with zipfile.ZipFile(root / "old-results.zip") as archive:
            old_prepared_raw = archive.read("output/prepared.pickle")
            old_report = json.loads(archive.read("output/report.json"))
        if digest(old_prepared_raw) != EXPECTED_OLD_PREPARED or old_report.get("status") != "completed":
            raise ValueError("old prepared snapshot identity mismatch")
        if any(op.name in UNSAFE_PICKLE_OPS for op, _, _ in pickletools.genops(old_prepared_raw)):
            raise ValueError("old prepared snapshot contains executable pickle opcodes")
        old_prepared = pickle.loads(old_prepared_raw)

        sys.path.insert(0, str(root / "e2-src"))
        from research.a.e2_search._official_b import load_bundle, read_config
        from research.a.e2_search._local_b import install as install_step3
        from research.a.e2_search._rank_b import install as install_rank
        from research.a.e2_search import _native_b

        def forbidden(*_args, **_kwargs):
            raise RuntimeError("E0/native scoring forbidden in preparation differential")

        _native_b.score = _native_b.get_lib = forbidden
        graph = json.loads((root / "graph.json").read_bytes())
        plan = json.loads((root / "plan.json").read_bytes())
        config = read_config(root / "config.txt", problem=2)
        runtime, support = load_bundle(2)
        runtime.evaluate_scene_b = forbidden
        step3_shape = install_step3(support)
        rank_shape = install_rank(runtime)
        report.update(status="preparing", manifest_sha256=digest(manifest_raw),
                      runner_commit=manifest["runner_commit"],
                      graph_sha256=digest((root / "graph.json").read_bytes()),
                      plan_sha256=digest((root / "plan.json").read_bytes()),
                      config_sha256=digest((root / "config.txt").read_bytes()),
                      step3_shape=step3_shape, rank_shape=rank_shape)
        save(output / "report.json", report)

        build_start = time.perf_counter()
        prepared = runtime._build_scene_b_tasks(graph, plan, config["bandwidth"], config["capacity"])
        built = time.perf_counter()
        tasks, cross, traffic, movement, _ = prepared
        runtime.validate_execution(tasks, cross)
        validated = time.perf_counter()
        packed = _native_b.pack(tasks, cross, runtime, config["bandwidth"])
        packed_at = time.perf_counter()
        new_raw = pickle.dumps(prepared, protocol=5)
        if len(new_raw) > 32 << 20:
            raise ValueError("prepared snapshot exceeds 32 MiB artifact cap")
        (output / "prepared.pickle").write_bytes(new_raw)
        different = first_difference(old_prepared, prepared)
        report.update(status="completed" if not different and new_raw == old_prepared_raw else "different",
                      build_seconds=built-build_start, validation_seconds=validated-built,
                      pack_seconds=packed_at-validated,
                      differential_seconds=time.perf_counter()-packed_at,
                      old_prepared_sha256=EXPECTED_OLD_PREPARED,
                      new_prepared_sha256=digest(new_raw),
                      byte_equal=new_raw == old_prepared_raw,
                      field_equal=different is None, first_difference=different,
                      task_operations=sum(len(t["seq"]) for t in tasks.values()),
                      cross_traffic=traffic, movement=movement,
                      packed_ops=len(packed.op_keys))
        for key in ("task_operations", "cross_traffic", "movement", "packed_ops"):
            if report[key] != old_report[key]:
                report["status"] = "different"
                report["first_difference"] = f"summary field {key} differs"
                break
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        report["total_wall_seconds"] = time.perf_counter()-started
        save(output / "report.json", report)
    print(json.dumps({key: report[key] for key in ("status", "byte_equal", "field_equal", "total_wall_seconds")}))
    if report["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
