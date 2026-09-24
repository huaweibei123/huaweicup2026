"""Copied finite payload semantics from bf9be734 continuation; never run during review.
Only run_stage imports E2/E0, and the new controller calls it after Job/nonce/ACK.
"""
from contextlib import contextmanager
import importlib.metadata
import json
import math
import os
from pathlib import Path
import pickle
import subprocess
import sys
import time
from gate_runtime import ROOT, CAPS, STAGES, elapsed, remaining, require, save, read, sha

PREVIOUS = ROOT / "results/a/review/e2-p2-windows-20260924/evidence"

def typed(value):
    """Lossless built-in type tree, ignoring only dictionary insertion order."""
    kind = type(value)
    if kind is dict:
        items = [[typed(k), typed(v)] for k, v in value.items()]
        items.sort(key=lambda pair: json.dumps(pair[0], sort_keys=True, ensure_ascii=False))
        return {"type": "dict", "items": items}
    if kind in (list, tuple):
        return {"type": kind.__name__, "items": [typed(x) for x in value]}
    if kind is float:
        require(math.isfinite(value), "non-finite float in official result")
        return {"type": "float", "hex": value.hex()}
    if kind in (str, int, bool, type(None)):
        return {"type": kind.__name__, "value": value}
    raise TypeError(f"unsupported type in result: {kind.__name__}")


def canonical(value):
    # JSON's key conversion is intentional in this second, separate contract.
    normalized = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    return json.dumps(normalized, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":"))


