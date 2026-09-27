"""Linear-time sufficient certificate for zero Step2 spills of singleton Q2/Q3 plans.
Not a makespan model. Does NOT certify Step3/global execution legality.
Conditions: validated bipartite graph, no eligible-touch DDR tensors, no internal excluded
COPY bridge, one eligible op per sg, correct per-core compute precedence.
"""
from __future__ import annotations
from collections import defaultdict
from graph_features import Graph

def certify(g:Graph,plan,capacity=None):
    if capacity is None:capacity={'L1':524288,'UB':131072}
    if set(plan)!={'node_to_subgraph','core_schedules'}:raise ValueError('plan fields')
    mp={int(o):sg for o,sg in plan['node_to_subgraph'].items()}
    if set(mp)!=g.eligible or len(mp)!=len(plan['node_to_subgraph']):raise ValueError('coverage or aliased IDs')
    if any(type(sg) is not int or sg<0 for sg in mp.values()):raise ValueError('subgraph ID')
    if len(set(mp.values()))!=len(mp):return {'supported':False,'reason':'non-singleton subgraphs'}
    schedules=plan['core_schedules'];sgop={sg:o for o,sg in mp.items()}
    flat=[sg for order in schedules for sg in order]
    if not schedules or len(flat)!=len(set(flat)) or set(flat)!=set(sgop):raise ValueError('core coverage')
    owner={};rank={}
    for c,order in enumerate(schedules):
        for i,sg in enumerate(order):owner[sgop[sg]]=c;rank[sgop[sg]]=i
    for o in g.ids:
        direct=set().union(*(g.cons[t]&g.eligible for t in g.outputs[o])) if g.outputs[o] else set()
        if direct!=g.succ[o]:return {'supported':False,'reason':'internal excluded-copy bridge'}
        for v in g.succ[o]:
            if owner[o]==owner[v] and rank[o]>=rank[v]:raise ValueError('same-core precedence')
    events=[{p:[0]*(len(order)+1) for p in capacity} for order in schedules]
    for tid,t in g.ts.items():
        incident=(g.prod[tid]|g.cons[tid])&g.eligible
        if not incident:continue
        if t['pos'] not in capacity:return {'supported':False,'reason':'eligible tensor outside onchip certificate domain'}
        intervals={}
        for o in incident:
            c=owner[o];i=rank[o]
            if c not in intervals:intervals[c]=[i,i]
            else:intervals[c][0]=min(intervals[c][0],i);intervals[c][1]=max(intervals[c][1],i)
        for c,(a,b) in intervals.items():
            events[c][t['pos']][a]+=t['size'];events[c][t['pos']][b+1]-=t['size']
    peaks=[]
    for c,order in enumerate(schedules):
        peak={p:0 for p in capacity}
        for p in capacity:
            live=0
            for d in events[c][p]:live+=d;peak[p]=max(peak[p],live)
            assert live==0
        peaks.append(peak)
    return {'supported':True,'no_spill_sufficient':all(v[p]<=capacity[p] for v in peaks for p in capacity),
            'bucket_peak_by_core':peaks,'certifies':'only zero Step2 spill for Q2/Q3; global legality and makespan unchecked'}
