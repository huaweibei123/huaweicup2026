"""Shared heavy-component suffix probe controller; no retries or hidden scorers.

Run executes only049/k5 and088/k5, one worker,30s constructor/90s E0/300s
batch by default; explicit frozen wrappers may declare other finite cells and
batch limits. Stops at first failure. Export is read-only and reuses fixed
bounded04 and official singlecore evidence without additional evaluation.
"""
from collections import Counter
from copy import deepcopy
import argparse
import gzip
import json
from pathlib import Path
import re
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from src.q1_benchmarks import bounded_full4_e0 as h
from src.q1_benchmarks.sink_probe_e0 import resource_snapshot

SOLVER = "4c8c58866cc8ffa5a3fa468adc727f8a0800bd0f"
ENTRY = "src/q1/heavy_suffix.py"
HERE = "src/q1_benchmarks/heavy_suffix_e0.py"
OLD = "d63001eb01cc254a20bc60cae5e50b1eb1ee2808"
OLD_FEED = "results/a/q1-bounded-matrix-20260924/20260924T1459Z-bounded400/board-feed.json"
CELLS = [("049",5),("088",5)]
RESULT_ROOT = ROOT / "results/a/q1-heavy-suffix-20260924"
DEPS = [ENTRY,"src/q1/sink_peel.py","src/q1/bounded_tasks.py","src/q1/tree_frontier.py","src/q1/component_pack.py",
        "src/q1_benchmarks/bounded_full4_e0.py","src/q1_benchmarks/sink_probe_e0.py","uv.lock","pyproject.toml"]


def verify(extra_sources=()):
    assert sys.version_info[:2] == (3,12), "Locked Python3.12 required"
    head = h.git("rev-parse","HEAD").decode().strip()
    if h.git("diff","--name-only",head).strip():
        raise RuntimeError("Tracked source differs from frozen runner")
    receipts=[]
    for path,commit in [(p,SOLVER) for p in DEPS]+[(p,head) for p in (HERE,*extra_sources)]:
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


