"""Recognition-only extraction; prebuilt entry removes only repeated views(graph)."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
import heapq
COPY = {"COPY_IN", "COPY_OUT"}
PIPES = ("PIPE_MTE2", "PIPE_MTE3", "PIPE_M", "PIPE_V")
SOURCE_COMMIT = 'a556d534382cc670a6e5450661da6f8adbe638ca'
SOURCE_PATH = 'AI chats/P1多Pipe链构造证明/附件/r1-p1_s6607/p1_phase_cut.py'
SOURCE_SHA256 = '5a753611e52654ca93155256602e4cc1ea75fc0234bd4db1b24f756d3fef96b0'

class Unsupported(ValueError):
    pass

def topo(pred, succ):
    deg = {u: len(ps) for u, ps in pred.items()}
    ready = [u for u, d in deg.items() if d == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in succ[u]:
            deg[v] -= 1
            if deg[v] == 0:
                heapq.heappush(ready, v)
    if len(order) != len(pred):
        raise ValueError('cycle')
    return order

@dataclass
class Views:
    ops: dict
    tensors: dict
    producers: dict
    consumers: dict
    pred: dict
    succ: dict
    in_t: dict
    out_t: dict

def views(graph: dict) -> Views:
    ops = {o['id']: o for o in graph['ops']}
    tensors = {t['id']: t for t in graph['tensors']}
    if len(ops) != len(graph['ops']) or len(tensors) != len(graph['tensors']) or ops.keys() & tensors.keys():
        raise ValueError('non-unique node IDs')
    for o in ops.values():
        if type(o['id']) is not int or o['id'] < 0 or type(o['cycles']) is not int or (o['cycles'] < 0) or (o['pipe'] not in PIPES):
            raise ValueError('bad op')
    for t in tensors.values():
        if type(t['size']) is not int or t['size'] < 0 or t['pos'] not in {'L1', 'UB', 'DDR'}:
            raise ValueError('bad tensor')
    pr = defaultdict(set)
    co = defaultdict(set)
    pred = {u: set() for u in ops}
    succ = {u: set() for u in ops}
    ins = {u: set() for u in ops}
    outs = {u: set() for u in ops}
    for e in graph['edges']:
        u, v = (e['source'], e['target'])
        if u not in ops and u not in tensors or (v not in ops and v not in tensors):
            raise ValueError('unknown endpoint')
        if u in ops and v in ops:
            succ[u].add(v)
            pred[v].add(u)
        elif u in ops:
            pr[v].add(u)
            outs[u].add(v)
        elif v in ops:
            co[u].add(v)
            ins[v].add(u)
        else:
            raise ValueError('tensor-to-tensor edge unsupported')
    for t in tensors:
        for u in pr[t]:
            for v in co[t]:
                succ[u].add(v)
                pred[v].add(u)
    topo(pred, succ)
    return Views(ops, tensors, pr, co, pred, succ, ins, outs)

def recognize(graph: dict):
    v = views(graph)
    eligible = {u for u, o in v.ops.items() if o['op'] not in COPY}
    if not eligible:
        raise Unsupported('empty compute graph')
    order = topo(v.pred, v.succ)
    before = {u: False for u in v.ops}
    after = {u: False for u in v.ops}
    for u in order:
        for w in v.succ[u]:
            before[w] |= before[u] or u in eligible
    for u in reversed(order):
        for w in v.succ[u]:
            after[u] |= after[w] or w in eligible
    if any((before[u] and after[u] for u in v.ops if u not in eligible)):
        raise Unsupported('excluded-COPY bridge: use frozen fallback')
    pred = {u: v.pred[u] & eligible for u in eligible}
    succ = {u: v.succ[u] & eligible for u in eligible}
    components = []
    seen = set()
    for root in sorted(eligible):
        if root in seen:
            continue
        group = set()
        stack = [root]
        seen.add(root)
        while stack:
            u = stack.pop()
            group.add(u)
            for w in pred[u] | succ[u]:
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        p = {u: pred[u] & group for u in group}
        s = {u: succ[u] & group for u in group}
        seq = topo(p, s)
        if any((seq[i + 1] not in s[seq[i]] for i in range(len(seq) - 1))):
            raise Unsupported('component has no certified dependency spine')
        word = [v.ops[u]['pipe'] for u in seq]
        if len(seq) < 3 or word[0] != 'PIPE_M' or word[-1] != 'PIPE_M' or any((x != 'PIPE_V' for x in word[1:-1])):
            raise Unsupported('not M -> V+ -> M')
        components.append(seq)
    components.sort(key=lambda c: min(c))
    which = {u: i for i, c in enumerate(components) for u in c}
    ct = defaultdict(list)
    for tid, t in v.tensors.items():
        ps = v.producers[tid] & eligible
        cs = v.consumers[tid] & eligible
        owners = {which[u] for u in ps | cs}
        if len(ps) > 1 or len(owners) > 1:
            raise Unsupported('multiple compute producers or shared external tensor')
        if owners:
            ct[next(iter(owners))].append(tid)
    signatures = []
    for i, chain in enumerate(components):
        index = {u: j for j, u in enumerate(chain)}
        tensors = []
        for tid in ct[i]:
            t = v.tensors[tid]
            ps = v.producers[tid] & eligible
            cs = v.consumers[tid] & eligible
            h = any((v.ops[u]['op'] == 'COPY_OUT' for u in v.consumers[tid]))
            if ps and cs and h:
                raise Unsupported('internal original output tap')
            tensors.append((tuple(sorted((index[u] for u in ps))), tuple(sorted((index[u] for u in cs))), 'UB' if t['pos'] == 'DDR' else t['pos'], t['size'], h))
        signatures.append((tuple(((v.ops[u]['pipe'], max(1, v.ops[u]['cycles'])) for u in chain)), tuple(sorted(((index[u], index[w]) for u in chain for w in succ[u]))), tuple(sorted(tensors))))
    if any((s != signatures[0] for s in signatures)):
        raise Unsupported('heterogeneous family: use frozen fallback')
    return (v, components, ct, pred, succ)

def recognize_prebuilt(v):
    eligible = {u for u, o in v.ops.items() if o['op'] not in COPY}
    if not eligible:
        raise Unsupported('empty compute graph')
    order = topo(v.pred, v.succ)
    before = {u: False for u in v.ops}
    after = {u: False for u in v.ops}
    for u in order:
        for w in v.succ[u]:
            before[w] |= before[u] or u in eligible
    for u in reversed(order):
        for w in v.succ[u]:
            after[u] |= after[w] or w in eligible
    if any((before[u] and after[u] for u in v.ops if u not in eligible)):
        raise Unsupported('excluded-COPY bridge: use frozen fallback')
    pred = {u: v.pred[u] & eligible for u in eligible}
    succ = {u: v.succ[u] & eligible for u in eligible}
    components = []
    seen = set()
    for root in sorted(eligible):
        if root in seen:
            continue
        group = set()
        stack = [root]
        seen.add(root)
        while stack:
            u = stack.pop()
            group.add(u)
            for w in pred[u] | succ[u]:
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        p = {u: pred[u] & group for u in group}
        s = {u: succ[u] & group for u in group}
        seq = topo(p, s)
        if any((seq[i + 1] not in s[seq[i]] for i in range(len(seq) - 1))):
            raise Unsupported('component has no certified dependency spine')
        word = [v.ops[u]['pipe'] for u in seq]
        if len(seq) < 3 or word[0] != 'PIPE_M' or word[-1] != 'PIPE_M' or any((x != 'PIPE_V' for x in word[1:-1])):
            raise Unsupported('not M -> V+ -> M')
        components.append(seq)
    components.sort(key=lambda c: min(c))
    which = {u: i for i, c in enumerate(components) for u in c}
    ct = defaultdict(list)
    for tid, t in v.tensors.items():
        ps = v.producers[tid] & eligible
        cs = v.consumers[tid] & eligible
        owners = {which[u] for u in ps | cs}
        if len(ps) > 1 or len(owners) > 1:
            raise Unsupported('multiple compute producers or shared external tensor')
        if owners:
            ct[next(iter(owners))].append(tid)
    signatures = []
    for i, chain in enumerate(components):
        index = {u: j for j, u in enumerate(chain)}
        tensors = []
        for tid in ct[i]:
            t = v.tensors[tid]
            ps = v.producers[tid] & eligible
            cs = v.consumers[tid] & eligible
            h = any((v.ops[u]['op'] == 'COPY_OUT' for u in v.consumers[tid]))
            if ps and cs and h:
                raise Unsupported('internal original output tap')
            tensors.append((tuple(sorted((index[u] for u in ps))), tuple(sorted((index[u] for u in cs))), 'UB' if t['pos'] == 'DDR' else t['pos'], t['size'], h))
        signatures.append((tuple(((v.ops[u]['pipe'], max(1, v.ops[u]['cycles'])) for u in chain)), tuple(sorted(((index[u], index[w]) for u in chain for w in succ[u]))), tuple(sorted(tensors))))
    if any((s != signatures[0] for s in signatures)):
        raise Unsupported('heterogeneous family: use frozen fallback')
    return (v, components, ct, pred, succ)
