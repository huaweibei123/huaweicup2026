"""P3 input-sharing constructors; no scoring, case-name lookup, or parameter sweep."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from fractions import Fraction

from .baseline import Index, UnsupportedStructure, derive_multicore_plan
from multicore_cut_evaluate_problem_1 import _original_tensor_views


class SharingIndex(Index):
    def __init__(self, graph):
        super().__init__(graph)
        self.owner = {u: j for j, job in enumerate(self.components) for u in job}
        self.inputs = [set() for _ in self.components]
        self.sizes = {t['id']: t['size'] for t in graph['tensors']}
        producers, consumers, _ = _original_tensor_views(graph)
        self.support = {}
        for tid, readers in consumers.items():
            jobs = {self.owner[u] for u in readers if u in self.owner}
            if jobs and not any(u in self.ops for u in producers.get(tid, ())):
                self.support[tid] = jobs
                for j in jobs:
                    self.inputs[j].add(tid)
        self.pipes = ('PIPE_M', 'PIPE_V', 'PIPE_MTE2', 'PIPE_MTE3')
        self.work = [[sum(self.duration(u) for u in job
                          if self.ops[u]['pipe'] == p) for p in self.pipes]
                     for job in self.components]

    def ingress_bytes(self, groups):
        return sum(sum(self.sizes[t] for t in set().union(
            *(self.inputs[j] for j in jobs))) for jobs in groups)

    def shared_assignment(self, cores):
        """Greedy input-net packing under baseline per-pipe load ceilings.

        If the bounded packing gets stuck, return the whole baseline assignment.
        Ceilings constrain a compute proxy only, never assert E0 dominance.
        """
        baseline = super().assignment(cores)
        caps = [max(sum(self.work[j][p] for j in jobs) for jobs in baseline)
                for p in range(len(self.pipes))]
        load = [[0] * len(self.pipes) for _ in range(cores)]
        seen = [set() for _ in range(cores)]
        groups = [[] for _ in range(cores)]
        shared = [sum(self.sizes[t] * (len(self.support[t]) - 1)
                      for t in self.inputs[j]) for j in range(len(self.components))]
        jobs = sorted(range(len(self.components)),
                      key=lambda j: (-max(self.work[j]), -shared[j],
                                     -sum(self.work[j]), min(self.components[j])))
        for j in jobs:
            feasible = [c for c in range(cores) if all(
                load[c][p] + self.work[j][p] <= caps[p] for p in range(len(caps)))]
            if not feasible:
                return baseline, True
            c = min(feasible, key=lambda c: (
                sum(self.sizes[t] for t in self.inputs[j] - seen[c]),
                max(Fraction(load[c][p] + self.work[j][p], max(1, caps[p]))
                    for p in range(len(caps))), sum(load[c]), c))
            groups[c].append(j)
            seen[c].update(self.inputs[j])
            for p in range(len(caps)):
                load[c][p] += self.work[j][p]
        for jobs in groups:
            jobs.sort(key=lambda j: min(self.components[j]))
        return groups, False

    def input_order(self, groups):
        """Use a common dominant input-bundle order on all cores.

        Equal support tensors form a static bundle only; real tensors, IDs,
        COPY operations and FIFO Cache semantics are never changed.
        """
        bundles = {}
        for tid, jobs in self.support.items():
            if len(jobs) > 1:
                bundles.setdefault(tuple(sorted(jobs)), []).append(tid)
        signatures = [[] for _ in self.components]
        ranked = sorted(bundles.items(), key=lambda item: (
            -sum(self.sizes[t] for t in item[1]) * (len(item[0]) - 1), min(item[1])))
        for rank, (jobs, _) in enumerate(ranked):
            for j in jobs:
                signatures[j].append(rank)
        fallback = len(ranked)
        return [sorted(jobs, key=lambda j: (tuple(signatures[j]) or (fallback,),
                                           min(self.components[j]))) for jobs in groups]

    def build_variant(self, cores, variant):
        if not 1 <= cores <= 5:
            raise ValueError('official experiment cores must be 1..5')
        try:
            self.word_descriptor()
            guarded = True
        except UnsupportedStructure:
            guarded = False
        if variant == 'baseline' or guarded:
            strategy = 'resource_word' if guarded else 'affine_eighth'
            plan, detail = self.build(cores, strategy)
            detail.update(variant=variant, selected=strategy,
                          ingress_proxy_bytes=self.ingress_bytes(self.assignment(cores)))
            return plan, detail
        groups = self.assignment(cores)
        before = self.ingress_bytes(groups)
        fallback = False
        if variant == 'shared_place':
            groups, fallback = self.shared_assignment(cores)
        elif variant != 'shared_order':
            raise ValueError(variant)
        groups = self.input_order(groups)
        sequences = []
        for jobs in groups:
            length = max((sum(self.duration(u) for u in self.components[j])
                          for j in jobs), default=1)
            lag = max(1, length // 8)
            tagged = []
            for pos, j in enumerate(jobs):
                prefix = 0
                for u in self.components[j]:
                    tagged.append((prefix + pos * lag, u))
                    prefix += self.duration(u)
            sequences.append([u for _, u in sorted(tagged)])
        mapping = {str(u): i for i, u in enumerate(self.order)}
        plan = {'node_to_subgraph': mapping,
                'core_schedules': [[mapping[str(u)] for u in seq] for seq in sequences]}
        derive_multicore_plan(self.graph, plan)
        return plan, dict(variant=variant, selected=variant, cores=cores,
                          components=len(self.components), eligible_ops=len(self.ops),
                          packing_fallback=fallback, baseline_ingress_proxy_bytes=before,
                          ingress_proxy_bytes=self.ingress_bytes(groups))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('graph', type=Path)
    ap.add_argument('--cores', type=int, required=True)
    ap.add_argument('--variant', choices=('baseline', 'shared_order', 'shared_place'), required=True)
    ap.add_argument('-o', '--output', type=Path, required=True)
    args = ap.parse_args()
    plan, detail = SharingIndex(json.loads(args.graph.read_text(encoding='utf-8'))).build_variant(
        args.cores, args.variant)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps(detail, sort_keys=True))


if __name__ == '__main__':
    main()
