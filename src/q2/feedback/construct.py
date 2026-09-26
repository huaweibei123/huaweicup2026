"""Deterministic P2 priority construction; no evaluator or score search.

Component ownership and the component/affine/guarded-word controls follow the
published Q3 Index at 5f7e6f5 (NikolaStarx), itself based on archived Pro2.
The new pipe_window policy schedules a bounded set of component topological
chains on ideal compute pipes. Those times are only priority coordinates.
COPY, bandwidth, spill, memory edges and final legality remain E0's job.
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))
from evaluation_validation import validate_graph  # noqa: E402
from stub_multicore_cut_and_schedule import (  # noqa: E402
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)

PIPES = ("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3")


class UnsupportedStructure(ValueError):
    pass


def topo(nodes, succ):
    nodes = set(nodes)
    degree = dict.fromkeys(nodes, 0)
    for u in nodes:
        for v in succ[u]:
            if v in nodes:
                degree[v] += 1
    ready = [u for u in nodes if not degree[u]]
    heapq.heapify(ready)
    order = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in sorted(succ[u]):
            if v in nodes:
                degree[v] -= 1
                if not degree[v]:
                    heapq.heappush(ready, v)
    if len(order) != len(nodes):
        raise ValueError("eligible dependency cycle")
    return order


class Index:
    def __init__(self, graph):
        validate_graph(graph)
        self.graph = graph
        self.ops = {o["id"]: o for o in graph["ops"]
                    if o["op"] not in {"COPY_IN", "COPY_OUT"}}
        _, full_succ = _build_op_adjacency(graph)
        self.pred, self.succ = _contract_excluded_copy_nodes(self.ops, full_succ)
        self.order = topo(self.ops, self.succ)
        unvisited = set(self.ops)
        self.components = []
        self.owner = {}
        for root in self.order:
            if root not in unvisited:
                continue
            j = len(self.components)
            self.components.append([])
            unvisited.remove(root)
            stack = [root]
            while stack:
                u = stack.pop()
                self.owner[u] = j
                for v in self.pred[u] | self.succ[u]:
                    if v in unvisited:
                        unvisited.remove(v)
                        stack.append(v)
        for u in self.order:
            self.components[self.owner[u]].append(u)
        self.work = [{p: sum(self.duration(u) for u in comp
                            if self.ops[u]["pipe"] == p) for p in PIPES}
                     for comp in self.components]

    def duration(self, u):
        return max(1, self.ops[u]["cycles"])

    def assignment(self, cores):
        if type(cores) is not int or not 1 <= cores <= 5:
            raise ValueError("cores must be an integer in 1..5")
        total = {p: max(1, sum(w[p] for w in self.work)) for p in PIPES}
        load = [{p: 0 for p in PIPES} for _ in range(cores)]
        groups = [[] for _ in range(cores)]
        for j in sorted(range(len(self.components)), key=lambda j: (
                -max(self.work[j].values()), -sum(self.work[j].values()),
                self.components[j][0])):
            c = min(range(cores), key=lambda c: (
                max((load[c][p] + self.work[j][p]) / total[p] for p in PIPES),
                sum(load[c].values()), c))
            groups[c].append(j)
            for p in PIPES:
                load[c][p] += self.work[j][p]
        for jobs in groups:
            jobs.sort(key=lambda j: self.components[j][0])
        return groups

    def word_descriptor(self):
        signatures = []
        for job in self.components:
            pipes = [self.ops[u]["pipe"] for u in job]
            if (len(job) < 3 or pipes[0] != "PIPE_M" or pipes[-1] != "PIPE_M"
                    or any(p != "PIPE_V" for p in pipes[1:-1])):
                raise UnsupportedStructure("requires M -> V* -> M components")
            # Consecutive edges plus topo order prove the chain; shortcut edges
            # are allowed and do not create an alternative parallel branch.
            if any(v not in self.succ[u] for u, v in zip(job, job[1:])):
                raise UnsupportedStructure("requires true serial chains")
            d = tuple(self.duration(u) for u in job)
            if d[0] != d[-1]:
                raise UnsupportedStructure("requires equal first/last M times")
            signatures.append(d)
        if not signatures or len(set(signatures)) != 1:
            raise UnsupportedStructure("requires homogeneous nonempty jobs")
        a, b = signatures[0][0], sum(signatures[0][1:-1])
        if b > 2 * a:
            raise UnsupportedStructure("ideal word domain requires b <= 2a")
        return a, b, 1 + math.ceil(b / a)

    def window_size(self, jobs):
        """Little's-law style compute-only admission heuristic, not a bound.

        ceil(total serial work / total bottleneck-pipe work) + 1 gives three
        active jobs for the known M-V-M family; cap at 8 to bound generation.
        No claim about the physical tensor live set or absence of spill.
        """
        if not jobs:
            return 0
        pipe_work = [sum(self.work[j][p] for j in jobs) for p in PIPES]
        return min(len(jobs), 8, 1 + math.ceil(sum(pipe_work) / max(pipe_work)))

    def pipe_window(self, jobs, window, prefer_fill=False):
        if not jobs:
            return [], {"window": 0, "ideal_coordinate_end": 0}
        window = min(len(jobs), window or self.window_size(jobs))
        if window < 1:
            raise ValueError("window must be positive")
        ready_time = {}
        position = {}
        tail = {}
        active = []
        pipe_time = dict.fromkeys(PIPES, 0)
        next_job = 0

        def admit(release):
            nonlocal next_job
            j = jobs[next_job]
            next_job += 1
            active.append(j)
            position[j] = 0
            ready_time[j] = release
            tail[j] = sum(self.work[j].values())

        for _ in range(window):
            admit(0)
        seq = []
        while active:
            def key(j):
                u = self.components[j][position[j]]
                start = max(ready_time[j], pipe_time[self.ops[u]["pipe"]])
                # Round 1 drains at a tie. The fill variant instead exposes
                # earlier job stages (larger remaining work) so the returning
                # bottleneck pipe need not wait for a late admitted last job.
                # Neither tie policy is an official optimality theorem.
                return start, -tail[j] if prefer_fill else tail[j], u
            j = min(active, key=key)
            u = self.components[j][position[j]]
            p = self.ops[u]["pipe"]
            end = max(ready_time[j], pipe_time[p]) + self.duration(u)
            pipe_time[p] = ready_time[j] = end
            tail[j] -= self.duration(u)
            seq.append(u)
            position[j] += 1
            if position[j] == len(self.components[j]):
                active.remove(j)
                if next_job < len(jobs):
                    # Admission waits for the completed job's ideal finish.
                    admit(end)
        return seq, {"window": window, "ideal_coordinate_end": max(pipe_time.values())}

    def sequence(self, jobs, strategy, window):
        nodes = [u for j in jobs for u in self.components[j]]
        if strategy == "component":
            return nodes, {}
        if strategy in ("pipe_window", "pipe_window_fill"):
            return self.pipe_window(jobs, window, strategy == "pipe_window_fill")
        if strategy == "affine_eighth":
            length = max((sum(self.work[j].values()) for j in jobs), default=1)
            lag = max(1, length // 8)
            tagged = []
            for pos, j in enumerate(jobs):
                prefix = 0
                for u in self.components[j]:
                    tagged.append((prefix + pos * lag, u))
                    prefix += self.duration(u)
            return [u for _, u in sorted(tagged)], {"lag": lag}
        if strategy == "resource_word":
            a, b, h = self.word_descriptor()
            first = [self.components[j][0] for j in jobs]
            last = [self.components[j][-1] for j in jobs]
            m_word = first[:h]
            for i, u in enumerate(last):
                m_word.append(u)
                if i + h < len(first):
                    m_word.append(first[i + h])
            v_word = [u for j in jobs for u in self.components[j][1:-1]]
            succ = {u: set(self.succ[u]) for u in nodes}
            for word in (m_word, v_word):
                for u, v in zip(word, word[1:]):
                    succ[u].add(v)
            ordered = topo(nodes, succ)
            earliest = dict.fromkeys(nodes, 0)
            for u in ordered:
                for v in succ[u]:
                    earliest[v] = max(earliest[v], earliest[u] + self.duration(u))
            return sorted(nodes, key=lambda u: (earliest[u], u)), {"a": a, "b": b, "lookahead": h}
        raise ValueError(f"unknown strategy: {strategy}")

    def build(self, cores=4, strategy="pipe_window", window=None):
        if type(cores) is not int or not 1 <= cores <= 5:
            raise ValueError("cores must be an integer in 1..5")
        if strategy == "tree_dp":
            if len(self.components) != 1 or any(len(s) > 1 for s in self.succ.values()):
                raise UnsupportedStructure("tree_dp requires one connected in-tree, outdegree <= 1")
            from .tree import build_tree_plan
            plan, meta = build_tree_plan(self, cores)
            derive_multicore_plan(self.graph, plan)
            return plan, meta
        if window is not None and (type(window) is not int or window < 1 or window > 8):
            raise ValueError("window must be an integer in 1..8")
        if strategy == "resource_word":
            self.word_descriptor()
        groups = self.assignment(cores)
        mapping = {str(u): i for i, u in enumerate(self.order)}
        sequences, detail = [], []
        for jobs in groups:
            seq, meta = self.sequence(jobs, strategy, window)
            sequences.append([mapping[str(u)] for u in seq])
            detail.append(meta)
        plan = {"node_to_subgraph": mapping, "core_schedules": sequences}
        derive_multicore_plan(self.graph, plan)
        return plan, {"strategy": strategy, "components": len(self.components),
                      "eligible_ops": len(self.ops), "cores": cores,
                      "jobs_by_core": [len(g) for g in groups], "core_detail": detail,
                      "scope": "compute priority heuristic; E0 execution not checked"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--strategy", choices=("component", "affine_eighth", "resource_word", "pipe_window", "pipe_window_fill", "tree_dp", "tensor_packet", "capacity_window", "gap_packet", "frontier_gap", "component_gate"), default="pipe_window")
    parser.add_argument("--window", type=int)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_bytes())
    try:
        if args.strategy in ("tensor_packet", "capacity_window", "gap_packet", "frontier_gap", "component_gate"):
            from . import tensor_packet
            from evaluation_validation import read_evaluation_config
            from multicore_cut_evaluate_problem_2 import read_scene_b_config
            config_path = ROOT / "data/raw/a/official/data/config.txt"
            config = {**read_evaluation_config(config_path), **read_scene_b_config(config_path)}
            try:
                index = tensor_packet.TensorIndex(graph)
                if args.strategy == "tensor_packet":
                    plan, meta = index.build_tensor_plan(
                        args.cores, config["bandwidth"], config["cross_core_copy_delay_cycles"])
                else:
                    if args.strategy == "capacity_window":
                        from .capacity_window import build
                    elif args.strategy == "frontier_gap":
                        from .frontier_gap import build
                    elif args.strategy == "component_gate":
                        from .component_gate import build
                    else:
                        from .gap_packet import build
                    plan, meta = build(index, args.cores, config["bandwidth"],
                                       config["cross_core_copy_delay_cycles"], config["capacity"])
            except tensor_packet.UnsupportedStructure as exc:
                raise UnsupportedStructure(str(exc)) from exc
        else:
            plan, meta = Index(graph).build(args.cores, args.strategy, args.window)
    except UnsupportedStructure as exc:
        print(json.dumps({"status": "unsupported", "reason": str(exc)}))
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(meta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
