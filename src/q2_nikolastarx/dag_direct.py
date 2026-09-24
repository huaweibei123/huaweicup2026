"""Deterministic tensor-aware earliest-finish construction for P2.

The clock model is a placement heuristic, NEVER an evaluator or lower bound.
All four pipe clocks are local, so simultaneous DDR copies are optimistically
charged their isolated bandwidth. Step2 spill / Step3 memory dependencies are
left to E0. See DAG_DIRECT.md for the exact applicability and complexity scope.
"""
from __future__ import annotations

from collections import defaultdict
import heapq
import math

from .direct import Index, derive_multicore_plan

PIPES = ('PIPE_MTE2', 'PIPE_MTE3', 'PIPE_M', 'PIPE_V')


class DAGIndex(Index):
    """Index real tensor incidences separately from contracted precedence edges."""

    def __init__(self, graph):
        super().__init__(graph)
        self.tensors = {t['id']: t for t in graph['tensors']}
        self.inputs = {u: set() for u in self.ops}
        self.outputs = {u: set() for u in self.ops}
        self.producers = defaultdict(set)
        self.consumers = defaultdict(set)
        self.direct_inputs = defaultdict(list)
        self.copy_out_inputs = set()
        original_ops = {o['id']: o for o in graph['ops']}
        for e in graph['edges']:
            a, b = e['source'], e['target']
            if a in self.ops and b in self.tensors:
                self.outputs[a].add(b)
                self.producers[b].add(a)
            elif a in self.tensors and b in self.ops:
                self.inputs[b].add(a)
                self.consumers[a].add(b)
            elif a in self.ops and b in self.ops and a != b:
                self.direct_inputs[b].append((a, max(0, int(e.get('data_size', 0)))))
            elif (a in self.tensors and b in original_ops
                  and original_ops[b].get('op') == 'COPY_OUT'):
                self.copy_out_inputs.add(a)
        self.inputs = {u: tuple(sorted(ts)) for u, ts in self.inputs.items()}
        self.outputs = {u: tuple(sorted(ts)) for u, ts in self.outputs.items()}
        self.direct_inputs = {u: tuple(sorted(self.direct_inputs[u])) for u in self.ops}
        self.tail = {}
        for u in reversed(self.order):
            self.tail[u] = self.duration(u) + max(
                (self.tail[v] for v in self.succ[u]), default=0)

    def build(self, cores, *, bandwidth, cross_core_delay):
        """Return a singleton plan and explicit heuristic diagnostics.

        A ready operation is selected by (-compute critical tail, op ID).
        Each candidate core is compared by (estimated finish including a final
        output write, incremental DDR bytes, total compute load, core ID).
        Tensor arrivals are shared only by identical (tensor, source core,
        destination core), matching P2's COPY construction granularity.
        """
        if type(cores) is not int or cores < 1:
            raise ValueError('cores must be a positive integer')
        if (isinstance(bandwidth, bool) or not isinstance(bandwidth, (int, float))
                or not math.isfinite(bandwidth) or bandwidth <= 0):
            raise ValueError('bandwidth must be finite and positive')
        if (isinstance(cross_core_delay, bool)
                or not isinstance(cross_core_delay, (int, float))
                or not math.isfinite(cross_core_delay) or cross_core_delay < 0):
            raise ValueError('cross_core_delay must be finite and nonnegative')
        pipe_at = [{p: 0 for p in PIPES} for _ in range(cores)]
        load = [0] * cores
        owner, finish = {}, {}
        tensor_source_finish = defaultdict(dict)
        remaining_producers = {t: len(ps) for t, ps in self.producers.items()}
        arrivals = {}
        degree = {u: len(self.pred[u]) for u in self.ops}
        ready = [(-self.tail[u], u) for u in self.order if degree[u] == 0]
        heapq.heapify(ready)
        dispatch = []
        per_core = [[] for _ in range(cores)]
        traffic = {'external_input_bytes': 0, 'cross_core_bytes': 0, 'output_bytes': 0}
        pair_count = 0

        def duration(size):
            return max(1, math.ceil(size / bandwidth))

        def propose(u, core):
            # Only touched clocks are copied; no O(k^2) matrix per vertex.
            updates = {}
            new_arrivals = {}
            added = dict.fromkeys(traffic, 0)
            new_pairs = 0

            def clock(c, pipe):
                return updates.get((c, pipe), pipe_at[c][pipe])

            def transfer(key, source, source_end, size):
                nonlocal new_pairs
                if key in arrivals:
                    return arrivals[key]
                if key in new_arrivals:
                    return new_arrivals[key]
                copy_time = duration(size)
                if source is None:
                    release = 0
                    added['external_input_bytes'] += size
                else:
                    out_end = max(source_end, clock(source, 'PIPE_MTE3')) + copy_time
                    updates[source, 'PIPE_MTE3'] = out_end
                    release = out_end + cross_core_delay
                    added['cross_core_bytes'] += 2 * size
                    new_pairs += 1
                in_end = max(release, clock(core, 'PIPE_MTE2')) + copy_time
                updates[core, 'PIPE_MTE2'] = in_end
                new_arrivals[key] = in_end
                return in_end

            # The contracted graph carries dependency direction, including paths
            # through excluded original COPY operations. Direct/tensor COPY costs
            # are added below only where P2's builder itself adds those copies.
            release = max((finish[v] for v in self.pred[u]), default=0)
            for tid in self.inputs[u]:
                size = self.tensors[tid]['size']
                if not self.producers[tid]:
                    release = max(release, transfer(('tensor', tid, None, core), None, 0, size))
                    continue
                for source, source_end in sorted(tensor_source_finish[tid].items()):
                    if source != core:
                        release = max(release, transfer(
                            ('tensor', tid, source, core), source, source_end, size))
            for pred, size in self.direct_inputs[u]:
                source = owner[pred]
                if source != core:
                    release = max(release, transfer(
                        ('direct', pred, u), source, finish[pred], size))
            pipe = self.ops[u]['pipe']
            end = max(release, clock(core, pipe)) + self.duration(u)
            updates[core, pipe] = end
            score_end = end
            # Final graph output: after the last producer dispatch, reserve one
            # write for every producing core, as the P2 builder does. This is a
            # predicted output cost; it is not an extra dependency for consumers.
            for tid in self.outputs[u]:
                if (self.consumers[tid] and tid not in self.copy_out_inputs
                        or remaining_producers[tid] != 1):
                    continue
                sources = dict(tensor_source_finish[tid])
                sources[core] = max(sources.get(core, 0), end)
                for source, source_end in sorted(sources.items()):
                    out_end = max(source_end, clock(source, 'PIPE_MTE3')) + duration(self.tensors[tid]['size'])
                    updates[source, 'PIPE_MTE3'] = out_end
                    score_end = max(score_end, out_end)
                    added['output_bytes'] += self.tensors[tid]['size']
            score = (score_end, sum(added.values()), load[core], core)
            return score, end, updates, new_arrivals, added, new_pairs

        while ready:
            _, u = heapq.heappop(ready)
            choices = [propose(u, core) for core in range(cores)]
            score, end, updates, incoming, added, pairs = min(choices, key=lambda c: c[0])
            core = score[-1]
            owner[u], finish[u] = core, end
            load[core] += self.duration(u)
            per_core[core].append(u)
            dispatch.append(u)
            for (c, pipe), at in updates.items():
                pipe_at[c][pipe] = at
            arrivals.update(incoming)
            pair_count += pairs
            for category in traffic:
                traffic[category] += added[category]
            for tid in self.outputs[u]:
                remaining_producers[tid] -= 1
                source = tensor_source_finish[tid]
                source[core] = max(source.get(core, 0), end)
            for v in sorted(self.succ[u]):
                degree[v] -= 1
                if degree[v] == 0:
                    heapq.heappush(ready, (-self.tail[v], v))
        if len(dispatch) != len(self.ops):
            raise ValueError('dependency cycle')
        mapping = {str(u): i for i, u in enumerate(self.order)}
        plan = {'node_to_subgraph': mapping,
                'core_schedules': [[mapping[str(u)] for u in seq] for seq in per_core]}
        derive_multicore_plan(self.graph, plan)  # Structural check, zero E0.
        return plan, {
            'strategy': 'tensor_dag_eft', 'eligible_ops': len(self.ops),
            'components': len(self.components), 'cores': cores,
            'bandwidth': bandwidth, 'cross_core_delay': cross_core_delay,
            'predicted_finish_cycles': max((max(p.values()) for p in pipe_at), default=0),
            'predicted_ddr_bytes_without_spill': traffic,
            'predicted_cross_core_pairs': pair_count,
            'compute_load_by_core': load,
            'model_limitations': ['isolated COPY bandwidth; shared DDR contention omitted',
                                  'spill, memory reuse dependencies and Step3 reorder omitted',
                                  'predicted times are not bounds or official scores'],
        }


def construct(graph, cores, *, bandwidth, cross_core_delay):
    return DAGIndex(graph).build(cores, bandwidth=bandwidth, cross_core_delay=cross_core_delay)


def build(graph, cores, config):
    """Root-router entrypoint; requires explicit official P2 settings."""
    return construct(graph, cores, bandwidth=config['bandwidth'],
                     cross_core_delay=config['cross_core_copy_delay_cycles'])


def main():
    import argparse
    import json
    from pathlib import Path
    import time
    from .baseline import OFFICIAL
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--config', type=Path, default=OFFICIAL.parent / 'data/config.txt')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    graph = json.loads(args.graph.read_text(encoding='utf-8'))
    config = {**read_evaluation_config(args.config), **read_scene_b_config(args.config)}
    plan, detail = build(graph, args.cores, config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(plan, stream, separators=(',', ':'))
        stream.write('\n')
    detail['read_to_plan_seconds'] = time.perf_counter() - started
    detail['timing_scope'] = ('graph/config read, index, construction, structural validation and '
                              'plan write; process startup/imports require external outer timer')
    print(json.dumps(detail, sort_keys=True))


if __name__ == '__main__':
    main()