def run(batch, *, cells=CELLS, batch_seconds=300, run_source=HERE, extra_sources=(), declaration=None, coordination=None):
    start=time.perf_counter(); started_at=h.utc(); deadline=start+batch_seconds
    head,official,files,receipts=verify(extra_sources)
    batch.mkdir(parents=True,exist_ok=False)
    meta={"run_id":batch.name,"solver_commit":SOLVER,"runner_commit":head,"runner_path":run_source,"source_receipts":receipts,
          "official_code_hash":official["official_code_hash"],"config_sha256":h.sha(h.OFFICIAL/"data/config.txt"),
          "input_archive_sha256":official["case_archive"]["sha256"],"environment":h.environment(),
          "runner_argv":["python","-B",run_source,"run",batch.name],"cells":cells,"started_at":started_at,"finished_at":None,"status":"running",
          "parameters":{"dominant_percent":80,"max_rounds":64,"max_sinks":64},
          "maximum_calls":{"solver":len(cells),"E0":len(cells),"E1":0,"E2":0},"timeouts_seconds":{"solver":30,"E0":90,"batch":batch_seconds},
          "resource_samples":[],"resource_coordination":coordination or "Parent confirmed P2/P3 currently0 real scores and granted049/088 window; one worker, no exclusive-host claim, no cloud/GPU",
          "stop_policy":"First constructor/E0/source/resource/cleanup failure stops batch; no retry; retain remaining not_run",
          "comparison_source":{"commit":OLD,"feed":OLD_FEED,"scope":"Exact bounded04 same-cell plans/results and official singlecore originals; no baseline calls"}}
    if declaration is not None: meta["declaration"]=declaration
    h.write(batch/"batch.json",meta)
    stopped=None
    def remaining(limit):
        left=deadline-time.perf_counter()
        if left<=0: raise TimeoutError(f"Batch{batch_seconds}s deadline reached")
        return min(limit,left)
    with tempfile.TemporaryDirectory(prefix="q1-heavy-input-") as tmp:
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
                verify(extra_sources); meta["resource_samples"].append(resource_snapshot()); r["started_at"]=h.utc(); stage="solver"
                r["solver"]=h.process([sys.executable,"-B",ENTRY,graph,"--cores",cores,"--output",plan,"--diagnostics",diag,
                    "--dominant-percent",80,"--max-rounds",64,"--max-sinks",64],folder,"solver",remaining(30),inputs,lambda:r["calls"].__setitem__("solver",1))
                if r["solver"]["status"]!="ok": raise h.CandidateFailure("constructor "+r["solver"]["status"])
                obj=h.read(plan); original=h.read(graph)
                assert set(obj)=={"node_to_subgraph","core_schedules"} and len(obj["core_schedules"])==cores
                assert set(obj["node_to_subgraph"])=={str(o["id"]) for o in original["ops"] if o["op"] not in {"COPY_IN","COPY_OUT"}}
                r.update(plan_sha256=h.sha(plan),diagnostics=h.read(diag),compute_coverage_checked=True)
                r["artifacts"].update(plan=h.artifact(plan),diagnostics=h.artifact(diag)); stage="E0"
                r["evaluation"]=h.process([sys.executable,"-B",h.OFFICIAL/"code/multicore_cut_evaluate_problem_1.py",graph,plan,
                    "--config",h.OFFICIAL/"data/config.txt","--output",result,"--trace-output",folder/"trace.json","--log-output",folder/"official.log"],
                    folder,"E0",remaining(90),inputs,lambda:r["calls"].__setitem__("E0",1))
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
    meta=h.read(batch/"batch.json"); cells=meta["cells"]
    if meta["status"]=="running": raise RuntimeError("Wait for execution to finish")
    old=json.loads(h.git("show",f"{OLD}:{OLD_FEED}"))
    records=[]; comparisons=[]; references=batch/"references"; references.mkdir(exist_ok=True)
    for case,cores in cells:
        previous=next(x for x in old["records"] if x["case_id"]==case and x["cores"]==cores)
        assert previous["status"]=="ok"
        folder=batch/"cells"/case/f"k{cores}"; r=h.read(folder/"run.json")
        saved={}
        for name,item in {"plan":previous["artifacts"]["plan"],"result":previous["artifacts"]["result"],"baseline":previous["baseline"]["result"]}.items():
            raw=h.git("show",f"{OLD}:{item['path']}"); assert h.digest(raw)==item["sha256"]
            dest=references/f"bounded-{case}-{name}-{Path(item['path']).name}"; dest.write_bytes(raw); saved[name]=h.artifact(dest)
        before=json.loads(gzip.decompress((ROOT/saved["result"]["path"]).read_bytes()))
        assert before["makespan"]==previous["metrics"]["makespan_cycles"] and before["scene"]=="A" and before["num_cores"]==cores
        d=r.get("data_movement_bytes",{}); metrics={"makespan_cycles":r["makespan_cycles"],"solver_wall_seconds":r.get("solver",{}).get("wall_seconds"),
            "evaluation_wall_seconds":r.get("evaluation",{}).get("wall_seconds"),"ddr_bytes":d.get("scheduled_copy_bytes"),"extra_ddr_bytes":d.get("added_copy_bytes"),"spill_bytes":d.get("spill_added_copy_bytes")}
        rec=deepcopy(previous); rec.update(attempt_id=f"nikolastarx-{batch.name}-P1-{case}-k{cores}-r0",revision=1,run_id=batch.name,
            algorithm_id="q1-heavy-component-suffix",algorithm_name="P1 dominant-component suffix waves",variant="dominant-pipe-suffix-waves",
            solver_commit=SOLVER,status=r["status"],metrics=metrics,observed_at=r["finished_at"])
        rec["parameters"]={"cores":cores,**meta["parameters"],"selected":r.get("diagnostics",{}).get("selected"),"constructor_timeout_seconds":30,"evaluation_timeout_seconds":90,
            "batch_timeout_seconds":meta["timeouts_seconds"]["batch"],"candidate_limit":1,"workers":1,"stop_policy":meta["stop_policy"],"scoring_backend":"none; external E0 only"}
        rec["evaluator"]["commit"]=SOLVER
        rec["identity"]={"graph_sha256":r["graph_sha256"],"config_sha256":meta["config_sha256"],"official_sha256":meta["official_code_hash"],"plan_sha256":r.get("plan_sha256")}
        rec["artifacts"]={k:v for k,v in r["artifacts"].items() if k!="diagnostics"}; rec["artifacts"]["run"]=h.artifact(folder/"run.json")
        rec["baseline"]=dict(previous["baseline"],result=saved["baseline"])
        p=rec["provenance"]
        p["solver"].update(source=h.source(SOLVER,ENTRY,"main"),method="Fixed80-percent dominant compute-pipe component trigger; bounded sink-exclusive suffix peeling; whole minor components placed in final wave; per-pipe greedy packet placement. Builds sink/bounded fallback first; no scoring/search.",
            references=[f"https://github.com/{h.REPO}/blob/{SOLVER}/docs/a/Q1_HEAVY_SUFFIX.md"],upstream=[h.source(SOLVER,x,"construct") for x in DEPS[1:5]])
        p["runner"]={"source":h.source(meta["runner_commit"],meta["runner_path"],"run"),"argv":meta["runner_argv"],"working_directory":"."}; p["environment"]=meta["environment"]
        p["measurement"].update(started_at=r["started_at"],finished_at=r["finished_at"],calls=r["calls"],failure=r["failure"],
            budget={"wall_seconds":30,"candidate_limit":1,"stop_reason":"direct construction complete" if r["status"]=="ok" else r.get("not_run_reason","first failure")},
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
            f"Bounded04 same-cell plan/result and singlecore originals reused from {OLD}; no comparison or baseline evaluation."]
        records.append(rec)
        comparisons.append({"case":case,"cores":cores,"status":r["status"],**metrics,"selected":r.get("diagnostics",{}).get("selected"),
            "bounded_makespan_cycles":before["makespan"],"bounded_movement_bytes":before["data_movement_bytes"],
            "bounded_over_new":before["makespan"]/r["makespan_cycles"] if r["makespan_cycles"] else None,"bounded_source":{"commit":OLD,"attempt_id":previous["attempt_id"],"preserved":saved},
            "diagnostics":r.get("diagnostics"),"failure":r["failure"]})
    h.write(batch/"board-feed.json",{"schema_version":1,"submission_version":1,"records":records})
    h.write(batch/"comparison.json",comparisons)
    print(json.dumps({"records":len(records),"comparisons":[{k:r[k] for k in ("case","status","makespan_cycles","bounded_makespan_cycles","bounded_over_new","extra_ddr_bytes","solver_wall_seconds","evaluation_wall_seconds")} for r in comparisons]}))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("action",choices=("run","export")); p.add_argument("run_id"); a=p.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+",a.run_id): p.error("valid run_id required")
    raise SystemExit(run(RESULT_ROOT/a.run_id) if a.action=="run" else export(RESULT_ROOT/a.run_id))
