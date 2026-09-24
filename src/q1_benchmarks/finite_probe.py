"""Reusable single-worker finite probe controller. An explicit frozen manifest owns scope.

Adapted from heavy_suffix_e0 at 08945a78250b2657ee2ecba00a6dc3ced6223fa2.
No retries, no baseline scoring, first failure stops; source receipts fail closed.
"""
from collections import Counter
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from src.q1_benchmarks import bounded_full4_e0 as h
from src.q1_benchmarks.sink_probe_e0 import resource_snapshot

HERE = "src/q1_benchmarks/finite_probe.py"
COMMON_SOURCES = ["src/q1_benchmarks/bounded_full4_e0.py", "src/q1_benchmarks/sink_probe_e0.py", "uv.lock", "pyproject.toml"]


def verify(spec):
    assert sys.version_info[:2] == (3,12), "Locked Python3.12 required"
    head = h.git("rev-parse","HEAD").decode().strip()
    if h.git("diff","--name-only",head).strip():
        raise RuntimeError("Tracked source differs from frozen runner")
    receipts=[]
    for path,commit in [(p,spec["solver_commit"]) for p in spec["algorithm_sources"]+COMMON_SOURCES]+[(p,head) for p in (HERE,spec["runner_path"],spec["manifest_path"])]:
        raw=(ROOT/path).read_bytes()
        if raw != h.git("show",f"{commit}:{path}"):
            raise RuntimeError(f"Source mismatch: {path}")
        receipts.append({"path":path,"commit":commit,"sha256":h.digest(raw)})
    manifest=h.read(ROOT/"docs/a/source-manifest.json")
    files={r["path"]:r for r in manifest["files"]}
    for path,row in files.items():
        if path.startswith("code/") or path=="data/config.txt":
            if h.sha(h.OFFICIAL/path)!=row["sha256"]:
                raise RuntimeError(f"Official source/config mismatch: {path}")
    code_hash=h.digest("".join(f"{p}\t{files[p]['sha256']}\n" for p in sorted(files) if p.startswith("code/")).encode())
    assert code_hash==manifest["official_code_hash"]
    assert h.sha(ROOT/manifest["case_archive"]["path"])==manifest["case_archive"]["sha256"]
    return head,manifest,files,receipts


