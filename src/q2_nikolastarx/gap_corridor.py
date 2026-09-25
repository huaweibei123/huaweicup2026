"""Exact pre-Step2 tensor-byte refinement inside a fixed gap-calendar corridor.

Adapted from ChatGPT 6 Pro r04 attachment ``r04-reuse_corridor.py`` in
``AI chats/20260924-P2-异构流水与最优性界/附件/``; source SHA-256:
119b5f25cff1b75a41abb4e052fbc07c03961712ee65498f88ca7c6004055346.

No official evaluator or prepared graph is called.  This is NOT a Makespan,
spill, or MEMORY_REUSE certificate.  The input timestamps are a witness for
an explicitly specified static per-edge-lag model and are never submitted.
All capacities and byte costs in the cut network use Python integers.
"""
from __future__ import annotations
from bisect import bisect_left
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Mapping, Sequence

COPY = {"COPY_IN", "COPY_OUT"}

@dataclass(frozen=True)
class Net:
    name: str
    pins: frozenset[int]
    weight: int

    def __post_init__(self):
        if not self.pins or type(self.weight) is not int or self.weight < 0:
            raise ValueError('nonempty pins and nonnegative integer weight required')

@dataclass(frozen=True)
class Interval:
    op: int
    pipe: str
    start: int
    end: int


def physical_nets(graph: dict, op_to_unit: Mapping[int, int]) -> tuple[int, list[Net]]:
    """Return K,nets such that pre-Step2 COPY bytes = K + sum w*(lambda-1).

    Requires validated graph identifiers/endpoints, nonnegative integer sizes,
    <=1 eligible producer per physical tensor, and no logical_tid annotation.
    Original COPY operations are not pins. Direct-edge records are not deduped.
    This function is deliberately not a replacement for official validation.
    """
    ops = {o['id']: o for o in graph['ops']}
    tensors = {t['id']: t for t in graph['tensors']}
    eligible = {u for u, o in ops.items() if o['op'] not in COPY}
    if set(op_to_unit) != eligible:
        raise ValueError('unit map must cover every eligible operation exactly')
    if len(ops) != len(graph['ops']) or len(tensors) != len(graph['tensors']) or set(ops)&set(tensors):
        raise ValueError('duplicate/overlapping identifiers')
    for t in tensors.values():
        if 'logical_tid' in t:
            raise ValueError('logical alias annotation outside this implementation guard')
        if type(t['size']) is not int or t['size'] < 0:
            raise ValueError('nonnegative integer tensor bytes required')
    ps, cs, direct = defaultdict(set), defaultdict(set), []
    for edge in graph['edges']:
        u, v = edge['source'], edge['target']
        if u in ops and v in tensors:
            ps[v].add(u)
        elif u in tensors and v in ops:
            cs[u].add(v)
        elif u in ops and v in ops:
            if u != v:  # matches _original_tensor_views; graph validation is separate
                size = edge.get('data_size', 0)
                if type(size) is not int or size < 0:
                    raise ValueError('direct edge size outside nonnegative integer guard')
                direct.append((u, v, size))
        else:
            raise ValueError('unsupported graph incidence')
    constant, nets = 0, []
    for tid, t in tensors.items():
        producers, consumers = ps[tid] & eligible, cs[tid] & eligible
        if len(producers) > 1:
            raise ValueError('multiple eligible tensor producers')
        s = t['size']
        if not producers:
            if consumers:
                constant += s
                nets.append(Net('input:'+str(tid), frozenset(op_to_unit[u] for u in consumers), s))
            continue
        if not consumers or any(ops[u]['op']=='COPY_OUT' for u in cs[tid]):
            constant += s
        pins = producers | consumers
        nets.append(Net('tensor:'+str(tid), frozenset(op_to_unit[u] for u in pins), 2*s))
    for number, (u, v, size) in enumerate(direct):
        if u in eligible and v in eligible:
            nets.append(Net('direct:'+str(number), frozenset((op_to_unit[u], op_to_unit[v])), 2*size))
    return constant, nets


