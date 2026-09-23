"""Small actual CLI/file smoke: full fallback plus streaming search with invalid."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from src.eval_exact._official import REPO_ROOT as ROOT
from src.eval_exact.batch_benchmark import equal


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    graph = dict(ops=[dict(id=1, op="CONV", pipe="PIPE_M", cycles=7)], tensors=[], edges=[])
    plan = dict(node_to_subgraph={"1": 0}, core_schedules=[[0]])
    (out / "graph.json").write_text(json.dumps(graph))
    (out / "plan.json").write_text(json.dumps(plan))
    (out / "plans.jsonl").write_text(json.dumps(plan) + "\n{}\n" + json.dumps(plan) + "\n")
    config = ROOT / "data/raw/a/official/data/config.txt"
    commands = {}
    for route, entry in (("e0", [str(ROOT / "data/raw/a/official/code/multicore_cut_evaluate_problem_1.py")]),
                         ("e2", ["-m", "research.a.e2_search.multicore_cut_evaluate_problem_1"])):
        command = [sys.executable, *entry, str(out / "graph.json"), str(out / "plan.json"), "--config", str(config),
                   "-o", str(out / f"{route}.json"), "--trace-output", str(out / f"{route}.trace.json"),
                   "--log-output", str(out / f"{route}.txt")]
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        commands[route] = dict(argv=[s.replace(str(ROOT), ".") for s in command], returncode=run.returncode,
                               stdout=run.stdout, stderr=run.stderr)
    for suffix in (".json", ".trace.json"):
        assert equal(json.loads((out / ("e0" + suffix)).read_text()), json.loads((out / ("e2" + suffix)).read_text()))
    assert (out / "e0.txt").read_bytes() == (out / "e2.txt").read_bytes()
    command = [sys.executable, "-m", "research.a.e2_search.cli", str(out / "graph.json"), str(out / "plans.jsonl"),
               "--config", str(config), "--output", str(out / "records.jsonl"), "--workers", "1"]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 1, run.stderr
    records = [json.loads(line) for line in (out / "records.jsonl").read_text().splitlines()]
    assert [r["status"] for r in records] == ["ok", "invalid", "ok"]
    assert records[0]["makespan"] == records[2]["makespan"] == 7
    commands["search"] = dict(argv=[s.replace(str(ROOT), ".") for s in command], returncode=run.returncode,
                              stdout=run.stdout, stderr=run.stderr)
    (out / "receipt.json").write_text(json.dumps(dict(commands=commands, full_fields_and_trace_equal=True,
                                                      log_byte_equal=True, streaming_statuses=[r["status"] for r in records]), indent=2))
    print("PASS full E0/E2 CLI result + trace values, log bytes; search invalid record does not stop batch")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output)
