"""r05: exact tensor-cost matching DURING reconstruction of a static schedule.

Ported from ChatGPT 6 Pro r05 attachment ``ready_exchange.py`` (SHA-256
975c71da280fdda1274a8a10223b0b72a68967fff88becf1ddc9b81a55d01c63).
Local changes: use the existing persistent gap_calendar; compute owner keys
once for physical-net validation instead of once per net. No search policy or
matching parameters changed.

Scope: one pass, ready antichains, <=1 packet from each tentative source core,
injective packet->core assignment. Packets are serial same-Pipe chains. Tensor
bytes are exact pre-Step2 connectivity bytes. All timing is an explicitly named
operation-edge-lag relaxation, NOT official cycles, capacity, spill, or credit.
No permutations/subsets of candidate assignments are enumerated by this module.
No official evaluator, prepared graph, network, or historical result is used.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass
import heapq
from typing import Mapping, Sequence

from .gap_calendar import empty, earliest, reserve

@dataclass(frozen=True)
class Op:
    pipe: str
    duration: int

@dataclass(frozen=True)
class Net:
    pins: frozenset[int]  # packet IDs, NOT tensor aliases
    weight: int
    name: str = ''


def min_assignment(costs: Sequence[Sequence[int | None]]):
    """Rectangular Hungarian, exact nonnegative integers; None = forbidden.
    Return (minimum_cost, row_to_column) or None. O(k^3), rows <= columns.
    """
    n=len(costs)
    if not n: return 0, []
    k=len(costs[0])
    if n>k or any(len(row)!=k for row in costs): raise ValueError('rectangular rows<=columns')
    if any(any(x is not None and (type(x) is not int or x<0) for x in row) for row in costs):
        raise ValueError('nonnegative exact integers required')
    if any(all(x is None for x in row) for row in costs): return None
    # Any fully finite assignment has cost smaller than forbidden.
    forbidden=1+sum(max(x for x in row if x is not None) for row in costs)
    a=[[forbidden if x is None else x for x in row] for row in costs]
    u=[0]*(n+1); v=[0]*(k+1); p=[0]*(k+1); way=[0]*(k+1)
    big=(n+k+2)*(forbidden+1)
    for i in range(1,n+1):
        p[0]=i; j0=0
        mv=[big]*(k+1); used=[False]*(k+1)
        while True:
            used[j0]=True; i0=p[j0]; delta=big; j1=0
            for j in range(1,k+1):
                if not used[j]:
                    cur=a[i0-1][j-1]-u[i0]-v[j]
                    if cur<mv[j]: mv[j],way[j]=cur,j0
                    if mv[j]<delta: delta,j1=mv[j],j
            for j in range(k+1):
                if used[j]: u[p[j]]+=delta; v[j]-=delta
                else: mv[j]-=delta
            j0=j1
            if p[j0]==0: break
        while True:
            j1=way[j0]; p[j0]=p[j1]; j0=j1
            if j0==0: break
    assignment=[-1]*n
    for j in range(1,k+1):
        if p[j]: assignment[p[j]-1]=j-1
    if any(costs[i][c] is None for i,c in enumerate(assignment)): return None
    return sum(costs[i][c] for i,c in enumerate(assignment)), assignment


def byte_budget_bottleneck(costs, horizons, reference):
    """Exact lex (minimum bottleneck horizon, minimum bytes, fewest relabels)
    subject to byte cost <= reference cost and edge eligibility.
    Feasibility at a threshold is a minimum-cost assignment, not an independent
    per-edge test. Binary search only mathematical breakpoints from this matrix.
    """
    m=len(costs)
    if not m: return {'assignment':[], 'bytes':0, 'horizon':0, 'matching_calls':0}
    k=len(costs[0])
    if len(set(reference))!=m: raise ValueError('reference must be injective')
    if any(costs[i][reference[i]] is None or horizons[i][reference[i]] is None for i in range(m)):
        raise ValueError('reference must be eligible')
    budget=sum(costs[i][reference[i]] for i in range(m))
    reference_h=max(horizons[i][reference[i]] for i in range(m))
    values=sorted({horizons[i][c] for i in range(m) for c in range(k)
                   if costs[i][c] is not None and horizons[i][c] is not None
                   and horizons[i][c]<=reference_h})
    calls=0; memo={}
    def check(at):
        nonlocal calls
        if at in memo: return memo[at]
        threshold=values[at]
        # Exact lex encoding, not an empirical bytes/cycles penalty.
        matrix=[[(costs[i][c]*(m+1)+int(c!=reference[i]))
                 if costs[i][c] is not None and horizons[i][c] is not None
                    and horizons[i][c]<=threshold else None
                 for c in range(k)] for i in range(m)]
        answer=min_assignment(matrix); calls+=1
        if answer is None: result=None
        else:
            _,a=answer; byte_cost=sum(costs[i][c] for i,c in enumerate(a))
            result=(byte_cost,a) if byte_cost<=budget else None
        memo[at]=result
        return result
    lo,hi=0,len(values)-1
    assert check(hi) is not None
    while lo<hi:
        mid=(lo+hi)//2
        if check(mid) is None: lo=mid+1
        else: hi=mid
    value,a=check(lo)
    return {'assignment':a, 'bytes':value, 'reference_bytes':budget,
            'horizon':values[lo], 'reference_horizon':reference_h,
            'matching_calls':calls, 'threshold_count':len(values)}


def net_cost(nets,owner,constant=0):
    return constant+sum(t.weight*(len({owner[j] for j in t.pins})-1) for t in nets)


def byte_matrix(nets, owner, batch, cores, incidence=None, counts=None):
    """Compute exact separable objective for an INJECTIVE batch assignment.
    Other units retain their currently complete tentative labels, including
    units whose operations have not been scheduled. No future reuse is guessed.
    """
    if incidence is None:
        incidence=defaultdict(list)
        for t,e in enumerate(nets):
            for j in e.pins: incidence[j].append(t)
    if counts is None:
        counts=[Counter(owner[j] for j in t.pins) for t in nets]
    touched={t for j in batch for t in incidence[j]}
    outside={t:counts[t].copy() for t in touched}
    for j in batch:
        for t in incidence[j]: outside[t][owner[j]]-=1
    matrix=[[sum(nets[t].weight for t in incidence[j] if outside[t][c]==0)
             for c in range(cores)] for j in batch]
    return matrix, outside


def topo(nodes, arcs):
    succ={u:[] for u in nodes}; deg=dict.fromkeys(nodes,0)
    for u,v in arcs:
        succ[u].append(v); deg[v]+=1
    ready=[u for u in nodes if not deg[u]]; heapq.heapify(ready); order=[]
    while ready:
        u=heapq.heappop(ready); order.append(u)
        for v in succ[u]:
            deg[v]-=1
            if not deg[v]: heapq.heappush(ready,v)
    if len(order)!=len(nodes): raise ValueError('cycle')
    return order,succ


def replay(ops:Mapping[int,Op], lags, op_owner, sequences):
    """Exact earliest schedule of a fixed COMPUTE/FIFO STATIC-LAG model.
    Not an official lower or upper bound. Both seed and rebuilt plan use this
    SAME operation-level timing model; old witness times are not compared to a
    different weaker model without relabeling the scope.
    """
    flat=[u for row in sequences for u in row]
    if len(flat)!=len(ops) or set(flat)!=set(ops): raise ValueError('coverage')
    arcs={(u,v):(lag if op_owner[u]!=op_owner[v] else 0) for (u,v),lag in lags.items()}
    for c,row in enumerate(sequences):
        last={}
        for u in row:
            if op_owner[u]!=c: raise ValueError('owner/sequence mismatch')
            pipe=ops[u].pipe
            if pipe in last: arcs.setdefault((last[pipe],u),0)
            last[pipe]=u
    order,succ=topo(ops,arcs)
    starts=dict.fromkeys(ops,0); ends={}
    for u in order:
        ends[u]=starts[u]+ops[u].duration
        for v in succ[u]: starts[v]=max(starts[v],ends[u]+arcs[u,v])
    return max(ends.values(),default=0),starts,ends


def rebuild(ops:Mapping[int,Op], packets:Sequence[Sequence[int]], lags,
            nets:Sequence[Net], constant:int, owner:Mapping[int,int],
            seed_sequences:Sequence[Sequence[int]], *, final_proxy_guard=True):
    """One deterministic ready-antichain matching pass. Old starts are discarded.

    Preconditions: packets partition ops, each is a serial same-Pipe chain,
    the seed labels each packet on one core, lags include the intended retained
    operation dependencies (zero-size communication edges must NOT be omitted).
    Returns op sequences and audit metadata, NOT an official validation result.
    """
    cores=len(seed_sequences); packet_count=len(packets)
    if not 1<=cores<=5: raise ValueError('one through five cores required')
    op_packet={u:j for j,row in enumerate(packets) for u in row}
    if set(op_packet)!=set(ops) or sum(map(len,packets))!=len(ops): raise ValueError('packet coverage')
    if set(owner)!=set(range(packet_count)): raise ValueError('owner coverage')
    for j,row in enumerate(packets):
        if not row or len({ops[u].pipe for u in row})!=1: raise ValueError('same-Pipe packet required')
        if not 0<=owner[j]<cores: raise ValueError('owner range')
        for u in row:
            if type(ops[u].duration) is not int or ops[u].duration<=0: raise ValueError('positive integer durations')
        for u,v in zip(row,row[1:]):
            if (u,v) not in lags: raise ValueError('packet must preserve actual serial links')
    if any(type(v) is not int or v<0 for v in lags.values()): raise ValueError('nonnegative static lags')
    owner_keys=set(owner)
    for t in nets:
        if not t.pins or not t.pins<=owner_keys or type(t.weight) is not int or t.weight<0:
            raise ValueError('invalid physical hyperedge')
    initial_owner=dict(owner); tentative=dict(owner)
    seed_op_owner={u:owner[op_packet[u]] for u in ops}
    seed_horizon,_,_=replay(ops,lags,seed_op_owner,seed_sequences)
    # Full tentative ownership load, including unscheduled future packets.
    pipes=sorted({o.pipe for o in ops.values()})
    work=[Counter({p:0 for p in pipes}) for _ in range(cores)]
    packet_work=[]
    for j,row in enumerate(packets):
        w=Counter()
        for u in row: w[ops[u].pipe]+=ops[u].duration
        packet_work.append(w); work[owner[j]].update(w)
    assert all(max(row.values(),default=0)<=seed_horizon for row in work)
    unit_arcs={(op_packet[u],op_packet[v]) for u,v in lags if op_packet[u]!=op_packet[v]}
    unit_order,unit_succ=topo(range(packet_count),unit_arcs)
    pending=[0]*packet_count; unit_pred=[set() for _ in packets]
    for u,v in unit_arcs: pending[v]+=1; unit_pred[v].add(u)
    predecessors={u:[] for u in ops}
    for (u,v),lag in lags.items(): predecessors[v].append((u,lag))
    duration=[sum(ops[u].duration for u in row) for row in packets]
    tail={}
    for j in reversed(unit_order):
        tail[j]=duration[j]+max((tail[v] for v in unit_succ[j]),default=0)
    queues=[[] for _ in range(cores)]
    for j in unit_order:
        if not pending[j]: heapq.heappush(queues[tentative[j]],(-tail[j],min(packets[j]),j))
    incidence=defaultdict(list)
    for t,e in enumerate(nets):
        for j in e.pins: incidence[j].append(t)
    counts=[Counter(owner[j] for j in t.pins) for t in nets]
    initial_bytes=net_cost(nets,owner,constant); current_bytes=initial_bytes
    calendars=[{p:empty() for p in pipes} for _ in range(cores)]
    placed=set(); starts={}; ends={}; records=[]
    calls=0
    while len(placed)<packet_count:
        batch=[heapq.heappop(q)[2] for q in queues if q]
        if not batch: raise AssertionError('ready frontier unexpectedly empty')
        reference=[tentative[j] for j in batch]
        assert len(set(reference))==len(reference)
        assert all(unit_pred[j]<=placed for j in batch)
        costs,_=byte_matrix(nets,tentative,batch,cores,incidence,counts)
        residual=[row.copy() for row in work]
        for j in batch: residual[tentative[j]].subtract(packet_work[j])
        horizons=[[None]*cores for _ in batch]; witnesses={}
        for i,j in enumerate(batch):
            for c in range(cores):
                if any(residual[c][p]+packet_work[j][p]>seed_horizon for p in pipes):
                    continue
                candidate=dict(calendars[c]); local_ends={}; local_starts={}
                for u in packets[j]:
                    release=0
                    for v,lag in predecessors[u]:
                        if v in local_ends: finish=local_ends[v]; pc=c
                        else:
                            finish=ends[v]; pc=tentative[op_packet[v]]
                        release=max(release,finish+(lag if pc!=c else 0))
                    pipe=ops[u].pipe; d=ops[u].duration
                    begin=earliest(candidate[pipe],release,d)
                    candidate[pipe]=reserve(candidate[pipe],begin,d)
                    local_starts[u]=begin; local_ends[u]=begin+d
                end=local_ends[packets[j][-1]]
                horizons[i][c]=end+tail[j]-duration[j]
                witnesses[i,c]=(candidate,local_starts,local_ends)
        eligible_costs=[[costs[i][c] if horizons[i][c] is not None else None
                         for c in range(cores)] for i in range(len(batch))]
        match=byte_budget_bottleneck(eligible_costs,horizons,reference)
        calls+=match['matching_calls']
        assignment=match['assignment']
        delta=match['bytes']-match['reference_bytes']
        assert delta<=0
        for j,c in zip(batch,reference):
            for t in incidence[j]: counts[t][c]-=1
        newwork=residual
        for i,(j,c) in enumerate(zip(batch,assignment)):
            tentative[j]=c; placed.add(j); newwork[c].update(packet_work[j])
            for t in incidence[j]: counts[t][c]+=1
            calendars[c],ls,le=witnesses[i,c]
            starts.update(ls); ends.update(le)
        work=newwork; current_bytes+=delta
        for j in batch:
            for v in unit_succ[j]:
                pending[v]-=1
                if not pending[v]: heapq.heappush(queues[tentative[v]],(-tail[v],min(packets[v]),v))
        records.append({'packets':batch,'old':reference,'new':assignment,
                        'saved_bytes':-delta, 'horizon':match['horizon'],
                        'reference_horizon':match['reference_horizon'],
                        'matching_calls':match['matching_calls'],
                        'eligible_edges':sum(h is not None for row in horizons for h in row),
                        'eligible_nonidentity_edges':sum(horizons[i][c] is not None and c!=reference[i]
                            for i in range(len(batch)) for c in range(cores))})
    assert current_bytes==net_cost(nets,tentative,constant)<=initial_bytes
    op_owner={u:tentative[op_packet[u]] for u in ops}
    seq=[[] for _ in range(cores)]
    for u in sorted(ops,key=lambda u:(starts[u],u)): seq[op_owner[u]].append(u)
    rebuilt_horizon,replay_starts,replay_ends=replay(ops,lags,op_owner,seq)
    witness_horizon=max(ends.values(),default=0)
    assert rebuilt_horizon<=witness_horizon
    if final_proxy_guard:
        use_new=(rebuilt_horizon<=seed_horizon and current_bytes<=initial_bytes
                 and (rebuilt_horizon<seed_horizon or current_bytes<initial_bytes))
    else: use_new=True
    final_seq=seq if use_new else [list(row) for row in seed_sequences]
    return final_seq, {
        'method':'ready_injective_tensor_matching', 'packet_count':packet_count,
        'rounds':len(records), 'assignment_solver_calls':calls,
        'pre_step2_bytes_seed':initial_bytes,'pre_step2_bytes_rebuilt':current_bytes,
        'seed_common_proxy_cycles':seed_horizon,'rebuilt_common_proxy_cycles':rebuilt_horizon,
        'constructive_witness_cycles':witness_horizon,
        'returned':'rebuilt' if use_new else 'seed',
        'changed_packets':sum(tentative[j]!=initial_owner[j] for j in tentative),
        'strict_byte_rounds':sum(r['saved_bytes']>0 for r in records),
        'eligible_nonidentity_edges':sum(r['eligible_nonidentity_edges'] for r in records),
        'strict_local_horizon_rounds':sum(r['horizon']<r['reference_horizon'] for r in records),
        'round_details':records,
        'rebuilt_owner':tentative,'rebuilt_starts':replay_starts,
        'calls':{'E0':0,'E1':0,'E2':0},
        'scope':'Exact conditional bytes and matching; feasible STATIC compute/edge-lag witness only.',
        'official_makespan_guarantee':False,'official_zero_spill_guarantee':False,
        'global_proxy_nonincrease_from_local_matches':False}
