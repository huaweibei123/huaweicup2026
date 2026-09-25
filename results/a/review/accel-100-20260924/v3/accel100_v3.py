"""Q1 加速比流水线 v3：官方单核分母（singlecore_evaluate.py）+ 多核分子（propose + 官方 E0）。

v2 的问题（队长 5811875496 纠正）：c1 分母用了 stub 随机切图 1 核执行，
不是官方基线。官方 README 第 93 行明确 `singlecore_evaluate.py` 才是单核基线。

v3 口径：
- c1 == 官方 singlecore_evaluate.py（原图全部非 COPY op 合一个子图放 core 0）直接调 CLI；
- c2..c5 == 与 v2 完全相同的候选生成协议（进程内复用 src/q1/search.py propose 逻辑，
  <=32 候选/60s 预算含内部 E0/单次 E0 30s 超时），评价用冻结官方 multicore_cut_evaluate_problem_1.py；
- 加速比 = 官方单核 makespan / cN makespan。

用法：
    python -B accel100_v3.py single 001 002 ...   # 只跑官方单核分母
    python -B accel100_v3.py sweep  017 018 ...   # 只跑多核分子（跳过已完成）
    python -B accel100_v3.py all    001 002 ...   # 两者
输出：results/a/review/accel-100-20260924/caseXXX/c1official/ 与 caseXXX/cN/。
断点续跑：c1official/summary.json 或 cN/summary.json 存在即跳过。
"""
import json
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "src" / "q1"))
sys.path.insert(0, str(ROOT / "data" / "raw" / "a" / "official" / "code"))

from prototype import (OFFICIAL, fixed_blocks, place_by_local_duration,  # noqa: E402
                       read_evaluation_config, read_scene_a_config,
                       generate_multicore_plan)
from structure import structural_partition, fuse_covers, topological  # noqa: E402
from stub_multicore_cut_and_schedule import (derive_multicore_plan,  # noqa: E402
                                             _build_op_adjacency,
                                             _contract_excluded_copy_nodes)
from evaluation_validation import validate_task_order  # noqa: E402

PY = sys.executable
DATA = ROOT / "data/raw/a/official/data"
OUT = ROOT / "results/a/review/accel-100-20260924"
EVAL = ROOT / "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py"
SINGLE = ROOT / "data/raw/a/official/code/singlecore_evaluate.py"
CONFIG = ROOT / "data/raw/a/official/data/config.txt"
CANDIDATES = 32


def write_json(path, obj):
    """Windows 偶发 PermissionError（杀软/索引器短暂锁文件）——重试后落 .tmp。"""
    data = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    for i in range(5):
        try:
            path.write_text(data, encoding="utf-8", newline="\n")
            return
        except PermissionError:
            time.sleep(0.5 * (i + 1))
    path.with_suffix(".json.tmp").write_text(data, encoding="utf-8", newline="\n")
BUDGET = 60.0
EVAL_TIMEOUT = 30
CORES = (1, 2, 3, 4, 5)

SETTINGS = None
WAITS = None


