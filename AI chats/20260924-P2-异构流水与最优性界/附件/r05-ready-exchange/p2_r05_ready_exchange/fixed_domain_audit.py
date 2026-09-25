"""Diagnostic only: exact two-core fixed-time assignment domain.
No attempt to optimize signed hyperedges, no full-label enumeration in this file.
"""
from collections import defaultdict


def audit(ops, units, owner, starts, unit_lags, nets, constant=0):
    n=len(units)
    if set(owner)!=set(range(n)) or any(c not in (0,1) for c in owner.values()):
        raise ValueError('exactly two possible core labels and full unit map required')
    parent=list(range(n))
    def find(a):
        while parent[a]!=a:
            parent[a]=parent[parent[a]]; a=parent[a]
        return a
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[max(a,b)]=min(a,b)
    first={j:starts[row[0]] for j,row in enumerate(units)}
    last={j:starts[row[-1]]+ops[row[-1]].duration for j,row in enumerate(units)}
    for j,row in enumerate(units):
        for a,b in zip(row,row[1:]):
            if starts[a]+ops[a].duration>starts[b]: raise ValueError('nonserial unit')
    for (a,b),lag in unit_lags.items():
        slack=first[b]-last[a]
        if slack<0 or (owner[a]!=owner[b] and slack<lag): raise ValueError('invalid lag witness')
        if slack<lag: union(a,b)
    queues=defaultdict(list)
    for j,row in enumerate(units):
        for u in row: queues[ops[u].pipe].append((starts[u],starts[u]+ops[u].duration,j))
    conflicts=0
    for rows in queues.values():
        rows.sort(); active=[]
        for begin,end,j in rows:
            active=[(e,g) for e,g in active if e>begin]
            for e,g in active:
                if owner[g]==owner[j]: raise ValueError('seed same-Pipe overlap')
                conflicts+=1; union(g,j)
            active.append((end,j))
    roots=sorted({find(j) for j in range(n)})
    numbering={r:i for i,r in enumerate(roots)}
    block={j:numbering[find(j)] for j in range(n)}
    initial=constant; possible=0; mutable=[]; invariant_cut=[]
    # Can ALL noninvariant positive nets be made monochromatic? This is only
    # the attainability test for the invariant lower bound, not weighted Max-Cut.
    parity_graph=defaultdict(list)
    for t,net in enumerate(nets):
        cut=len({owner[j] for j in net.pins})==2
        initial+=net.weight*int(cut)
        phases=defaultdict(set)
        for j in net.pins: phases[block[j]].add(owner[j])
        forced_cut=any(len(cs)==2 for cs in phases.values())
        if net.weight and not forced_cut and len(phases)>1:
            root=next(iter(phases)); root_phase=next(iter(phases[root]))
            for b,cs in phases.items():
                if b!=root:
                    required=root_phase ^ next(iter(cs))
                    parity_graph[root].append((b,required))
                    parity_graph[b].append((root,required))
        if cut and forced_cut: invariant_cut.append(t)
        elif cut and len(phases)>1:
            possible+=net.weight; mutable.append(t)
    parity_values={}; attainable=True
    for root in range(len(roots)):
        if root in parity_values: continue
        parity_values[root]=0; stack=[root]
        while stack:
            u=stack.pop()
            for v,required in parity_graph[u]:
                value=parity_values[u]^required
                if v in parity_values:
                    if parity_values[v]!=value: attainable=False
                else:
                    parity_values[v]=value; stack.append(v)
    return {'blocks':block,'block_count':len(roots),'overlap_pairs':conflicts,
            'seed_bytes':initial,'potential_saving_upper_bytes':possible,
            'fixed_domain_byte_lower_bound':initial-possible,
            'byte_lower_bound_attainable_in_fixed_domain':attainable,
            'currently_cut_mutable_nets':mutable,'forced_cut_nets':invariant_cut,
            'scope':'Only fixed units, fixed starts, all supplied symmetric unit lags, two homogeneous cores.'}