def run(batch, spec):
    cells=spec["cells"]; limits=spec["timeouts_seconds"]
    start=time.perf_counter(); started_at=h.utc(); deadline=start+limits["batch"]
    head,official,files,receipts=verify(spec)
    batch.mkdir(parents=True,exist_ok=False)
    meta={"run_id":batch.name,"solver_commit":spec["solver_commit"],"runner_commit":head,"runner_path":spec["runner_path"],"source_receipts":receipts,
          "official_code_hash":official["official_code_hash"],"config_sha256":h.sha(h.OFFICIAL/"data/config.txt"),
          "input_archive_sha256":official["case_archive"]["sha256"],"environment":h.environment(),
          "runner_argv":["python","-B",spec["runner_path"],"run",batch.name],"cells":cells,"started_at":started_at,"finished_at":None,"status":"running",
          "parameters":spec["parameters"],
          "maximum_calls":spec["maximum_calls"],"timeouts_seconds":limits,
          "resource_samples":[],"resource_coordination":spec["coordination"],
          "stop_policy":"First constructor/E0/source/resource/cleanup failure stops batch; no retry; retain remaining not_run",
          "comparison_source":spec["comparison_source"]}
    meta["declaration"]={"path":spec["manifest_path"],"sha256":h.sha(ROOT/spec["manifest_path"]),"content":h.read(ROOT/spec["manifest_path"])}
    if spec.get("execution_authorization"):
        meta["execution_authorization"]=spec["execution_authorization"]
        meta["resource_coordination"] += " Execution released: " + spec["execution_authorization"]["authorization_message"]
    h.write(batch/"batch.json",meta)
    stopped=None
    def remaining(limit):
        left=deadline-time.perf_counter()
        if left<=0: raise TimeoutError(f"Batch{limits['batch']}s deadline reached")
        return min(limit,left)
    with tempfile.TemporaryDirectory(prefix="q1-probe-input-") as tmp:
        inputs=Path(tmp); t0=time.perf_counter()
        with zipfile.ZipFile(ROOT/official["case_archive"]["path"]) as z:
            for case,_ in cells:
                raw=z.read(f"data/case_{case}.json")
                assert h.digest(raw)==files[f"data/case_{case}.json"]["sha256"]
                (inputs/f"case_{case}.json").write_bytes(raw)
        meta["input_preparation_wall_seconds"]=time.perf_counter()-t0
        for case,cores in cells:
            folder=batch/"cells"/case/f"k{cores}"; folder.mkdir(parents=True)
            r={"case_id":case,"cores":cores,"status":"not_run","started_at":None,"finished_at":None,
               "graph_sha256":files[f"data/case_{case}.json"]["sha256"],"calls":{"solver":0,"E0":0,"E1":0,"E2":0},
               "artifacts":{},"failure":None,"makespan_cycles":None}
            if stopped:
                r["not_run_reason"]=stopped; h.write(folder/"run.json",r); continue
            graph=inputs/f"case_{case}.json"; plan=folder/f"case_{case}_multicore_res.json"; diag=folder/"diagnostics.json"; result=folder/"result.json"
            stage="supervisor"
            try:
                verify(spec); meta["resource_samples"].append(resource_snapshot()); r["started_at"]=h.utc(); stage="solver"
                r["solver"]=h.process([sys.executable,"-B",spec["entrypoint"],graph,"--cores",cores,"--output",plan,"--diagnostics",diag,
                    *spec["solver_extra_argv"]],folder,"solver",remaining(limits["solver"]),inputs,lambda:r["calls"].__setitem__("solver",1))
                if r["solver"]["status"]!="ok": raise h.CandidateFailure("constructor "+r["solver"]["status"])
                obj=h.read(plan); original=h.read(graph)
                assert set(obj)=={"node_to_subgraph","core_schedules"} and len(obj["core_schedules"])==cores
                assert set(obj["node_to_subgraph"])=={str(o["id"]) for o in original["ops"] if o["op"] not in {"COPY_IN","COPY_OUT"}}
                r.update(plan_sha256=h.sha(plan),diagnostics=h.read(diag),compute_coverage_checked=True)
                r["artifacts"].update(plan=h.artifact(plan),diagnostics=h.artifact(diag)); stage="E0"
                r["evaluation"]=h.process([sys.executable,"-B",h.OFFICIAL/"code/multicore_cut_evaluate_problem_1.py",graph,plan,
                    "--config",h.OFFICIAL/"data/config.txt","--output",result,"--trace-output",folder/"trace.json","--log-output",folder/"official.log"],
                    folder,"E0",remaining(limits["E0"]),inputs,lambda:r["calls"].__setitem__("E0",1))
                if r["evaluation"]["status"]!="ok": raise h.CandidateFailure("E0 "+r["evaluation"]["status"])
                out=h.read(result)
                assert out.get("scene")=="A" and out.get("num_cores")==cores and type(out.get("makespan")) in (int,float) and out["makespan"]>0
                r.update(status="ok",makespan_cycles=out["makespan"],data_movement_bytes=out["data_movement_bytes"])
                r["artifacts"].update(result=h.compress(result),trace=h.compress(folder/"trace.json"),log=h.artifact(folder/"official.log"))
            except Exception as error:
                rec=r.get("evaluation" if stage=="E0" else "solver",{})
                r.update(status="timeout" if rec.get("status")=="timeout" or isinstance(error,TimeoutError) else "failed",makespan_cycles=None,
                    failure={"stage":stage,"reason":f"{type(error).__name__}: {error}","exit_code":rec.get("exit_code"),"elapsed_seconds":rec.get("wall_seconds")})
                stopped=f"First failure {case}/k{cores}: {r['failure']['reason']}"
            finally:
                r["finished_at"]=h.utc(); h.write(folder/"run.json",r)
                print(json.dumps({"case":case,"cores":cores,"status":r["status"],"makespan":r["makespan_cycles"]}),flush=True)
    rows=[h.read(batch/"cells"/c/f"k{k}"/"run.json") for c,k in cells]
    meta.update(finished_at=h.utc(),status="stopped" if stopped else "complete",stop_reason=stopped or f"{len(cells)} declared cells complete",
                status_counts=dict(Counter(r["status"] for r in rows)),batch_wall_seconds=time.perf_counter()-start,
                actual_calls={k:sum(r["calls"][k] for r in rows) for k in ("solver","E0","E1","E2")})
    h.write(batch/"batch.json",meta)
    return 1 if stopped else 0


