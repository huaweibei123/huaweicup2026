"""Compile component orders into legal submission priorities, without scoring.

Resource-word and affine priorities adapt the archived Pro2 construction ideas;
see docs/a/q3/METHOD.md for provenance, guards and limitations.
"""
from __future__ import annotations

import argparse
import heapq
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OFFICIAL = ROOT / "data/raw/a/official/code"
sys.path.insert(0, str(OFFICIAL))
from evaluation_validation import validate_graph  # noqa: E402
from stub_multicore_cut_and_schedule import (  # noqa: E402
    _build_op_adjacency, _contract_excluded_copy_nodes, derive_multicore_plan,
)


class UnsupportedStructure(ValueError):
    """A guarded constructor does not apply; never pretend it was evaluated."""


def topo(nodes, successors):
    nodes = set(nodes)
    degrees = dict.fromkeys(nodes, 0)
    for u in nodes:
        for v in successors[u]:
            if v in nodes:
                degrees[v] += 1
    ready = [u for u in nodes if not degrees[u]]
    heapq.heapify(ready)
    order = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in sorted(successors[u]):
            if v in nodes:
                degrees[v] -= 1
                if not degrees[v]:
                    heapq.heappush(ready, v)
    if len(order) != len(nodes):
        raise ValueError("precedence cycle")
    return order


class Index:
    def __init__(self, graph):
        validate_graph(graph)
        self.graph = graph
        self.ops = {o["id"]: o for o in graph["ops"]
                    if o["op"] not in {"COPY_IN", "COPY_OUT"}}
        _, original_succ = _build_op_adjacency(graph)
        self.pred, self.succ = _contract_excluded_copy_nodes(self.ops, original_succ)
        self.order = topo(self.ops, self.succ)
        remaining = set(self.ops)
        components = []
        # One traversal, followed by a global topological-order filter.
        owner = {}
        for root in self.order:
            if root not in remaining:
                continue
            cid = len(components)
            components.append([])
            remaining.remove(root)
            stack = [root]
            while stack:
                u = stack.pop()
                owner[u] = cid
                for v in self.pred[u] | self.succ[u]:
                    if v in remaining:
                        remaining.remove(v)
                        stack.append(v)
        for u in self.order:
            components[owner[u]].append(u)
        self.components = components

    def duration(self, u):
        # Priority coordinates only; official durations and contention are E0's.
        return max(1, self.ops[u]["cycles"])

    def assignment(self, cores):
        if type(cores) is not int or cores < 1:
            raise ValueError("cores must be a positive integer")
        pipes = ("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3")
        work = [[sum(self.duration(u) for u in c if self.ops[u]["pipe"] == p)
                 for p in pipes] for c in self.components]
        total = [max(1, sum(w[p] for w in work)) for p in range(len(pipes))]
        load = [[0] * len(pipes) for _ in range(cores)]
        groups = [[] for _ in range(cores)]
        for j in sorted(range(len(work)), key=lambda j: (-max(work[j]), -sum(work[j]),
                                                         min(self.components[j]))):
            c = min(range(cores), key=lambda c: (
                max((load[c][p] + work[j][p]) / total[p] for p in range(len(pipes))),
                sum(load[c]), c))
            groups[c].append(j)
            for p in range(len(pipes)):
                load[c][p] += work[j][p]
        for jobs in groups:
            jobs.sort(key=lambda j: min(self.components[j]))
        return groups

    def word_descriptor(self):
        desc = []
        for job in self.components:
            pipes = [self.ops[u]["pipe"] for u in job]
            if (len(job) < 3 or pipes[0] != "PIPE_M" or pipes[-1] != "PIPE_M"
                    or any(p != "PIPE_V" for p in pipes[1:-1])):
                raise UnsupportedStructure("requires M -> V* -> M components")
            if any(v not in self.succ[u] for u, v in zip(job, job[1:])):
                raise UnsupportedStructure("requires an actual serial chain")
            durations = tuple(self.duration(u) for u in job)
            if durations[0] != durations[-1]:
                raise UnsupportedStructure("requires equal first/last M work")
            desc.append(durations)
        if not desc or len(set(desc)) != 1:
            raise UnsupportedStructure("requires homogeneous nonempty jobs")
        a, b = desc[0][0], sum(desc[0][1:-1])
        # This is the domain of the archived ideal two-resource result.
        if b > 2 * a:
            raise UnsupportedStructure("ideal word guard requires b <= 2a")
        return a, b, 1 + (b + a - 1) // a

    def sequences(self, cores, strategy):
        groups = self.assignment(cores)
        if strategy == "resource_word":
            a, b, lookahead = self.word_descriptor()
            detail = {"a": a, "b": b, "lookahead": lookahead}
        else:
            detail = {}
        sequences = []
        for jobs in groups:
            nodes = [u for j in jobs for u in self.components[j]]
            if strategy == "component":
                seq = nodes
            elif strategy == "affine_eighth":
                length = max((sum(self.duration(u) for u in self.components[j])
                              for j in jobs), default=1)
                lag = max(1, length // 8)
                tagged = []
                for pos, j in enumerate(jobs):
                    prefix = 0
                    for u in self.components[j]:
                        tagged.append((prefix + pos * lag, u))
                        prefix += self.duration(u)
                seq = [u for _, u in sorted(tagged)]
            elif strategy == "resource_word":
                first = [self.components[j][0] for j in jobs]
                last = [self.components[j][-1] for j in jobs]
                m_word = first[:lookahead]
                for i, u in enumerate(last):
                    m_word.append(u)
                    if i + lookahead < len(first):
                        m_word.append(first[i + lookahead])
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
                seq = sorted(nodes, key=lambda u: (earliest[u], u))
            else:
                raise ValueError(f"unknown strategy: {strategy}")
            sequences.append(seq)
        return sequences, detail

    def build(self, cores=4, strategy="component"):
        sequences, detail = self.sequences(cores, strategy)
        # Fix map insertion order and singleton subgraph IDs across all strategies.
        # Only core_schedules changes; all preserve component/core ownership.
        mapping = {str(u): i for i, u in enumerate(self.order)}
        plan = {"node_to_subgraph": mapping,
                "core_schedules": [[mapping[str(u)] for u in seq] for seq in sequences]}
        derive_multicore_plan(self.graph, plan)
        return plan, {"strategy": strategy, "components": len(self.components),
                      "eligible_ops": len(self.ops), "cores": cores, **detail}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--strategy", choices=("component", "affine_eighth", "resource_word"),
                        default="component")
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    start = time.perf_counter()
    graph = json.loads(args.graph.read_text())
    plan, meta = Index(graph).build(args.cores, args.strategy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(",", ":")) + "\n")
    meta["read_to_plan_seconds"] = time.perf_counter() - start
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