def preserve_object(private, name, value):
    """Write the original types BEFORE any comparison; never unpickle files."""
    data = pickle.dumps(value, protocol=5)
    with (private / (name + ".pickle")).open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    save(private / (name + ".typed.json"), typed(value), exclusive=True)
    with (private / (name + ".canonical.json")).open("x", encoding="utf-8", newline="\n") as f:
        f.write(canonical(value) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return {"pickle_sha256": sha(data), "typed_saved": True, "canonical_saved": True}


def frozen_inputs(private):
    # The approved manifest pins the prior evidence bytes, not just filenames.
    manifest = read(Path(__file__).with_name("contract.json"))
    for name, wanted in manifest["prior_files_sha256"].items():
        require(sha((ROOT / name).read_bytes()) == wanted, f"prior file changed: {name}")
    identity = read(PREVIOUS / "IDENTITY.json")
    hashes = {}
    for name, wanted in identity["source_sha256"].items():
        if name.startswith("research/a/review/"):
            continue  # Old driver's CRLF/Git difference is already documented.
        hashes[name] = sha((ROOT / name).read_bytes())
        require(hashes[name] == wanted, f"production/dependency/DLL changed: {name}")
    require(sys.version == identity["python"], "Python runtime identity changed")
    require(importlib.metadata.version("numpy") == "2.5.3", "NumPy version changed")
    save(private / "REUSED_IDENTITY.json", {"source_sha256": hashes, "python": sys.version,
                                           "numpy": "2.5.3", "dll_recompiled": False})
    data = read(PREVIOUS / "inputs.json")
    save(private / "inputs.json", data, exclusive=True)
    bad = next(e["record"] for e in read(PREVIOUS / "B.child.json")["events"]
               if e["label"] == "B-empty" and e["kind"] == "record")
    save(private / "prior-invalid.json", bad, exclusive=True)
    save(private / "prior-truth.json", read(PREVIOUS / "A-R.truth.json"), exclusive=True)


def run_stage(stage, private):
    stage_start = time.perf_counter()
    require(remaining(private, stage_start, stage) > 0, "window expired")
    sys.path.insert(0, str(ROOT))
    from research.a.e2_search import E2BatchEvaluator, read_config, _native_b
    if stage == "preflight":
        lib = _native_b.get_lib()
        require(lib.replay_bc_abi() == 1, "BC ABI mismatch")
        require(Path(lib._name).resolve() == (ROOT / "research/a/e2_search/native/libreplay_bc.dll").resolve(), "wrong loaded DLL")
        save(private / "ABI.json", {"abi": 1, "loaded_path": lib._name, "new_evaluations": 0})
        return 0

    data = read(private / "inputs.json")
    graph, plan, config = data["graph"], data["plans"]["R"], data["config"]
    official_config = read_config(ROOT / "data/raw/a/official/data/config.txt", problem=2)
    official_config.setdefault("max_iter", 1000000)
    require(typed(config) == typed(official_config), "P2 config identity differs")
    truth, bad = read(private / "prior-truth.json"), read(private / "prior-invalid.json")
    receipt = {"stage": stage, "admitted": {"record": 0, "fixed_e0": 0}, "events": [], "pools": []}

    def flush():
        save(private / (stage + ".child.json"), receipt)

    def admit(kind, label, count=1):
        require(remaining(private, stage_start, stage) > 0, "no cleanup-safe evaluation time")
        limit = STAGES[stage][0 if kind == "record" else 1]
        require(receipt["admitted"][kind] + count <= limit, "stage invocation cap")
        require(not any(e["label"] == label for e in receipt["events"]), "no retry/duplicate labels")
        receipt["admitted"][kind] += count
        event = {"kind": kind, "label": label, "count": count, "status": "reserved",
                 "possible_e0_reserved": count, "wall_since_t0": elapsed(private)}
        receipt["events"].append(event)
        flush()
        return event

    @contextmanager
    def pool(**options):
        instance = E2BatchEvaluator(graph, problem=2, workers=options.pop("workers", 1),
            timeout_seconds=options.pop("timeout_seconds", 30), startup_timeout_seconds=15,
            cache_bytes=16 << 20, **options)
        try:
            yield instance
        finally:
            # Runs on assertions, serialization errors and unexpected exceptions.
            close_result = {"closed": False, "slots_empty": False}
            receipt["pools"].append(close_result)
            try:
                instance.close()
                instance.close()
                close_result.update(closed=True, slots_empty=all(x is None for x in instance._slots))
                require(close_result["slots_empty"], "pool slots remained live")
            finally:
                flush()

    def batch(label, instance, plans, *, full=False, expected=None, row_check=None):
        event = admit("record", label, len(plans))
        event["records"] = []
        flush()
        iterator = instance.evaluate_batch(plans, full=full, **config)
        try:
            for i, row in enumerate(iterator):
                event["records"].append(row)
                if row.get("status") == "timeout" or row.get("route") is None:
                    event["unknown_e0_slots"] = event.get("unknown_e0_slots", 0) + 1
                flush()
                if full and "result" in row:
                    receipt["full_artifacts"] = preserve_object(private, "C-pool-full", row["result"])
                    flush()
                require(row["index"] == i, "pool response index mismatch")
                contract = (expected or ["native"] * len(plans))[i]
                if contract == "invalid":
                    invalid(row)
                elif contract == "timeout":
                    require(row["status"] == "timeout" and row["problem"] == 2, "tiny timeout contract failed")
                else:
                    score(row, contract)
                if row_check:
                    row_check(row)
        finally:
            iterator.close()
        event.update(status="returned", returned=len(event["records"]))
        flush()
        require(event["returned"] == len(plans), "missing records; keep reservations")
        return event["records"]

    def score(row, route="native"):
        require(row["problem"] == 2 and row["route"] == route and row["status"] == "ok", "unexpected successful route/status")
        for key in ("makespan", "data_movement_bytes", "cross_task_traffic"):
            require(typed(row[key]) == typed(truth[key]), "score mismatch: " + key)

    def invalid(row):
        for key in ("status", "error_type", "message", "route", "problem"):
            require(typed(row[key]) == typed(bad[key]), "invalid contract mismatch: " + key)

    def cli(label, arguments):
        command = [sys.executable, "-B", *arguments]
        save(private / (label + ".command.json"), command, exclusive=True)
        with (private / (label + ".stdout")).open("xb") as out, (private / (label + ".stderr")).open("xb") as err:
            return subprocess.run(command, cwd=ROOT, stdout=out, stderr=err,
                timeout=min(30, remaining(private, stage_start, stage))).returncode

    exit_code = 1
    try:
        if stage == "C_full":
            from research.a.e2_search._official_b import load_bundle
            oracle, _ = load_bundle(2)
            event = admit("fixed_e0", "C-fresh-official")
            try:
                expected = oracle.evaluate_scene_b(graph, plan, **config)
            except Exception as error:
                event.update(status="exception", error_type=type(error).__name__, message=str(error))
                flush()
                raise
            event["status"] = "returned"
            flush()
            event["artifacts"] = preserve_object(private, "C-oracle", expected)
            flush()
            with pool() as instance:
                row = batch("C-pool-full", instance, [plan], full=True, expected=["e0_full"])[0]
                key_types = {}
                for name, value in (("oracle", expected), ("pool", row["result"])):
                    key_types[name] = {field: [{"key": repr(k), "type": type(k).__name__}
                        for k in value[field]] for field in ("memory_peak_by_core", "step3_by_core")}
                receipt["key_types"] = key_types
                receipt["python_type_value_equal"] = typed(row["result"]) == typed(expected)
                receipt["canonical_json_equal"] = canonical(row["result"]) == canonical(expected)
                receipt["prior_canonical_equal"] = canonical(expected) == canonical(truth)
                flush()
                for value in (expected, row["result"]):
                    for field in ("memory_peak_by_core", "step3_by_core"):
                        require(set(value[field]) == {0, 1} and all(type(k) is int for k in value[field]), "integer core keys not preserved")
                require(receipt["python_type_value_equal"] and receipt["canonical_json_equal"]
                        and receipt["prior_canonical_equal"], "full result contract mismatch")
        elif stage == "D_order":
            with pool(workers=2, max_tasks_per_worker=1) as instance:
                prior_slots = {}
                receipt["slot_recycle_observations"] = []
                def observe_slot(row):
                    slot_index = row["index"] % 2
                    slot = instance._slots[slot_index]
                    require(slot is not None, "response slot unexpectedly empty")
                    process, _, count = slot
                    evidence = {"index": row["index"], "slot": slot_index,
                        "returned_pid": row["worker_pid"], "slot_pid": process.pid,
                        "tasks_after_response": count, "max_tasks": instance._max_tasks,
                        "rss_policy": instance._recycle_rss,
                        "native_recycle_reason": row.get("recycle_reason"),
                        "interpretation": "max_tasks branch from fixed source and slot counter; no native max_tasks reason field"}
                    if slot_index in prior_slots:
                        previous = prior_slots[slot_index]
                        evidence.update(previous_pid=previous["pid"],
                            previous_tasks=previous["tasks"],
                            previous_process_closed=getattr(previous["process"], "_closed", False))
                    receipt["slot_recycle_observations"].append(evidence)
                    flush()
                    require(row["worker_pid"] == process.pid and count == 1
                            and instance._max_tasks == 1 and instance._recycle_rss is None,
                            "per-slot task-count recycle preconditions not observed")
                    require("recycle_reason" not in row and "recycle_after_response" not in row,
                            "unexpected RSS recycle annotation in max_tasks-only test")
                    if slot_index in prior_slots:
                        require(evidence["previous_tasks"] == 1 and evidence["previous_process_closed"]
                                and evidence["previous_pid"] != evidence["slot_pid"],
                                "same-slot replacement not demonstrated; no retry for possible PID reuse")
                    prior_slots[slot_index] = {"pid": process.pid, "tasks": count, "process": process}
                rows = batch("D-ordered-recycle", instance, [plan, {}, plan, plan],
                             expected=["native", "invalid", "native", "native"], row_check=observe_slot)
                require([r["index"] for r in rows] == [0, 1, 2, 3], "index order mismatch")
                for i in (0, 2, 3):
                    score(rows[i])
                invalid(rows[1])
                require(rows[0]["worker_pid"] != rows[2]["worker_pid"]
                        and rows[1]["worker_pid"] != rows[3]["worker_pid"], "both slots must demonstrate replacement")
                require(rows[0]["worker_pid"] != rows[1]["worker_pid"]
                        and rows[2]["worker_pid"] != rows[3]["worker_pid"], "simultaneously active slots share PID")
                receipt["observed_pid_set"] = sorted({r["worker_pid"] for r in rows})
                flush()
        elif stage == "D_timeout":
            with pool(timeout_seconds=1e-12) as instance:
                row = batch("D-expected-timeout", instance, [plan], expected=["timeout"])[0]
                require(row["status"] == "timeout" and row["problem"] == 2, "tiny timeout contract failed")
                instance._timeout = 30
                score(batch("D-post-timeout-recovery", instance, [plan])[0])
        elif stage == "D_rss":
            def rss_check(row):
                require(row["worker_peak_rss_bytes"] > 0 and row["recycle_reason"] == "peak_rss_threshold", "RSS recycle contract failed")
            with pool(recycle_peak_rss_bytes=1) as instance:
                rows = batch("D-rss-recycle", instance, [plan, plan], row_check=rss_check)
                for row in rows:
                    score(row)
                    require(row["worker_peak_rss_bytes"] > 0 and row["recycle_reason"] == "peak_rss_threshold", "RSS recycle contract failed")
                require(rows[0]["worker_pid"] != rows[1]["worker_pid"], "RSS recycle retained PID")
        elif stage == "E_search":
            save(private / "search-graph.json", graph, exclusive=True)
            with (private / "search-plans.jsonl").open("x", encoding="utf-8", newline="\n") as f:
                for value in (plan, {}, plan):
                    f.write(json.dumps(value) + "\n")
                f.flush()
                os.fsync(f.fileno())
            event = admit("record", "E-search-three-lines", 3)
            output = private / "search-output.jsonl"
            rc = cli("E-search", ["-m", "research.a.e2_search.cli", str(private / "search-graph.json"),
                str(private / "search-plans.jsonl"), "--problem", "2", "--workers", "1", "--timeout", "30",
                "--config", str(ROOT / "data/raw/a/official/data/config.txt"), "--output", str(output)])
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            event.update(status="returned", returncode=rc, records=rows)
            flush()
            require(rc == 1 and len(rows) == 3 and [r["index"] for r in rows] == [0, 1, 2], "search CLI exit/order mismatch")
            score(rows[0]); invalid(rows[1]); score(rows[2])
            metadata = read(Path(str(output) + ".run.json"))
            require(metadata["engine"] == "p2-e2-native-search-v1" and metadata["workers"] == 1, "CLI metadata mismatch")
        elif stage in ("E_full_valid", "E_full_invalid"):
            valid = stage == "E_full_valid"
            save(private / (stage + ".graph.json"), graph, exclusive=True)
            save(private / (stage + ".plan.json"), plan if valid else {}, exclusive=True)
            # contest_io adds these two documented fields to CLI output only.
            cli_truth = dict(truth, input_graph=stage + ".graph.json", input_plan=stage + ".plan.json")
            prefixes = []
            for mode in ("official", "adapter"):
                event = admit("fixed_e0", stage + "-" + mode)
                prefix = private / (stage + "-" + mode)
                prefixes.append(prefix)
                start = [str(ROOT / "data/raw/a/official/code/multicore_cut_evaluate_problem_2.py")] if mode == "official" else ["-m", "research.a.e2_search.multicore_cut_evaluate_problem_2"]
                rc = cli(stage + "-" + mode, start + [str(private / (stage + ".graph.json")),
                    str(private / (stage + ".plan.json")), "--config", str(ROOT / "data/raw/a/official/data/config.txt"),
                    "--output", str(prefix) + ".json", "--trace-output", str(prefix) + ".trace.json",
                    "--log-output", str(prefix) + ".log"])
                event.update(status="returned", returncode=rc)
                flush()
                require(rc == (0 if valid else 1), "full CLI exit mismatch")
                if valid:
                    require(canonical(read(Path(str(prefix) + ".json"))) == canonical(cli_truth), "full CLI prior truth mismatch")
                else:
                    require(bad["message"] in (private / (stage + "-" + mode + ".stderr")).read_text(encoding="utf-8"), "invalid CLI error message mismatch")
                    require(not any(Path(str(prefix) + suffix).exists() for suffix in (".json", ".trace.json", ".log")), "invalid CLI emitted success artifacts")
            if valid:
                for suffix in (".json", ".trace.json", ".log"):
                    require(Path(str(prefixes[0]) + suffix).read_bytes() == Path(str(prefixes[1]) + suffix).read_bytes(), "full CLI bytes differ: " + suffix)
                require(canonical(read(Path(str(prefixes[0]) + ".json"))) == canonical(cli_truth), "full CLI prior truth mismatch")
            # Invalid stderr/outputs are retained, but adapter route stderr is
            # not required to be byte-identical to the direct official CLI.
        require(tuple(receipt["admitted"][k] for k in ("record", "fixed_e0")) == STAGES[stage], "matrix incomplete")
        exit_code = 0
    except BaseException as error:
        receipt.update(error_type=type(error).__name__, message=str(error))
        raise
    finally:
        receipt.update(exit_code=exit_code, wall_since_t0=elapsed(private))
        flush()
    return exit_code

