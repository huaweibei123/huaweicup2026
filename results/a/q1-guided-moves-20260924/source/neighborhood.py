"""Exact Task-order insertion intervals for fixed-partition Q1 moves.

Legality here concerns the augmented Task DAG, not execution cost or the
subsequent expanded FIFO/memory graph; every candidate still goes to E0/E1.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import random
import time

from search import plan_key
from stub_multicore_cut_and_schedule import derive_multicore_plan, MulticoreCutError
from evaluation_validation import validate_task_order, EvaluationValidationError


def reachable(start, adjacency):
    seen, stack = set(), list(adjacency[start])
    while stack:
        node = stack.pop()
        if node not in seen:
            seen.add(node)
            stack.extend(adjacency[node] - seen)
    return seen


class TaskOrderIndex:
    def __init__(self, graph, plan):
        view = derive_multicore_plan(graph, plan)
        validate_task_order(view)
        self.plan = copy.deepcopy(plan)
        self.nodes = view['subgraph_ids']
        self.data_edges = view['dependency_pairs']
        self.orders = [list(x) for x in plan['core_schedules']]
        self._bounds = {}

    def _relations(self, task):
        if task not in self._bounds:
            successors = {t: set() for t in self.nodes}
            predecessors = {t: set() for t in self.nodes}
            edges = set(self.data_edges)
            for order in self.orders:
                rest = [t for t in order if t != task]
                edges.update(zip(rest, rest[1:]))
            for a, b in edges:
                successors[a].add(b)
                predecessors[b].add(a)
            self._bounds[task] = reachable(task, predecessors), reachable(task, successors)
        return self._bounds[task]

    def positions(self, task, target):
        """All legal insertion slots in the target order after removing task."""
        ancestors, descendants = self._relations(task)
        target_order = [t for t in self.orders[target] if t != task]
        lower = 1 + max((i for i, t in enumerate(target_order) if t in ancestors), default=-1)
        upper = min((i for i, t in enumerate(target_order) if t in descendants), default=len(target_order))
        return range(lower, upper + 1)

    def move(self, task, target, position):
        orders = [[t for t in order if t != task] for order in self.orders]
        orders[target].insert(position, task)
        return {'node_to_subgraph': dict(self.plan['node_to_subgraph']), 'core_schedules': orders}


def generate(graph, plan, method, seed, count, max_proposals):
    start = time.perf_counter()
    index = TaskOrderIndex(graph, plan)
    index_seconds = time.perf_counter() - start
    rng = random.Random(seed)
    nonempty = [k for k, order in enumerate(index.orders) if order]
    seen, candidates = {plan_key(plan)}, []
    attempts = rejected = duplicate = 0
    start = time.perf_counter()
    while attempts < max_proposals and len(candidates) < count:
        attempts += 1
        source = rng.choice(nonempty)
        task = rng.choice(index.orders[source])
        target = rng.randrange(len(index.orders))
        if method == 'guided':
            slots = list(index.positions(task, target))
        else:
            slots = list(range(len(index.orders[target]) - int(source == target) + 1))
        if not slots:
            rejected += 1
            continue
        candidate = index.move(task, target, rng.choice(slots))
        key = plan_key(candidate)
        if key in seen:
            duplicate += 1
            continue
        if method == 'random':
            try:
                validate_task_order(derive_multicore_plan(graph, candidate))
            except (MulticoreCutError, EvaluationValidationError):
                rejected += 1
                continue
        seen.add(key)
        candidates.append(candidate)
    return {'plans': candidates, 'method': method, 'seed': seed,
            'attempts': attempts, 'rejected': rejected, 'duplicate': duplicate,
            'index_seconds': index_seconds, 'generation_seconds': time.perf_counter() - start,
            'cached_task_relations': len(index._bounds),
            'scope': 'Fixed partition and fixed incumbent; Task-order legality only; exact execution evaluation follows'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('graph', type=Path); p.add_argument('plan', type=Path); p.add_argument('output', type=Path)
    p.add_argument('--method', choices=['random', 'guided'], required=True)
    p.add_argument('--seed', type=int, default=0); p.add_argument('--count', type=int, default=31)
    p.add_argument('--max-proposals', type=int, default=128)
    args = p.parse_args()
    if args.count < 0 or args.max_proposals < 1:
        p.error('invalid generation budget')
    result = generate(json.loads(args.graph.read_text()), json.loads(args.plan.read_text()),
                      args.method, args.seed, args.count, args.max_proposals)
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