def make_plan(kind, graph, cores, seed, parent):
    """与 v2/仓库 propose 逐字一致的候选生成。"""
    if kind == "official_stub":
        return generate_multicore_plan(graph, num_cores=cores, seed=seed)
    if kind == "single":
        nodes = [op["id"] for op in graph["ops"]
                 if op["op"] not in {"COPY_IN", "COPY_OUT"}]
        return {"node_to_subgraph": {v: 0 for v in nodes},
                "core_schedules": [[0]] + [[] for _ in range(cores - 1)]}
    if kind in ("chain", "component", "fixed64"):
        plan = (fixed_blocks(graph, cores, seed, 64) if kind == "fixed64"
                else structural_partition(graph, cores, kind))
        return place_by_local_duration(graph, plan, SETTINGS, WAITS)
    plan = json.loads(json.dumps(parent))
    if kind.startswith("fuse"):
        plan, _ = fuse_covers(graph, plan, 128, kind == "fuse_protected")
        return plan
    rng = random.Random(seed)
    orders = plan["core_schedules"]
    if kind == "move":
        source = rng.choice([k for k, order in enumerate(orders) if order])
        task = rng.choice(orders[source])
        destination = rng.randrange(cores)
        orders[source].remove(task)
        orders[destination].insert(rng.randrange(len(orders[destination]) + 1), task)
    elif kind == "swap":
        choices = [k for k, order in enumerate(orders) if len(order) >= 2]
        if not choices:
            raise ValueError("No adjacent pair to swap")
        order = orders[rng.choice(choices)]
        i = rng.randrange(len(order) - 1)
        order[i], order[i + 1] = order[i + 1], order[i]
    elif kind == "split":
        view = derive_multicore_plan(graph, plan)
        choices = [t for t, nodes in view["nodes_by_subgraph"].items() if len(nodes) >= 2]
        if not choices:
            raise ValueError("No splittable Task")
        task = rng.choice(choices)
        nodes = view["nodes_by_subgraph"][task]
        eligible = sorted(view["mapping"])
        _, full = _build_op_adjacency(graph)
        _, successors = _contract_excluded_copy_nodes(eligible, full)
        local = {v: successors[v] & set(nodes) for v in nodes}
        order = topological(nodes, local)
        cut = rng.randrange(1, len(order))
        new_task = max(view["subgraph_ids"]) + 1
        for v in order[cut:]:
            plan["node_to_subgraph"][str(v)] = new_task
        for core in orders:
            if task in core:
                core.insert(core.index(task) + 1, new_task)
                break
    return plan


def run_eval(cmd, prefix, timeout):
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, capture_output=True, shell=False, timeout=timeout)
        rc = p.returncode
        err = p.stderr.decode("utf-8", errors="replace")[-400:]
    except subprocess.TimeoutExpired:
        rc, err = 124, "timeout"
    wall = time.monotonic() - t0
    Path(prefix + ".cmd.txt").write_text(
        " ".join(cmd) + "\n", encoding="utf-8", newline="\n")
    if rc != 0:
        return None, wall, rc, err
    try:
        result = json.loads(Path(prefix + "-result.json").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, wall, rc, "unreadable result: {}".format(exc)
    ms = result.get("makespan")
    return (ms if isinstance(ms, int) else None), wall, rc, ""


def singlecore(case_id):
    """官方单核基线（分母）。"""
    d = OUT / f"case{case_id}" / "c1official"
    if (d / "summary.json").exists():
        r = json.loads((d / "summary.json").read_text(encoding="utf-8"))
        return r["makespan"], -1.0
    d.mkdir(parents=True, exist_ok=True)
    graph_path = DATA / f"case_{case_id}.json"
    prefix = str(d / "singlecore")
    cmd = [PY, "-B", str(SINGLE), str(graph_path), "--config", str(CONFIG),
           "-o", prefix + "-result.json", "--trace-output", prefix + "-trace.json",
           "--log-output", prefix + ".log"]
    ms, wall, rc, err = run_eval(cmd, prefix, EVAL_TIMEOUT)
    if ms is None:
        print(f"case{case_id} c1official: FAIL rc={rc} {err}", flush=True)
        return None, wall
    write_json(d / "summary.json",
               {"case": case_id, "denominator": "official-singlecore", "makespan": ms,
                "entry": "data/raw/a/official/code/singlecore_evaluate.py",
                "wall_s": round(wall, 3), "rc": rc})
    print(f"case{case_id} c1official: makespan={ms} wall={round(wall,2)}", flush=True)
    return ms, wall


def evaluate(graph_path, plan, prefix):
    plan_path = prefix + "-plan.json"
    Path(plan_path).write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    cmd = [PY, "-B", str(EVAL), str(graph_path), plan_path,
           "--config", str(CONFIG), "-o", prefix + "-result.json",
           "--trace-output", prefix + "-trace.json",
           "--log-output", prefix + ".log"]
    ms, wall, rc, err = run_eval(cmd, prefix, EVAL_TIMEOUT)
    return (ms, plan_path) if ms is not None else (None, None)


def sweep(case_id, cores):
    """多核分子：与 v2 同一协议。"""
    d = OUT / f"case{case_id}" / f"c{cores}"
    best = d / "best_plan.json"
    summary = d / "summary.json"
    if best.exists() and summary.exists():
        r = json.loads(summary.read_text(encoding="utf-8"))
        return r["makespan"], -1, -1.0
    if best.exists() and not summary.exists():
        # 陈旧中断残留（有 best 无 summary）：视为未完成，重跑本单元；
        # 旧文件改名保留为 .stale 证据，不删除。
        for p in d.glob("*"):
            try:
                p.rename(p.with_name(p.name + ".stale"))
                print(f"case{case_id} c{cores}: stale file kept: {p.name}.stale",
                      flush=True)
            except OSError:
                pass
    d.mkdir(parents=True, exist_ok=True)
    graph_path = DATA / f"case_{case_id}.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    methods = ["official_stub", "single", "chain", "component", "fixed64",
               "fuse_protected", "fuse_free"]
    inc = None
    seen = set()
    evaluations = attempts = 0
    t0 = time.monotonic()
    while evaluations < CANDIDATES and attempts < CANDIDATES * 4:
        if time.monotonic() - t0 > BUDGET:
            break
        kind = methods.pop(0) if methods else ("split" if attempts % 8 == 0 else
                                              ("move" if attempts % 2 else "swap"))
        attempts += 1
        seed = attempts * 7919
        try:
            plan = make_plan(kind, graph, cores, seed, inc[2] if inc else None)
            validate_task_order(derive_multicore_plan(graph, plan))
        except Exception:
            continue
        key = json.dumps(plan, separators=(",", ":"))
        if key in seen:
            continue
        seen.add(key)
        evaluations += 1
        prefix = str(d / f"{attempts:03d}_{kind}")
        ms, path = evaluate(graph_path, plan, prefix)
        if ms is None:
            continue
        if inc is None or ms < inc[0]:
            inc = (ms, path, plan)
            best.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            try:
                (d / "best-result.json").write_bytes(Path(path).with_name(
                    Path(path).name.replace("-plan.json", "-result.json")).read_bytes())
            except OSError as exc:  # noqa: BLE001
                print(f"case{case_id} c{cores}: best-result copy skipped: {exc}",
                      flush=True)
    elapsed = time.monotonic() - t0
    if inc is None:
        print(f"case{case_id} c{cores}: NO-BEST evals={evaluations}", flush=True)
        return None, evaluations, elapsed
    write_json(d / "summary.json",
               {"case": case_id, "cores": cores, "makespan": inc[0],
                "evaluations": evaluations, "attempts": attempts,
                "elapsed_s": round(elapsed, 2)})
    print(f"case{case_id} c{cores}: makespan={inc[0]} evals={evaluations} "
          f"elapsed={round(elapsed,1)}", flush=True)
    return inc[0], evaluations, elapsed


