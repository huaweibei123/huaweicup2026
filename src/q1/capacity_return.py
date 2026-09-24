"""One direct, capacity-derived return-cut candidate for private M/V/M chains.

This is an experimental constructor, not an evaluator or a quality guarantee.
It reuses the archived Pro recognizer and encoder, without its ideal-model
chooser. All chains are cut immediately before their final M operation.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
AUTHOR_PATH = ROOT / 'AI chats/P1多Pipe链构造证明/附件/r1-p1_s6607/p1_phase_cut.py'
spec = importlib.util.spec_from_file_location('_p1_archived_return', AUTHOR_PATH)
author = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = author
spec.loader.exec_module(author)


def construct(graph, cores, capacity=None):
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError('cores must be an integer in 1..5')
    capacity = {'L1': 524288, 'UB': 131072} if capacity is None else capacity
    if set(capacity) != {'L1', 'UB'} or any(type(v) is not int or v <= 0 for v in capacity.values()):
        raise ValueError('capacity must contain positive integer L1 and UB bytes')
    view, chains, _, _, _ = author.recognize(graph)

    def footprint(nodes):
        touched = set()
        for node in nodes:
            touched.update(view.in_t[node] | view.out_t[node])
        return {p: sum(view.tensors[t]['size'] for t in touched
                       if ('UB' if view.tensors[t]['pos'] == 'DDR' else view.tensors[t]['pos']) == p)
                for p in capacity}

    # Different chains have disjoint tensor identities. Within a mixed Task,
    # count both the new prefixes and the preceding packet's returns, including
    # their interface tensors; do not treat the cut as a free synchronization.
    prefix = footprint(chains[0][:-1])
    suffix = footprint(chains[0][-1:])
    mixed = {p: prefix[p] + suffix[p] for p in capacity}
    per_core = (len(chains) + cores - 1) // cores
    packet = min([per_core] + [capacity[p] // mixed[p] for p in capacity if mixed[p]])
    if packet < 1:
        raise author.Unsupported('mixed packet exceeds conservative virgin capacity')
    plan = author.encode(chains, graph['ops'], cores, packet=packet,
                         cut_count=len(chains), whole_packet=1)
    author.validate_plan_structure(graph, plan)
    return plan, dict(algorithm_id='q1-capacity-return', variant='all-cut-capacity-packet-v1',
                     chains=len(chains), packet=packet, cut_chains=len(chains),
                     representative_prefix_bytes=prefix, representative_return_bytes=suffix,
                     mixed_packet_bytes={p: packet * mixed[p] for p in capacity},
                     capacity_bytes=capacity, tasks=sum(map(len, plan['core_schedules'])),
                     scope='Graph-derived candidate; no model scoring, no DDR or quality certificate; external E0 required')


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