def export(batch):
    meta=h.read(batch/"batch.json"); cells=meta["cells"]; spec=meta["declaration"]["content"]; limits=meta["timeouts_seconds"]
    solver=meta["solver_commit"]; old_commit=meta["comparison_source"]["commit"]; old_feed=meta["comparison_source"]["feed"]
    if meta["status"]=="running": raise RuntimeError("Wait for execution to finish")
    old=json.loads(h.git("show",f"{old_commit}:{old_feed}"))
    records=[]; comparisons=[]; references=batch/"references"; references.mkdir(exist_ok=True)
    for case,cores in cells:
        previous=next(x for x in old["records"] if x["case_id"]==case and x["cores"]==cores)
        assert previous["status"]=="ok"
        folder=batch/"cells"/case/f"k{cores}"; r=h.read(folder/"run.json")
        saved={}
        for name,item in {"plan":previous["artifacts"]["plan"],"result":previous["artifacts"]["result"],"baseline":previous["baseline"]["result"]}.items():
            raw=h.git("show",f"{old_commit}:{item['path']}"); assert h.digest(raw)==item["sha256"]
            dest=references/f"bounded-{case}-{name}-{Path(item['path']).name}"; dest.write_bytes(raw); saved[name]=h.artifact(dest)
        before=json.loads(gzip.decompress((ROOT/saved["result"]["path"]).read_bytes()))
        assert before["makespan"]==previous["metrics"]["makespan_cycles"] and before["scene"]=="A" and before["num_cores"]==cores
        d=r.get("data_movement_bytes",{}); metrics={"makespan_cycles":r["makespan_cycles"],"solver_wall_seconds":r.get("solver",{}).get("wall_seconds"),
            "evaluation_wall_seconds":r.get("evaluation",{}).get("wall_seconds"),"ddr_bytes":d.get("scheduled_copy_bytes"),"extra_ddr_bytes":d.get("added_copy_bytes"),"spill_bytes":d.get("spill_added_copy_bytes")}
        rec=deepcopy(previous); rec.update(attempt_id=f"nikolastarx-{batch.name}-P1-{case}-k{cores}-r0",revision=1,run_id=batch.name,
            algorithm_id=spec["algorithm_id"],algorithm_name=spec["algorithm_name"],variant=spec["variant"],
            solver_commit=solver,status=r["status"],metrics=metrics,observed_at=r["finished_at"])
        rec["parameters"]={"cores":cores,**meta["parameters"],"selected":r.get("diagnostics",{}).get("selected"),"constructor_timeout_seconds":limits["solver"],"evaluation_timeout_seconds":limits["E0"],
            "batch_timeout_seconds":meta["timeouts_seconds"]["batch"],"candidate_limit":1,"workers":1,"stop_policy":meta["stop_policy"],"scoring_backend":"none; external E0 only"}
        rec["evaluator"]["commit"]=solver
        rec["identity"]={"graph_sha256":r["graph_sha256"],"config_sha256":meta["config_sha256"],"official_sha256":meta["official_code_hash"],"plan_sha256":r.get("plan_sha256")}
        rec["artifacts"]={k:v for k,v in r["artifacts"].items() if k!="diagnostics"}; rec["artifacts"]["run"]=h.artifact(folder/"run.json")
        rec["baseline"]=dict(previous["baseline"],result=saved["baseline"])
        p=rec["provenance"]
        p["solver"].update(source=h.source(solver,spec["entrypoint"],"main"),method=spec["method"],
            references=[f"https://github.com/{h.REPO}/blob/{solver}/{spec['documentation']}"],
            upstream=[h.source(solver,x,"construct") for x in spec["algorithm_sources"][1:]])
        p["runner"]={"source":h.source(meta["runner_commit"],meta["runner_path"],"run"),"argv":meta["runner_argv"],"working_directory":"."}; p["environment"]=meta["environment"]
        p["measurement"].update(started_at=r["started_at"],finished_at=r["finished_at"],calls=r["calls"],failure=r["failure"],
            budget={"wall_seconds":limits["solver"],"candidate_limit":1,"stop_reason":"direct construction complete" if r["status"]=="ok" else r.get("not_run_reason","first failure")},
            offline_costs=f"uv sync --locked and verified ZIP materialization ({meta['input_preparation_wall_seconds']} seconds); no training, online scorer or baseline rerun. Source/coverage audits and gzip/export outside constructor/E0 timers.")
        missing={"provenance.environment.threads":"Thread count not sampled; OMP/BLAS/MKL environment1","provenance.environment.peak_rss_bytes":"Not sampled; host memory proxy sampled before cells","provenance.measurement.seed":"Deterministic construction has no RNG"}
        for key in ("started_at","finished_at"):
            if r[key] is None: missing[f"provenance.measurement.{key}"]=r.get("not_run_reason","not started")
        if r["failure"]:
            for key in ("exit_code","elapsed_seconds"):
                if r["failure"].get(key) is None: missing[f"provenance.measurement.failure.{key}"]="No completed child receipt"
        p["missing_reasons"]=missing
        rec["notes"]=[meta["resource_coordination"],f"{len(cells)} preselected mechanism probes; not all-case quality or independent blind acceptance. No sink8 batch executed.",
            "Fresh interpreter per cell, OS caches not flushed; previous bounded04 used two workers, so timings are descriptive and cannot establish controlled speedups.",
            f"Bounded04 same-cell plan/result and singlecore originals reused from {old_commit}; no comparison or baseline evaluation."]
        records.append(rec)
        comparisons.append({"case":case,"cores":cores,"status":r["status"],**metrics,"selected":r.get("diagnostics",{}).get("selected"),
            "bounded_makespan_cycles":before["makespan"],"bounded_movement_bytes":before["data_movement_bytes"],
            "bounded_over_new":before["makespan"]/r["makespan_cycles"] if r["makespan_cycles"] else None,"bounded_source":{"commit":old_commit,"attempt_id":previous["attempt_id"],"preserved":saved},
            "diagnostics":r.get("diagnostics"),"failure":r["failure"]})
    h.write(batch/"board-feed.json",{"schema_version":1,"submission_version":1,"records":records})
    h.write(batch/"comparison.json",comparisons)
    print(json.dumps({"records":len(records),"comparisons":[{k:r[k] for k in ("case","status","makespan_cycles","bounded_makespan_cycles","bounded_over_new","extra_ddr_bytes","solver_wall_seconds","evaluation_wall_seconds")} for r in comparisons]}))
