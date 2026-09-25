"""C01 receiver-closure exchange: one guarded, unevaluated singleton candidate.

A critical link is caller-provided prepared/trace evidence, not a certificate
created here. No task builder, scheduler, E0/E1/E2 or graph-specific rule runs.
"""
from __future__ import annotations

from .dag_direct import DAGIndex
from .direct import derive_multicore_plan, topo
from .candidate_ddr import mandatory_copy_work
from .fifo_bound import fixed_fifo_lower_bound
from .zero_spill_intervals import certify

PIPES = ('PIPE_M', 'PIPE_V')


def _rows(graph, plan, index):
    view = derive_multicore_plan(graph, plan)
    if any(len(nodes) != 1 for nodes in view['nodes_by_subgraph'].values()):
        raise ValueError('singleton plan required')
    inverse = {sg: u for u, sg in view['mapping'].items()}
    rows = [[inverse[sg] for sg in row] for row in plan['core_schedules']]
    if set(u for row in rows for u in row) != set(index.ops):
        raise ValueError('eligible operation coverage mismatch')
    return rows


def _acyclic(index, rows):
    succ = {u: set(v) for u, v in index.succ.items()}
    for row in rows:
        for u, v in zip(row, row[1:]):
            succ[u].add(v)
    try:
        topo(index.ops, succ)
        return True
    except ValueError:
        return False


def _load(index, rows):
    return [{p: sum(index.duration(u) for u in row if index.ops[u]['pipe'] == p)
             for p in PIPES} for row in rows]


def _insert(row, packet, position):
    return row[:position] + list(packet) + row[position:]


def _positions(index, row, packet, anchor):
    """At most two local insertion positions; global cycle is checked later.

    Only direct eligible edges into/out of the packet are used here. Indirect
    cross-core precedence is deliberately left to the complete priority DAG.
    """
    at = {u: i for i, u in enumerate(row)}
    lower, upper = 0, len(row)
    for u in packet:
        lower = max([lower, *(at[v] + 1 for v in index.pred[u] if v in at)])
        upper = min([upper, *(at[v] for v in index.succ[u] if v in at)])
    if lower > upper:
        return []
    return sorted({lower, min(upper, max(lower, anchor))})


def _plan(plan, rows):
    mapping = plan['node_to_subgraph']
    return {'node_to_subgraph': dict(mapping),
            'core_schedules': [[mapping[str(u)] for u in row] for row in rows]}