def cost(nets: Sequence[Net], owner: Mapping[int, int], constant: int = 0) -> int:
    return constant + sum(e.weight*(len({owner[v] for v in e.pins})-1) for e in nets)


def delta_all(nets: Sequence[Net], owner: Mapping[int, int], moved: set[int], a: int, b: int) -> int:
    """Exact simultaneous delta; do not sum stale single-unit deltas."""
    if a == b or any(owner[v] != a for v in moved):
        raise ValueError('move must be unidirectional between distinct cores')
    ans = 0
    for e in nets:
        donor = {v for v in e.pins if owner[v] == a}
        touched = donor & moved
        if touched:
            opened = not any(owner[v] == b for v in e.pins)
            closed = donor <= moved
            ans += e.weight*(int(opened)-int(closed))
    return ans


class _Dinic:
    """Integer max flow, iterative blocking paths (no recursion-depth dependence)."""
    def __init__(self, n: int):
        self.g: list[list[list[int]]] = [[] for _ in range(n)]
        self.original: list[tuple[int,int,int]] = []
    def node(self) -> int:
        self.g.append([])
        return len(self.g)-1
    def add(self, u: int, v: int, cap: int) -> None:
        if cap < 0 or type(cap) is not int:
            raise ValueError('integer nonnegative capacities required')
        if u == v or cap == 0:
            return
        iu, iv = len(self.g[u]), len(self.g[v])
        self.g[u].append([v, iv, cap])
        self.g[v].append([u, iu, 0])
        self.original.append((u,v,cap))
    def solve(self, s: int, t: int) -> tuple[int, set[int]]:
        n, total = len(self.g), 0
        path_limit = 1 + sum(c for u,v,c in self.original if u == s)
        while True:
            level = [-1]*n
            level[s] = 0
            queue = deque([s])
            while queue:
                u = queue.popleft()
                for v, _, cap in self.g[u]:
                    if cap and level[v] < 0:
                        level[v] = level[u]+1
                        queue.append(v)
            if level[t] < 0:
                break
            cur = [0]*n
            while True:
                vs, es, minimum = [s], [], [path_limit]
                found = False
                while vs:
                    u = vs[-1]
                    if u == t:
                        amount = minimum[-1]
                        for p, j in es:
                            edge = self.g[p][j]
                            v, rev, _ = edge
                            edge[2] -= amount
                            self.g[v][rev][2] += amount
                        total += amount
                        found = True
                        break
                    while cur[u] < len(self.g[u]):
                        v, _, cap = self.g[u][cur[u]]
                        if cap and level[v] == level[u]+1:
                            break
                        cur[u] += 1
                    if cur[u] == len(self.g[u]):
                        level[u] = -1
                        vs.pop(); minimum.pop()
                        if es:
                            p, _ = es.pop()
                            cur[p] += 1
                    else:
                        j = cur[u]
                        v, _, cap = self.g[u][j]
                        es.append((u,j)); vs.append(v)
                        minimum.append(min(minimum[-1],cap))
                if not found:
                    break
        reachable = {s}
        queue = deque([s])
        while queue:
            u = queue.popleft()
            for v, _, cap in self.g[u]:
                if cap and v not in reachable:
                    reachable.add(v); queue.append(v)
        cut = sum(c for u,v,c in self.original if u in reachable and v not in reachable)
        if cut != total:
            raise AssertionError('max-flow/min-cut mismatch')
        return total, reachable


