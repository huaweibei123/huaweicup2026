"""a-q1-stage-replay-farmer 的最小运行包装（标准库 only，任务卡允许）。

用法：python run_replay.py <case-tag> <graph.json> <plan.json> <out-prefix>
参数数组、shell=False、timeout=30s；stdout/stderr/rc/墙钟写入 out-prefix.run.json。
"""
import json
import subprocess
import sys
import time
from pathlib import Path

def main():
    tag, graph, plan, prefix = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    cmd = [
        sys.executable, "-B",
        "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py",
        graph, plan,
        "--config", "data/raw/a/official/data/config.txt",
        "-o", prefix + "-result.json",
        "--trace-output", prefix + "-trace.json",
        "--log-output", prefix + ".log",
    ]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, shell=False, timeout=30)
    wall = time.perf_counter() - t0
    record = {
        "case": tag,
        "cmd": cmd,
        "exit_code": proc.returncode,
        "wall_seconds": round(wall, 4),
        "stdout": proc.stdout.decode("utf-8", errors="replace"),
        "stderr": proc.stderr.decode("utf-8", errors="replace"),
        "timeout": False,
    }
    Path(prefix + "-run.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps({k: record[k] for k in ("case", "exit_code", "wall_seconds")},
                     ensure_ascii=False))
    print("stdout tail:", record["stdout"][-300:])
    if record["stderr"]:
        print("stderr tail:", record["stderr"][-300:])

if __name__ == "__main__":
    main()
