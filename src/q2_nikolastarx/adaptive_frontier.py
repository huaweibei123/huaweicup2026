"""Frozen structural routes for indivisible components and shared input pressure.

This is a new solver version, not a replacement of historical b7 results.
All thresholds are derived from workload or configured memory capacities.
No case IDs, score tables, online evaluator or candidate search is used.
"""
from collections import Counter, defaultdict

from . import adaptive_semantic, component_envelope, shared_input_wave
from .direct import UnsupportedStructure


def component_pressure(index, cores, capacity):
    total = Counter()
    largest = Counter()
    component = {}
    for j, job in enumerate(index.components):
        work = Counter()
        for u in job:
            component[u] = j
            work[index.ops[u]['pipe']] += index.duration(u)
        total.update(work)
        for pipe, amount in work.items():
            largest[pipe] = max(largest[pipe], amount)
    balanced = {p: (amount + cores - 1)//cores for p, amount in total.items()}
    indivisible = any(largest[p] > balanced[p] for p in total)
    shared = Counter()
    users = defaultdict(set)
    for u in index.ops:
        for t in index.inputs[u]:
            if not index.producers[t]:
                users[t].add(component[u])
    for t, jobs in users.items():
        if len(jobs) > 1:
            tensor = index.tensors[t]
            pool = 'UB' if tensor['pos'] == 'DDR' else tensor['pos']
            shared[pool] += tensor['size']
    return {'largest_component_pipe_work': dict(largest),
            'balanced_pipe_work_lower_bound': balanced,
            'component_exceeds_balanced_pipe_work': indivisible,
            'shared_external_bytes': dict(shared),
            'shared_external_exceeds_capacity': any(shared[p] > capacity[p] for p in capacity)}


def component_route(index, cores, config, *, wave_builder=None, allow_component_split=True):
    pressure = component_pressure(index, cores, config['capacity'])
    if not allow_component_split and pressure['component_exceeds_balanced_pipe_work']:
        pressure['component_split_deferred'] = 'compute imbalance alone omits COPY and memory costs'
    if allow_component_split and cores > 1 and pressure['component_exceeds_balanced_pipe_work']:
        plan, detail = index.build(cores, bandwidth=config['bandwidth'],
                                  cross_core_delay=config['cross_core_copy_delay_cycles'])
        return plan, {**detail, 'selected_strategy': 'dominant_component_dag',
                      'component_pressure': pressure,
                      'route_guarantee': 'heuristic; splitting may add COPY, spill and delays'}
    if pressure['shared_external_exceeds_capacity']:
        try:
            plan, detail = (wave_builder or shared_input_wave.build_from_index)(index, cores, config)
        except UnsupportedStructure as error:
            pressure['wave_rejected'] = str(error)
        else:
            return plan, {**detail, 'component_pressure': pressure}
    plan, detail = component_envelope.build_from_index(index, cores, config)
    return plan, {**detail, 'component_pressure': pressure}


def build(graph, cores, config):
    return adaptive_semantic.build(graph, cores, config, component_builder=component_route)


def main():
    adaptive_semantic.main(constructor=build, label='adaptive_frontier')


if __name__ == '__main__':
    main()
