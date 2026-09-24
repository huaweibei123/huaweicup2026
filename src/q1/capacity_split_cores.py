"""Direct private-chain candidate with separate whole and return-cut cores.

The rate calculation is a scheduling proxy, not an E0 prediction or proof.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1.capacity_return import author


def construct(graph, cores, capacity=None):
    if type(cores) is not int or not 2 <= cores <= 5:
        raise ValueError('cores must be an integer in 2..5')
    capacity = {'L1': 524288, 'UB': 131072} if capacity is None else capacity
    if set(capacity) != {'L1', 'UB'} or any(type(v) is not int or v <= 0 for v in capacity.values()):
        raise ValueError('capacity must contain positive integer L1 and UB bytes')
    view, chains, _, _, _ = author.recognize(graph)
    n = len(chains)

    def footprint(nodes):
        touched = set()
        for u in nodes:
            touched.update(view.in_t[u] | view.out_t[u])
        return {p: sum(view.tensors[t]['size'] for t in touched
                       if ('UB' if view.tensors[t]['pos'] == 'DDR' else view.tensors[t]['pos']) == p)
                for p in capacity}

    prefix = footprint(chains[0][:-1])
    ret = footprint(chains[0][-1:])
    whole = footprint(chains[0])
    mixed = {p: prefix[p] + ret[p] for p in capacity}

    def fit(sizes):
        return min([n] + [capacity[p] // sizes[p] for p in capacity if sizes[p]])

    qcut, qwhole = fit(mixed), fit(whole)
    if min(qcut, qwhole) < 1:
        raise author.Unsupported('whole or mixed task exceeds conservative virgin capacity')

    first = chains[0]
    a = max(1, view.ops[first[0]]['cycles'])
    b = sum(max(1, view.ops[u]['cycles']) for u in first[1:-1])
    c = max(1, view.ops[first[-1]]['cycles'])
    gate = 100
    # Whole chains remain serial in the M FIFO; batching amortizes only the
    # Task gate, not chain work. The split pipeline has a separate rate proxy.
    whole_rate = Fraction(a + b + c) + Fraction(gate, qwhole)
    cut_rate = Fraction(max(qcut * (a + c), a + b + (qcut - 1) * max(a, b)) + gate, qcut)
    whole_plan = author.encode(chains, graph['ops'], cores, packet=1,
                               cut_count=0, whole_packet=qwhole)
    d0 = author.boundary_counts(graph, whole_plan, 60)['boundary_service_cycles']
    delta = author.cut_table(graph, first, 60)[-1]['one_cut_extra_service_with_external_duplication']

    def floorceil_clipped(value):
        lo = max(0, min(n, value.numerator // value.denominator))
        return {lo, min(n, lo + 1)}

    best = None
    for w in range(1, cores):
        cut_cores = cores - w
        ab = whole_rate * n * cut_cores / (whole_rate * cut_cores + cut_rate * w)
        ad = (whole_rate * n - d0 * w) / (whole_rate + delta * w)
        xs = {0, n} | floorceil_clipped(ab) | floorceil_clipped(ad)
        for x in sorted(xs):
            # Integer per-core chain counts; gate cost remains an amortized proxy.
            whole_load = (n - x + w - 1) // w
            cut_load = (x + cut_cores - 1) // cut_cores
            score = max(whole_rate * whole_load, cut_rate * cut_load, d0 + delta * x)
            key = (score, w, x)
            if best is None or key < best[0]:
                best = (key, w, x)
    _, w, x = best
    whole_chains, cut_chains = chains[:n-x], chains[n-x:]
    def ops_for(group):
        nodes = {u for chain in group for u in chain}
        return [op for op in graph['ops'] if op['id'] in nodes]

    whole_part = author.encode(whole_chains, ops_for(whole_chains), w, packet=1,
                               cut_count=0, whole_packet=qwhole)
    cut_part = author.encode(cut_chains, ops_for(cut_chains), cores-w, packet=qcut,
                             cut_count=x, whole_packet=1)
    offset = sum(map(len, whole_part['core_schedules']))
    plan = {
        'node_to_subgraph': {**whole_part['node_to_subgraph'],
                             **{u: task + offset for u, task in cut_part['node_to_subgraph'].items()}},
        'core_schedules': whole_part['core_schedules'] +
                          [[task + offset for task in line] for line in cut_part['core_schedules']],
    }
    author.validate_plan_structure(graph, plan)
    info = dict(algorithm_id='q1-capacity-split-cores', variant='whole-cut-separate-cores-v1',
                chains=n, whole_cores=w, cut_cores=cores-w, whole_chains=n-x, cut_chains=x,
                whole_packet=qwhole, cut_packet=qcut, prefix_bytes=prefix, return_bytes=ret,
                whole_bytes=whole, mixed_bytes=mixed, capacity_bytes=capacity,
                model=dict(a=a, b=b, c=c, gate=gate, whole_rate=str(whole_rate),
                           cut_rate=str(cut_rate), whole_boundary_service=d0,
                           extra_cut_service=delta, predicted_max=str(best[0][0])),
                scope='Deterministic graph-derived proxy; no E0 score or quality certificate')
    return plan, info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostics', type=Path, required=True)
    args = parser.parse_args()
    if args.output == args.diagnostics or args.output.exists() or args.diagnostics.exists():
        raise FileExistsError('Refuse to overwrite artifacts')
    started = time.perf_counter()
    plan, info = construct(json.loads(args.graph.read_bytes()), args.cores)
    info['constructor_including_read_seconds'] = time.perf_counter() - started
    for path, data in ((args.output, plan), (args.diagnostics, info)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as stream:
            json.dump(data, stream, separators=(',', ':'))
            stream.write('\n')


if __name__ == '__main__':
    main()
