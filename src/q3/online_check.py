"""Three-call online-path check with an external solver clock; no retry/search."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from .construct import ROOT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    t0 = time.perf_counter()
    utc = datetime.now(timezone.utc).isoformat()
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    baseline = ROOT / "results/a/q3-nikolastarx/pilot-20260924"
    pilot = json.loads((baseline / "run.json").read_text())
    selections = json.loads((baseline / "best/manifest.json").read_text())["plans"]
    records = []
    status = {"status": "running", "t0_utc": utc, "records": records,
              "formal_e0_limit": 3, "workers": 1, "call_timeout_seconds": 30,
              "outer_limit_seconds": 120, "stop_launch_after_seconds": 90,
              "baseline_run_sha256": digest(baseline / "run.json"),
              "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "command": ["python", "-m", "src.q3.online_check", str(a.output)],
              "python": sys.version}
    paths = list((ROOT / "src/q3").glob("*.py")) + list((ROOT / "data/raw/a/official/code").glob("*.py"))
    paths += [ROOT / "uv.lock", ROOT / "data/raw/a/official/data/config.txt"]
    paths += [ROOT / f"data/raw/a/official/data/case_{c}.json" for c in ("008", "044", "080")]
    status["source_input_sha256"] = {str(p.relative_to(ROOT)): digest(p) for p in paths}

    def save():
        status["elapsed_seconds"] = time.perf_counter() - t0
        (out / "run.json").write_text(json.dumps(status, indent=2) + "\n")

    save()
    try:
        for case in ("008", "044", "080"):
            if time.perf_counter() - t0 >= 90:
                raise TimeoutError("no new evaluation after T0+90s")
            item = {"case": case, "e0_calls_reserved": 1, "status": "reserved"}
            records.append(item)
            save()
            plan = out / f"case_{case}_multicore_res.json"
            evidence = out / f"case_{case}-evidence"
            command = [sys.executable, "-m", "src.q3.solve",
                       str(ROOT / f"data/raw/a/official/data/case_{case}.json"), "--cores", "4",
                       "-o", str(plan), "--evidence", str(evidence)]
            start = time.perf_counter()
            try:
                r = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                                   timeout=min(30, 90 - (time.perf_counter() - t0)))
            except subprocess.TimeoutExpired as e:
                (out / f"case_{case}.stdout.txt").write_bytes(e.stdout or b"")
                (out / f"case_{case}.stderr.txt").write_bytes(e.stderr or b"")
                item.update(status="timeout", solver_process_wall_seconds=time.perf_counter()-start)
                raise
            item["solver_process_wall_seconds"] = time.perf_counter() - start
            (out / f"case_{case}.stdout.txt").write_text(r.stdout)
            (out / f"case_{case}.stderr.txt").write_text(r.stderr)
            if r.returncode:
                item["status"] = "error"
                raise RuntimeError(f"case {case}: solver exited {r.returncode}; see stderr")
            item.update(json.loads(r.stdout))
            reference = next(s for s in selections if s["case"] == case)
            old = next(r for r in pilot["records"] if r["case"] == case and r["problem"] == 3
                       and r["strategy"] == reference["strategy"] and not r["repeat"])
            item["same_plan_as_pilot_selected"] = digest(plan) == old["plan_sha256"]
            item["same_full_result_as_pilot"] = digest(evidence / "result.json.gz") == old["result_sha256"]
            if not item["same_plan_as_pilot_selected"] or not item["same_full_result_as_pilot"]:
                item["status"] = "identity_mismatch"
                raise AssertionError(f"case {case}: plan/full result changed; no retries")
            item["status"] = "ok"
            save()
        status["status"] = "complete"
        lines = ["# Q3 在线路径检查", "", f"实测代码：{status['head']}。T0：{utc}。", "",
                 "固定结构规则选一个候选，在线原版E0成功后输出正式计划；不做事后候选比较。",
                 "计时为外层子进程启动至退出，覆盖读取、import、分析、构造、E0、诊断及计划落盘。", "",
                 "| case | 在线策略 | Makespan cycles | 完整solver wall ms | 与旧plan/full E0相同 |",
                 "| --- | --- | ---: | ---: | --- |"]
        for r in records:
            lines.append(f"| {r['case']} | {r['strategy']} | {r['makespan']} | "
                         f"{r['solver_process_wall_seconds']*1000:.2f} | 是/是 |")
        lines += ["", "3次正式P3，全部成功，无额外外部E0；完整E0结果与上一批同计划逐字节一致。",
                  "本轮只是已见开发图的路径检查，不是独立泛化/全用例/独立平台验收。",
                  "每图仅一次，非独占主机，不把单次耗时当稳定尾延迟；没有E2或云资源。",
                  "旧17次批次不重写；新3次单独计账，累计20次正式E0。程序失败会停止而不输出合法性标签。",
                  "策略由首批结构证据启发，尚无普适收益证明；没有假称文件名无分支就等于无开发集偏差。",
                  "", "复现：python -m src.q3.online_check results/a/q3-nikolastarx/NEW_DIRECTORY", ""]
        (out / "REPORT.md").write_text("\n".join(lines))
        if time.perf_counter() - t0 > 120:
            status["status"] = "completed_over_outer_budget"
        save()
    except Exception as e:
        status["status"] = "stopped_on_failure"
        status["error"] = f"{type(e).__name__}: {e}"
        save()
        raise
    print(json.dumps({"status": status["status"], "reserved_e0_calls": len(records),
                      "elapsed_seconds": status["elapsed_seconds"]}))


if __name__ == "__main__":
    main()
