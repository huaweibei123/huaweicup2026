"""Single R7 shared-input band candidate. Structural prototype; never scores a plan.

The supplied baseline is returned unchanged on any unsupported input. Diagnostics are
separate from the official two-key submission. This does not compile Tasks or run E0.
"""
from __future__ import annotations

from collections import defaultdict, deque
from math import ceil
from pathlib import Path
import sys

_OFFICIAL = Path(__file__).resolve().parents[2] / 'data/raw/a/official/code'
if str(_OFFICIAL) not in sys.path:
    sys.path.insert(0, str(_OFFICIAL))
from evaluation_validation import EvaluationValidationError, validate_graph, validate_task_order  # noqa: E402
from stub_multicore_cut_and_schedule import MulticoreCutError, derive_multicore_plan  # noqa: E402


class Unsupported(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise Unsupported(reason)


def _spine(component, preds, succs):
    members = set(component)
    degree = {x: len(preds[x] & members) for x in members}
    ready = sorted(x for x in members if degree[x] == 0)
    order = []
    while ready:
        _need(len(ready) == 1, 'component lacks unique topological spine')
        x = ready.pop()
        order.append(x)
        for y in succs[x] & members:
            degree[y] -= 1
            if degree[y] == 0:
                ready.append(y)
    _need(len(order) == len(members), 'component cycle')
    return order


def _views(graph):
    ops = {o['id']: o for o in graph['ops']}
    tensors = {t['id']: t for t in graph['tensors']}
    _need(all('logical_tid' not in t and 'version' not in t
              for t in graph['tensors']), 'aliased or versioned tensor')
    eligible = {i for i, o in ops.items() if o['op'] not in ('COPY_IN', 'COPY_OUT')}
    prod, cons = defaultdict(set), defaultdict(set)
    direct = []
    for e in graph['edges']:
        a, b = e['source'], e['target']
        if a in ops and b in tensors:
            prod[b].add(a)
        elif a in tensors and b in ops:
            cons[a].add(b)
        elif a in ops and b in ops:
            direct.append((a, b))
        else:
            raise Unsupported('unsupported graph edge')
    _need(all(len(prod[t]) <= 1 for t in tensors), 'tensor has multiple producers')
    for o in graph['ops']:
        i = o['id']
        ins = [t for t in tensors if i in cons[t]]
        outs = [t for t in tensors if i in prod[t]]
        if o['op'] == 'COPY_IN':
            _need(len(ins) == len(outs) == 1 and tensors[ins[0]]['pos'] == 'DDR'
                  and tensors[outs[0]]['pos'] in ('L1', 'UB')
                  and not prod[ins[0]] and bool(cons[outs[0]])
                  and all(x in eligible for x in cons[outs[0]]), 'nonstandard COPY_IN')
        elif o['op'] == 'COPY_OUT':
            _need(len(ins) == len(outs) == 1 and tensors[ins[0]]['pos'] in ('L1', 'UB')
                  and tensors[outs[0]]['pos'] == 'DDR' and not cons[outs[0]]
                  and len(prod[ins[0]]) == 1
                  and next(iter(prod[ins[0]])) in eligible,
                  'nonstandard COPY_OUT')
        else:
            _need(all(tensors[t]['pos'] != 'DDR' for t in ins + outs),
                  'compute op touches DDR')
    preds = {i: set() for i in eligible}
    succs = {i: set() for i in eligible}
    for a, b in direct:
        _need(a in eligible and b in eligible, 'direct edge crosses COPY')
        succs[a].add(b); preds[b].add(a)
    for t in tensors:
        for a in prod[t] & eligible:
            for b in cons[t] & eligible:
                succs[a].add(b); preds[b].add(a)
    seen, components = set(), []
    for root in sorted(eligible):
        if root in seen:
            continue
        seen.add(root); q = deque([root]); part = []
        while q:
            x = q.popleft(); part.append(x)
            for y in sorted(preds[x] | succs[x]):
                if y not in seen:
                    seen.add(y); q.append(y)
        components.append(_spine(part, preds, succs))
    components.sort(key=lambda c: min(c))
    return ops, tensors, eligible, prod, cons, direct, preds, succs, components


def _signature(spine, ops, tensors, prod, cons, shared, direct):
    rank = {x: i for i, x in enumerate(spine)}
    sig = []
    for x in spine:
        ins = []
        outs = []
        for t in tensors:
            if x in cons[t]:
                ps = prod[t]
                if t in shared:
                    ins.append(('shared', t, tensors[t]['pos'], tensors[t]['size']))
                elif ps & set(spine):
                    ins.append(('internal', rank[next(iter(ps))], tensors[t]['pos'], tensors[t]['size']))
                else:
                    _need(len(ps) == 1 and ops[next(iter(ps))]['op'] == 'COPY_IN',
                          'private input lacks standard COPY_IN')
                    ins.append(('private', tensors[t]['pos'], tensors[t]['size']))
            if x in prod[t]:
                local = tuple(sorted(rank[y] for y in cons[t] if y in rank))
                copy_out = sum(ops[y]['op'] == 'COPY_OUT' for y in cons[t])
                _need(len(cons[t] - set(spine)) == copy_out,
                      'internal output crosses components')
                outs.append((tensors[t]['pos'], tensors[t]['size'], local, copy_out))
        o = ops[x]
        sig.append((o['op'], o['pipe'], o['cycles'], tuple(sorted(ins)), tuple(sorted(outs)),
                    tuple(sorted(rank[a] for a, b in direct if b == x and a in rank))))
    return tuple(sig)


def _footprint(nodes, tensors, prod, cons):
    by_pos = {'L1': 0, 'UB': 0}
    for t, v in tensors.items():
        if (prod[t] | cons[t]) & nodes:
            pos = v['pos'] if v['pos'] != 'DDR' else 'UB'
            by_pos[pos] += v['size']
    return by_pos


def _traffic(graph, mapping, tensors, prod, cons, eligible, ops):
    original = 0
    for o in graph['ops']:
        i = o['id']
        if o['op'] == 'COPY_IN':
            original += sum(tensors[t]['size'] for t in tensors if i in prod[t])
        elif o['op'] == 'COPY_OUT':
            original += sum(tensors[t]['size'] for t in tensors if i in cons[t])
    scheduled = 0
    by_task = defaultdict(set)
    for i, task in mapping.items():
        by_task[task].add(i)
    for nodes in by_task.values():
        for t, v in tensors.items():
            lp, lc = prod[t] & nodes, cons[t] & nodes
            if not (lp or lc):
                continue
            if lc and not lp:
                scheduled += v['size']
            if lp and (any(ops[x]['op'] == 'COPY_OUT' for x in cons[t])
                       or not (cons[t] & eligible)
                       or bool((cons[t] & eligible) - nodes)):
                scheduled += v['size']
    return {'original_graph_copy_bytes': original,
            'scheduled_copy_bytes_no_spill': scheduled,
            'partition_added_copy_bytes': scheduled - original}


def construct(graph, baseline, capacity, bandwidth):
    """Return (one candidate or the supplied baseline, diagnostics).

    capacity is the official {'L1': bytes, 'UB': bytes}; bandwidth is bytes/cycle.
    A rejected input never mutates baseline or writes a plan.
    """
    info = {'selected': 'baseline', 'reason': None, 'official_calls': 0,
            'task_compile_calls': 0}
    try:
        _need(type(bandwidth) is int and bandwidth > 0, 'invalid bandwidth')
        _need(isinstance(capacity, dict) and set(capacity) == {'L1', 'UB'}
              and all(type(v) is int and v >= 0 for v in capacity.values()),
              'invalid capacity')
        validate_graph(graph)
        base_view = derive_multicore_plan(graph, baseline)
        validate_task_order(base_view)
        k = base_view['num_cores']
        ops, tensors, eligible, prod, cons, direct, preds, succs, components = _views(graph)
        n = len(components)
        _need(n > 1 and k > 1, 'insufficient components or cores')
        _need(all(len(c) == len(components[0]) for c in components),
              'component lengths differ')
        rank_by_op = {x: (ci, r) for ci, c in enumerate(components) for r, x in enumerate(c)}
        shared = {t for t in tensors if len({rank_by_op[x][0] for x in cons[t] & eligible}) > 1}
        _need(shared, 'no shared inputs')
        for t in shared:
            _need(len(prod[t]) == 1 and ops[next(iter(prod[t]))]['op'] == 'COPY_IN'
                  and len(cons[t] & eligible) == n
                  and all(len([x for x in cons[t] if x in c]) == 1 for c in components),
                  'shared tensor identity or consumer count differs')
            ranks = {rank_by_op[x][1] for x in cons[t] & eligible}
            _need(len(ranks) == 1, 'shared tensor positions differ')
        ref = _signature(components[0], ops, tensors, prod, cons, shared, direct)
        _need(all(_signature(c, ops, tensors, prod, cons, shared, direct) == ref
                  for c in components[1:]), 'component signatures differ')
        positions = sorted({rank_by_op[next(iter(cons[t] & eligible))][1] for t in shared})
        _need(positions[0] == 0, 'spine begins before first shared input')
        h = ceil(n / k); m = ceil(n / h)
        _need(m > 1, 'no useful peripheral grouping')
        columns = []
        for j, start in enumerate(positions):
            end = positions[j + 1] if j + 1 < len(positions) else len(components[0])
            ts = [t for t in shared if rank_by_op[next(iter(cons[t] & eligible))][1] == start]
            _need(len(ts) == 1, 'multiple common inputs at same position')
            u = sum(ops[x]['cycles'] for x in components[0][start:end])
            b = max(1, ceil(tensors[ts[0]]['size'] / bandwidth))
            columns.append({'start': start, 'end': end, 'u': u, 'b': b,
                            'marked': m * b > n * u, 'gain': max(0, m * b - n * u)})
        bands = []; first = None
        for j, col in enumerate(columns + [{'marked': False}]):
            if col['marked'] and first is None:
                first = j
            if not col['marked'] and first is not None:
                bands.append((sum(x['gain'] for x in columns[first:j]), first, j))
                first = None
        _need(bands, 'no positive consecutive band')
        _, lo, hi = max(bands, key=lambda x: (x[0], -x[1]))
        start, stop = columns[lo]['start'], columns[hi - 1]['end']
        _need(start > 0 and stop < len(components[0]), 'band lacks prefix or suffix')
        widths = [n // m + (j < n % m) for j in range(m)]
        groups = []; cursor = 0
        for width in widths:
            groups.append(components[cursor:cursor + width]); cursor += width
        def nodes_for(comp_group, a, b):
            return {x for c in comp_group for x in c[a:b]}
        tasks = []
        for group in groups:
            tasks.append(('prefix', nodes_for(group, 0, start)))
        bandslices = []; left = lo
        while left < hi:
            best = None
            for right in range(left + 1, hi + 1):
                nodes = nodes_for(components, columns[left]['start'], columns[right - 1]['end'])
                footprint = _footprint(nodes, tensors, prod, cons)
                if any(footprint[p] > capacity[p] for p in capacity):
                    break
                best = (right, nodes, footprint)
            _need(best is not None, 'single band column exceeds capacity')
            bandslices.append(best); left = best[0]
        _need(len(bandslices) <= k, 'more band slices than cores')
        tasks.extend(('band', nodes) for _, nodes, _ in bandslices)
        for group in groups:
            tasks.append(('suffix', nodes_for(group, stop, len(group[0]))))
        footprints = [_footprint(nodes, tensors, prod, cons) for _, nodes in tasks]
        _need(all(all(fp[p] <= capacity[p] for p in capacity) for fp in footprints),
              'peripheral task exceeds capacity')
        allnodes = [x for _, nodes in tasks for x in nodes]
        _need(len(allnodes) == len(set(allnodes)) and set(allnodes) == eligible,
              'candidate does not exactly cover compute ops')
        owner = m if m < k else min(range(m), key=lambda j:
            (sum(ops[x]['cycles'] for c in groups[j] for x in c), j))
        schedules = [[] for _ in range(k)]
        band_ids = list(range(m, m + len(bandslices)))
        for j in range(m):
            schedules[j].append(j)
            if j == owner:
                schedules[j].extend(band_ids)
            schedules[j].append(m + len(bandslices) + j)
        if owner >= m:
            schedules[owner].extend(band_ids)
        membership = {x: j for j, (_, nodes) in enumerate(tasks) for x in nodes}
        plan = {'node_to_subgraph': {str(o['id']): membership[o['id']]
                  for o in graph['ops'] if o['id'] in eligible},
                'core_schedules': schedules}
        view = derive_multicore_plan(graph, plan)
        validate_task_order(view)
        # Independent explicit boundary accounting mirrors the official predicate.
        copies = _traffic(graph, membership, tensors, prod, cons, eligible, ops)
        info.update(selected='candidate', reason='structural gates passed',
                    components=n, cores=k, peripheral_groups=m,
                    column_count=len(columns), band_column_range=[lo, hi],
                    band_rank_range=[start, stop],
                    band_slices=[[columns[(lo if j == 0 else bandslices[j-1][0])]['start'],
                                  columns[right-1]['end']]
                                 for j, (right, _, _) in enumerate(bandslices)],
                    owner_core=owner, task_count=len(tasks),
                    task_footprints=footprints, copy_accounting=copies,
                    dependency_pairs=len(view['dependency_pairs']))
        return plan, info
    except (Unsupported, EvaluationValidationError, MulticoreCutError,
            ValueError, KeyError, IndexError, StopIteration) as exc:
        info['reason'] = str(exc)
        return baseline, info
