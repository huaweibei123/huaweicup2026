"""Budgeted P1-only Windows regression under a kill-on-close process-tree job."""
from __future__ import annotations
import argparse
import ctypes as ct
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))


def save(path, value):
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def child(stage, private):
    gate = private / (stage + ".gate")
    until = time.perf_counter() + 15
    while not gate.exists():
        if time.perf_counter() >= until:
            raise TimeoutError("controller did not assign job/open gate")
        time.sleep(.01)
    from research.a.e2_search import E2BatchEvaluator, E2Evaluator, _native
    from research.a.e2_search.tests.test_search import SearchTest, simple_graph, PLAN
    from research.a.e2_search.tests.test_resources import ResourceTest
    from src.eval_exact import read_config
    from unittest.mock import patch
    counts = dict(inputs_consumed=0, completed_records=0, direct_e2=0, direct_e0=0)
    records = []
    original = E2BatchEvaluator.evaluate_batch
    def counted(self, plans, *args, **kwargs):
        def incoming():
            for plan in plans:
                counts["inputs_consumed"] += 1
                yield plan
        delegate = original(self, incoming(), *args, **kwargs)
        try:
            for row in delegate:
                counts["completed_records"] += 1
                records.append(row)
                yield row
        finally:
            delegate.close()
    E2BatchEvaluator.evaluate_batch = counted
    receipt = dict(stage=stage, counts=counts, records=records,
                   monotonic=vars(time.get_clock_info("monotonic")),
                   perf_counter=vars(time.get_clock_info("perf_counter")))
    code = 0
    try:
        if stage != "probe":
            names = {
                "resources": ["test_actual_host_peak_and_high_resolution_timeout",
                              "test_requested_rss_limit_never_silently_ignores_missing_telemetry",
                              "test_windows_counter_field_widths_and_peak_not_current"],
                "pool_order": ["test_pool_order_error_recycling_and_cleanup"],
                "pool_cancel": ["test_pool_timeout_crash_cancellation_and_stream_bound"],
            }[stage]
            cls = ResourceTest if stage == "resources" else SearchTest
            result = unittest.TextTestRunner(verbosity=2, failfast=True).run(unittest.TestSuite(cls(n) for n in names))
            receipt.update(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors))
            code = 0 if result.wasSuccessful() else 1
        else:
            config = read_config(ROOT / "data/raw/a/official/data/config.txt")
            with E2BatchEvaluator(simple_graph(), workers=1, recycle_peak_rss_bytes=1) as pool:
                rss = list(pool.evaluate_batch([PLAN, PLAN], **config))
            assert all(r["worker_peak_rss_bytes"] > 0 and r["recycle_reason"] == "peak_rss_threshold" for r in rss)
            assert rss[0]["worker_pid"] != rss[1]["worker_pid"]
            with E2BatchEvaluator(simple_graph(), workers=1, timeout_seconds=1e-12) as pool:
                tiny = list(pool.evaluate_batch([PLAN]*8, **config))
                assert all(r["status"] == "timeout" for r in tiny)
                pool._timeout = 30
                normal = list(pool.evaluate_batch([PLAN], **config))[0]
            assert normal["route"] == "native" and normal["status"] == "ok"
            with patch.object(_native, "get_lib", side_effect=OSError("injected missing native library")):
                counts["direct_e2"] += 1
                fallback = E2Evaluator(simple_graph()).evaluate_record(PLAN, **config)
            assert fallback["route"] == "e1_fallback"
            from src.eval_exact._official import load_problem1_bundle
            oracle, _ = load_problem1_bundle("_windows_fix_synthetic_e0")
            counts["direct_e0"] += 1
            truth = oracle.evaluate_scene_a(simple_graph(), PLAN, **config)
            assert normal["makespan"] == fallback["makespan"] == truth["makespan"]
            receipt.update(rss=rss, tiny=tiny, normal=normal, fallback=fallback,
                           graph=simple_graph(), plan=PLAN, config=config, truth=truth,
                           limitation="Missing-library route uses explicit fault injection; no library files moved.")
    except BaseException as error:
        code = 1
        receipt.update(error_type=type(error).__name__, message=str(error))
        raise
    finally:
        receipt["exit_code"] = code
        save(private / (stage + ".child.json"), receipt)
    return code


class BasicLimit(ct.Structure):
    _fields_ = [("p_time",ct.c_int64),("j_time",ct.c_int64),("flags",ct.c_uint32),
                ("min_ws",ct.c_size_t),("max_ws",ct.c_size_t),("active_limit",ct.c_uint32),
                ("affinity",ct.c_size_t),("priority",ct.c_uint32),("scheduling",ct.c_uint32)]
class IO(ct.Structure):
    _fields_ = [(name,ct.c_uint64) for name in ("r_op","w_op","o_op","r_byte","w_byte","o_byte")]
class Extended(ct.Structure):
    _fields_ = [("basic",BasicLimit),("io",IO)]+[(name,ct.c_size_t) for name in ("p_limit","j_limit","p_peak","j_peak")]
class Accounting(ct.Structure):
    _fields_ = [(name,ct.c_int64) for name in ("u","k","period_u","period_k")]+[(name,ct.c_uint32) for name in ("faults","total","active","terminated")]


