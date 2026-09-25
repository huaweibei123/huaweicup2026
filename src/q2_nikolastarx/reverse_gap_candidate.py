"""Sink-first P2 chain/gap candidate on a *virtual* reversed precedence DAG.

Original graph tensors and dependencies are never reversed. Calendar timestamps
are construction priorities, not official start times, scores, or lower bounds.
"""
from __future__ import annotations

import heapq
import math

from .dag_direct import DAGIndex
from .direct import derive_multicore_plan, topo
from .gap_calendar import earliest, empty, reserve
from .gap_candidate import _chain_dag


def build(graph, cores, config):
    """Build one deterministic singleton plan, without evaluator calls."""
    bandwidth = config['bandwidth']
    cross_delay = config['cross_core_copy_delay_cycles']
    if (type(cores) is not int or not 1 <= cores <= 5
            or type(bandwidth) not in (int, float) or not math.isfinite(bandwidth) or bandwidth <= 0
            or type(cross_delay) is not int or cross_delay < 0):
        raise ValueError('invalid fixed parameters')
    index = DAGIndex(graph)
    forward_chains, forward_pred, forward_succ, forward_delay, forward_order = _chain_dag(
        index, bandwidth, cross_delay)
    chains = [list(reversed(chain)) for chain in forward_chains]
    pred, succ = forward_succ, forward_pred
    delay = {(b, a): lag for (a, b), lag in forward_delay.items()}
    order = list(reversed(forward_order))
    rank = {}
    for j in reversed(order):
        rank[j] = sum(index.duration(u) for u in chains[j]) + max(
            (rank[v] for v in succ[j]), default=0)
    degree = [len(ps) for ps in pred]
    ready = [(-rank[j], min(chains[j]), j) for j, count in enumerate(degree) if not count]
    heapq.heapify(ready)
    pipes = sorted({op['pipe'] for op in index.ops.values()})
    calendars = [dict.fromkeys(pipes, empty()) for _ in range(cores)]
    placement, finish, starts = {}, {}, {}
    per_core = [[] for _ in range(cores)]
    choices = paired = 0

    def place(j, core, calendar, temporary=None):
        release = cuts = 0
        for p in pred[j]:
            pc, end = (temporary[1:3] if temporary is not None and p == temporary[0]
                       else (placement[p], finish[p]))
            release = max(release, end + (delay[p, j] if pc != core else 0))
            cuts += pc != core
        updated, entries = dict(calendar), []
        for u in chains[j]:
            pipe, duration = index.ops[u]['pipe'], index.duration(u)
            start = earliest(updated[pipe], release, duration)
            updated[pipe] = reserve(updated[pipe], start, duration)
            release = start + duration
            entries.append((u, start))
        return release, cuts, updated, entries

    while ready:
        _, _, j = heapq.heappop(ready)
        if j in placement:
            continue
        candidate = next(iter(succ[j])) if len(succ[j]) == 1 else None
        join = candidate if (candidate is not None and len(pred[candidate]) > 1
                             and pred[candidate] - {j} <= placement.keys()) else None
        best = None
        for core in range(cores):
            end, cuts, calendar, entries = place(j, core, calendars[core])
            if join is None:
                options = [((end, cuts, core), [(j, core, end, calendar, entries)])]
            else:
                options = []
                for target in range(cores):
                    final, other_cuts, joined, other_entries = place(
                        join, target, calendar if core == target else calendars[target],
                        (j, core, end))
                    options.append(((final, end, cuts + other_cuts, core, target),
                                    [(j, core, end, calendar, entries),
                                     (join, target, final, joined, other_entries)]))
            choices += len(options)
            for item in options:
                if best is None or item[0] < best[0]:
                    best = item
        paired += join is not None
        for v, core, end, calendar, entries in best[1]:
            placement[v], finish[v], calendars[core] = core, end, calendar
            for u, start in entries:
                starts[u] = start
                per_core[core].append(u)
        for v, *_ in best[1]:
            for successor in succ[v]:
                degree[successor] -= 1
                if degree[successor] == 0 and successor not in placement:
                    heapq.heappush(ready, (-rank[successor], min(chains[successor]), successor))
    if len(placement) != len(chains):
        raise ValueError('incomplete reverse join/gap construction')
    mapping = {str(u): position for position, u in enumerate(index.order)}
    schedules = [list(reversed(sorted(sequence, key=lambda u: (starts[u], mapping[str(u)]))))
                 for sequence in per_core]
    # The official derivation checks the plan's structural format. A global
    # precedence check also catches cycles caused by interleaved core orders.
    combined = {u: set(index.succ[u]) for u in index.ops}
    for sequence in schedules:
        for u, v in zip(sequence, sequence[1:]):
            combined[u].add(v)
    topo(index.ops, combined)
    plan = {'node_to_subgraph': mapping,
            'core_schedules': [[mapping[str(u)] for u in seq] for seq in schedules]}
    derive_multicore_plan(graph, plan)
    return plan, {
        'selected': 'reverse_join_gap_candidate', 'chains': len(chains),
        'paired_reverse_joins': paired, 'arithmetic_placement_choices': choices,
        'choice_bound': len(chains) * cores * cores,
        'modeled_reverse_compute_finish': max(finish.values(), default=0),
        'online_E0_calls': 0,
        'scope': ('Static reverse-time communication/compute calendar; no dynamic DDR, '
                  'capacity, spill, COPY contention, official score, or lower-bound guarantee.'),
    }


if __name__ == '__main__':
    from .adaptive_semantic import main
    main(constructor=build, label='reverse_join_gap_candidate')
