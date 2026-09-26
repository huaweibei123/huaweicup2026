"""Frozen one-worker P3 pilot. No retries, scoring search, or budget overrides."""
from __future__ import annotations

import argparse
import ctypes
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
SOLVER_COMMIT = "8f8bfce73b0b8e350de1dc40af21f3787c8ac8d6"
CASES = ("008", "037", "044", "080")
VARIANTS = ("baseline", "shared_order", "shared_place")
DEFAULT_OUTPUT = "results/a/q3-yuanzhifang/pilot-20260924"
OFFICIAL = Path("data/raw/a/official")
CONFIG = OFFICIAL / "data/config.txt"
MANIFEST = Path("docs/a/source-manifest.json")
SESSION = "yuanzhifang30-sudo/s-3d9c78db26714786b88b987ca6f58e2b"
RUN_ID = "yuanzhifang-q3-sharing-pilot-20260924"
BUDGET = dict(workers=1, cold_solver_limit=12, E0_limit=24, E1_limit=0,
              E2_limit=0, per_call_seconds=30, batch_seconds=600,
              dispatch_until_seconds=550, retries=0)


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative(path):
    return Path(os.path.relpath(path, ROOT)).as_posix()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def artifact(path):
    return dict(path=relative(path), sha256=sha(path))


def compress(path):
    """Preserve exact bytes, verify decompression, then remove this raw output only."""
    path = Path(path)
    raw = path.read_bytes()
    packed = gzip.compress(raw, mtime=0)
    target = path.with_name(path.name + ".gz")
    if target.exists():
        raise FileExistsError(relative(target))
    target.write_bytes(packed)
    if gzip.decompress(target.read_bytes()) != raw:
        raise ValueError("gzip round-trip mismatch: " + relative(path))
    path.unlink()
    return dict(**artifact(target), raw_sha256=digest(raw), raw_bytes=len(raw),
                gzip_bytes=len(packed))


def preflight(graph_dir):
    source = json.loads(MANIFEST.read_text(encoding="utf-8"))
    verified = []
    for item in source["files"]:
        name = item["path"]
        path = graph_dir / Path(name).name if name.startswith("data/case_") else OFFICIAL / name
        raw = path.read_bytes()
        if digest(raw) != item["sha256"] or len(raw) != item["bytes"]:
            raise ValueError("frozen source mismatch: " + name)
        verified.append(dict(manifest_path=name, actual_path=path.as_posix(),
                             sha256=digest(raw), bytes=len(raw)))
    code = "".join(f"{i['path']}\t{i['sha256']}\n" for i in sorted(
        source["files"], key=lambda x: x["path"]) if i["path"].startswith("code/"))
    if digest(code.encode()) != source["official_code_hash"]:
        raise ValueError("official aggregate mismatch")
    implementation = []
    for name in ("src/q3_yuanzhifang/construct.py", "src/q3_yuanzhifang/baseline.py"):
        raw = Path(name).read_bytes()
        if raw != git("show", SOLVER_COMMIT + ":" + name):
            raise ValueError("solver bytes differ from fixed commit: " + name)
        implementation.append(dict(path=name, sha256=digest(raw)))
    runner_commit = git("rev-parse", "HEAD").decode().strip()
    for name in ("src/q3_yuanzhifang/benchmark.py", "src/q3_yuanzhifang/export_feed.py"):
        if Path(name).read_bytes() != git("show", runner_commit + ":" + name):
            raise ValueError("runner must be committed with identical bytes: " + name)
    return dict(official_code_hash=source["official_code_hash"],
                source_manifest=artifact(MANIFEST), config_sha256=sha(CONFIG),
                verified_files=verified, implementation=implementation,
                solver_commit=SOLVER_COMMIT, runner_commit=runner_commit,
                runner_sha256=sha(__file__))


