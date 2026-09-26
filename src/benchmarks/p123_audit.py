"""Read-only audit of completed P1/P2/P3 receipts and comparison.csv.

No solver, evaluator, native library, plotting module or subprocess is imported
or started. Existing timeouts/errors are outcomes, not audit failures. Missing
coverage is reported separately from inconsistency. Default output is JSON on
stdout; --output creates a NEW report file. Exit codes: 0 consistent (possibly
partial), 1 inconsistent, 2 incomplete when --require-full was requested.
Run after the controller stops/finishes aggregation; live CSVs can be stale.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
CASES = tuple(f"{number:03d}" for number in range(1, 101))
PROBLEMS = ("P1", "P2", "P3")
BASELINE_COMMIT = "f27ef37bb76dcf556f35d3f2328e405d92241d9c"
NUMBERS = ("makespan_cycles", "singlecore_cycles", "multicore_speedup", "solver_wall_seconds",
           "e0_wall_seconds", "cache_hit_rate", "no_cache_makespan_cycles", "cache_speedup")
FIELDS = ("case", "problem", "cores", "algorithm", "status", *NUMBERS,
          "data_movement_bytes", "error", "source_commit", "result_path")


def number(value):
    if value is None or value == "":
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite numerical field")
    return result


def same(a, b):
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)


class Audit:
    def __init__(self, run):
        self.run = run.resolve()
        self.errors = []
        self.warnings = []
        self.hashes = {}
        self.raw_hashes = {}
        self.json_files = {}
        self.rows = {}
        self.baselines = {}
        self.receipts = {}
        self.harness_hashes = set()
        self.invocations = []
        self.legacy_files = {}

    def lineage(self):
        original = self.protocol["source_sha256"]["p123_run.py"]
        self.harness_hashes = {original}
        path = self.run / "harness/revisions.json"
        if path.exists():
            lineage = self.read(path)
            self.check(lineage["original_protocol_sha256"] == self.digest(self.run / "protocol.json"),
                       self.label(path), "revision lineage refers to a different original protocol")
            for revision in lineage["revisions"]:
                digest = revision["sha256"]
                self.check(isinstance(digest, str) and len(digest) == 64
                           and all(char in "0123456789abcdef" for char in digest),
                           self.label(path), "invalid harness revision hash")
                self.check(bool(revision.get("note")), self.label(path), "harness revision lacks rationale")
                self.harness_hashes.add(digest)
                snapshot = self.run / "harness" / f"p123_run-{digest}.py"
                self.check(self.digest(snapshot) == digest, self.label(snapshot), "harness snapshot bytes differ")
            self.check(original in {item["sha256"] for item in lineage["revisions"]},
                       self.label(path), "original harness missing from revision lineage")
            legacy = lineage.get("legacy_evidence")
            if legacy:
                manifest_path = self.within(legacy["file"])
                self.check(self.digest(manifest_path) == legacy["sha256"],
                           self.label(manifest_path), "preflight manifest identity differs")
                manifest = self.read(manifest_path)
                self.check(manifest["harness_sha256"] == original,
                           self.label(manifest_path), "preflight controller identity differs")
                self.legacy_files = manifest["files"]
                for relative, record in self.legacy_files.items():
                    artifact = self.within(relative)
                    self.check(artifact.stat().st_size == record["bytes"]
                               and self.digest(artifact) == record["sha256"],
                               relative, "observed preflight evidence changed")
        else:
            self.warnings.append(dict(where="harness/revisions.json", message="legacy run has no harness revision snapshots"))
        self.check(self.digest(ROOT / "src/benchmarks/p123_evaluate.py")
                   == self.protocol["source_sha256"]["p123_evaluate.py"],
                   "protocol.json", "official wrapper differs from pinned original protocol")
        for path in sorted((self.run / "invocations").glob("*.json")):
            invocation = self.read(path)
            self.check(invocation["harness_sha256"] in self.harness_hashes,
                       self.label(path), "invocation uses unrecorded harness revision")
            self.invocations.append(dict(file=self.label(path), status=invocation.get("status"),
                                         harness_sha256=invocation["harness_sha256"]))
        for path in sorted((self.run / "cells").rglob("process.json")) + sorted((self.run / "baselines").rglob("process.json")):
            process = self.read(path)
            if "harness_sha256" not in process and len(self.harness_hashes) > 1:
                self.check(self.label(path) in self.legacy_files, self.label(path),
                           "unversioned process receipt is not in the observed preflight manifest")
            self.check(process.get("harness_sha256", original) in self.harness_hashes,
                       self.label(path), "process uses unrecorded harness revision")
            self.check(not process.get("cleanup_unconfirmed"), self.label(path), "process cleanup was not confirmed")

    def label(self, path):
        try:
            return path.resolve().relative_to(self.run).as_posix()
        except ValueError:
            return path.name

    def fail(self, where, message):
        self.errors.append(dict(where=str(where), message=message))

    def check(self, condition, where, message):
        if not condition:
            self.fail(where, message)

    def read(self, path):
        if path not in self.json_files:
            with path.open(encoding="utf-8-sig") as stream:
                self.json_files[path] = json.load(stream)
        return self.json_files[path]

    def digest(self, path, *, decompressed=False):
        cache = self.raw_hashes if decompressed else self.hashes
        if path not in cache:
            value = hashlib.sha256()
            opener = gzip.open if decompressed else open
            with opener(path, "rb") as stream:
                for part in iter(lambda: stream.read(1 << 20), b""):
                    value.update(part)
            cache[path] = value.hexdigest()
        return cache[path]

    def artifact(self, path, gzip_hash, raw_hash=None):
        self.check(bool(gzip_hash), self.label(path), "missing recorded artifact SHA-256")
        self.check(self.digest(path) == gzip_hash, self.label(path), "artifact SHA-256 mismatch")
        if raw_hash is not None:
            self.check(self.digest(path, decompressed=True) == raw_hash,
                       self.label(path), "decompressed raw SHA-256 mismatch")

    def within(self, relative):
        path = (self.run / relative).resolve()
        if not path.is_relative_to(self.run):
            raise ValueError("result path escapes run directory")
        return path

    def guarded(self, where, function):
        try:
            function()
        except (OSError, ValueError, TypeError, KeyError, IndexError, EOFError) as error:
            message = str(error).replace(str(self.run), "<run>").replace(str(ROOT), "<repository>")
            self.fail(where, f"{type(error).__name__}: {message}")

    def load_csv(self):
        path = self.run / "comparison.csv"
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not set(FIELDS) <= set(reader.fieldnames or ()):
                raise ValueError("comparison.csv lacks required columns")
            for line, row in enumerate(reader, 2):
                where = f"comparison.csv:{line}"
                try:
                    key = (row["problem"], row["case"], int(row["cores"]))
                    if key[0] not in PROBLEMS or key[1] not in CASES or key[2] not in range(1, 6):
                        raise ValueError("invalid problem/case/core key")
                    if key in self.rows:
                        raise ValueError(f"duplicate CSV key {key}")
                    row["cores"] = key[2]
                    for field in NUMBERS:
                        row[field] = number(row[field])
                    row["data_movement_bytes"] = (json.loads(row["data_movement_bytes"])
                                                   if row["data_movement_bytes"] else None)
                    self.rows[key] = row
                except (ValueError, TypeError) as error:
                    self.fail(where, str(error))

    def identity(self, summary, case, where, *, official=False):
        expected_graph = self.manifest_records[f"data/case_{case}.json"]["sha256"]
        self.check(summary["graph_sha256"] == expected_graph, where, "graph identity mismatch")
        self.check(summary["config_sha256"] == self.manifest_records["data/config.txt"]["sha256"],
                   where, "configuration identity mismatch")
        if official:
            self.check(summary["official_code_hash"] == self.manifest["official_code_hash"],
                       where, "official code hash mismatch")
            self.check(summary["manifest_sha256"] == self.protocol["official_source_manifest_sha256"],
                       where, "source manifest identity mismatch")
            self.check(summary["graph_manifest_verified"] is True, where, "graph was not manifest verified")

    def official_result(self, folder, case, mode, *, plan_hash=None):
        summary = self.read(folder / "summary.json")
        where = self.label(folder)
        self.check(summary["status"] == "ok", where, "successful row points to failed official receipt")
        self.check(summary["mode"] == mode, where, "official evaluation mode mismatch")
        self.check(summary["official_calls"] == 1, where, "expected one recorded official evaluation")
        self.identity(summary, case, where, official=True)
        if plan_hash is not None:
            self.check(summary["plan_sha256"] == plan_hash, where, "official evaluation used a different plan")
        self.artifact(folder / "result.json.gz", summary["result_gzip_sha256"], summary["result_sha256"])
        return summary

    def baseline(self, path):
        case = path.parent.parent.name
        if case not in CASES:
            raise ValueError("unexpected baseline case")
        value = self.read(path)
        self.baselines[case] = value
        if value["status"] == "ok":
            self.official_result(path.parent, case, "single")
        self.check(value["status"] in ("ok", "error", "timeout"), self.label(path), "unknown baseline outcome")
        for problem in ("P1", "P2"):
            key = (problem, case, 1)
            row = self.rows.get(key)
            if row is None:
                self.fail(str(key), "completed baseline missing from CSV; aggregation may be stale")
                continue
            self.check(row["status"] == value["status"], str(key), "baseline status differs from receipt")
            self.check(row["algorithm"] == "official_singlecore_baseline", str(key), "unexpected baseline algorithm")
            self.check(row["source_commit"] == BASELINE_COMMIT, str(key), "baseline source commit mismatch")
            self.check(same(row["makespan_cycles"], number(value.get("makespan_cycles"))), str(key), "baseline Makespan differs")
            self.check(same(row["singlecore_cycles"], number(value.get("makespan_cycles"))), str(key), "single-core baseline differs")
            self.check(same(row["multicore_speedup"], 1.0 if value["status"] == "ok" else None),
                       str(key), "baseline ratio must be 1 only for a successful baseline")
            if value["status"] == "ok":
                self.check(self.within(row["result_path"]) == (path.parent / "result.json.gz").resolve(),
                           str(key), "baseline CSV points to wrong artifact")

    def compare_receipt(self, row, saved, where):
        for field in FIELDS:
            expected = saved.get(field)
            observed = row.get(field)
            if field in NUMBERS:
                equal = same(observed, number(expected))
            elif field == "data_movement_bytes":
                expected = json.loads(expected) if isinstance(expected, str) and expected else expected
                equal = observed == expected
            elif field == "cores":
                equal = observed == int(expected)
            else:
                equal = (observed or "") == (expected or "")
            self.check(equal, where, f"CSV field {field} differs from cell receipt")

    def cell(self, path):
        key = (path.parents[2].name, path.parents[1].name, int(path.parent.name.removeprefix("k")))
        receipt = self.read(path)
        self.receipts[key] = receipt
        if "harness_sha256" not in receipt and len(self.harness_hashes) > 1:
            self.check(self.label(path) in self.legacy_files, self.label(path),
                       "unversioned cell receipt is not in the observed preflight manifest")
        self.check(receipt.get("harness_sha256", self.protocol["source_sha256"]["p123_run.py"])
                   in self.harness_hashes, self.label(path), "cell uses unrecorded harness revision")
        row = self.rows.get(key)
        if row is None:
            self.fail(str(key), "completed cell missing from CSV; aggregation may be stale")
            return
        where = str(key)
        self.compare_receipt(row, receipt["row"], where)
        problem, case, core = key
        self.check(row["source_commit"] == self.protocol["versions"][problem]["commit"], where, "solver commit differs from protocol")
        self.check(row["algorithm"] == self.protocol["algorithms"][problem], where, "algorithm differs from protocol")
        for process in receipt.get("processes", []):
            self.check(not process.get("cleanup_unconfirmed"), where, "process cleanup was not confirmed")
        if row["status"] != "ok":
            return  # Expected failure: never require a successful result artifact.
        folder = path.parent
        plan_hash = self.digest(folder / "plan.json")
        self.check(plan_hash == receipt["plan_sha256"], where, "saved plan SHA-256 differs from receipt")
        if problem == "P1":
            search = self.read(folder / "search/summary.json")
            self.check(search["e0_confirms_selected_makespan"] is True, where, "P1 has no official incumbent confirmation")
            self.check(search["e0_best"]["status"] == "ok", where, "P1 E0 best did not succeed")
            self.check(same(number(search["e0_best"]["makespan"]), row["makespan_cycles"]), where, "P1 E0 Makespan differs")
            self.check(self.digest(folder / "search/best_plan.json") == plan_hash, where, "P1 published plan differs from selected plan")
            for label, artifact in receipt["evidence"].items():
                if artifact is not None:
                    item = folder / "search" / (label + ".gz")
                    self.artifact(item, artifact["gzip_sha256"], artifact["raw_sha256"])
            self.check(receipt["evidence"].get("e0_best/result.json") is not None, where, "missing P1 primary result hash")
            expected_result = folder / "search/e0_best/result.json.gz"
        elif problem == "P2":
            result = self.official_result(folder / "e0", case, "P2", plan_hash=plan_hash)
            self.check(same(number(result["makespan_cycles"]), row["makespan_cycles"]), where, "P2 official Makespan differs")
            self.check(result["data_movement_bytes"] == row["data_movement_bytes"], where, "P2 movement bytes differ")
            expected_result = folder / "e0/result.json.gz"
        else:
            result = self.read(folder / "online/receipt.json")
            self.identity(result, case, where)
            self.check(result["plan_sha256"] == plan_hash, where, "P3 official result used a different plan")
            self.check(result["official_e0_calls"] == 1, where, "P3 did not record one online E0 call")
            self.check(result["cores"] == core, where, "P3 receipt core count differs")
            self.check(same(number(result["makespan"]), row["makespan_cycles"]), where, "P3 official Makespan differs")
            self.check(result["data_movement_bytes"] == row["data_movement_bytes"], where, "P3 movement bytes differ")
            stats = result["cache_stats"]
            self.check(same(number(stats["hit_rate"]), row["cache_hit_rate"]), where, "P3 cache hit rate differs")
            byte_total = stats["hit_bytes"] + stats["miss_bytes"]
            expected_hit_rate = stats["hit_bytes"] / byte_total if byte_total else 0.0
            self.check(same(row["cache_hit_rate"], expected_hit_rate), where, "P3 cache hit rate is not byte-based")
            expected_result = folder / "online/result.json.gz"
            self.artifact(expected_result, result["result_sha256"])
            if row["cache_speedup"] is not None:
                paired = self.official_result(folder / "no_cache", case, "P2", plan_hash=plan_hash)
                self.check(paired["num_cores"] == core, where, "P3 paired no-cache core count differs")
                self.check(same(number(paired["makespan_cycles"]), row["no_cache_makespan_cycles"]),
                           where, "paired P2 Makespan differs")
            else:
                self.check(bool(receipt.get("cache_pair_error")), where, "P3 cache ratio missing without paired-failure evidence")
        self.check(self.within(row["result_path"]) == expected_result.resolve(), where, "CSV points to wrong result artifact")

    def row_math(self, key, row):
        where = str(key)
        self.check(row["status"] in ("ok", "error", "timeout"), where, "unknown cell status")
        if row["status"] != "ok":
            for field in ("multicore_speedup", "cache_speedup"):
                self.check(row[field] is None, where, f"failed row must retain NA for {field}")
            return
        self.check(not row["error"], where, "row is marked ok but contains an error")
        makespan = row["makespan_cycles"]
        self.check(makespan is not None and makespan > 0, where, "successful Makespan must be positive")
        baseline = self.baselines.get(key[1])
        self.check(baseline is not None, where, "missing shared baseline receipt")
        if baseline is not None:
            single = number(baseline.get("makespan_cycles")) if baseline["status"] == "ok" else None
            self.check(same(row["singlecore_cycles"], single), where, "single-core denominator source differs")
            expected = single / makespan if single is not None and makespan and makespan > 0 else None
            self.check(same(row["multicore_speedup"], expected), where, "wrong multicore ratio or failed baseline was not NA")
        no_cache = row["no_cache_makespan_cycles"]
        expected_cache = no_cache / makespan if no_cache is not None and makespan and makespan > 0 else None
        self.check(same(row["cache_speedup"], expected_cache), where, "wrong no-cache/Cache ratio")
        for field in ("solver_wall_seconds", "e0_wall_seconds"):
            self.check(row[field] is None or row[field] >= 0, where, f"negative {field}")
        if key[0] != "P3":
            self.check(row["cache_speedup"] is None and row["cache_hit_rate"] is None,
                       where, "Cache-only metrics appeared outside P3")

    def execute(self):
        self.protocol = self.read(self.run / "protocol.json")
        manifest_path = ROOT / "docs/a/source-manifest.json"
        self.manifest = self.read(manifest_path)
        self.manifest_records = {item["path"]: item for item in self.manifest["files"]}
        self.check(self.digest(manifest_path) == self.protocol["official_source_manifest_sha256"],
                   "protocol.json", "local frozen source manifest differs from run")
        self.guarded("harness lineage", self.lineage)
        self.guarded("comparison.csv", self.load_csv)
        for path in sorted((self.run / "baselines").glob("*/e0/summary.json")):
            self.guarded(self.label(path), lambda path=path: self.baseline(path))
        for path in sorted((self.run / "cells").glob("*/*/k*/cell.json")):
            self.guarded(self.label(path), lambda path=path: self.cell(path))
        for key, row in self.rows.items():
            expected = key[1] in self.baselines if key[0] in ("P1", "P2") and key[2] == 1 else key in self.receipts
            self.check(expected, str(key), "CSV row has no baseline/cell receipt")
            self.guarded(str(key), lambda key=key, row=row: self.row_math(key, row))
        groups = []
        for problem in PROBLEMS:
            for core in range(1, 6):
                rows = [self.rows.get((problem, case, core)) for case in CASES]
                counts = Counter(row["status"] for row in rows if row is not None)
                groups.append(dict(problem=problem, cores=core, expected=100,
                                   recorded=sum(counts.values()), ok=counts["ok"],
                                   failed=sum(count for status, count in counts.items() if status != "ok"),
                                   timeout=counts["timeout"], missing=sum(row is None for row in rows),
                                   multicore_ratio_n=sum(row is not None and row["status"] == "ok"
                                                         and row["multicore_speedup"] is not None for row in rows),
                                   cache_ratio_n=sum(row is not None and row["status"] == "ok"
                                                    and row["cache_speedup"] is not None for row in rows)))
        unfinished = [self.label(path) for path in (self.run / "cells").glob("*/*/k*")
                      if path.is_dir() and not (path / "cell.json").exists()]
        unfinished += [self.label(path) for path in (self.run / "baselines").glob("*")
                       if path.is_dir() and not (path / "e0/summary.json").exists()]
        full = (len(self.baselines) == 100 and len(self.receipts) == 1300
                and len(self.rows) == 1500 and not unfinished)
        return dict(audited_at=datetime.now(timezone.utc).isoformat(),
                    status="inconsistent" if self.errors else "consistent_full" if full else "consistent_partial",
                    coverage="full" if full else "partial", full_coverage_means="all outcomes recorded, not all evaluations succeeded",
                    baseline_outcomes=dict(Counter(value["status"] for value in self.baselines.values())),
                    baseline_receipts=len(self.baselines), expected_baselines=100,
                    cell_receipts=len(self.receipts), expected_cells=1300,
                    csv_rows=len(self.rows), expected_csv_rows=1500, groups=groups,
                    unfinished_directories=sorted(unfinished), errors=self.errors, warnings=self.warnings,
                    artifact_files_hashed=len(self.hashes), decompressed_artifacts_hashed=len(self.raw_hashes),
                    protocol_sha256=self.digest(self.run / "protocol.json"),
                    csv_sha256=self.digest(self.run / "comparison.csv"),
                    audit_source_sha256=self.digest(Path(__file__)),
                    solver_versions={role: data["commit"] for role, data in self.protocol["versions"].items()},
                    declared_harness_sha256=self.protocol["source_sha256"],
                    allowed_harness_sha256=sorted(self.harness_hashes), invocations=self.invocations,
                    scope="CSV/receipt equality, formulas, recorded outcomes, artifact byte identities and fixed-manifest provenance; no scoring",
                    limitations=["No independent solver rebuild or semantic re-evaluation of complete result traces",
                                 "P3 online receipt stores compressed result identity, not a separate raw JSON digest",
                                 "Harness snapshots and revision hashes checked; revision notes remain declarations, not proof of unchanged semantics",
                                 "Partial/live runs can have stale aggregation; run again after controller completion"],
                    evaluator_calls=0, solver_starts=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-full", action="store_true")
    args = parser.parse_args()
    audit = Audit(args.run_dir)
    try:
        report = audit.execute()
    except (OSError, ValueError, TypeError, KeyError) as error:
        message = str(error).replace(str(audit.run), "<run>").replace(str(ROOT), "<repository>")
        report = dict(status="inconsistent", coverage="unknown",
                      errors=audit.errors + [dict(where="audit", message=f"{type(error).__name__}: {message}")],
                      evaluator_calls=0, solver_starts=0)
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
    else:
        print(payload, end="")
    return 1 if report["errors"] else 2 if args.require_full and report["coverage"] != "full" else 0


if __name__ == "__main__":
    raise SystemExit(main())