def exact_one_way_cut(nets: Sequence[Net], owner: Mapping[int,int],
                      movable: set[int], a: int, b: int) -> tuple[set[int], dict]:
    """Globally minimize exact byte cost over ALL subsets of movable a->b.

    Resource and lag admissibility of every subset must be established by the
    caller. Other cores and all nonmovable units are fixed. One max-flow call.
    """
    if a == b or any(owner[v] != a for v in movable):
        raise ValueError('invalid one-way domain')
    # Exact decision-signature compression: physical tensors remain distinct
    # in accounting, but identical variable supports share OR/AND capacities.
    supports = defaultdict(lambda: [0,0])  # [opening bytes, closing bytes]
    incident_nets = 0
    for e in nets:
        if not e.weight:
            continue
        donor = {v for v in e.pins if owner[v] == a}
        variables = frozenset(donor & movable)
        if not variables:
            continue
        open_b = not any(owner[v] == b for v in e.pins)
        can_close_a = donor <= movable
        if open_b or can_close_a:
            incident_nets += 1
            supports[variables][0] += e.weight*int(open_b)
            supports[variables][1] += e.weight*int(can_close_a)
    # A term has values 0, O, O-R; hence it can save at most max(0,R-O).
    potential = sum(max(0,R-O) for O,R in supports.values())
    if not potential:
        return set(), {'potential_saving_upper_bytes':0, 'flow_calls':0,
                       'saving_bytes':0, 'movable_groups':len(movable),
                       'incident_nets':incident_nets, 'decision_supports':len(supports)}
    number = {v: i+2 for i,v in enumerate(sorted(movable))}
    flow = _Dinic(2+len(number))
    source, sink = 0, 1
    finite = sum(abs(O-R) if len(F)==1 else O+R for F,(O,R) in supports.items())
    infinity = finite+1
    empty_cut = 0
    for variables,(O,R) in supports.items():
        if len(variables)==1:
            node = number[next(iter(variables))]
            coefficient = O-R
            if coefficient >= 0:
                flow.add(node,sink,coefficient)
            else:
                flow.add(source,node,-coefficient)
                empty_cut -= coefficient
            continue
        if O:
            node = flow.node()
            flow.add(node,sink,O)
            for v in variables:
                flow.add(number[v],node,infinity)
        if R:
            node = flow.node()
            flow.add(source,node,R)
            for v in variables:
                flow.add(node,number[v],infinity)
            empty_cut += R
    value, reachable = flow.solve(source,sink)
    moved = {v for v, node in number.items() if node in reachable}
    actual_delta = delta_all(nets,owner,moved,a,b)
    if actual_delta != value-empty_cut or actual_delta > 0:
        raise AssertionError('cut network does not equal exact connectivity delta')
    if actual_delta == 0:
        moved = set()  # no gratuitous relabeling at zero byte improvement
    return moved, {'potential_saving_upper_bytes':potential, 'flow_calls':1,
                   'saving_bytes':-actual_delta, 'flow_value':value,
                   'empty_move_cut_value':empty_cut, 'flow_nodes':len(flow.g),
                   'flow_arcs':len(flow.original), 'movable_groups':len(movable),
                   'incident_nets':incident_nets, 'decision_supports':len(supports)}


class _DSU:
    def __init__(self,n): self.p=list(range(n))
    def find(self,x):
        while self.p[x] != x:
            self.p[x]=self.p[self.p[x]]; x=self.p[x]
        return x
    def union(self,x,y):
        x,y=self.find(x),self.find(y)
        if x != y: self.p[max(x,y)]=min(x,y)


def _check_calendars(footprints, owners):
    queues = defaultdict(list)
    for g, row in footprints.items():
        for iv in row:
            queues[owners[g],iv.pipe].append(iv)
    for row in queues.values():
        row.sort(key=lambda v:(v.start,v.end,v.op))
        for x,y in zip(row,row[1:]):
            if x.end > y.start:
                raise ValueError('compute calendar overlap')
    return queues


def _fits(row, calendars, target):
    for iv in row:
        busy = calendars.get((target,iv.pipe), [])
        # A production adapter should keep these start arrays persistent.
        starts = [x.start for x in busy]
        at = bisect_left(starts,iv.start)
        if (at and busy[at-1].end > iv.start) or (at<len(busy) and busy[at].start < iv.end):
            return False
    return True


