"""Choose active cores from shared-input/work proxies, then refine bounded Tasks.

Only metadata for <=K resource configurations is compared; bounded.construct is
called once. No evaluator, case-ID routing, graph ID rewriting or plan search.
The cost is neither a lower bound nor an E0/spill prediction.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1.bounded_tasks import construct as bounded_construct
from stub_multicore_cut_and_schedule import (
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)
from evaluation_validation import (
    read_bandwidth_config, read_required_settings, validate_graph, validate_task_order,
)

CONFIG = ROOT / "data/raw/a/official/data/config.txt"
TRIGGER_OPS, CHUNK_OPS = 4096, 1024


def _view(graph):
    validate_graph(graph)
    ops = {o["id"]: o for o in graph["ops"] if o["op"] not in {"COPY_IN", "COPY_OUT"}}
    if not ops:
        raise ValueError("Require nonempty compute operations")
    tensors = {t["id"]: t for t in graph["tensors"]}
    all_ops = {o["id"]: o for o in graph["ops"]}
    producers, consumers, copy_out = defaultdict(set), defaultdict(set), set()
    for e in graph["edges"]:
        u, v = e["source"], e["target"]
        if u in ops and v in tensors:
            producers[v].add(u)
        if u in tensors and v in ops:
            consumers[u].add(v)
        if u in tensors and v in all_ops and all_ops[v]["op"] == "COPY_OUT":
            copy_out.add(u)
    original_copy_edges = set()
    for e in graph["edges"]:
        u, v = e["source"], e["target"]
        if u in all_ops and all_ops[u]["op"] == "COPY_IN" and v in tensors:
            original_copy_edges.add((u, v))
        if u in tensors and v in all_ops and all_ops[v]["op"] == "COPY_OUT":
            original_copy_edges.add((v, u))
    original_copy_bytes = sum(tensors[t]["size"] for _, t in original_copy_edges)
    external = {t for t in consumers if not producers[t]}
    reads = defaultdict(set)
    for t in external:
        for u in consumers[t]:
            reads[u].add(t)
    _, full = _build_op_adjacency(graph)
    pred, succ = _contract_excluded_copy_nodes(sorted(ops), full)
    degree = {u: len(pred[u]) for u in ops}
    ready = deque(sorted(u for u in ops if not degree[u]))
    depth = dict.fromkeys(ops, 0)
    parent = {u: u for u in ops}

    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u

    seen = 0
    while ready:
        u = ready.popleft()
        seen += 1
        for v in sorted(succ[u]):
            depth[v] = max(depth[v], depth[u] + 1)
            a, b = find(u), find(v)
            if a != b:
                parent[max(a, b)] = min(a, b)
            degree[v] -= 1
            if not degree[v]:
                ready.append(v)
    if seen != len(ops):
        raise ValueError("Cyclic compute graph")
    groups = defaultdict(list)
    for u in ops:
        groups[find(u)].append(u)
    components = []
    for nodes in groups.values():
        work = Counter()
        for u in nodes:
            work[ops[u]["pipe"]] += ops[u]["cycles"]
        components.append((nodes, work, min(nodes)))
    # Exactly the frozen component_pack priority and placement tie-breaks.
    components.sort(key=lambda x: (-max(x[1].values()), -sum(x[1].values()),
                                   -len(x[0]), x[2]))
    return dict(ops=ops, tensors=tensors, producers=producers, consumers=consumers,
                original_copy_out=copy_out, external=external, reads=reads,
                depth=depth, components=components, original_copy_bytes=original_copy_bytes)


def _size(ids, view):
    return sum(view["tensors"][t]["size"] for t in ids)


def _windows(nodes, view, budget, max_phases):
    """Metadata only: ordered subsets of one old Task, never combines old Tasks."""
    levels = defaultdict(list)
    for u in nodes:
        levels[view["depth"][u]].append(u)
    phases, current, inputs, current_bytes = [], [], set(), 0
    for _, level in sorted(levels.items()):
        needed = {t for u in level for t in view["reads"][u]}
        fresh_bytes = _size(needed - inputs, view)
        if current and inputs and fresh_bytes and current_bytes + fresh_bytes > budget:
            phases.append(current)
            current, inputs, current_bytes = [], set(), 0
            fresh_bytes = _size(needed, view)
        current.extend(level)
        inputs.update(needed)
        current_bytes += fresh_bytes
    if current:
        phases.append(current)
    limited = len(phases) > max_phases
    if limited:
        phases = [list(nodes)]
    return phases, limited


def _configuration(view, cores, budget, max_phases, bandwidth, same_wait):
    """Load/input metadata, not a submission plan; mirrors frozen base packing."""
    loads, counts = [Counter() for _ in range(cores)], [0] * cores
    grouped = [[] for _ in range(cores)]
    for nodes, work, _ in view["components"]:
        choices = []
        for c in range(cores):
            after = [loads[c][p] + work[p] for p in loads[c].keys() | work.keys()]
            choices.append((max(after), sum(after), counts[c], c))
        c = min(choices)[-1]
        loads[c].update(work)
        counts[c] += len(nodes)
        grouped[c].append(nodes)
    blocks = []
    for c, components in enumerate(grouped):
        if not components:
            continue
        if counts[c] <= TRIGGER_OPS:
            bins = [[u for ns in components for u in ns]]
        else:
            # Same first-fit component chunks as bounded_tasks. These are only
            # metadata; the single real base constructor runs after selection.
            bins = []
            for ns in sorted(components, key=lambda ns: (-len(ns), min(ns))):
                chosen = next((b for b in bins if len(b) + len(ns) <= CHUNK_OPS), None)
                if chosen is None:
                    chosen = []
                    bins.append(chosen)
                chosen.extend(ns)
        blocks.extend((c, b) for b in bins)
    owner, task_counts = {}, [0] * cores
    external_sum = 0
    ddr_cycles = 0
    window_pipe_work = [0] * cores
    phase_limit_blocks = 0
    max_phase_inputs = 0
    oversized_phases = 0
    for b, (c, nodes) in enumerate(blocks):
        phases, limited = _windows(nodes, view, budget, max_phases)
        phase_limit_blocks += limited
        task_counts[c] += len(phases)
        for w, members in enumerate(phases):
            label = (c, b, w)
            for u in members:
                owner[u] = label
            input_ids = {t for u in members for t in view["reads"][u]}
            ext_bytes = _size(input_ids, view)
            external_sum += ext_bytes
            ddr_cycles += sum(max(1, (view["tensors"][t]["size"] + bandwidth - 1) // bandwidth)
                              for t in input_ids)
            work = Counter()
            for u in members:
                work[view["ops"][u]["pipe"]] += max(1, view["ops"][u]["cycles"])
            window_pipe_work[c] += max(work.values(), default=0)
            max_phase_inputs = max(max_phase_inputs, ext_bytes)
            oversized_phases += ext_bytes > budget
    boundary_payload, internal_copy = 0, 0
    terminal_copy = 0
    # Count unscheduled boundary traffic from direct compute incidences. This
    # omits spill, capacity/FIFO order and DDR overlap. Per-COPY rounding is kept.
    for t, tensor in view["tensors"].items():
        ps = {owner[u] for u in view["producers"][t]}
        cs = {owner[u] for u in view["consumers"][t]}
        if not ps:
            continue  # external loads already counted per metadata Task
        internal_copy += len(cs - ps) * tensor["size"]
        output_count = sum(t in view["original_copy_out"] or not cs or bool(cs - {p}) for p in ps)
        ddr_cycles += (len(cs - ps) + output_count) * max(1, (tensor["size"] + bandwidth - 1) // bandwidth)
        if cs and any(cs - {p} for p in ps):
            boundary_payload += tensor["size"]
            internal_copy += output_count * tensor["size"]
        else:
            terminal_copy += output_count * tensor["size"]
    copy_bytes = external_sum + internal_copy + terminal_copy
    gates = [same_wait * max(0, n - 1) for n in task_counts]
    pipe_gate = max((w + h for w, h in zip(window_pipe_work, gates)), default=0)
    return dict(active_cores=cores, core_compute_ops=counts,
                core_compute_pipe_work=[dict(sorted(x.items())) for x in loads],
                base_task_count=len(blocks), task_counts_by_core=task_counts,
                input_copy_proxy_bytes=external_sum,
                input_repeat_proxy_bytes=external_sum - _size(view["external"], view),
                cut_tensor_payload_bytes_once=boundary_payload,
                internal_boundary_copy_proxy_bytes=internal_copy,
                terminal_copy_proxy_bytes=terminal_copy,
                total_copy_proxy_bytes=copy_bytes,
                original_graph_copy_bytes=view["original_copy_bytes"],
                partition_added_copy_proxy_bytes=copy_bytes-view["original_copy_bytes"],
                max_window_input_union_bytes=max_phase_inputs,
                windows_over_input_budget=oversized_phases,
                phase_limit_base_tasks=phase_limit_blocks,
                same_core_wait_proxy_by_core=gates,
                window_pipe_work_proxy_by_core=window_pipe_work,
                max_compute_with_wait_proxy_cycles=pipe_gate,
                ddr_service_proxy_cycles=ddr_cycles,
                cost_proxy_cycles=max(pipe_gate, ddr_cycles))


def _refine(base, view, budget, max_phases, cores):
    old = {int(u): t for u, t in base["node_to_subgraph"].items()}
    grouped = defaultdict(list)
    for u in view["ops"]:
        grouped[old[u]].append(u)
    mapping, schedules, details = {}, [], []
    next_task = max(old.values()) + 1
    for order in base["core_schedules"]:
        schedule = []
        for task in order:
            phases, limited = _windows(grouped[task], view, budget, max_phases)
            ids = [task] + list(range(next_task, next_task + len(phases) - 1))
            next_task += len(phases) - 1
            schedule.extend(ids)
            phase_info = []
            for tid, members in zip(ids, phases):
                for u in members:
                    mapping[u] = tid
                phase_info.append(dict(task=tid, compute_ops=len(members),
                    depth_begin=min(view["depth"][u] for u in members),
                    depth_end=max(view["depth"][u] for u in members),
                    external_input_bytes=_size({t for u in members for t in view["reads"][u]}, view)))
            details.append(dict(base_task=task, new_tasks=ids, phase_limit_fallback=limited,
                                phases=phase_info))
        schedules.append(schedule)
    schedules.extend([] for _ in range(cores - len(schedules)))
    return {"node_to_subgraph": {u: mapping[u] for u in view["ops"]},
            "core_schedules": schedules}, details


def construct(graph, cores, *, input_budget_bytes=262144,
              activation_bytes=524288, max_phases=32):
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError("cores must be an integer in 1..5")
    for value in (input_budget_bytes, activation_bytes, max_phases):
        if type(value) is not int or value < 1:
            raise ValueError("Require positive integer construction budgets")
    view = _view(graph)
    external_bytes = _size(view["external"], view)
    info = dict(algorithm_id="q1-shared-input-budget", variant="active-core-then-local-windows",
                requested_cores=cores, input_budget_bytes=input_budget_bytes,
                activation_bytes=activation_bytes, max_phases=max_phases,
                external_input_bytes=external_bytes, components=len(view["components"]),
                scope="Static proxies are neither lower bounds, E0 predictions, nor capacity certificates")
    if len(view["components"]) < cores or external_bytes <= activation_bytes:
        result, base = bounded_construct(graph, cores)
        info.update(selected="bounded04", reason="not enough components or external inputs below activation",
                    active_cores=cores, configurations=[], base=base)
        return result, info
    bandwidth = read_bandwidth_config(CONFIG)
    waits = read_required_settings(CONFIG, "multicore_scene_a",
                                   ("task_cross_core_wait_cycles", "task_same_core_wait_cycles"))
    configs = [_configuration(view, a, input_budget_bytes, max_phases, bandwidth,
                              waits["task_same_core_wait_cycles"]) for a in range(1, cores + 1)]
    chosen = min(configs, key=lambda x: (x["cost_proxy_cycles"], x["total_copy_proxy_bytes"], -x["active_cores"]))
    active = chosen["active_cores"]
    # Exactly once, with the selected a; original K-boundaries are not preserved.
    base_plan, base_info = bounded_construct(graph, active)
    result, details = _refine(base_plan, view, input_budget_bytes, max_phases, cores)
    after = derive_multicore_plan(graph, result)
    validate_task_order(after)
    actual_counts = [len(order) for order in result["core_schedules"][:active]]
    if actual_counts != chosen["task_counts_by_core"]:
        raise AssertionError("Static packing/window metadata drifted from selected bounded base")
    # Whole components remain on their selected core; all new dependencies are local.
    if any(after["core_by_subgraph"][a] != after["core_by_subgraph"][b]
           for a, b in after["dependency_pairs"]):
        raise AssertionError("Component-preserving windows introduced a remote dependency")
    info.update(selected="shared-input-budget", active_cores=active,
                configurations=configs, chosen_configuration=chosen,
                fixed_bandwidth_bytes_per_cycle=bandwidth, fixed_task_waits=waits,
                base=base_info, task_refinements=details, tasks=len(after["subgraph_ids"]))
    return result, info


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("graph", type=Path)
    p.add_argument("--cores", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--diagnostics", type=Path)
    p.add_argument("--input-budget-bytes", type=int, default=262144)
    p.add_argument("--activation-bytes", type=int, default=524288)
    p.add_argument("--max-phases", type=int, default=32)
    a = p.parse_args()
    if a.output.exists() or (a.diagnostics and a.diagnostics.exists()):
        raise FileExistsError("Refuse to overwrite existing experiment artifacts")
    plan, info = construct(json.loads(a.graph.read_text()), a.cores,
        input_budget_bytes=a.input_budget_bytes, activation_bytes=a.activation_bytes,
        max_phases=a.max_phases)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x") as f:
        json.dump(plan, f, separators=(",", ":"))
        f.write("\n")
    if a.diagnostics:
        a.diagnostics.parent.mkdir(parents=True, exist_ok=True)
        with a.diagnostics.open("x") as f:
            json.dump(info, f, indent=2)
            f.write("\n")
    print(json.dumps(info))


if __name__ == "__main__":
    main()
