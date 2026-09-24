"""Guarded shared-input waves for repeated independent compute components.

Only constructs a static priority plan. Raw touch intervals are diagnostics,
not a Step2/Step3 spill or official makespan guarantee.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from .dag_direct import DAGIndex
from .direct import UnsupportedStructure, derive_multicore_plan


def _pool(tensor):
    return 'UB' if tensor['pos'] == 'DDR' else tensor['pos']


def _raw_peak(index, sequence):
    first, last = {}, {}
    for i, u in enumerate(sequence):
        for t in set(index.inputs[u]) | set(index.outputs[u]):
            first.setdefault(t, i)
            last[t] = i
    change = defaultdict(Counter)
    for t, at in first.items():
        p = _pool(index.tensors[t])
        change[at][p] += index.tensors[t]['size']
        change[last[t] + 1][p] -= index.tensors[t]['size']
    live, peak = Counter(), Counter()
    for i in range(len(sequence)):
        live.update(change[i])
        for p in ('L1', 'UB'):
            peak[p] = max(peak[p], live[p])
    return {p: peak[p] for p in ('L1', 'UB')}


def _recognize(index):
    jobs = index.components
    if len(jobs) < 2:
        raise UnsupportedStructure('requires at least two independent compute components')
    if any(index.direct_inputs.values()):
        raise UnsupportedStructure('direct op edges are outside shared-input wave guard')
    owner = {u: j for j, job in enumerate(jobs) for u in job}
    for u in index.ops:
        via_tensors = set().union(*(index.producers[t] for t in index.inputs[u]))
        if via_tensors != index.pred[u]:
            raise UnsupportedStructure('contracted dependencies differ from tensor incidences')
        if any(owner[v] != owner[u] for v in index.pred[u]):
            raise UnsupportedStructure('compute components have cross dependencies')
        if len(index.outputs[u]) != 1:
            raise UnsupportedStructure('requires one output tensor per compute op')
    if any(len(ps) > 1 for ps in index.producers.values()):
        raise UnsupportedStructure('multi-producer tensors are outside guard')
    external_users = defaultdict(set)
    for u in index.ops:
        for t in index.inputs[u]:
            if not index.producers[t]:
                external_users[t].add(owner[u])
    shared = {t for t, users in external_users.items() if len(users) > 1}
    if len(shared) < 2 or any(external_users[t] != set(range(len(jobs))) for t in shared):
        raise UnsupportedStructure('requires at least two external inputs shared by every component')
    # Full structural signatures include shared tensor identity and private tensor
    # shape. Recursive signatures are interned, so their size is linear in DAG size.
    intern = {}
    def atom(value):
        if value not in intern:
            intern[value] = len(intern)
        return intern[value]
    tensor_sig = {}
    op_sig = {}
    for t, tensor in index.tensors.items():
        if not index.producers[t]:
            tensor_sig[t] = atom(('shared', t) if t in shared else
                                 ('private_input', tensor['pos'], tensor['size']))
    for u in index.order:
        inputs = tuple(sorted(tensor_sig[t] for t in index.inputs[u]))
        output = index.outputs[u][0]
        shape = (index.tensors[output]['pos'], index.tensors[output]['size'])
        op = index.ops[u]
        op_sig[u] = atom(('op', op['op'], op['pipe'], index.duration(u), inputs, shape))
        tensor_sig[output] = atom(('produced', op_sig[u], shape))
    by_job = []
    for job in jobs:
        signatures = {op_sig[u]: u for u in job}
        if len(signatures) != len(job):
            raise UnsupportedStructure('ambiguous repeated op signatures inside a component')
        by_job.append(signatures)
    template = set(by_job[0])
    if any(set(row) != template for row in by_job[1:]):
        raise UnsupportedStructure('component templates differ')
    # Every shared input has one corresponding consuming operation per job.
    anchor = {}
    for t in shared:
        consumers = [u for u in jobs[0] if t in index.inputs[u]]
        if len(consumers) != 1 or any(sum(t in index.inputs[u] for u in job) != 1 for job in jobs[1:]):
            raise UnsupportedStructure('shared input must have one consumer per component')
        anchor[t] = op_sig[consumers[0]]
    if len(set(anchor.values())) != len(anchor):
        raise UnsupportedStructure('shared inputs have ambiguous anchor operations')
    # Order by the first component's topological position. Its structural
    # template is matched before this order is reused for other components.
    rank = {u: i for i, u in enumerate(jobs[0])}
    waves = sorted(shared, key=lambda t: rank[by_job[0][anchor[t]]])
    return by_job, waves, anchor


def _sequence(index, group, by_job, waves, anchor):
    emitted = {j: set() for j in group}
    result = []
    def close(j, u, added):
        stack = [(u, False)]
        while stack:
            node, expanded = stack.pop()
            if node in emitted[j]:
                continue
            if expanded:
                emitted[j].add(node)
                added.append(node)
            else:
                stack.append((node, True))
                stack.extend((v, False) for v in sorted(index.pred[node], reverse=True))
    for t in waves:
        for j in group:
            block = []
            close(j, by_job[j][anchor[t]], block)
            result.extend(block)
    for j in group:
        for u in index.components[j]:
            block = []
            close(j, u, block)
            result.extend(block)
    return result


def build_from_index(index, cores, config):
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be a positive integer')
    capacity = config['capacity']
    if set(capacity) != {'L1', 'UB'} or any(type(capacity[p]) is not int or capacity[p] < 0 for p in ('L1', 'UB')):
        raise ValueError('capacity must contain nonnegative integer L1 and UB bytes')
    if len(index.components) < cores:
        raise UnsupportedStructure('requires at least as many components as cores')
    by_job, waves, anchor = _recognize(index)
    groups = index.assignment(cores)
    sequences = [_sequence(index, group, by_job, waves, anchor) for group in groups]
    mapping = {str(u): i for i, u in enumerate(index.order)}
    plan = {'node_to_subgraph': mapping,
            'core_schedules': [[mapping[str(u)] for u in seq] for seq in sequences]}
    derive_multicore_plan(index.graph, plan)
    peaks = [_raw_peak(index, seq) for seq in sequences]
    return plan, {'selected_strategy': 'shared_input_wave', 'components': len(index.components),
                  'cores': cores, 'shared_external_inputs': len(waves),
                  'shared_external_bytes': sum(index.tensors[t]['size'] for t in waves),
                  'raw_priority_peak_bytes': peaks,
                  'raw_peaks_fit_capacity': all(all(row[p] <= capacity[p] for p in ('L1', 'UB')) for row in peaks),
                  'zero_spill_claim': False,
                  'limitations': ['raw touch intervals omit official COPY/spill and Step2/Step3 reorder',
                                  'fixed whole-component assignment; activation frontier may grow with component count']}


def build(graph, cores, config):
    return build_from_index(DAGIndex(graph), cores, config)