def repair_gap_witness(graph: dict, chains: Sequence[Sequence[int]],
                       placement: Mapping[int,int], starts: Mapping[int,int],
                       delays: Mapping[tuple[int,int],int], cores: int,
                       mapping: Mapping[str,int]) -> tuple[dict,dict]:
    """Adapter for gap_candidate.build just before singleton plan creation.

    `delays` is exactly its chosen STATIC unit-edge delay map.  All starts are
    kept unchanged. The current source-only groups are the sole flow variables.
    At most k*(k-1) one-way corridor flows; no convergence loop or E2 search.
    The caller MUST call official derive_multicore_plan on the returned plan.
    """
    ops = {o['id']:o for o in graph['ops'] if o['op'] not in COPY}
    op_unit = {u:j for j,row in enumerate(chains) for u in row}
    if set(op_unit)!=set(ops) or sum(map(len,chains))!=len(ops):
        raise ValueError('chains must partition eligible operations')
    if set(placement)!=set(range(len(chains))) or set(starts)!=set(ops):
        raise ValueError('incomplete placement/start witness')
    if set(mapping)!={str(u) for u in ops} or len(set(mapping.values()))!=len(ops):
        raise ValueError('a fixed singleton map is required')
    if type(cores) is not int or cores<1 or any(type(c) is not int or not 0<=c<cores for c in placement.values()):
        raise ValueError('invalid cores')
    footprints = {}
    unit_start,unit_end={},{}
    for j,row in enumerate(chains):
        if not row: raise ValueError('empty chain')
        values=[]
        for u in row:
            if type(starts[u]) is not int or starts[u]<0 or type(ops[u]['cycles']) is not int:
                raise ValueError('integer model timestamps and durations required')
            iv=Interval(u,ops[u]['pipe'],starts[u],starts[u]+max(1,ops[u]['cycles']))
            values.append(iv)
        for x,y in zip(values,values[1:]):
            if x.end>y.start: raise ValueError('chain witness not sequential')
        footprints[j]=values
        unit_start[j]=values[0].start; unit_end[j]=values[-1].end
    _check_calendars(footprints,placement)
    # Verify the caller did not omit a represented inter-unit dependency.
    producer = defaultdict(set)
    consumer = defaultdict(set)
    physical_edges = set()
    tensors = {t['id'] for t in graph['tensors']}
    for edge in graph['edges']:
        u,v=edge['source'],edge['target']
        if u in ops and v in tensors: producer[v].add(u)
        elif u in tensors and v in ops: consumer[u].add(v)
        elif u in ops and v in ops and u!=v: physical_edges.add((u,v))
    for t in tensors:
        for u in producer[t]:
            for v in consumer[t]:
                if u!=v: physical_edges.add((u,v))
    expected = {(op_unit[u],op_unit[v]) for u,v in physical_edges if op_unit[u]!=op_unit[v]}
    if set(delays)!=expected:
        raise ValueError('static unit delay map does not cover represented inter-unit edges exactly')
    for u,v in physical_edges:
        if starts[v]<starts[u]+max(1,ops[u]['cycles']):
            raise ValueError('initial witness violates a retained physical dependency')
    dsu=_DSU(len(chains))
    for (u,v),lag in delays.items():
        if type(lag) is not int or lag<0: raise ValueError('invalid static lag')
        slack=unit_start[v]-unit_end[u]
        if slack<0 or (placement[u]!=placement[v] and slack<lag):
            raise ValueError('initial witness violates chosen static model')
        if slack<lag: dsu.union(u,v)
    roots=sorted({dsu.find(j) for j in range(len(chains))})
    group_id={r:i for i,r in enumerate(roots)}
    unit_group={j:group_id[dsu.find(j)] for j in range(len(chains))}
    group_owner={}; group_footprints=defaultdict(list)
    for j in range(len(chains)):
        g=unit_group[j]
        if g in group_owner and group_owner[g]!=placement[j]:
            raise ValueError('tight group split in seed')
        group_owner[g]=placement[j]
        group_footprints[g].extend(footprints[j])
    constant,nets=physical_nets(graph,{u:unit_group[j] for u,j in op_unit.items()})
    initial_owner=dict(group_owner)
    before=cost(nets,group_owner,constant)
    # Byte-derived priority, not a learned threshold. Every ordered pair once.
    affinity=defaultdict(int)
    for e in nets:
        touched={group_owner[v] for v in e.pins}
        for a in touched:
            for b in touched:
                if a!=b: affinity[a,b]+=e.weight
    pairs=sorted(((a,b) for a in range(cores) for b in range(cores) if a!=b),
                 key=lambda pair:(-affinity[pair],pair))
    reports=[]
    for a,b in pairs:
        calendars=_check_calendars(group_footprints,group_owner)
        # Precompute binary-search keys once, avoiding repeated large lists.
        target_rows={pipe:(row,[iv.start for iv in row])
                     for (core,pipe),row in calendars.items() if core==b}
        def fits(g):
            for iv in group_footprints[g]:
                row,keys=target_rows.get(iv.pipe,([],[]))
                at=bisect_left(keys,iv.start)
                if ((at and row[at-1].end>iv.start)
                    or (at<len(row) and row[at].start<iv.end)):
                    return False
            return True
        movable={g for g in group_owner if group_owner[g]==a and fits(g)}
        selected,detail=exact_one_way_cut(nets,group_owner,movable,a,b)
        old=cost(nets,group_owner,constant)
        for g in selected: group_owner[g]=b
        new=cost(nets,group_owner,constant)
        if old-new!=detail['saving_bytes'] or new>old:
            raise AssertionError('global byte counter and flow disagree')
        reports.append({'source_core':a,'target_core':b,'moved_groups':sorted(selected),**detail})
    _check_calendars(group_footprints,group_owner)
    for (u,v),lag in delays.items():
        crossed=group_owner[unit_group[u]]!=group_owner[unit_group[v]]
        if unit_start[v]<unit_end[u]+(lag if crossed else 0):
            raise AssertionError('static release witness changed')
    per_core=[[] for _ in range(cores)]
    for u,j in op_unit.items(): per_core[group_owner[unit_group[j]]].append(u)
    plan={'node_to_subgraph':dict(mapping),'core_schedules':[
        [mapping[str(u)] for u in sorted(row,key=lambda u:(starts[u],mapping[str(u)]))]
        for row in per_core]}
    after=cost(nets,group_owner,constant)
    return plan, {'method':'one_pass_tensor_cut_corridor','pre_step2_bytes_before':before,
        'pre_step2_bytes_after':after,'saved_pre_step2_bytes':before-after,
        'fixed_proxy_horizon':max((unit_end[j] for j in unit_end),default=0),
        'original_chain_count':len(chains),'tight_group_count':len(roots),
        'changed_groups_final':sum(initial_owner[g]!=c for g,c in group_owner.items()),
        'flow_calls':sum(r['flow_calls'] for r in reports),'pairs':reports,
        'official_validation_executed':False,'official_M_guarantee':False,
        'zero_spill_guarantee':False,'COPY_count_guarantee':False,
        'calls':{'E0':0,'E1':0,'E2':0},
        'scope':'Exact pre-Step2 byte improvement; unchanged feasibility witness for caller static lag model only.'}


