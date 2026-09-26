"""Independent reconstruction of the homogeneous reentrant-word baseline described
in the supplied Pro2 report. Not Pro2's unavailable original implementation.
"""
import heapq,math

def homogeneous_word(g,owner,groups,k):
    pos={o:i for i,o in enumerate(g.topo)};jobs=[];ab=[]
    for group in groups:
        phases=[]
        for o in sorted(group,key=pos.get):
            p=g.ops[o]['pipe']
            if not phases or phases[-1][0]!=p:phases.append([p,[]])
            phases[-1][1].append(o)
        if [x[0] for x in phases]!=['PIPE_M','PIPE_V','PIPE_M']:raise ValueError('unsupported non M-V-M component')
        dur=[sum(g.duration(o) for o in phase[1]) for phase in phases]
        if dur[0]!=dur[2]:raise ValueError('asymmetric end stages')
        ab.append(tuple(dur[:2]));jobs.append([x[1] for x in phases])
    if len(set(ab))!=1:raise ValueError('heterogeneous word baseline unsupported')
    a,b=ab[0];h=1+math.ceil(b/a);succ={o:set(g.succ[o]) for o in g.ids}
    for core in range(k):
        jj=[i for i,x in enumerate(jobs) if owner[x[0][0]]==core];m=[];v=[]
        for idx in jj[:h]:m+=jobs[idx][0]
        for j,idx in enumerate(jj):
            m+=jobs[idx][2]
            if j+h<len(jj):m+=jobs[jj[j+h]][0]
            v+=jobs[idx][1]
        for word in [m,v]:
            for u,w in zip(word,word[1:]):succ[u].add(w)
    deg={o:0 for o in g.ids}
    for ss in succ.values():
        for v in ss:deg[v]+=1
    heap=[o for o in g.ids if deg[o]==0];heapq.heapify(heap);order=[]
    while heap:
        o=heapq.heappop(heap);order.append(o)
        for v in sorted(succ[o]):
            deg[v]-=1
            if deg[v]==0:heapq.heappush(heap,v)
    if len(order)!=len(g.ids):raise ValueError('word augmented graph cycle')
    return order,{'word_a':a,'word_b':b,'lookahead_jobs':h}
