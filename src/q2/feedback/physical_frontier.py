"""Bucket-closed physical-token capacity certificate for singleton P2 plans.

This proves only absence of Step2 spill for the reconstructed local buffers.
It does not bound global execution memory or Makespan.
"""
from __future__ import annotations

from collections import defaultdict

from .construct import UnsupportedStructure, derive_multicore_plan
from .tensor_packet import TensorIndex
from stub_multicore_cut_and_schedule import MulticoreCutError


def certificate(index: TensorIndex, plan, capacity) -> dict:
    """Return a sufficient local Step2 certificate for a validated singleton plan.

    Token construction and two event sweeps cost O(V+E+I) after indexing.
    ``derive_multicore_plan`` performs its own sorting/validation separately;
    this function does not claim linear end-to-end time. No V-by-T matrix is built.
    """
    if not isinstance(index, TensorIndex):
        raise TypeError('TensorIndex required')
    if (not isinstance(capacity, dict) or set(capacity) != {'L1', 'UB'}
            or any(type(v) is not int or v < 0 for v in capacity.values())):
        raise ValueError('nonnegative integer L1 and UB capacity required')
    if any('logical_tid' in tensor for tensor in index.tensors.values()):
        raise UnsupportedStructure('logical_tid alias requires separate physical identity proof')
    try:
        view = derive_multicore_plan(index.graph, plan)
    except MulticoreCutError as error:
        raise ValueError('invalid multicore plan: ' + str(error)) from error
    mapping = view['mapping']
    if len(set(mapping.values())) != len(mapping):
        raise UnsupportedStructure('singleton subgraphs required')
    inverse = {sg: u for u, sg in mapping.items()}
    orders = [[inverse[sg] for sg in view['core_orders'][core]]
              for core in range(view['num_cores'])]
    rank = [{u: i for i, u in enumerate(order)} for order in orders]
    core_of = {u: view['core_by_subgraph'][sg] for u, sg in mapping.items()}
    tokens = [{} for _ in orders]

    def touch(core, ident, pool, size, position):
        table = tokens[core]
        if ident not in table:
            table[ident] = {'id': ident, 'pool': pool, 'size': size,
                            'first': position, 'last': position}
        else:
            item = table[ident]
            if item['pool'] != pool or item['size'] != size:
                raise AssertionError('inconsistent physical token')
            item['first'] = min(item['first'], position)
            item['last'] = max(item['last'], position)

    # P2 keeps one local copy of each original tensor per touched core.
    for core, order in enumerate(orders):
        for position, u in enumerate(order):
            for tid in index.inputs[u]:
                tensor = index.tensors[tid]
                touch(core, f'tensor:{tid}:c{core}',
                      'UB' if tensor['pos'] == 'DDR' else tensor['pos'],
                      tensor['size'], position)
            for tid in index.outputs[u]:
                tensor = index.tensors[tid]
                touch(core, f'tensor:{tid}:c{core}',
                      'UB' if tensor['pos'] == 'DDR' else tensor['pos'],
                      tensor['size'], position)

    base_copy_bytes = 0
    base_copy_count = 0
    producer_cores = defaultdict(set)
    for u in index.ops:
        for tid in index.outputs[u]:
            producer_cores[tid].add(core_of[u])
    for tid, tensor in index.tensors.items():
        producers = producer_cores[tid]
        consumers = {core_of[u] for u in index.consumers[tid]}
        incoming = len(consumers) if consumers and not producers else 0
        outgoing = len(producers) if producers and tid in index.final else 0
        cross_pairs = sum(a != b for a in producers for b in consumers)
        copies = incoming + outgoing + 2 * cross_pairs
        base_copy_count += copies
        base_copy_bytes += copies * tensor['size']

    # A direct cross-core edge creates a distinct local UB buffer at each end.
    for edge_id, edge in enumerate(index.graph['edges']):
        src, dst = edge['source'], edge['target']
        if src not in core_of or dst not in core_of or core_of[src] == core_of[dst]:
            continue
        src_core, dst_core = core_of[src], core_of[dst]
        size = max(0, int(edge.get('data_size', 0)))
        touch(src_core, f'direct:{edge_id}:c{src_core}', 'UB', size, rank[src_core][src])
        touch(dst_core, f'direct:{edge_id}:c{dst_core}', 'UB', size, rank[dst_core][dst])
        base_copy_count += 2
        base_copy_bytes += 2 * size

    details = []
    for core, order in enumerate(orders):
        entries = list(tokens[core].values())
        adds = [[0, 0] for _ in order]
        frees = [[0, 0] for _ in order]
        for item in entries:
            pool = 0 if item['pool'] == 'L1' else 1
            adds[item['first']][pool] += item['size']
            frees[item['last']][pool] += item['size']
        live, peak = [0, 0], [0, 0]
        peak_bucket = [None, None]
        for position in range(len(order)):
            for pool in range(2):
                live[pool] += adds[position][pool]
                if peak_bucket[pool] is None or live[pool] > peak[pool]:
                    peak[pool], peak_bucket[pool] = live[pool], position
                live[pool] -= frees[position][pool]
        if any(live):
            raise AssertionError('physical token lifetime did not close')
        names = ('L1', 'UB')
        peak_values = dict(zip(names, peak))
        positions = dict(zip(names, peak_bucket))
        snapshots = {pool: [dict(id=item['id'], size=item['size']) for item in entries
                            if item['pool'] == pool and positions[pool] is not None
                            and item['first'] <= positions[pool] <= item['last']]
                     for pool in names}
        details.append({'core': core, 'peak_bytes': peak_values,
                        'peak_bucket': positions, 'peak_live_tokens': snapshots,
                        'tokens': entries,
                        'certified': all(peak_values[p] <= capacity[p] for p in names)})
    return {'certified': all(item['certified'] for item in details),
            'scope': 'singleton P2 local Step2 bucket envelope; no global peak or Makespan guarantee',
            'capacity_bytes': dict(capacity), 'cores': details,
            'base_copy_bytes': base_copy_bytes, 'base_copy_count': base_copy_count}
