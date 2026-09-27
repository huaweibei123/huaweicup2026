"""Construct, not simulate: compile identical M -> V* -> M jobs into a FIFO word.
All score times are discarded; only original-op subgraph priorities are emitted.
"""
import heapq, math
from construct import component_assignment,plan_from_groups

def descriptor(a,job):
    e=a['eligible'];w=[e[u]['pipe'] for u in job]
    if len(job)<3 or w[0]!='PIPE_M' or w[-1]!='PIPE_M' or any(p!='PIPE_V' for p in w[1:-1]):
        raise ValueError('not an M V* M resource word')
    aa=max(1,e[job[0]]['cycles']);cc=max(1,e[job[-1]]['cycles'])
    if aa!=cc:raise ValueError('prototype requires equal first/last M durations')
    ds=tuple(max(1,e[u]['cycles']) for u in job)
    return aa,sum(ds[1:-1]),ds

def word_plan(a,k,lookahead=None):
    cs=a['components'];e=a['eligible'];desc=[descriptor(a,c) for c in cs]
    if len(set(desc))!=1:raise ValueError('prototype requires homogeneous resource words')
    aa,b,_=desc[0]
    h=max(1,1+math.ceil(b/aa)) if lookahead is None else lookahead
    groups=[]
    for jobs in component_assignment(a,k,'lpt'):
        vs=[u for j in jobs for u in cs[j]];ss={u:set(a['succ'][u]) for u in vs};pp={u:set(a['pred'][u]) for u in vs}
        first=[cs[j][0] for j in jobs];last=[cs[j][-1] for j in jobs];M=first[:h]
        for i,u in enumerate(last):
            M.append(u)
            if i+h<len(first):M.append(first[i+h])
        V=[u for j in jobs for u in cs[j][1:-1]]
        for word in [M,V]:
            for u,v in zip(word,word[1:]):ss[u].add(v);pp[v].add(u)
        deg={u:len(pp[u]) for u in vs};q=[u for u in vs if not deg[u]];heapq.heapify(q);earliest={u:0 for u in vs};top=[]
        while q:
            u=heapq.heappop(q);top.append(u)
            for v in ss[u]:
                earliest[v]=max(earliest[v],earliest[u]+max(1,e[u]['cycles']));deg[v]-=1
                if not deg[v]:heapq.heappush(q,v)
        if len(top)!=len(vs):raise RuntimeError('resource-word precedence cycle')
        groups.append([[u] for u in sorted(vs,key=lambda u:(earliest[u],u))])
    return plan_from_groups(groups,k),{'a':aa,'b':b,'lookahead':h,'jobs':len(cs),'ideal_model_only':'fixed durations, no copies, no memory gate; source-derived priority, not submitted times'}
