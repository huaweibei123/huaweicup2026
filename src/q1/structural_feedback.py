"""Read existing fixed64 evidence; no solver or evaluator is started."""
from collections import Counter, defaultdict
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))
from stub_multicore_cut_and_schedule import (  # noqa: E402
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--feed", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)

    def blob(path):
        return subprocess.check_output(["git", "show", args.source_commit + ":" + path], cwd=ROOT)

    def original(ref):
        raw = blob(ref["path"])
        if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
            raise ValueError("Existing evidence hash mismatch: " + ref["path"])
        return json.loads(gzip.decompress(raw) if ref["path"].endswith(".gz") else raw)

    feed_bytes = blob(args.feed)
    records = json.loads(feed_bytes)["records"]
    if len(records) != 500 or len({(r["case_id"], r["cores"]) for r in records}) != 500:
        raise ValueError("Require the unmodified complete 100 x 5 batch")
    baselines, by_core = {}, defaultdict(list)
    rows = []
    for r in records:
        if r["status"] != "ok" or r["algorithm_id"] != "q1-fixed64-local-finish":
            raise ValueError("Mixed method or incomplete batch")
        case = r["case_id"]
        if case not in baselines:
            baselines[case] = original(r["baseline"]["result"])["makespan"]
        m = r["metrics"]
        row = {"case": case, "cores": r["cores"], "baseline": baselines[case],
               "makespan": m["makespan_cycles"], "speedup": baselines[case] / m["makespan_cycles"],
               "solver_wall_seconds": m["solver_wall_seconds"],
               "extra_ddr_bytes": m["extra_ddr_bytes"], "spill_bytes": m["spill_bytes"]}
        rows.append(row)
        by_core[r["cores"]].append(row)
    aggregate = {}
    for k, cells in sorted(by_core.items()):
        times = sorted(r["solver_wall_seconds"] for r in cells)
        aggregate[k] = {"n": len(cells),
                        "mean_speedup": statistics.mean(r["speedup"] for r in cells),
                        "median_speedup": statistics.median(r["speedup"] for r in cells),
                        "slower_than_singlecore": sum(r["speedup"] < 1 for r in cells),
                        "spill_cases": sum(r["spill_bytes"] > 0 for r in cells),
                        "solver_wall_median": statistics.median(times),
                        "solver_wall_p95_nearest_rank": times[math.ceil(.95 * len(times)) - 1],
                        "solver_wall_max": max(times)}
    witnesses = []
    with zipfile.ZipFile(ROOT / "data/raw/a/official-cases.zip") as archive:
        for case in ("001", "014", "020", "044", "045", "080", "097"):
            raw = archive.read(f"data/case_{case}.json")
            record = next(r for r in records if r["case_id"] == case and r["cores"] == 5)
            if hashlib.sha256(raw).hexdigest() != record["identity"]["graph_sha256"]:
                raise ValueError("Graph hash mismatch")
            graph = json.loads(raw)
            plan = original(record["artifacts"]["plan"])
            view = derive_multicore_plan(graph, plan)
            ids = sorted(view["mapping"])
            _, full = _build_op_adjacency(graph)
            _, succ = _contract_excluded_copy_nodes(ids, full)
            parent = {v: v for v in ids}

            def find(v):
                while parent[v] != v:
                    parent[v] = parent[parent[v]]
                    v = parent[v]
                return v

            for u in ids:
                for v in succ[u]:
                    a, b = find(u), find(v)
                    if a != b:
                        parent[b] = a
            sizes = Counter(find(v) for v in ids)
            pairs = set(map(tuple, view["dependency_pairs"]))
            tasks = view["subgraph_ids"]
            witnesses.append({"case": case, "compute_ops": len(ids), "components": len(sizes),
                              "largest_component_ops": max(sizes.values()), "fixed64_tasks": len(tasks),
                              "mixed_component_tasks": sum(len({find(v) for v in nodes}) > 1
                                                           for nodes in view["nodes_by_subgraph"].values()),
                              "consecutive_task_dependency_edges": sum((a, b) in pairs
                                                                       for a, b in zip(tasks, tasks[1:])),
                              "core_task_counts": [len(x) for x in plan["core_schedules"]]})
    output = {"source_commit": args.source_commit, "feed": args.feed,
              "feed_sha256": hashlib.sha256(feed_bytes).hexdigest(),
              "analysis_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "calls": {"solver": 0, "E0": 0, "E1": 0, "E2": 0},
              "limits": "Existing feed metrics; all 100 singlecore and seven plan originals hash-checked. No new evaluation or causal speed proof.",
              "aggregate": aggregate, "structural_witnesses": witnesses, "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as f:
        json.dump(output, f, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps({"aggregate": aggregate, "structural_witnesses": witnesses}))


if __name__ == "__main__":
    main()
