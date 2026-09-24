"""One predeclared diagnostic attempt per prior E0 timeout; first failure stops.

Rebuild with the same solver, demand exact old plan SHA, then allow external E0
180 seconds. This is a separate run, not a retry hidden in the original batch.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks import bounded_full4_e0 as h

HERE = "src/q1_benchmarks/bounded_timeout_e0.py"
MANIFEST = "src/q1_benchmarks/bounded_timeout_batch.json"
RESULT_ROOT = ROOT / "results/a/q1-bounded-timeout-20260924"


def run(batch):
    begin = time.perf_counter()
    cfg = h.read(ROOT / MANIFEST)
    head, official, files = h.verify()
    assert cfg["solver_commit"] == h.SOLVER and cfg["workers"] == 1
    assert 0 < len(cfg["cells"]) <= 6
    for p in (HERE, MANIFEST):
        if (ROOT / p).read_bytes() != h.git("show", f"{head}:{p}"):
            raise RuntimeError("Controller/manifest not frozen")
    prior_batch = json.loads(h.git("show", f"{cfg['previous_commit']}:{cfg['previous_batch']}/batch.json"))
    assert prior_batch["status"] == "complete_with_candidate_failures"
    declared = {(c["case_id"], c["cores"]) for c in cfg["cells"]}
    prior_failures = set()
    for case, cores in prior_batch["cells"]:
        r = json.loads(h.git("show", f"{cfg['previous_commit']}:{cfg['previous_batch']}/cells/{case}/k{cores}/run.json"))
        if r["status"] == "ok":
            continue
        assert r["status"] == "timeout" and r["failure"]["stage"] == "E0"
        assert r["solver"]["status"] == "ok" and r["evaluation"]["cleanup_confirmed"] is True
        prior_failures.add((case, cores))
    assert declared == prior_failures
    for c in cfg["cells"]:
        prior = json.loads(h.git("show", f"{cfg['previous_commit']}:{c['old_run_path']}"))
        assert prior["plan_sha256"] == c["old_plan_sha256"]
        assert h.digest(h.git("show", f"{cfg['previous_commit']}:{prior['artifacts']['plan']['path']}")) == c["old_plan_sha256"]
    batch.mkdir(parents=True, exist_ok=False)
    deadline = begin + cfg["batch_timeout_seconds"]
    meta = {"run_id": batch.name, "solver_commit": h.SOLVER, "runner_commit": head, "runner_path": HERE,
            "runner_argv": ["python", "-B", HERE, batch.name], "manifest": cfg, "environment": h.environment(),
            "official_code_hash": official["official_code_hash"], "config_sha256": h.sha(h.OFFICIAL / "data/config.txt"),
            "started_at": h.utc(), "finished_at": None, "status": "running", "resource_samples": []}
    h.write(batch / "batch.json", meta)
    stop = None
    def guard():
        if h.git("diff", "--name-only", head).strip():
            raise RuntimeError("Tracked source differs from frozen runner")
        h.verify()
        raw = subprocess.check_output(["vm_stat"]).decode()
        size = int(re.search(r"page size of (\d+) bytes", raw).group(1))
        counters = {a.strip(): int(b) for a,b in re.findall(r"([^\n:]+):\s+(\d+)\.", raw)}
        available = size * sum(counters.get(k,0) for k in ("Pages free", "Pages inactive", "Pages speculative"))
        busy = 0
        for line in subprocess.check_output(["ps", "-axo", "pid=,pcpu=,command="]).decode().splitlines():
            parts = line.strip().split(None,2)
            if len(parts) == 3 and int(parts[0]) != os.getpid() and float(parts[1]) >= 25 and "huaweicup2026" in parts[2] and batch.name not in parts[2]:
                busy += 1
        meta["resource_samples"].append({"utc":h.utc(), "available_memory_estimate_bytes":available,"other_busy_project_processes":busy})
        if available < cfg["minimum_available_memory_bytes"] or busy > cfg["maximum_other_busy_project_processes"]:
            raise RuntimeError("Resource guard: stop dispatch and coordinate")
    def remaining(limit):
        left = deadline - time.perf_counter()
        if left <= 0:
            raise TimeoutError("Whole-batch deadline")
        return min(limit,left)
    with tempfile.TemporaryDirectory(prefix="q1-bounded-timeout-input-") as tmp:
        inputs = Path(tmp)
        t0 = time.perf_counter()
        with zipfile.ZipFile(ROOT / official["case_archive"]["path"]) as z:
            for case in sorted({c["case_id"] for c in cfg["cells"]}):
                raw = z.read(f"data/case_{case}.json")
                assert h.digest(raw) == files[f"data/case_{case}.json"]["sha256"]
                (inputs / f"case_{case}.json").write_bytes(raw)
        meta["input_preparation_wall_seconds"] = time.perf_counter() - t0
        for c in cfg["cells"]:
            case, cores = c["case_id"], c["cores"]
            folder = batch / "cells" / case / f"k{cores}"
            folder.mkdir(parents=True, exist_ok=False)
            r = {"case_id":case, "cores":cores,"status":"not_run","started_at":None,"finished_at":None,
                 "graph_sha256":files[f"data/case_{case}.json"]["sha256"],"makespan_cycles":None,"failure":None,
                 "calls":{"solver":0,"E0":0,"E1":0,"E2":0},"artifacts":{},"prior_attempt":c,"plan_bytes_equal":None}
            if stop:
                r["not_run_reason"] = stop
                h.write(folder / "run.json",r)
                continue
            graph = inputs / f"case_{case}.json"
            plan, diag, result = folder / f"case_{case}_multicore_res.json", folder / "diagnostics.json", folder / "result.json"
            stage = "supervisor"
            try:
                guard()
                r["started_at"] = h.utc()
                stage = "solver"
                r["solver"] = h.process([sys.executable,"-B",h.SOLVER_PATH,graph,"--output",plan,"--cores",cores,
                    "--packet-factor",4,"--trigger-ops",4096,"--chunk-ops",1024,"--diagnostics",diag],folder,"solver",remaining(30),inputs,lambda:r["calls"].__setitem__("solver",1))
                if r["solver"]["status"] != "ok":
                    raise h.CandidateFailure("Constructor " + r["solver"]["status"])
                assert set(h.read(plan)) == {"node_to_subgraph","core_schedules"}
                r["plan_sha256"] = h.sha(plan)
                r["artifacts"].update(plan=h.artifact(plan), diagnostics=h.artifact(diag))
                r["diagnostics"] = h.read(diag)
                r["plan_bytes_equal"] = r["plan_sha256"] == c["old_plan_sha256"]
                stage = "plan_identity"
                if not r["plan_bytes_equal"]:
                    raise RuntimeError("Reconstructed plan SHA differs; do not evaluate")
                stage = "E0"
                r["evaluation"] = h.process([sys.executable,"-B",h.OFFICIAL / "code/multicore_cut_evaluate_problem_1.py",graph,plan,
                    "--config",h.OFFICIAL / "data/config.txt","--output",result,"--trace-output",folder / "trace.json","--log-output",folder / "official.log"],
                    folder,"E0",remaining(180),inputs,lambda:r["calls"].__setitem__("E0",1))
                if r["evaluation"]["status"] != "ok":
                    raise h.CandidateFailure("E0 " + r["evaluation"]["status"])
                obj = h.read(result)
                assert obj.get("scene") == "A" and obj.get("num_cores") == cores
                assert type(obj.get("makespan")) in (int,float) and obj["makespan"] > 0
                r.update(status="ok",makespan_cycles=obj["makespan"],data_movement_bytes=obj["data_movement_bytes"])
                r["artifacts"].update(result=h.compress(result),trace=h.compress(folder / "trace.json"),log=h.artifact(folder / "official.log"))
            except Exception as error:
                receipt = r.get("evaluation" if stage == "E0" else "solver",{})
                r.update(status="timeout" if receipt.get("status") == "timeout" or isinstance(error,TimeoutError) else "failed",makespan_cycles=None,
                    failure_class="candidate" if isinstance(error,h.CandidateFailure) and receipt.get("cleanup_confirmed") is True else "supervisor",
                    failure={"stage":stage,"reason":f"{type(error).__name__}: {error}","exit_code":receipt.get("exit_code"),"elapsed_seconds":receipt.get("wall_seconds")})
                stop = f"first new failure: {case}/k{cores} {r['failure']['reason']}"
            finally:
                r["finished_at"] = h.utc()
                h.write(folder / "run.json",r)
                print(json.dumps({"case":case,"cores":cores,"status":r["status"],"makespan":r["makespan_cycles"],"plan_bytes_equal":r["plan_bytes_equal"]}),flush=True)
    rows = [h.read(batch / "cells" / c["case_id"] / f"k{c['cores']}" / "run.json") for c in cfg["cells"]]
    meta.update(finished_at=h.utc(),status="stopped" if stop else "complete",stop_reason=stop or "all declared diagnostics complete",
                status_counts=dict(Counter(r["status"] for r in rows)),actual_calls={k:sum(r["calls"][k] for r in rows) for k in ("solver","E0","E1","E2")},
                batch_wall_seconds=time.perf_counter()-begin)
    h.write(batch / "batch.json",meta)
    return 1 if stop else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_id")
    args = p.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+",args.run_id):
        p.error("valid run_id required")
    raise SystemExit(run(RESULT_ROOT / args.run_id))
