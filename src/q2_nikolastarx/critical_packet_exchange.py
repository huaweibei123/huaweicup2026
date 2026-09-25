"""C01 critical downstream packet exchange; static, unevaluated construction.

A caller supplies prepared/trace link witnesses and old critical eligible op IDs.
Neither this module nor its helpers prepare official tasks or score a plan.
"""
from __future__ import annotations

import heapq
import json

from .dag_direct import DAGIndex
from .direct import derive_multicore_plan
from .receiver_closure_exchange import _rows, _acyclic, _load, _plan, PIPES
from .candidate_ddr import mandatory_copy_work
from .fifo_bound import fixed_fifo_lower_bound
from .zero_spill_intervals import certify


def _merge(index, rows, packet, *, packet_first=True, start_times=None, exposed_delay=0):
    """Topologically merge retained per-core chains and old packet chain."""
    moved = set(packet)
    succ = {u: set(v) for u, v in index.succ.items()}
    for row in rows:
        kept = [u for u in row if u not in moved]
        for u, v in zip(kept, kept[1:]):
            succ[u].add(v)
    for u, v in zip(packet, packet[1:]):
        succ[u].add(v)
    degree = {u: 0 for u in index.ops}
    for targets in succ.values():
        for v in targets:
            degree[v] += 1
    def key(u):
        if start_times is not None:
            old = start_times[u]
            return (max(0, old - exposed_delay) if u in moved else old, u)
        return (0 if (u in moved) == packet_first else 1, u)
    ready = [key(u) for u, d in degree.items() if d == 0]
    heapq.heapify(ready)
    ordered = []
    while ready:
        _, u = heapq.heappop(ready)
        ordered.append(u)
        for v in sorted(succ[u]):
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, key(v))
    return ordered if len(ordered) == len(index.ops) else None


