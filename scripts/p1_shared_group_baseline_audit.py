"""Read saved K5 plans and result bytes for four shared-input census cases.

No solver, Task compiler, or evaluator is imported or called.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

from p1_shared_group_census import FOCUS, ROOT, SOURCE, SOURCE_SHA256, sha256


BASE = ROOT / "results/a/p1-branch-refine-full500-20260925/20260925T1525Z-s6607-branch-full500/cells"


def shared_inputs(graph: dict) -> tuple[dict, dict[int, set[int]], list[int]]:
    ops = {op["id"]: op for op in graph["ops"]}
    tensors = {tensor["id"]: tensor for tensor in graph["tensors"]}
    compute = {op_id for op_id, op in ops.items() if op["op"] not in {"COPY_IN", "COPY_OUT"}}
    producers: dict[int, set[int]] = defaultdict(set)
    consumers: dict[int, set[int]] = defaultdict(set)
    adjacency = {op_id: set() for op_id in compute}
    direct = []
    for edge in graph["edges"]:
        source, target = edge["source"], edge["target"]
        if source in ops and target in tensors:
            producers[target].add(source)
        elif source in tensors and target in ops:
            consumers[source].add(target)
        elif source in compute and target in compute:
            direct.append((source, target))
    for source, target in direct:
        adjacency[source].add(target)
        adjacency[target].add(source)
    for tensor_id in tensors:
        for source in producers[tensor_id] & compute:
            for target in consumers[tensor_id] & compute:
                adjacency[source].add(target)
                adjacency[target].add(source)
    component_of = {}
    for root in sorted(compute):
        if root in component_of:
            continue
        index = len(set(component_of.values()))
        queue = deque([root])
        component_of[root] = index
        while queue:
            source = queue.popleft()
            for target in adjacency[source]:
                if target not in component_of:
                    component_of[target] = index
                    queue.append(target)
    shared = [
        tensor_id for tensor_id in tensors
        if len({component_of[op_id] for op_id in consumers[tensor_id] & compute}) > 1
        and len(producers[tensor_id]) == 1
        and ops[next(iter(producers[tensor_id]))]["op"] == "COPY_IN"
    ]
    return tensors, consumers, shared


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sha256(SOURCE) != SOURCE_SHA256:
        raise SystemExit("Official ZIP hash mismatch")
    rows = []
    with zipfile.ZipFile(SOURCE) as archive:
        for case_id in FOCUS:
            graph = json.loads(archive.read(f"data/case_{case_id}.json"))
            tensors, consumers, shared = shared_inputs(graph)
            directory = BASE / f"{case_id}-k5/originals"
            plan_path, result_path = directory / "plan.json", directory / "prior-result.json.gz"
            plan = json.loads(plan_path.read_bytes())
            with gzip.open(result_path, "rt", encoding="utf-8") as stream:
                result = json.load(stream)
            mapping = {int(op_id): task for op_id, task in plan["node_to_subgraph"].items()}
            task_histogram = Counter()
            byte_histogram = Counter()
            for tensor_id in shared:
                task_count = len({mapping[op_id] for op_id in consumers[tensor_id] if op_id in mapping})
                task_histogram[task_count] += 1
                byte_histogram[task_count] += tensors[tensor_id]["size"]
            movement = result["data_movement_bytes"]
            rows.append({
                "case_id": case_id,
                "plan_path": str(plan_path.relative_to(ROOT)),
                "plan_sha256": sha256(plan_path),
                "saved_result_path": str(result_path.relative_to(ROOT)),
                "saved_result_sha256": sha256(result_path),
                "core_schedules": plan["core_schedules"],
                "shared_copy_in_tensor_count": len(shared),
                "task_count_histogram": {str(count): number for count, number in sorted(task_histogram.items())},
                "task_count_byte_histogram": {str(count): number for count, number in sorted(byte_histogram.items())},
                "multi_task_shared_tensor_fraction": sum(number for count, number in task_histogram.items() if count > 1) / len(shared),
                "extra_shared_input_read_bytes_structural": sum((count - 1) * value for count, value in byte_histogram.items()),
                "saved_spill_added_copy_bytes": movement["spill_added_copy_bytes"],
                "saved_total_added_copy_bytes": movement["added_copy_bytes"],
            })
    output = {"source_zip_sha256": SOURCE_SHA256,
              "scope": "Read-only saved-plan/task-boundary arithmetic and saved result fields; no new evaluation or performance inference.",
              "cases": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