def environment():
    cpu = platform.processor()
    ram = None
    gpu = "none used; CPU-only algorithm and official Python evaluators"
    if os.name == "nt":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            cpu = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in (
                    "total_phys", "avail_phys", "total_page", "avail_page",
                    "total_virtual", "avail_virtual", "avail_extended")]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            ram = status.total_phys
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                capture_output=True, timeout=10)
            if result.returncode == 0:
                names = result.stdout.decode("utf-8", errors="replace").strip().splitlines()
                gpu += "; installed adapters: " + "; ".join(names)
            else:
                gpu += "; installed adapter inventory unavailable (query failed)"
        except subprocess.TimeoutExpired:
            gpu += "; installed adapter inventory unavailable (query exceeded 10 seconds)"
    return dict(os=platform.platform(), cpu=cpu, gpu=gpu, ram_bytes=ram,
                python=platform.python_version(),
                dependencies="uv sync --locked; uv.lock sha256=" + sha("uv.lock") +
                "; solver and E0 use Python standard library only",
                threads=1, workers=1, peak_rss_bytes=None)


class Stopped(RuntimeError):
    pass


class Pilot:
    def __init__(self, args):
        self.args = args
        self.out = args.output
        self.out.mkdir(parents=True, exist_ok=False)
        self.started = time.perf_counter()
        self.calls = []
        self.constructions = []
        self.evaluations = []
        self.info = dict(schema="q3-sharing-pilot-v1", run_id=RUN_ID,
                         producer_session=SESSION, started_at=utc(), budget=BUDGET,
                         argv=[relative(sys.executable), "-B", relative(__file__),
                               "--graph-dir", args.graph_dir.as_posix(),
                               "--output", args.output.as_posix()],
                         working_directory=".", status="running",
                         cold_start_definition="fresh Python process per call; OS file cache not flushed",
                         offline_costs="No training, compilation or input-specific precomputation in this batch. "
                         "Parent reports two prior static build_variant structure/dedup passes and two groups "
                         "of synthetic structure tests; these are development work, not cold CLI calls here. "
                         "Environment preparation uv sync --locked completed before batch; its wall was not recorded.")

    def save(self):
        self.info["calls"] = {kind: sum(c["kind"] == kind for c in self.calls)
                              for kind in ("solver", "E0", "E1", "E2")}
        self.info["elapsed_seconds"] = time.perf_counter() - self.started
        self.info["constructions"] = self.constructions
        self.info["evaluations"] = self.evaluations
        write_json(self.out / "manifest.json", self.info)
        write_json(self.out / "call-ledger.json", self.calls)

    def invoke(self, kind, call_id, argv, folder):
        elapsed = time.perf_counter() - self.started
        limit = BUDGET["cold_solver_limit" if kind == "solver" else "E0_limit"]
        if elapsed >= BUDGET["dispatch_until_seconds"]:
            raise Stopped("dispatch cutoff reached; no additional call launched")
        if sum(c["kind"] == kind for c in self.calls) >= limit:
            raise Stopped(kind + " call cap reached; no additional call launched")
        folder.mkdir(parents=True, exist_ok=True)
        stdout, stderr = folder / "stdout.txt", folder / "stderr.txt"
        call = dict(call_id=call_id, kind=kind, argv=argv, working_directory=".",
                    started_at=utc(), batch_elapsed_at_dispatch=elapsed, status="running",
                    timeout_seconds=min(30, BUDGET["batch_seconds"] - elapsed))
        self.calls.append(call)
        self.save()  # Started/unknown calls remain accounted even if driver is interrupted.
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
                   PYTHONHASHSEED="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                   MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
        start = time.perf_counter()
        try:
            with stdout.open("wb") as out, stderr.open("wb") as err:
                process = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=out, stderr=err)
                try:
                    call["exit_code"] = process.wait(timeout=call["timeout_seconds"])
                    call["status"] = "ok" if call["exit_code"] == 0 else "failed"
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    call.update(status="timeout", exit_code=process.returncode)
        except OSError as exc:
            call.update(status="failed", exit_code=None, failure_type=type(exc).__name__)
        finally:
            call.update(wall_seconds=time.perf_counter() - start, finished_at=utc())
            call["stdout"] = compress(stdout)
            call["stderr"] = compress(stderr)
            write_json(folder / "call.json", call)
            self.save()
        print(json.dumps({k: call[k] for k in ("call_id", "status", "wall_seconds")}), flush=True)
        if call["status"] != "ok":
            raise Stopped("first unsuccessful call: " + call_id)
        return call

    def run(self):
        try:
            self.info["identity"] = preflight(self.args.graph_dir)
            self.info["environment"] = environment()
            self.save()
            seen = {}
            python = relative(sys.executable)
            for case in CASES:
                graph = self.args.graph_dir / f"case_{case}.json"
                for variant in VARIANTS:
                    folder = self.out / case / variant
                    plan_path = folder / f"case_{case}_multicore_res.json"
                    construct_id = f"{case}-{variant}"
                    argv = [python, "-B", "-m", "src.q3_yuanzhifang.construct",
                            graph.as_posix(), "--cores", "4", "--variant", variant,
                            "--output", plan_path.as_posix()]
                    call = self.invoke("solver", construct_id, argv, folder / "solver")
                    plan = plan_path.read_bytes()
                    if set(json.loads(plan)) != {"node_to_subgraph", "core_schedules"}:
                        raise Stopped("invalid plan top-level fields: " + construct_id)
                    detail = json.loads(gzip.decompress((ROOT / call["stdout"]["path"]).read_bytes()))
                    construction = dict(construction_id=construct_id, case_id=case,
                                        variant=variant, cores=4, graph_sha256=sha(graph),
                                        plan=artifact(plan_path), solver=call, detail=detail,
                                        alias_of=None, evaluation_ids=[])
                    self.constructions.append(construction)
                    key = (case, digest(plan))
                    if key in seen:
                        owner = seen[key]
                        # Hash is the index; raw equality is the actual deduplication rule.
                        if (ROOT / owner["plan"]["path"]).read_bytes() != plan:
                            raise Stopped("plan hash collision")
                        construction["alias_of"] = owner["construction_id"]
                        construction["evaluation_ids"] = list(owner["evaluation_ids"])
                        self.save()
                        continue
                    seen[key] = construction
                    for problem in (2, 3):
                        eval_id = f"{construct_id}-P{problem}"
                        destination = folder / f"P{problem}"
                        outputs = {name: destination / filename for name, filename in (
                            ("result", "result.json"), ("trace", "trace.json"), ("log", "result.log"))}
                        entry = OFFICIAL / f"code/multicore_cut_evaluate_problem_{problem}.py"
                        argv = [python, "-B", entry.as_posix(), graph.as_posix(), plan_path.as_posix(),
                                "--config", CONFIG.as_posix(), "--output", outputs["result"].as_posix(),
                                "--trace-output", outputs["trace"].as_posix(),
                                "--log-output", outputs["log"].as_posix()]
                        call = self.invoke("E0", eval_id, argv, destination)
                        result = json.loads(outputs["result"].read_text(encoding="utf-8"))
                        if result["scene"] != "B" or result["num_cores"] != 4 or result["makespan"] <= 0:
                            raise Stopped("official result mismatch: " + eval_id)
                        if problem == 3 and (result.get("problem") != 3 or result.get("cache_mode") != "read_only"):
                            raise Stopped("official P3 identity mismatch: " + eval_id)
                        evaluation = dict(evaluation_id=eval_id, construction_id=construct_id,
                                          case_id=case, variant=variant, problem=f"P{problem}",
                                          makespan_cycles=result["makespan"], call=call,
                                          artifacts={name: compress(path) for name, path in outputs.items()})
                        self.evaluations.append(evaluation)
                        construction["evaluation_ids"].append(eval_id)
                        self.save()
            self.info.update(status="ok", stop_reason="all prescribed constructions and unique-plan P2/P3 pairs completed")
        except Exception as exc:
            # No retry path: keep every receipt and partial output for diagnosis.
            self.info.update(status="stopped", stop_reason=str(exc), failure_type=type(exc).__name__)
        finally:
            self.info["finished_at"] = utc()
            self.save()
        print(json.dumps(dict(status=self.info["status"], calls=self.info["calls"],
                              elapsed_seconds=self.info["elapsed_seconds"],
                              stop_reason=self.info["stop_reason"])), flush=True)
        return 0 if self.info["status"] == "ok" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-dir", type=Path, default=Path("../huaweicup2026/data/raw/a/official-cases/data"))
    parser.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.graph_dir.is_absolute() or args.output.is_absolute() or ".." in args.output.parts:
        parser.error("use project-relative input and an in-project output")
    if args.check_only:
        checked = preflight(args.graph_dir)
        print(json.dumps(dict(verified_files=len(checked["verified_files"]),
                              solver_commit=checked["solver_commit"], runner_commit=checked["runner_commit"])))
        return 0
    return Pilot(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