def propose(graph, plan, config, critical_links, critical_operations, *, incumbent_makespan,
            max_seeds=8, merge_policy='extremes', original_start_times=None,
            closure_scope='same_core'):
    """Return ordered distinct complete plans and bounded diagnostics.

    At most max_seeds witnessed links: two extreme merges or one shifted merge each.
    The critical set is supplied evidence, never inferred from an absent trace.
    Closure follows original edges between old critical vertices; these edges
    need not themselves be tight. The cone's packet and retained chains are
    subsequences of one baseline topological order, so their union with the
    original DAG is structurally acyclic. Old critical membership does not
    guarantee a new critical path; capacity and COPY remain guarded, and
    Makespan still requires scoring and independent official E0 verification.
    """
    meta = {'status': 'no_candidate', 'scope': 'static C01 critical packet; unscored',
            'seeds_seen': 0, 'candidates_checked': 0, 'rejections': {},
            'candidate_summaries': [], 'selected': None, 'unique_count': 0,
            'duplicates': 0, 'validated_candidates': 0,
            'complexity': ('at most 8 seeds and 8 plans; per seed O(V+E) closure plus one O((V+E) log V) Kahn merge and whole-graph legality, capacity, COPY, and FIFO-bound guards; no subset enumeration'
                           if merge_policy == 'shifted' else
                           'at most 8 seeds and 16 plans; per seed O(V+E) closure plus two O((V+E) log V) merges and whole-graph legality, capacity, COPY, and FIFO-bound guards; no subset enumeration'),
            'official_makespan_guarantee': False, 'merge_policy': merge_policy,
            'closure_scope': closure_scope,
            'start_time_scope': 'Old observed starts guide priority only; not predicted new schedule or guarantee.'}
    def reject(code):
        meta['rejections'][code] = meta['rejections'].get(code, 0) + 1
    if type(max_seeds) is not int or not 0 <= max_seeds <= 8:
        raise ValueError('max_seeds must be an integer in [0,8]')
    if type(incumbent_makespan) is not int or incumbent_makespan <= 0:
        raise ValueError('incumbent_makespan must be a positive integer from the audited trace')
    try:
        index = DAGIndex(graph)
        if merge_policy not in ('extremes', 'shifted'):
            raise ValueError('unsupported merge_policy')
        if closure_scope not in ('same_core', 'critical_cone'):
            raise ValueError('unsupported closure_scope')
        if merge_policy == 'shifted' and (type(original_start_times) is not dict
                or set(original_start_times) != set(index.ops)
                or any(type(u) is not int or type(t) is not int or t < 0
                       for u, t in original_start_times.items())):
            raise ValueError('shifted requires exact nonnegative integer starts for eligible original ops')
        rows = _rows(graph, plan, index)
        if len(rows) < 2 or not _acyclic(index, rows):
            raise ValueError('singleton baseline priority union invalid')
        baseline_order = (_merge(index, rows, [], packet_first=True)
                          if closure_scope == 'critical_cone' else None)
        if closure_scope == 'critical_cone' and baseline_order is None:
            raise ValueError('baseline global topological order unavailable')
        cert = certify(graph, plan, config)
        if not cert['supported'] or not cert['zero_spill_certificate']:
            raise ValueError('baseline zero-spill certificate unavailable')
        if any('logical_tid' in t for t in graph['tensors']):
            raise ValueError('logical tensor alias outside guard')
        if not isinstance(critical_links, (list, tuple)) or not isinstance(critical_operations, (list, tuple, set, frozenset)):
            raise ValueError('critical evidence container missing')
        if any(type(u) is not int or u not in index.ops for u in critical_operations):
            raise ValueError('critical operation outside original eligible graph')
        critical = set(critical_operations)
        owner = {u: c for c, row in enumerate(rows) for u in row}
        baseline_bytes = mandatory_copy_work(graph, plan, config['bandwidth'])['transfer_bytes']
        loads = _load(index, rows)
        caps = {p: max(row[p] for row in loads) for p in PIPES}
        original_ops = {o['id'] for o in graph['ops']}
        producers = {t['id']: set() for t in graph['tensors']}
        for edge in graph['edges']:
            if edge['source'] in original_ops and edge['target'] in producers:
                producers[edge['target']].add(edge['source'])
    except (ValueError, TypeError, KeyError) as error:
        meta['status'] = 'unsupported'
        reject(type(error).__name__ + ': ' + str(error))
        return [], meta
    seeds = []
    for ordinal, link in enumerate(critical_links):
        if not isinstance(link, dict):
            reject('invalid_link'); continue
        tid, a, b = link.get('tensor_id'), link.get('source_core'), link.get('target_core')
        delay = link.get('exposed_delay', link.get('exposed_delay_cycles'))
        if (type(tid) is not int or tid not in index.tensors
                or type(a) is not int or type(b) is not int or a == b
                or not 0 <= a < len(rows) or not 0 <= b < len(rows)
                or type(delay) is not int or delay <= 0):
            reject('invalid_or_unexposed_link'); continue
        seeds.append((-delay, ordinal, tid, a, b))
    seeds.sort()
    candidates = []
    seen_plans = {}
    for neg_delay, ordinal, tid, a, b in seeds[:max_seeds]:
        meta['seeds_seen'] += 1
        origins = producers.get(tid, set())
        if len(origins) != 1 or next(iter(origins)) not in index.ops:
            reject('nonunique_or_excluded_producer'); continue
        source = next(iter(origins))
        if owner[source] != a:
            reject('source_core_mismatch'); continue
        x = {u for u in rows[b] if u in index.consumers.get(tid, set())}
        if not x:
            reject('empty_receiver_closure'); continue
        receiver_count = len(x)
        # One monotone closure over old critical eligible successors, either
        # on the receiving core alone or across all old cores.
        stack = list(sorted(x))
        while stack:
            u = stack.pop()
            for v in sorted(index.succ[u]):
                if (closure_scope == 'critical_cone' or owner[v] == b) and v in critical and v not in x:
                    x.add(v)
                    stack.append(v)
        packet = ([u for u in baseline_order if u in x] if closure_scope == 'critical_cone'
                  else [u for u in rows[b] if u in x])
        packet_old_core_counts = {c: sum(owner[u] == c for u in packet)
                                  for c in range(len(rows)) if any(owner[u] == c for u in packet)}
        effective_moved_count = sum(owner[u] != a for u in packet)
        removed = [{p: 0 for p in PIPES} for _ in rows]
        added = {p: 0 for p in PIPES}
        for u in packet:
            pipe, duration = index.ops[u]['pipe'], index.duration(u)
            removed[owner[u]][pipe] += duration
            added[pipe] += duration
        proposed_peaks = {p: max(loads[c][p] - removed[c][p] + (added[p] if c == a else 0)
                                 for c in range(len(rows))) for p in PIPES}
        # Old load peaks are not hard limits: communicating schedules can be
        # mostly idle. Only the valid compute lower bound can reject a claimed
        # strict Makespan improvement, and the chosen candidate still needs E0.
        if max(proposed_peaks.values()) >= incumbent_makespan:
            reject('load_lower_bound_no_strict_gain'); continue
        for packet_first in ((True, False) if merge_policy == 'extremes' else (None,)):
            meta['candidates_checked'] += 1
            ordered = _merge(index, rows, packet, packet_first=packet_first,
                             start_times=original_start_times if merge_policy == 'shifted' else None,
                             exposed_delay=-neg_delay)
            if ordered is None:
                reject('merge_cycle'); continue
            new_owner = {**owner, **{u: a for u in packet}}
            proposed = [[u for u in ordered if new_owner[u] == c] for c in range(len(rows))]
            if not _acyclic(index, proposed):
                reject('priority_cycle'); continue
            if any([u for u in proposed[c] if u not in x] != [u for u in rows[c] if u not in x]
                   for c in range(len(rows))):
                reject('retained_core_order_changed'); continue
            candidate = _plan(plan, proposed)
            try:
                derive_multicore_plan(graph, candidate)
                candidate_cert = certify(graph, candidate, config)
                if not candidate_cert['supported'] or not candidate_cert['zero_spill_certificate']:
                    reject('zero_spill_not_certified'); continue
                if any(u in index.consumers[tid] for u in proposed[b]):
                    reject('receiver_not_closed'); continue
                copied = mandatory_copy_work(graph, candidate, config['bandwidth'])['transfer_bytes']
                bound = fixed_fifo_lower_bound(graph, candidate)
                if not bound['supported']:
                    reject('fifo_bound_unsupported'); continue
                if bound['makespan_lower_bound_cycles'] >= incumbent_makespan:
                    reject('fifo_lower_bound_no_strict_gain'); continue
            except (ValueError, KeyError, TypeError) as error:
                reject('candidate_guard_failure:' + type(error).__name__); continue
            row = {'tensor_id': tid, 'source_core': a, 'target_core': b,
                   'exposed_delay': -neg_delay, 'packet_size': len(packet),
                   'receiver_count': receiver_count,
                   'critical_downstream_added': len(packet) - receiver_count,
                   'closure_scope': closure_scope,
                   'packet_old_core_counts': packet_old_core_counts,
                   'effective_moved_count': effective_moved_count,
                   'packet': packet, 'merge': ('shifted' if merge_policy == 'shifted' else
                                             'packet_first' if packet_first else 'retained_first'),
                   'fifo_compute_lower_bound': bound['makespan_lower_bound_cycles'],
                   'pipe_load_peaks_before': caps, 'pipe_load_peaks_after': proposed_peaks,
                   'incumbent_makespan': incumbent_makespan,
                   'mandatory_copy_bytes_before': baseline_bytes,
                   'mandatory_copy_bytes_after': copied}
            key = (row['fifo_compute_lower_bound'], copied, neg_delay, ordinal,
                   0 if packet_first else 1)
            meta['validated_candidates'] += 1
            origin = {'seed_ordinal': ordinal, 'tensor_id': tid,
                      'merge': row['merge'], 'exposed_delay': -neg_delay}
            fingerprint = json.dumps(candidate, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False)
            if fingerprint in seen_plans:
                meta['duplicates'] += 1
                candidates[seen_plans[fingerprint]]['detail']['origins'].append(origin)
                continue
            row['origins'] = [origin]
            row['static_rank_key'] = list(key)
            seen_plans[fingerprint] = len(candidates)
            candidates.append({'plan': candidate, 'detail': row})
            meta['candidate_summaries'].append(row)
    if candidates:
        meta.update(status='candidates', unique_count=len(candidates),
                    accepted_candidates=len(candidates))
    return candidates, meta


def construct(graph, plan, config, critical_links, critical_operations, *, incumbent_makespan,
              max_seeds=8, merge_policy='extremes', original_start_times=None,
              closure_scope='same_core'):
    """Keep the original static single-candidate choice over propose's list."""
    candidates, meta = propose(graph, plan, config, critical_links,
                               critical_operations, incumbent_makespan=incumbent_makespan,
                               max_seeds=max_seeds, merge_policy=merge_policy,
                               original_start_times=original_start_times,
                               closure_scope=closure_scope)
    if not candidates:
        return None, meta
    chosen = min(candidates, key=lambda item: tuple(item['detail']['static_rank_key']))
    meta.update(status='candidate', selected=chosen['detail'])
    return chosen['plan'], meta
