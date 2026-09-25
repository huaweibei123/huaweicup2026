"""One bounded pairwise chain placement pass using exact original COPY bytes.

Pipe caps protect the initial compute-work peak only. They do not bound
official Makespan, COPY contention, capacity, or Step2 spill.
"""
from __future__ import annotations

from collections import Counter
import heapq

from .binary_hypercut import Hyperedge, connectivity_cost, load_guarded_cut
from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan
from .gap_candidate import _chain_dag
from .hypergraph_cost import HypergraphCost, UnsupportedHypergraph


def _priority(index, plan, view):
    """Toposort the union of original DAG and original per-core singleton order."""
    succ = {u: set(index.succ[u]) for u in index.ops}
    inverse = {sg: u for u, sg in view['mapping'].items()}
    for row in plan['core_schedules']:
        nodes = [inverse[sg] for sg in row]
        for u, v in zip(nodes, nodes[1:]):
            succ[u].add(v)
    degree = {u: 0 for u in index.ops}
    for row in succ.values():
        for v in row:
            degree[v] += 1
    position = {u: i for i, u in enumerate(index.order)}
    ready = [(position[u], u) for u, count in degree.items() if count == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        _, u = heapq.heappop(ready)
        order.append(u)
        for v in sorted(succ[u]):
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, (position[v], v))
    if len(order) != len(index.ops):
        raise UnsupportedStructure('original core priorities and DAG form a cycle')
    return order


def refine(graph, plan, config, region_width=16, *, model_factory=None,
           cost_label='original_copy_bytes'):
    if type(region_width) is not int or not 1 <= region_width <= 16:
        raise ValueError('region_width must be in 1..16')
    index = DAGIndex(graph)
    chains, _, _, _, chain_order = _chain_dag(
        index, config['bandwidth'], config['cross_core_copy_delay_cycles'])
    try:
        view = derive_multicore_plan(graph, plan)
    except Exception as error:
        raise UnsupportedStructure('input plan failed structural validation') from error
    if any(len(nodes) != 1 for nodes in view['nodes_by_subgraph'].values()):
        raise UnsupportedStructure('requires singleton subgraphs')
    priority = _priority(index, plan, view)
    core_by_op = {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}
    chaincores = {}
    for j, chain in enumerate(chains):
        owners = {core_by_op[u] for u in chain}
        if len(owners) != 1:
            raise UnsupportedStructure('each chain must be on one core')
        chaincores[j] = owners.pop()
    try:
        model = (model_factory or HypergraphCost)(graph, index.ops)
    except UnsupportedHypergraph as error:
        raise UnsupportedStructure(str(error)) from error
    state = model.state(core_by_op)
    initial_cost = state.total_bytes
    cores = len(plan['core_schedules'])
    pipes = sorted({op['pipe'] for op in index.ops.values()})
    work = {j: dict(Counter({p: sum(index.duration(u) for u in chain
                                      if index.ops[u]['pipe'] == p) for p in pipes}))
            for j, chain in enumerate(chains)}
    loads = {c: {p: 0 for p in pipes} for c in range(cores)}
    for j, c in chaincores.items():
        for p, amount in work[j].items():
            loads[c][p] += amount
    before_loads = {c: dict(row) for c, row in loads.items()}
    peak = {p: max(loads[c][p] for c in loads) for p in pipes}
    caps = {c: dict(peak) for c in loads}
    opchain = {u: j for j, chain in enumerate(chains) for u in chain}
    regions = flows = accepted = skipped_by_bound = 0

    for a in range(cores):
        for b in range(a + 1, cores):
            pair = [j for j in chain_order if chaincores[j] in (a, b)]
            for start in range(0, len(pair), region_width):
                units = pair[start:start + region_width]
                if not units:
                    continue
                regions += 1
                unitset = set(units)
                incident = {e for j in units for u in chains[j] for e in model.incidence[u]}
                edges = []
                for edge_id in sorted(incident):
                    edge = model.edges[edge_id]
                    inside = frozenset(opchain[u] for u in edge.pins if opchain[u] in unitset)
                    outside_cores = frozenset(state.assignment[u] for u in edge.pins
                                              if opchain[u] not in unitset)
                    edges.append(Hyperedge(inside, outside_cores, edge.weight))
                initial = {j: chaincores[j] for j in units}
                outside = {c: dict(loads[c]) for c in (a, b)}
                for j in units:
                    for p, amount in work[j].items():
                        outside[chaincores[j]][p] -= amount
                baseline_cost = connectivity_cost(initial, edges)
                connection_floor = sum(edge.weight *
                                       (len(edge.fixed_cores) -
                                        int(bool(edge.fixed_cores & {a, b})))
                                       for edge in edges)
                if baseline_cost == connection_floor:
                    skipped_by_bound += 1
                    continue
                region_work = {j: work[j] for j in units}
                cut = load_guarded_cut(units, edges, a, b, initial,
                                       region_work, outside, caps)
                flows += cut.flow_calls
                if cut.cost >= baseline_cost:
                    continue
                old_total = state.total_bytes
                for source, target in ((a, b), (b, a)):
                    movers = [j for j in units if initial[j] == source and cut.labels[j] == target]
                    pins = [u for j in movers for u in chains[j]]
                    if pins:
                        state.apply(pins, source, target)
                if state.total_bytes - old_total != cut.cost - baseline_cost:
                    raise AssertionError('region cut cost disagrees with original-pin cost')
                for j in units:
                    source, target = initial[j], cut.labels[j]
                    if source != target:
                        for p, amount in work[j].items():
                            loads[source][p] -= amount
                            loads[target][p] += amount
                        chaincores[j] = target
                accepted += 1
    detail = {f'before_{cost_label}': initial_cost,
              f'after_{cost_label}': state.total_bytes,
              'before_pipe_loads': before_loads, 'after_pipe_loads': loads,
              'pipe_caps': caps, 'regions': regions, 'flows': flows,
              'accepted_regions': accepted, 'skipped_by_connection_floor': skipped_by_bound,
              'region_width': region_width,
              'scope': ('Pre-Step2 original COPY bytes and compute-work caps only; no Makespan or capacity guarantee'
                        if cost_label == 'original_copy_bytes' else
                        'Sum isolated-transfer proxy and compute-work caps only; no Makespan or capacity guarantee')}
    if not accepted:
        return plan, detail
    mapping = plan['node_to_subgraph']
    output = {'node_to_subgraph': dict(mapping), 'core_schedules': [
        [mapping[str(u)] if str(u) in mapping else mapping[u]
         for u in priority if state.assignment[u] == c] for c in range(cores)]}
    derive_multicore_plan(graph, output)
    return output, detail
