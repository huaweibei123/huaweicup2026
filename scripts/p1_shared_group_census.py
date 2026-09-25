"""Read-only P1 shared COPY_IN structure census over the frozen official ZIP.

This script never imports a solver, constructs a plan, or calls Task/E0/E1/E2.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/a/official-cases.zip"
SOURCE_SHA256 = "e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528"
FOCUS = ("011", "027", "059", "097")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def census_case(graph: dict, case_id: str) -> dict:
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
        elif source in ops and target in ops:
            direct.append((source, target))
        else:
            raise ValueError(f"{case_id}: unexpected edge {source}->{target}")

    for source, target in direct:
        if source in compute and target in compute:
            adjacency[source].add(target)
            adjacency[target].add(source)
    for tensor_id in tensors:
        local_producers = producers[tensor_id] & compute
        local_consumers = consumers[tensor_id] & compute
        for source in local_producers:
            for target in local_consumers:
                adjacency[source].add(target)
                adjacency[target].add(source)

    components = []
    seen = set()
    for root in sorted(compute):
        if root in seen:
            continue
        queue = deque([root])
        seen.add(root)
        component = []
        while queue:
            source = queue.popleft()
            component.append(source)
            for target in adjacency[source]:
                if target not in seen:
                    seen.add(target)
                    queue.append(target)
        components.append(component)
    components.sort(key=min)
    component_of = {op_id: index for index, component in enumerate(components) for op_id in component}

    # Consumer sets, not tensor IDs or graph-wide component counts, define the
    # observable reuse groups. No scheduling or benefit is inferred here.
    reused = []
    groups: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for tensor_id, tensor in tensors.items():
        consumer_components = tuple(sorted({component_of[op_id] for op_id in consumers[tensor_id] & compute}))
        if len(consumer_components) < 2:
            continue
        producer_ids = producers[tensor_id]
        copy_in = len(producer_ids) == 1 and ops[next(iter(producer_ids))]["op"] == "COPY_IN"
        reused.append((tensor_id, consumer_components, copy_in))
        if copy_in:
            groups[consumer_components].append(tensor_id)

    reusable = [entry for entry in reused if entry[2]]
    coverage = Counter(len(components) for _, components, _ in reusable)
    group_rows = [
        {"component_ids_zero_based": list(group),
         "component_count": len(group),
         "tensor_count": len(ids),
         "tensor_bytes": sum(tensors[tensor_id]["size"] for tensor_id in ids)}
        for group, ids in groups.items()
    ]
    group_rows.sort(key=lambda row: (-row["tensor_count"], row["component_ids_zero_based"]))
    return {
        "case_id": case_id,
        "compute_ops": len(compute),
        "component_count": len(components),
        "component_size_histogram": {str(size): count for size, count in sorted(Counter(map(len, components)).items())},
        "cross_component_tensors": len(reused),
        "cross_component_copy_in_tensors": len(reusable),
        "partial_copy_in_tensors": sum(len(group) < len(components) for _, group, _ in reusable),
        "shared_copy_in_bytes": sum(tensors[tensor_id]["size"] for tensor_id, _, _ in reusable),
        "copy_in_coverage_histogram": {str(size): count for size, count in sorted(coverage.items())},
        "consumer_group_count": len(group_rows),
        "consumer_group_tensor_count_histogram": {
            str(count): number for count, number in sorted(Counter(row["tensor_count"] for row in group_rows).items())
        },
        "consumer_groups": group_rows if case_id in FOCUS else [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    actual_sha = sha256(SOURCE)
    if actual_sha != SOURCE_SHA256:
        raise SystemExit(f"Source ZIP hash mismatch: {actual_sha}")
    with zipfile.ZipFile(SOURCE) as archive:
        names = sorted(name for name in archive.namelist() if name.startswith("data/case_") and name.endswith(".json"))
        if len(names) != 100:
            raise SystemExit(f"Expected 100 official cases, found {len(names)}")
        cases = [census_case(json.loads(archive.read(name)), name[len("data/case_"):-len(".json")]) for name in names]
    result = {
        "source": {"path": "data/raw/a/official-cases.zip", "sha256": actual_sha, "case_count": len(cases)},
        "definitions": {
            "component": "Weakly connected component of non-COPY ops under direct op edges and producer-tensor-consumer edges.",
            "cross_component_copy_in": "Tensor consumed by compute ops in at least two components and produced by exactly one COPY_IN op.",
            "partial": "Such a tensor is consumed by fewer than all compute components in its graph.",
            "consumer_group": "Exact set of compute-component indices consuming the same COPY_IN tensor. Indices are zero based after sorting components by minimum op ID.",
        },
        "summary": {
            "cases_with_cross_component_copy_in": sum(case["cross_component_copy_in_tensors"] > 0 for case in cases),
            "cases_with_partial_copy_in": sum(case["partial_copy_in_tensors"] > 0 for case in cases),
            "focus_cases": list(FOCUS),
        },
        "cases": cases,
        "scope": "Graph structure only; no plan validity, capacity feasibility, Task behavior, E0/E1/E2 result, or Makespan claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