def main():
    global SETTINGS, WAITS
    SETTINGS = read_evaluation_config(str(CONFIG))
    WAITS = read_scene_a_config(str(CONFIG))
    OUT.mkdir(parents=True, exist_ok=True)
    mode = sys.argv[1]
    ids = sys.argv[2:]
    if ids == ["all"]:
        ids = sorted(p.stem.replace("case_", "") for p in DATA.glob("case_*.json"))
    for case_id in ids:
        row = {"case": case_id}
        if mode in ("single", "all"):
            row["c1"], _ = singlecore(case_id)
        else:
            sp = OUT / f"case{case_id}" / "c1official" / "summary.json"
            row["c1"] = (json.loads(sp.read_text(encoding="utf-8"))["makespan"]
                         if sp.exists() else None)
        if mode in ("sweep", "all"):
            for cores in CORES[1:]:
                ms, n, el = sweep(case_id, cores)
                row[f"c{cores}"] = ms
        else:
            for cores in CORES[1:]:
                sp = OUT / f"case{case_id}" / f"c{cores}" / "summary.json"
                row[f"c{cores}"] = (json.loads(sp.read_text(encoding="utf-8"))["makespan"]
                                    if sp.exists() else None)
        base = row["c1"]
        for cores in CORES[1:]:
            if row.get(f"c{cores}") and base:
                row[f"speedup{cores}"] = round(base / row[f"c{cores}"], 4)
        write_json(OUT / f"case{case_id}-summary-v3.json", row)
        print("ROWV3:", json.dumps(row, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
