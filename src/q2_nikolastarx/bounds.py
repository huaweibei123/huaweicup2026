"""Admissible P2 bounds for structurally validated plans, not score proxies."""


def assigned_pipe_lower_bound(graph, plan):
    """Return max per-core original compute Pipe work, or abstain with None.

    Frozen P2 preserves every non-COPY_IN/OUT op on its assigned core, with
    duration max(1, cycles). Each (core, pipe) has one executor slot. Its compute
    operations cannot overlap and start no earlier than zero, so their total
    duration <= Makespan for every successful evaluation. Added COPY, waits and
    memory dependencies cannot reduce that total. This is assignment-dependent;
    the weaker graph-wide work/k bound alone would miss serialization.

    Only integer cycles are admitted: we do not certify floating accumulation
    equivalence. Caller must first obtain a structurally valid official plan.
    Unknown/unsupported input returns None and must not cause a prune.
    """
    ops = {str(o['id']): o for o in graph['ops']
           if o['op'] not in ('COPY_IN', 'COPY_OUT')}
    mapping = plan['node_to_subgraph']
    if set(mapping) != set(ops):
        return None
    owners = {}
    for core, sequence in enumerate(plan['core_schedules']):
        for group in sequence:
            if group in owners:
                return None
            owners[group] = core
    loads = {}
    for node, group in mapping.items():
        operation = ops[node]
        cycles = operation.get('cycles', 1)
        pipe = operation['pipe']
        if (type(cycles) is not int or group not in owners or
                pipe not in ('PIPE_M', 'PIPE_V', 'PIPE_MTE2', 'PIPE_MTE3')):
            return None
        key = owners[group], pipe
        loads[key] = loads.get(key, 0) + max(1, cycles)
    return max(loads.values(), default=0)
