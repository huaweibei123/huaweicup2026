"""One hash-verified official evaluation in a dedicated subprocess.

result.json.gz serializes the complete official function return, without CLI
input_graph/input_plan decoration or Trace formatting. It is not CLI output.
No retries, fallback, plan generation, native backend or worker pool is used.
The controller owns process deadlines and charges calls whose outcome is lost.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib
import json
from pathlib import Path, PurePosixPath
import platform
import re
import sys
import time
import traceback


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_record(path, record, label):
    raw = path.read_bytes()
    if len(raw) != record["bytes"] or sha_bytes(raw) != record["sha256"]:
        raise ValueError(f"frozen byte identity mismatch: {label}")
    return raw


def verify_sources(args, summary):
    manifest_raw = args.manifest.read_bytes()
    manifest = json.loads(manifest_raw)
    records = {entry["path"]: entry for entry in manifest["files"]}
    if len(records) != len(manifest["files"]):
        raise ValueError("duplicate manifest paths")
    code_records = {key: value for key, value in records.items() if key.startswith("code/")}
    if not code_records:
        raise ValueError("manifest has no official code")
    code_root = args.official_root.resolve() / "code"
    expected_python = set()
    verified = {}
    for name, record in sorted(code_records.items()):
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe manifest code path")
        target = (args.official_root / Path(*relative.parts)).resolve()
        if not target.is_relative_to(code_root):
            raise ValueError("manifest code path escapes official code")
        verify_record(target, record, name)
        verified[name] = record["sha256"]
        if target.suffix == ".py":
            expected_python.add(target)
    if set(code_root.rglob("*.py")) != expected_python:
        raise ValueError("official Python source inventory differs from manifest")
    combined = sha_bytes("".join(f"{key}\t{value}\n" for key, value in sorted(verified.items())).encode())
    if combined != manifest["official_code_hash"]:
        raise ValueError("official aggregate source hash mismatch")
    config_raw = verify_record(args.config, records["data/config.txt"], "config")
    summary.update(manifest_sha256=sha_bytes(manifest_raw), official_code_hash=combined,
                   config_sha256=sha_bytes(config_raw), verified_code_files=len(verified))
    graph_raw = args.graph.read_bytes()
    summary["graph_sha256"] = sha_bytes(graph_raw)
    graph_record = records.get("data/" + args.graph.name)
    summary["graph_manifest_verified"] = graph_record is not None
    if graph_record is not None:
        if len(graph_raw) != graph_record["bytes"] or summary["graph_sha256"] != graph_record["sha256"]:
            raise ValueError("frozen byte identity mismatch: graph")
    plan = None
    if args.plan is not None:
        plan_raw = args.plan.read_bytes()
        summary["plan_sha256"] = sha_bytes(plan_raw)
        plan = json.loads(plan_raw)
    # This runner requires a fresh process; do not reuse mutable evaluator modules.
    for source in expected_python:
        if source.stem in sys.modules:
            raise RuntimeError("official module already loaded before source verification")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(code_root))
    return json.loads(graph_raw), plan


def select_evaluator(mode, config):
    validation = importlib.import_module("evaluation_validation")
    settings = validation.read_evaluation_config(str(config))
    if mode in ("single", "P1"):
        module = importlib.import_module("multicore_cut_evaluate_problem_1")
        scene = module.read_scene_a_config(str(config))
        settings.update(cross_core_wait=scene["task_cross_core_wait_cycles"],
                        same_core_wait=scene["task_same_core_wait_cycles"])
        function = (importlib.import_module("singlecore_evaluate").evaluate_singlecore
                    if mode == "single" else module.evaluate_scene_a)
    else:
        module = importlib.import_module(
            "multicore_cut_evaluate_problem_2" if mode == "P2"
            else "multicore_cut_evaluate_problem_3")
        scene = module.read_scene_b_config(str(config))
        settings["cross_core_copy_delay"] = scene["cross_core_copy_delay_cycles"]
        if mode == "P3":
            settings.update(module.read_cache_config(str(config)))
        function = module.evaluate_scene_b if mode == "P2" else module.evaluate_problem_3
    return function, settings


def save_result(result, path):
    """Stream complete JSON, then verify the persisted gzip by decompression."""
    digest = hashlib.sha256()
    encoder = json.JSONEncoder(ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    with path.open("xb") as raw_file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_file, mtime=0) as compressed:
            parts, characters = [], 0
            for text in encoder.iterencode(result):
                parts.append(text)
                characters += len(text)
                if characters < 262144:
                    continue
                chunk = "".join(parts).encode("utf-8")
                digest.update(chunk)
                compressed.write(chunk)
                parts, characters = [], 0
            if parts:
                chunk = "".join(parts).encode("utf-8")
                digest.update(chunk)
                compressed.write(chunk)
    observed = hashlib.sha256()
    with gzip.open(path, "rb") as decoded:
        for chunk in iter(lambda: decoded.read(1024 * 1024), b""):
            observed.update(chunk)
    if observed.digest() != digest.digest():
        raise IOError("persisted gzip did not reproduce complete JSON bytes")
    return digest.hexdigest(), sha_file(path)


def public_error(error, args):
    text = str(error)
    for role in ("official_root", "graph", "config", "manifest", "plan", "output_dir"):
        value = getattr(args, role)
        if value is not None:
            for spelling in (str(value.resolve()), str(value)):
                text = text.replace(spelling, f"<{role}>")
    text = re.sub(r"[A-Za-z]:[\\/][^\r\n\"']+", "<local-path>", text)
    text = re.sub(r"(?<!\w)/(?:[^\s\"':;,]+/)*[^\s\"':;,]+", "<local-path>", text)
    return text[:1000]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("single", "P1", "P2", "P3"), required=True)
    for name in ("graph", "config", "official-root", "manifest", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--plan", type=Path)
    args = parser.parse_args(argv)
    if args.mode != "single" and args.plan is None:
        parser.error("--plan is required for P1/P2/P3")
    if args.mode == "single" and args.plan is not None:
        parser.error("single mode builds the official baseline; omit --plan")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    summary = dict(mode=args.mode, status="error", graph=args.graph.name,
                   config=args.config.name, plan=args.plan.name if args.plan else None,
                   python_version=platform.python_version(), official_calls=0,
                   eval_seconds=None, graph_sha256=None, config_sha256=None,
                   plan_sha256=None, result_sha256=None, result_gzip_sha256=None,
                   makespan_cycles=None, data_movement_bytes=None,
                   cache_hit_rate=None, cache_stats=None,
                   result_format="complete official function return; compact JSON in gzip, not CLI formatting")
    phase = "identity_check"
    try:
        graph, plan = verify_sources(args, summary)
        phase = "official_import_and_config"
        function, settings = select_evaluator(args.mode, args.config)
        phase = "official_evaluation"
        summary["official_calls"] = 1
        eval_start = time.perf_counter()
        try:
            result = (function(graph, **settings) if args.mode == "single"
                      else function(graph, plan, **settings))
        finally:
            summary["eval_seconds"] = time.perf_counter() - eval_start
        phase = "result_publication"
        result_hash, compressed_hash = save_result(result, args.output_dir / "result.json.gz")
        cache = result.get("cache_stats")
        summary.update(status="ok", makespan_cycles=result["makespan"],
                       num_cores=result["num_cores"],
                       data_movement_bytes=result["data_movement_bytes"],
                       cache_stats=cache, cache_hit_rate=cache["hit_rate"] if cache is not None else None,
                       result_sha256=result_hash, result_gzip_sha256=compressed_hash,
                       result_gzip_verified=True, exception_type=None, exception_message=None)
    except Exception as error:
        summary.update(exception_type=type(error).__name__, exception_message=public_error(error, args),
                       failure_phase=phase)
        traceback.print_exc(file=sys.stderr)  # Local diagnostic; never copied into summary.
    summary["runner_seconds"] = time.perf_counter() - start
    summary["timing_note"] = "eval_seconds covers one function call; runner_seconds excludes process startup/import before main"
    with (args.output_dir / "summary.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: summary.get(key) for key in (
        "mode", "status", "graph", "makespan_cycles", "official_calls", "exception_type")}))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