def construct(graph, plan, config, critical_links, *, max_seeds=8, max_packet_ops=16):
    """Return (one candidate or None, diagnostics); never claim a score gain.

    Link keys: tensor_id, source_core, target_core, exposed_delay (positive
    integer cycles). Missing/invalid trace evidence is skipped, never inferred.
    """
    meta = {'status': 'no_candidate', 'scope': 'unevaluated C01 local constructor',
            'seeds_seen': 0, 'candidates_checked': 0, 'rejections': {},
            'selected': None, 'official_makespan_guarantee': False}
    def reject(reason):
        meta['rejections'][reason] = meta['rejections'].get(reason, 0) + 1
    if (type(max_seeds) is not int or not 0 <= max_seeds <= 8
            or type(max_packet_ops) is not int or not 1 <= max_packet_ops <= 16):
        raise ValueError('limits must be integers within C01 budget')
    try:
        index = DAGIndex(graph)
        rows = _rows(graph, plan, index)
        if len(rows) < 2 or not _acyclic(index, rows):
            raise ValueError('baseline priority union cyclic or single core')
        base_cert = certify(graph, plan, config)
        if not base_cert['supported'] or not base_cert['zero_spill_certificate']:
            raise ValueError('baseline zero-spill certificate unavailable')
        base_bytes = mandatory_copy_work(graph, plan, config['bandwidth'])['transfer_bytes']
        original_producers = {t['id']: set() for t in graph['tensors']}
        original_ops = {u['id'] for u in graph['ops']}
        for edge in graph['edges']:
            if edge['source'] in original_ops and edge['target'] in original_producers:
                original_producers[edge['target']].add(edge['source'])
        if any('logical_tid' in t for t in graph['tensors']):
            raise ValueError('logical tensor alias outside guard')
        owner = {u: c for c, row in enumerate(rows) for u in row}
        base_load = _load(index, rows)
        caps = {p: max(load[p] for load in base_load) for p in PIPES}
    except (ValueError, KeyError, TypeError) as error:
        meta['status'] = 'unsupported'
        reject(type(error).__name__ + ': ' + str(error))
        return None, meta
    if not isinstance(critical_links, (list, tuple)):
        reject('critical_links must be list/tuple of prepared-trace witnesses')
        return None, meta
    seeds = []
    for ordinal, link in enumerate(critical_links):
        if not isinstance(link, dict):
            reject('invalid_link_record'); continue
        delay = link.get('exposed_delay', link.get('exposed_delay_cycles'))
        a, b, tid = link.get('source_core'), link.get('target_core'), link.get('tensor_id')
        if (type(delay) is not int or delay <= 0 or type(tid) is not int
                or type(a) is not int or type(b) is not int
                or a == b or not 0 <= a < len(rows) or not 0 <= b < len(rows)
                or tid not in index.tensors):
            reject('invalid_or_unexposed_link'); continue
        seeds.append((-delay, ordinal, tid, a, b))
    seeds.sort()
    candidates = []
    for neg_delay, ordinal, tid, a, b in seeds[:max_seeds]:
        meta['seeds_seen'] += 1
        producers = original_producers.get(tid, set())
        if len(producers) != 1 or next(iter(producers)) not in index.ops:
            reject('nonunique_or_excluded_producer'); continue
        producer = next(iter(producers))
        if owner[producer] != a:
            reject('source_core_mismatch'); continue
        consumers = index.consumers.get(tid, set())
        x = [u for u in rows[b] if u in consumers]
        if not x or len(x) > max_packet_ops:
            reject('empty_or_oversize_closure'); continue
        x_set = set(x)
        wx = {p: sum(index.duration(u) for u in x if index.ops[u]['pipe'] == p)
              for p in PIPES}
        def balanced(y):
            wy = {p: sum(index.duration(u) for u in y if index.ops[u]['pipe'] == p)
                  for p in PIPES}
            return all(max(base_load[a][p] + wx[p] - wy[p],
                           base_load[b][p] - wx[p] + wy[p]) <= caps[p] for p in PIPES)
        y_choices = [()]
        if not balanced(()) :
            y_choices = []
            anchor = rows[a].index(producer)
            forbidden = consumers | {producer}
            for direction in (1, -1):
                packet = []
                scan = rows[a][anchor + 1:anchor + 1 + max_packet_ops] if direction == 1 else \
                    list(reversed(rows[a][max(0, anchor - max_packet_ops):anchor]))
                for u in scan:
                    if u in forbidden or len(packet) + len(x) >= max_packet_ops:
                        break
                    packet.append(u)
                    if balanced(packet):
                        y_choices.append(tuple(u for u in rows[a] if u in packet))
                        break
        if not y_choices:
            reject('no_bounded_balancing_prefix'); continue
        y = min(y_choices, key=lambda seq: (len(seq), tuple(seq)))
        if len(x) + len(y) > max_packet_ops:
            reject('packet_limit'); continue
        stripped_a = [u for u in rows[a] if u not in y]
        stripped_b = [u for u in rows[b] if u not in x_set]
        a_positions = _positions(index, stripped_a, x,
                                 stripped_a.index(producer) + 1)
        old_x_position = min(rows[b].index(u) for u in x)
        b_positions = _positions(index, stripped_b, y, old_x_position) if y else [0]
        if not a_positions or not b_positions:
            reject('no_local_insertion_interval'); continue
        for ap in a_positions:
            for bp in b_positions:
                new_rows = [list(row) for row in rows]
                new_rows[a] = _insert(stripped_a, x, ap)
                new_rows[b] = _insert(stripped_b, y, bp)
                meta['candidates_checked'] += 1
                if not _acyclic(index, new_rows):
                    reject('priority_cycle'); continue
                candidate = _plan(plan, new_rows)
                try:
                    derive_multicore_plan(graph, candidate)
                    cert = certify(graph, candidate, config)
                    if not cert['supported'] or not cert['zero_spill_certificate']:
                        reject('zero_spill_not_certified'); continue
                    if any(u in index.consumers[tid] for u in new_rows[b]):
                        reject('receiver_not_closed'); continue
                    bytes_now = mandatory_copy_work(graph, candidate, config['bandwidth'])['transfer_bytes']
                    bound = fixed_fifo_lower_bound(graph, candidate)
                    if not bound['supported']:
                        reject('fifo_bound_unsupported'); continue
                except (ValueError, KeyError, TypeError) as error:
                    reject('candidate_guard_failure: ' + type(error).__name__); continue
                key = (neg_delay, bound['makespan_lower_bound_cycles'], bytes_now,
                       ordinal, len(y), ap, bp)
                candidates.append((key, candidate, {'tensor_id': tid, 'source_core': a,
                    'target_core': b, 'exposed_delay': -neg_delay, 'moved_x': x,
                    'compensation_y': list(y), 'insertions': [ap, bp],
                    'fifo_compute_lower_bound': bound['makespan_lower_bound_cycles'],
                    'mandatory_copy_bytes_before': base_bytes,
                    'mandatory_copy_bytes_after': bytes_now}))
    if candidates:
        _, selected, detail = min(candidates, key=lambda item: item[0])
        meta.update(status='candidate', selected=detail, accepted_candidates=len(candidates))
        return selected, meta
    return None, meta
