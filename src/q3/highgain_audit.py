"""Read fixed Git artifacts and compute workload bounds; no evaluator calls."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from .construct import Index, ROOT


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_artifact(commit, reference):
    raw = subprocess.check_output(["git", "show", f"{commit}:{reference['path']}"], cwd=ROOT)
    if digest(raw) != reference["sha256"]:
        raise ValueError(f"artifact hash mismatch: {reference['path']}")
    return json.loads(gzip.decompress(raw) if reference["path"].endswith(".gz") else raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source = json.loads(args.input.read_text())
    rows = []
    for record in source["records"]:
        cid, cores = record["case_id"], record["cores"]
        raw = (ROOT / f"data/raw/a/official/data/case_{cid}.json").read_bytes()
        if digest(raw) != record["identity"]["graph_sha256"]:
            raise ValueError("graph identity mismatch")
        index = Index(json.loads(raw))
        a, b, h = index.word_descriptor()
        commit = record["source"]["commit"]
        result = read_artifact(commit, record["artifacts"]["result"])
        plan = read_artifact(commit, record["artifacts"]["plan"])
        baseline = read_artifact(commit, record["baseline"]["result"])
        expected, _ = index.build(cores, "resource_word")
        if plan != expected:
            raise ValueError("current resource-word construction differs from fixed plan")
        pipe_work = {pipe: sum(index.duration(u) for u in index.ops
                               if index.ops[u]["pipe"] == pipe)
                     for pipe in sorted({op["pipe"] for op in index.ops.values()})}
        # Frozen P3 uses one non-preemptive slot per core/pipe and keeps compute cycles.
        # Ignoring COPY, dependencies and memory relaxes constraints, so this is a
        # necessary bound for ANY legal allocation, not a predicted attainable optimum.
        lower_bound = max((work + cores - 1) // cores for work in pipe_work.values())
        makespan = result["makespan"]
        if makespan != record["metrics"]["makespan_cycles"] or makespan < lower_bound:
            raise ValueError("score or compute workload bound mismatch")
        pair = record.get("cache_pair")
        pair_makespan = read_artifact(commit, pair["result"])["makespan"] if pair else None
        rows.append({"case_id": cid, "cores": cores, "components": len(index.components),
                     "word": {"a_cycles": a, "b_cycles": b, "lookahead": h},
                     "jobs_per_core": [len(group) for group in index.assignment(cores)],
                     "pipe_work_cycles": pipe_work, "compute_lower_bound_cycles": lower_bound,
                     "baseline_cycles": baseline["makespan"], "makespan_cycles": makespan,
                     "baseline_speedup": baseline["makespan"] / makespan,
                     "max_remaining_makespan_reduction_percent": 100 * (1 - lower_bound / makespan),
                     "cache_stats": result["cache_stats"],
                     "data_movement_bytes": result["data_movement_bytes"],
                     "same_plan_P2_cycles": pair_makespan,
                     "source_commit": commit, "artifacts": record["artifacts"],
                     "baseline": record["baseline"], "cache_pair": pair})
    ones = {row["case_id"]: row for row in rows if row["cores"] == 1}
    for row in rows:
        one = ones[row["case_id"]]
        if one["baseline_cycles"] != row["baseline_cycles"]:
            raise ValueError("baseline numerator changed across core counts")
        row["gain_over_optimized_singlecore"] = one["makespan_cycles"] / row["makespan_cycles"]
    output = {"schema": "q3-highgain-audit-v1", "evaluation_calls": 0,
              "input_sha256": digest(args.input.read_bytes()),
              "script_sha256": digest(Path(__file__).read_bytes()),
              "method": "Fixed Git artifact hashes checked; local unchanged input parsed; current construction compared as JSON. No E0 rerun, no independent experimental reproduction.",
              "bound_scope": "max_pipe ceil(original non-COPY compute cycles / cores); frozen PIPE_SLOTS=1. Upper cap on further Makespan reduction, not an attainable-gain forecast.",
              "records": rows}
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"records": len(rows), "evaluation_calls": 0, "output": str(args.output)}))


if __name__ == "__main__":
    main()
