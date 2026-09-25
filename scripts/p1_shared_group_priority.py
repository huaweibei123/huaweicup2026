"""Join saved P1 K5 evidence with input reuse and an optimistic resource bound.

Reads frozen originals only. This is research triage, not a candidate score.
"""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import zipfile

from p1_shared_group_baseline_audit import BASE, shared_inputs
from p1_shared_group_census import ROOT, SOURCE, SOURCE_SHA256, sha256


AUDIT = ROOT / "results/a/p1-branch-refine-full500-20260925/independent-audit.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sha256(SOURCE) != SOURCE_SHA256:
        raise ValueError("Official input ZIP differs from frozen source")
    saved = json.loads(AUDIT.read_text())
    observed = {row["case"]: row["makespan"] for row in saved["rows"] if row["cores"] == 5}
    if set(observed) != {f"{i:03d}" for i in range(1, 101)}:
        raise ValueError("Expected all 100 K5 checkpoint cells")
    rows = []
    with zipfile.ZipFile(SOURCE) as archive:
        for case_id, makespan in sorted(observed.items()):
            graph = json.loads(archive.read(f"data/case_{case_id}.json"))
            tensors, consumers, shared = shared_inputs(graph)
            plan_path = BASE / f"{case_id}-k5/originals/plan.json"
            plan = json.loads(plan_path.read_bytes())
            mapping = {int(op_id): task for op_id, task in plan["node_to_subgraph"].items()}
            counts = {t: len({mapping[o] for o in consumers[t] if o in mapping}) for t in shared}
            work: Counter[str] = Counter()
            for op in graph["ops"]:
                if op["op"] not in {"COPY_IN", "COPY_OUT"}:
                    if type(op["cycles"]) is not int or op["cycles"] < 0:
                        raise ValueError("Invalid compute duration")
                    if op["id"] not in mapping:
                        raise ValueError("Saved plan omits a compute op")
                    work[op["pipe"]] += max(1, op["cycles"])
            lower = max((cycles + 4) // 5 for cycles in work.values())
            if not 0 < lower <= makespan:
                raise ValueError("Resource bound inconsistent with saved E0")
            baseline_path = BASE.parent / "baselines" / f"{case_id}-singlecore.json.gz"
            with gzip.open(baseline_path, "rt") as stream:
                baseline = json.load(stream)["makespan"]
            rows.append({
                "case_id": case_id,
                "saved_makespan": makespan,
                "singlecore_baseline_makespan": baseline,
                "compute_resource_lower_bound": lower,
                "optimistic_mean_headroom": (baseline / lower - baseline / makespan) / 100,
                "shared_copy_in_tensors": len(shared),
                "shared_tensors_crossing_tasks": sum(n > 1 for n in counts.values()),
                "structural_extra_shared_read_bytes": sum((counts[t] - 1) * tensors[t]["size"] for t in shared),
                "plan_sha256": sha256(plan_path),
                "singlecore_baseline_sha256": sha256(baseline_path),
            })
    eligible = [r for r in rows if r["structural_extra_shared_read_bytes"] > 0]
    output = {
        "scope": "Static triage only: shared rereads and an optimistic bound do not predict attainable savings. No solver, Task compiler, E0, E1 or E2 calls.",
        "bound_assumptions": "Each non-COPY op once; at least max(1, cycles) duration; five cores; one slot per Pipe. Ignores dependencies, FIFO, capacity, COPY and DDR contention.",
        "source_zip_sha256": SOURCE_SHA256,
        "checkpoint_audit_sha256": sha256(AUDIT),
        "frozen_checkpoint_commit": "a1bb4451cd85c46b32bb928d57c81e22cfeca1a6",
        "shared_cases_by_optimistic_headroom": [r["case_id"] for r in sorted(eligible, key=lambda r: (-r["optimistic_mean_headroom"], r["case_id"]))],
        "cases": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
