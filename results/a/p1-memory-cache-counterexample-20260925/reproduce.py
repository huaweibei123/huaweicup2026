#!/usr/bin/env python3
"""Two synthetic Task compiles, no solver or evaluator calls."""
import hashlib
import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.q1.variable_packet import Family
from src.q1.compiled_memory_response import compile_plan

HERE = Path(__file__).resolve().parent
CAPACITY = {"L1": 80, "UB": 80}


def write_new(name, value):
    path = HERE / name
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def make_graph():
    ops, tensors, edges = [], [], []
    mapping = {}
    for task_id, (chain, tids) in enumerate((([1, 2, 3, 4], [10, 11, 12]),
                                             ([20, 21, 22, 23], [15, 16, 17]))):
        m, v1, v2, ret = chain
        inp, mid, out = tids
        for op_id, pipe in zip(chain, ("PIPE_M", "PIPE_V", "PIPE_V", "PIPE_M")):
            ops.append({"id": op_id, "op": "COMPUTE", "pipe": pipe, "cycles": 1})
            mapping[str(op_id)] = task_id
        tensors += [{"id": tid, "pos": "UB", "size": 40} for tid in tids]
        edges += [{"source": source, "target": target} for source, target in (
            (m, v1), (v1, v2), (v2, ret), (inp, m), (inp, v2),
            (m, mid), (mid, v2), (ret, out))]
    return ({"ops": ops, "tensors": tensors, "edges": edges},
            {"node_to_subgraph": mapping, "core_schedules": [[0, 1]]})


def main():
    global HERE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='new output directory; existing artifacts are never overwritten')
    HERE = parser.parse_args().output.resolve()
    HERE.mkdir(parents=True, exist_ok=True)
    for name in ("graph.json", "plan.json", "compile-certificate.json", "signature-difference.json", "receipt.json"):
        if (HERE / name).exists():
            raise FileExistsError(name)
    graph, plan = make_graph()
    family = Family(graph, 1, CAPACITY, 60)
    lines, certificate = compile_plan(graph, plan, CAPACITY, 60)
    assert len(lines) == 1 and len(lines[0]) == 2
    signatures = [task.signature() for task in lines[0]]
    assert signatures[0] != signatures[1]
    need = [next(op.need for port in task.ports for op in port
                 if op.original_id in (4, 23)) for task in lines[0]]
    assert need == [(1, 2, 0, 0), (0, 2, 0, 0)]
    write_new("graph.json", graph)
    write_new("plan.json", plan)
    write_new("compile-certificate.json", certificate)
    write_new("signature-difference.json", {
        "family_certificate": family.family_certificate,
        "task_signatures": signatures,
        "final_M_ids": [4, 23], "final_M_need": need,
        "claim": "ordered Family acceptance does not guarantee equal PortOp signatures",
        "semantic_limit": "extra first-M predecessor is redundant through second V; no response or score difference proved",
    })
    files = ["graph.json", "plan.json", "compile-certificate.json", "signature-difference.json"]
    write_new("receipt.json", {
        "python": platform.python_version(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_hashes": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in (ROOT / "src/q1/variable_packet.py",
                                       ROOT / "src/q1/compiled_memory_response.py",
                                       ROOT / "src/q1/response_oracle.py")},
        "artifacts_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in files},
        "synthetic_official_task_compiles": 2,
        "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
        "scope": "signature counterexample only; no performance inference",
    })


if __name__ == "__main__":
    main()
