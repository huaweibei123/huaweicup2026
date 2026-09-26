"""One guarded 067/k5 response audit. This file only supervises a later, separately authorized run."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import ctypes, gzip, hashlib, json, os, platform, shutil, subprocess, sys, time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
RUN = OUT / "run.json"
if any((OUT / name).exists() for name in ("run.json", "stdout.json.gz", "stderr.txt.gz")):
    raise SystemExit("sealed or partial result exists; refusing to overwrite")

NEW_COMMIT = "1b70dd6076430230c531b10e3e403e88474179cc"
MODEL_COMMIT = "68fbe66e97f78161bfb6f4f9e83cd2f0977ce7a9"
GRAPH = Path("../huaweicup2026/data/raw/a/official-cases/data/case_067.json")
CONFIG = Path("data/raw/a/official/data/config.txt")
EXPECTED_GRAPH = "f49b5087689e18c6bf231843f8f3bbaca238a547ea5309b2492c76d5f170b542"
EXPECTED_CONFIG = "dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9"
PINNED = {
    "docs/a/source-manifest.json": NEW_COMMIT,
    "src/q3_yuanzhifang/tail_response_model.py": NEW_COMMIT,
    "src/q3_yuanzhifang/tail_response_audit.py": NEW_COMMIT,
    "docs/a/q3-yuanzhifang/TAIL_RESPONSE_AUDIT.md": NEW_COMMIT,
    **{"src/q3_yuanzhifang/" + f: MODEL_COMMIT for f in (
        "tail_stair_model.py", "tail_phase_model.py", "tail_fifo_bound.py",
        "wave_tail.py", "wave_capacity.py", "active_stages.py", "construct.py", "baseline.py")},
}
COMMAND = [".venv/Scripts/python.exe", "-X", "utf8", "-B", "-m",
           "src.q3_yuanzhifang.tail_response_audit", GRAPH.as_posix(),
           "--cores", "5", "--config", CONFIG.as_posix()]
sha = lambda b: hashlib.sha256(b).hexdigest()
now = lambda: datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
def git_bytes(rev: str, path: str) -> bytes:
    return subprocess.run(["git", "show", f"{rev}:{path}"], cwd=ROOT,
                          capture_output=True, check=True).stdout
def resource_gate() -> dict:
    gate = {"available_phys_bytes": None, "free_disk_bytes": None,
            "minimum_phys_bytes": 1024**3, "minimum_disk_bytes": 256*1024**2,
            "passed": False}
    if os.name != "nt":
        gate["error"] = "Windows GlobalMemoryStatusEx unavailable"
        return gate
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (n, ctypes.c_ulonglong) for n in ("total_phys", "avail_phys", "total_page",
            "avail_page", "total_virtual", "avail_virtual", "avail_extended")]
    s = MemoryStatus(); s.length = ctypes.sizeof(s)
    try:
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)):
            gate["available_phys_bytes"] = s.avail_phys
        gate["free_disk_bytes"] = shutil.disk_usage(OUT).free
    except OSError as e:
        gate["error"] = type(e).__name__
    gate["passed"] = (gate["available_phys_bytes"] is not None and
        gate["available_phys_bytes"] >= gate["minimum_phys_bytes"] and
        gate["free_disk_bytes"] is not None and gate["free_disk_bytes"] >= gate["minimum_disk_bytes"])
    return gate

started = now()
head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                      text=True, check=True).stdout.strip()
source_checks = {}
for path, rev in PINNED.items():
    current = (ROOT / path).read_bytes(); frozen = git_bytes(rev, path)
    source_checks[path] = {"commit": rev, "bytes": len(current),
        "working_sha256": sha(current), "frozen_sha256": sha(frozen), "matches": current == frozen}
manifest = json.loads((ROOT / "docs/a/source-manifest.json").read_text(encoding="utf-8"))
official = ROOT / "data/raw/a/official"
official_checks = {}
manifest_code_paths = {x["path"] for x in manifest["files"] if x["path"].startswith("code/") and x["path"].endswith(".py")}
actual_code_paths = {p.relative_to(official).as_posix() for p in (official / "code").glob("*.py")}
official_manifest_coverage = {"manifest_code_py_count": len(manifest_code_paths),
    "actual_code_py_count": len(actual_code_paths), "code_paths_match": manifest_code_paths == actual_code_paths,
    "config_present": any(x["path"] == "data/config.txt" for x in manifest["files"])}
for item in manifest["files"]:
    p = item["path"]
    if p.startswith("code/") or p == "data/config.txt":
        raw = (official / p).read_bytes()
        official_checks[p] = {"expected_sha256": item["sha256"], "actual_sha256": sha(raw),
                              "matches": sha(raw) == item["sha256"]}
graph_bytes = (ROOT / GRAPH).read_bytes(); config_bytes = (ROOT / CONFIG).read_bytes()
identity_ok = (all(x["matches"] for x in source_checks.values()) and
    all(x["matches"] for x in official_checks.values()) and
    official_manifest_coverage["code_paths_match"] and official_manifest_coverage["config_present"] and
    sha(graph_bytes) == EXPECTED_GRAPH and sha(config_bytes) == EXPECTED_CONFIG)
record = {"schema": "q3-tail-response-static-run-v1", "started_at_utc": started,
    "supervisor_sha256": sha(Path(__file__).read_bytes()),
    "head_context": head, "source_checks": source_checks, "official_checks": official_checks,
    "official_manifest_coverage": official_manifest_coverage,
    "graph_sha256": sha(graph_bytes), "expected_graph_sha256": EXPECTED_GRAPH,
    "config_sha256": sha(config_bytes), "expected_config_sha256": EXPECTED_CONFIG,
    "command": COMMAND, "working_directory": ".", "timeout_seconds": 10, "retries": 0,
    "priority": "BELOW_NORMAL_PRIORITY_CLASS", "environment": {
        "python": sys.version, "executable": Path(sys.executable).relative_to(ROOT).as_posix(), "platform": platform.platform(),
        "temp_scope": "output directory", "PYTHONDONTWRITEBYTECODE": "1"},
    "resource_gate": None, "calls": {"response_analysis": 0, "derive": 0, "Step": 0,
        "E0": 0, "E1": 0, "E2": 0}, "status": "stopped"}
if not identity_ok:
    record["stop_reason"] = "pinned source or input identity mismatch"
else:
    record["resource_gate"] = resource_gate()
    if not record["resource_gate"]["passed"]:
        record["stop_reason"] = "RAM/disk below gate or unknown; no subprocess dispatched"
    else:
        env = dict(os.environ, TMP=str(OUT), TEMP=str(OUT), PYTHONDONTWRITEBYTECODE="1")
        creationflags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000)
        t0 = time.perf_counter(); record["process_started_at_utc"] = now()
        record["calls"]["response_analysis"] = 1
        try:
            proc = subprocess.run(COMMAND, cwd=ROOT, env=env, capture_output=True,
                timeout=10, creationflags=creationflags)
            stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, code = exc.stdout or b"", exc.stderr or b"", None
            record["timed_out"] = True
        record["external_process_wall_seconds"] = time.perf_counter() - t0
        record["process_finished_at_utc"] = now(); record["returncode"] = code
        for name, raw in (("stdout.json.gz", stdout), ("stderr.txt.gz", stderr)):
            packed = gzip.compress(raw, mtime=0); (OUT / name).write_bytes(packed)
            record[name] = {"raw_sha256": sha(raw), "raw_bytes": len(raw),
                            "gzip_sha256": sha(packed), "gzip_bytes": len(packed)}
        if code == 0 and not record.get("timed_out"):
            try:
                result = json.loads(stdout)
                record["decoded_result"] = {k: result.get(k) for k in
                    ("schema", "status", "checks", "reference", "response", "oracle", "calls",
                     "response_body_seconds", "oracle_body_seconds", "analysis_body_seconds")}
                checks = result.get("checks", {})
                record["checks_all_true"] = bool(checks) and all(v is True for v in checks.values())
                record["expected_comparison"] = {"bound": result.get("reference", {}).get("bound") == 11856672,
                    "cuts": result.get("reference", {}).get("cuts") == [0,20,44,66,94,124],
                    "h": result.get("reference", {}).get("h") == 2,
                    "first_wave_sizes": result.get("reference", {}).get("first_wave_sizes") == [2,3,4,5,6],
                    "schema": result.get("schema") == "q3-tail-response-audit-v1",
                    "status": result.get("status") == "ok",
                    "graph_identity": result.get("graph_sha256") == EXPECTED_GRAPH,
                    "config_identity": result.get("config_sha256") == EXPECTED_CONFIG,
                    "cores": result.get("cores") == 5,
                    "jobs": result.get("jobs") == 71}
                record["status"] = "ok" if (record["checks_all_true"] and
                    all(record["expected_comparison"].values())) else "checks_mismatch"
            except Exception as exc:
                record["decode_error"] = type(exc).__name__
                record["status"] = "decode_failed"
        else:
            record["stop_reason"] = "timeout or nonzero child exit"
record["finished_at_utc"] = now()
RUN.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(OUT / "README.md").write_text("# Tail response static audit\n\n067/k5 one-process audit only; not a submission plan or E0 result. `run.json` records source-manifest and pinned-source identities, resource gate, command, timing, calls, and stdout/stderr raw/gzip hashes. All reference checks are reported without retuning.\n", encoding="utf-8")
print(json.dumps({"status": record["status"], "stop_reason": record.get("stop_reason"),
                  "checks_all_true": record.get("checks_all_true"),
                  "expected_comparison": record.get("expected_comparison")}, ensure_ascii=False))