def controlled(stage, private, deadline):
    k = ct.WinDLL("kernel32",use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([ct.c_void_p,ct.c_wchar_p],ct.c_void_p),
        "SetInformationJobObject": ([ct.c_void_p,ct.c_int,ct.c_void_p,ct.c_uint32],ct.c_int),
        "AssignProcessToJobObject": ([ct.c_void_p,ct.c_void_p],ct.c_int),
        "QueryInformationJobObject": ([ct.c_void_p,ct.c_int,ct.c_void_p,ct.c_uint32,ct.c_void_p],ct.c_int),
        "TerminateJobObject": ([ct.c_void_p,ct.c_uint32],ct.c_int),
        "CloseHandle": ([ct.c_void_p],ct.c_int),
    }
    for name,(args,restype) in signatures.items():
        fn=getattr(k,name);fn.argtypes=args;fn.restype=restype
    job=k.CreateJobObjectW(None,None)
    if not job: raise ct.WinError(ct.get_last_error())
    limits=Extended();limits.basic.flags=0x2000
    process=None
    start=time.perf_counter()
    record=dict(stage=stage, job_kill_on_close=True, wall_scope="spawn, imports, IPC, tests, worker cleanup; preparation charged to global deadline")
    try:
        if not k.SetInformationJobObject(job,9,ct.byref(limits),ct.sizeof(limits)):
            raise ct.WinError(ct.get_last_error())
        with (private/(stage+".stdout")).open("wb") as stdout, (private/(stage+".stderr")).open("wb") as stderr:
            process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"--child",stage,"--private",str(private)],
                cwd=ROOT,stdout=stdout,stderr=stderr,env=dict(os.environ,PYTHONIOENCODING="utf-8"))
            record["pid"]=process.pid
            if not k.AssignProcessToJobObject(job,int(process._handle)):
                process.kill();process.wait(timeout=5)
                raise ct.WinError(ct.get_last_error())
            save(private/(stage+".gate"),dict(job_assigned=True,pid=process.pid))
            remaining=(deadline-datetime.now(timezone.utc)).total_seconds()-10
            if remaining<=0: raise TimeoutError("no remaining cleanup-safe budget")
            try:
                record["returncode"]=process.wait(timeout=min(90,remaining))
            except subprocess.TimeoutExpired:
                record["status"]="outer_timeout"
                k.TerminateJobObject(job,137)
                process.wait(timeout=5)
        accounting=Accounting()
        if not k.QueryInformationJobObject(job,1,ct.byref(accounting),ct.sizeof(accounting),None):
            raise ct.WinError(ct.get_last_error())
        record["active_before_cleanup"]=accounting.active
        record["total_job_processes"]=accounting.total
        if accounting.active:
            record["forced_descendant_cleanup"]=True
            k.TerminateJobObject(job,137)
        for _ in range(100):
            if not k.QueryInformationJobObject(job,1,ct.byref(accounting),ct.sizeof(accounting),None):
                raise ct.WinError(ct.get_last_error())
            if not accounting.active: break
            time.sleep(.05)
        record["active_after_cleanup"]=accounting.active
        if accounting.active: record["status"]="cleanup_failed"
    except Exception as error:
        record.update(status="controller_error",error_type=type(error).__name__,message=str(error))
        if process is not None and process.poll() is None:
            k.TerminateJobObject(job,137)
            process.wait(timeout=5)
    finally:
        k.CloseHandle(job)
        record["wall_seconds"]=time.perf_counter()-start
        save(private/(stage+".controller.json"),record)
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private",type=Path,required=True)
    p.add_argument("--child",choices=["resources","pool_order","pool_cancel","probe"])
    a=p.parse_args()
    if a.child: return child(a.child,a.private)
    t0=datetime.fromisoformat((a.private/"T0.txt").read_text(encoding="utf-8-sig").strip())
    deadline=t0+timedelta(seconds=600)
    ledger=dict(t0=t0.isoformat(),deadline=deadline.isoformat(),head=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
                reserved_e2=0,reserved_truth_possible=0,reserved_direct_e0=0,stages=[],formal_candidates=0,formal_e0=0)
    for stage,e2,truth,direct,control in [("resources",12,12,0,2),("pool_order",8,8,0,0),("pool_cancel",6,6,0,0),("probe",12,13,1,0)]:
        if (deadline-datetime.now(timezone.utc)).total_seconds()<20:
            ledger["stop"]="global_deadline_no_stage_started";break
        ledger["reserved_e2"]+=e2;ledger["reserved_truth_possible"]+=truth;ledger["reserved_direct_e0"]+=direct
        assert ledger["reserved_e2"]<=48 and ledger["reserved_truth_possible"]<=64 and ledger["reserved_direct_e0"]<=4
        ledger["stages"].append(dict(stage=stage,reserved_e2=e2,reserved_truth_possible=truth,reserved_direct_e0=direct,control_injection_records=control))
        save(a.private/"ledger.json",ledger)
        result=controlled(stage,a.private,deadline)
        ledger["stages"][-1]["controller"]=result
        save(a.private/"ledger.json",ledger)
        print(stage,json.dumps(result),flush=True)
        if result.get("returncode")!=0 or result.get("status") or result.get("forced_descendant_cleanup"):
            ledger["stop"]="first_failure";break
    ledger["end"]=datetime.now(timezone.utc).isoformat()
    ledger["total_wall_since_t0"]=(datetime.now(timezone.utc)-t0).total_seconds()
    save(a.private/"ledger.json",ledger)
    return 1 if ledger.get("stop") else 0


if __name__=="__main__":
    raise SystemExit(main())
