"""Heavy-tensor must-link contraction, least acyclic SCC closure, list construction.
Only SCC closure is exact. Thresholds and completion estimates are construction heuristics.
"""
from collections import defaultdict
import heapq

def scc(adj):
    n=len(adj);vis=set();finish=[]
    for r in range(n):
        if r in vis:continue
        vis.add(r);stack=[(r,iter(adj[r]))]
        while stack:
            u,it=stack[-1]
            try:v=next(it)
            except StopIteration:finish.append(u);stack.pop();continue
            if v not in vis:vis.add(v);stack.append((v,iter(adj[v])))
    rev=[[] for _ in range(n)]
    for u,vs in enumerate(adj):
        for v in vs:rev[v].append(u)
    comps=[];seen=set()
    for r in reversed(finish):
        if r in seen:continue
        todo=[r];seen.add(r);c=[]
        while todo:
            u=todo.pop();c.append(u)
            for v in rev[u]:
                if v not in seen:seen.add(v);todo.append(v)
        comps.append(sorted(c))
    return comps

def heavy_blocks(a,tau):
    vs=a['top'];e=a['eligible'];par={u:u for u in vs}
    def find(u):
        while par[u]!=u:par[u]=par[par[u]];u=par[u]
        return u
    for t,ts in a['ts'].items():
        if ts['size']<=tau:continue
        prods=[u for u in a['prod'][t] if u in e];cs=[u for u in a['cons'][t] if u in e]
        if not prods or not cs:continue
        allv=prods+cs;r=find(allv[0])
        for u in allv[1:]:par[find(u)]=r
    initial=defaultdict(list)
    for u in vs:initial[find(u)].append(u)
    initial=list(initial.values());bid={u:j for j,c in enumerate(initial) for u in c};adj=[set() for _ in initial]
    for u in vs:
        for v in a['succ'][u]:
            if bid[u]!=bid[v]:adj[bid[u]].add(bid[v])
    closure=scc(adj);blocks=[[u for j in c for u in initial[j]] for c in closure]
    pos={u:i for i,u in enumerate(vs)};blocks=[sorted(c,key=pos.get) for c in blocks]
    blocks.sort(key=lambda c:pos[c[0]])
    return blocks,{'initial_blocks':len(initial),'scc_merges':sum(len(c)-1 for c in closure)}

def heavy_plan(a,k,tau=64,problem=2,order_mode='critical'):
    blocks,info=heavy_blocks(a,tau);bid={u:j for j,c in enumerate(blocks) for u in c};n=len(blocks)
    pred=[set() for _ in blocks];succ=[set() for _ in blocks];bw=defaultdict(int)
    for u in a['top']:
        for v in a['succ'][u]:
            x,y=bid[u],bid[v]
            if x!=y:pred[y].add(x);succ[x].add(y)
    for t,ts in a['ts'].items():
        ps={bid[u] for u in a['prod'][t] if u in bid};qs={bid[u] for u in a['cons'][t] if u in bid}
        for x in ps:
            for y in qs:
                if x!=y:bw[x,y]+=ts['size']
    # explicit time proxy: per block bottleneck compute work, not E0 prediction/certificate
    pipes=('PIPE_M','PIPE_V','PIPE_MTE2','PIPE_MTE3');e=a['eligible']
    work=[max(sum(max(1,e[u]['cycles']) for u in c if e[u]['pipe']==p) for p in pipes) for c in blocks]
    deg=list(map(len,pred));hq=[i for i,d in enumerate(deg) if d==0];heapq.heapify(hq);top=[]
    while hq:
        u=heapq.heappop(hq);top.append(u)
        for v in succ[u]:
            deg[v]-=1
            if deg[v]==0:heapq.heappush(hq,v)
    if len(top)!=n:raise RuntimeError('SCC closure invariant violated')
    rank=[0.]*n
    for u in reversed(top):rank[u]=work[u]+max((rank[v] for v in succ[u]),default=0)
    avail=[0.]*k;finish={};which={};orders=[[] for _ in range(k)];deg=list(map(len,pred));hq=[]
    for i,d in enumerate(deg):
        if not d:heapq.heappush(hq,(-rank[i] if order_mode=='critical' else i,i))
    dispatch=[]
    while hq:
        _,u=heapq.heappop(hq);dispatch.append(u)
        def estimate(c):
            rel=max((finish[p]+(1000 if problem==1 else 500)+2*bw[p,u]/60 if which[p]!=c else finish[p] for p in pred[u]),default=0)
            return max(avail[c]+(100 if problem==1 and orders[c] else 0),rel)+work[u]
        c=min(range(k),key=lambda c:(estimate(c),avail[c],c));finish[u]=estimate(c);which[u]=c;avail[c]=finish[u];orders[c].append(u)
        for v in succ[u]:
            deg[v]-=1
            if not deg[v]:heapq.heappush(hq,(-rank[v] if order_mode=='critical' else v,v))
    # sg labels are canonical dispatch ranks; core schedules are subsequences of that order.
    sg={u:i for i,u in enumerate(dispatch)}
    plan={'node_to_subgraph':{str(v):sg[j] for j,b in enumerate(blocks) for v in b},'core_schedules':[[sg[j] for j in o] for o in orders]}
    return plan