def build(graph: dict, cores: int, config: dict) -> tuple[dict, dict]:
    """Seed once, repair within fixed timestamps, and independently count bytes.

    This is a new candidate constructor, not a Makespan or spill certificate.
    Each ordered core pair is visited once; no evaluator is called.
    """
    from .candidate_ddr import mandatory_copy_work
    from .direct import derive_multicore_plan
    from .gap_candidate import build_with_witness

    seed, seed_meta, witness = build_with_witness(graph, cores, config)
    derive_multicore_plan(graph, seed)
    repaired, repair_meta = repair_gap_witness(graph, cores=cores, **witness)
    derive_multicore_plan(graph, repaired)
    before = mandatory_copy_work(graph, seed, config['bandwidth'])['transfer_bytes']
    after = mandatory_copy_work(graph, repaired, config['bandwidth'])['transfer_bytes']
    if (before != repair_meta['pre_step2_bytes_before']
            or after != repair_meta['pre_step2_bytes_after'] or after > before):
        raise AssertionError('independent original COPY byte count disagrees')
    selected = repaired if after < before else seed
    return selected, {'selected': 'gap_corridor' if after < before else 'gap_seed',
                      'seed': seed_meta, 'repair': repair_meta,
                      'independent_original_copy_bytes_before': before,
                      'independent_original_copy_bytes_after': after,
                      'scope': 'Fixed static-calendar corridor; no official Makespan, spill or capacity guarantee'}
