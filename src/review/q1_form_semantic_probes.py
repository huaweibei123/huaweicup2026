"""Independent, bounded Q1 probes; official files are never changed.

Synthetic inputs test mechanisms, not contest-wide solver quality. A Python
profile hook observes Step2 returns, then an uninstrumented run and official CLI
verify that observation has not changed the result. No timing claims are made.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "data/raw/a/official/code"
CONFIG = ROOT / "data/raw/a/official/data/config.txt"
sys.dont_write_bytecode = True
sys.path.insert(0, str(CODE))
import multicore_cut_evaluate_problem_1 as p1
from evaluation_validation import read_evaluation_config
from schedule_step1 import step1_schedule
from schedule_step2 import step2_spill_insertion


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tensor_graph():
    size = 262144
    graph = {
        "ops": [{"id": i, "op": "COPY_IN" if i == 1 else "CONV",
                 "pipe": "PIPE_MTE2" if i == 1 else "PIPE_M",
                 "cycles": 0 if i == 1 else 4} for i in range(1, 9)],
        "tensors": [{"id": 10001+i, "pos": "DDR" if i == 0 else "L1",
                     "size": size} for i in range(9)],
    }
    edges = [(10001,1),(1,10002),(10002,2),(2,10003),(10003,3),
             (3,10004),(3,4),(10002,4),(4,10005),(10005,5),
             (5,10006),(10006,6),(6,10007),(10007,7),(7,10008),
             (7,8),(10002,8),(8,10009)]
    graph["edges"] = [{"source": a, "target": b} for a,b in edges]
    plan = {"node_to_subgraph": {str(i): 0 for i in range(2,9)},
            "core_schedules": [[0], []]}
    return graph, plan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    hashes = {p.relative_to(ROOT).as_posix(): digest(p)
              for p in sorted(CODE.glob("*.py")) + [CONFIG]}
    cfg = read_evaluation_config(CONFIG)
    waits = p1.read_scene_a_config(CONFIG)

    def evaluate(g, plan):
        return p1.evaluate_scene_a(
            g, plan, cfg["bandwidth"], cfg["capacity"],
            waits["task_cross_core_wait_cycles"],
            waits["task_same_core_wait_cycles"])

    graph, plan = tensor_graph()
    dump(out / "spill.graph.json", graph)
    dump(out / "spill.plan.json", plan)
    # Bottom-up micro observation and reachable Q1 observation are separate.
    local = step2_spill_insertion(graph, step1_schedule(graph), cfg["capacity"])
    captured = []

    def observe(frame, event, value):
        if (event == "return" and frame.f_code.co_name == "step2_spill_insertion"
                and Path(frame.f_code.co_filename).resolve() == CODE / "schedule_step2.py"
                and isinstance(value, dict)):
            captured.append(copy.deepcopy(value))

    sys.setprofile(observe)
    try:
        observed = evaluate(graph, plan)
    finally:
        sys.setprofile(None)
    plain = evaluate(graph, plan)
    assert plain == observed, "profile observation changed full result"
    assert len(captured) == 1
    records = captured[0]["spill_records"]
    retained = [s for s in records if s["logical_tid"] == 10002]
    assert [s["version"] for s in retained] == [1, 2]
    assert all(s["pos"] == "L1" and s["spill_out_id"] is None
               and not s["spill_out_copies_data"]
               and s["backing_source"] == "original_copy_in" for s in retained)
    assert retained[0]["backing_tid"] == retained[1]["backing_tid"]
    assert retained[1]["from_tid"] == retained[0]["to_tid"]
    new_tensor_ids = {t["id"] for t in captured[0]["new_tensors"]}
    assert all(s["backing_tid"] not in new_tensor_ids for s in retained)
    # A deliberately wrong rule interpretation is killed by this witness.
    rule_mutant = all(s["spill_out_id"] is not None and s["version"] == 1
                      and s["pos"] == "UB" for s in retained)
    assert not rule_mutant
    dump(out / "spill.step2.json", {"standalone": local, "scene_a": captured[0]})
    dump(out / "spill.function-result.json", plain)
    command = [sys.executable, "-B", str(CODE / "multicore_cut_evaluate_problem_1.py"),
               str(out / "spill.graph.json"), str(out / "spill.plan.json"),
               "--config", str(CONFIG), "--output", str(out / "spill.cli.json"),
               "--trace-output", str(out / "spill.trace.json"),
               "--log-output", str(out / "spill.log.txt")]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                               timeout=30, check=True)
    cli = json.loads((out / "spill.cli.json").read_text())
    normalized = json.loads(json.dumps(plain))
    assert all(cli[k] == value for k, value in normalized.items()), "CLI mismatch"

    # Unit-level, tensor-free input accepted by the public evaluator; not a
    # claim about formal-case distribution. Op 3 is independent but behind 2.
    fifo_graph = {"ops": [
        {"id":1,"op":"VADD","pipe":"PIPE_V","cycles":100},
        {"id":2,"op":"CONV","pipe":"PIPE_M","cycles":1},
        {"id":3,"op":"CONV","pipe":"PIPE_M","cycles":1}],
        "tensors": [], "edges": [{"source":1,"target":2}]}
    fifo_plan = {"node_to_subgraph":{"1":0,"2":0,"3":0},
                 "core_schedules":[[0],[]]}
    fifo = evaluate(fifo_graph, fifo_plan)
    ops = {x["op_id"]:x for x in fifo["per_core_timeline"][0]["ops"]}
    assert [(ops[i]["start"],ops[i]["end"]) for i in (1,2,3)] == [
        (0,100),(100,101),(101,102)]
    assert fifo["makespan"] == 102
    dump(out / "fifo.json", {"domain":"synthetic tensor-free function boundary",
                              "graph":fifo_graph,"plan":fifo_plan,"result":fifo})
    assert hashes == {name:digest(ROOT / name) for name in hashes}
    summary = {
        "reviewed_form_commit":"65d6c0e6facee2ec8ce9694c30dd805de99abf7e",
        "python":sys.version,"platform":platform.platform(),"seed":None,
        "command":["uv","run","python","-B","src/review/q1_form_semantic_probes.py",
                   "--output",out.relative_to(ROOT).as_posix()],
        "script_sha256":digest(Path(__file__)),"uv_lock_sha256":digest(ROOT / "uv.lock"),
        "graph_sha256":digest(out / "spill.graph.json"),
        "plan_sha256":digest(out / "spill.plan.json"),
        "config":cfg | waits,"official_file_sha256":hashes,
        "spill": {"domain":"synthetic graph accepted by frozen Q1 CLI; not an official case",
                  "retained_records":retained,"makespan":plain["makespan"],
                  "movement":plain["data_movement_bytes"],
                  "profile_full_result_equal":True,"cli_all_function_fields_equal":True,
                  "F_TASK_006_unconditional_reading_refuted":True,
                  "mutant_killed":not rule_mutant},
        "fifo":{"makespan":102,"ready_later_op_start":101,
                "hand_schedule":[[1,0,100],[2,100,101],[3,101,102]]},
        "official_files_unchanged":True,
        "limits":["No full FORM acceptance", "No E1/E2 test", "No solver quality benchmark"],
    }
    dump(out / "summary.json", summary)
    print(json.dumps({"passed":True,"spill_makespan":plain["makespan"],
                      "spill_versions":[s["version"] for s in retained],
                      "fifo_makespan":102}))


if __name__ == "__main__":
    main()
