#!/usr/bin/env python3
"""Bounded integer checks for *mathematical subroutines*, not an NPU solver.
No official code or input modification. Standard library only.
"""
from __future__ import annotations
import collections,itertools,json,pathlib,random,time
class Dinic:
    def __init__(self,n): self.g=[[] for _ in range(n)]
    def add(self,u,v,c):
        assert c>=0
        self.g[u].append([v,c,len(self.g[v])]); self.g[v].append([u,0,len(self.g[u])-1])
    def solve(self,s,t):
        total=0
        while True:
            level=[-1]*len(self.g);level[s]=0;q=collections.deque([s])
            while q:
                u=q.popleft()
                for v,c,_ in self.g[u]:
                    if c>0 and level[v]<0:level[v]=level[u]+1;q.append(v)
            if level[t]<0:break
            it=[0]*len(self.g)
            def dfs(u,f):
                if u==t:return f
                while it[u]<len(self.g[u]):
                    e=self.g[u][it[u]];v,c,ri=e
                    if c>0 and level[v]==level[u]+1:
                        d=dfs(v,min(c,f))
                        if d:e[1]-=d;self.g[v][ri][1]+=d;return d
                    it[u]+=1
                return 0
            while (f:=dfs(s,10**30)):total+=f
        reach={s};q=[s]
        for u in q:
            for v,c,_ in self.g[u]:
                if c>0 and v not in reach:reach.add(v);q.append(v)
        return total,reach

def cutsolve(n,edges,nets,unary):
    s=n+2*len(nets);t=s+1;d=Dinic(t+1)
    big=1+sum(abs(x) for x in unary)+sum(c for e,c in nets)
    for u,v in edges:d.add(v,u,big)  # down-set constraint: v selected => u selected
    for j,(vertices,c) in enumerate(nets):
        a=n+2*j;b=a+1;d.add(a,b,c)
        for v in vertices:d.add(v,a,big);d.add(b,v,big)
    for v,c in enumerate(unary):
        if c>=0:d.add(v,t,c)
        else:d.add(s,v,-c)
    flow,reach=d.solve(s,t)
    return flow+sum(c for c in unary if c<0),frozenset(v for v in range(n) if v in reach)

def objective(S,nets,u):return sum(u[v] for v in S)+sum(c for net,c in nets if any(v in S for v in net) and any(v not in S for v in net))
def run_cut(seed=20260923,trials=240):
    rng=random.Random(seed);checks=0;breakpoints=[]
    for k in range(trials):
        n=rng.randrange(2,9);edges=[(u,v) for u in range(n) for v in range(u+1,n) if rng.random()<.22]
        nets=[(tuple(sorted(rng.sample(range(n),rng.randint(2,n)))),rng.randint(0,12)) for _ in range(rng.randint(1,n))]
        u=[rng.randint(-12,12) for _ in range(n)];w=[rng.randint(1,4) for _ in range(n)]
        ideals=[frozenset(v for v in range(n) if mask>>v&1) for mask in range(1<<n) if all(not(mask>>v&1) or mask>>a&1 for a,v in edges)]
        prior=None;distinct=set()
        for lam in [-6,-3,0,3,6]:
            costs=[u[i]+lam*w[i] for i in range(n)]
            val,S=cutsolve(n,edges,nets,costs); brute=min(objective(I,nets,costs) for I in ideals)
            assert val==brute and S in ideals and objective(S,nets,costs)==brute,(k,lam,val,brute)
            if prior is not None:assert S.issubset(prior),(k,lam,prior,S)
            prior=S;distinct.add(S);checks+=1
        breakpoints.append(len(distinct))
    return {'domain':'exact integer ideal-constrained all-or-nothing hypergraph-cut surrogate, not official Makespan','random_graphs':trials,'max_vertices':8,'price_settings_per_graph':5,'checks_against_exhaustive_ideal_search':checks,'failures':0,'nested_minimal_source_sides_all_passed':True,'seed':seed}

def eliminate(n,arcs,keep):
    succ=[{} for _ in range(n)];pred=[{} for _ in range(n)]
    for u,v,w in arcs:
        if w>succ[u].get(v,-10**30):succ[u][v]=w;pred[v][u]=w
    maxedges=len(arcs)
    for x in range(n):
        if x in keep:continue
        for u,a in list(pred[x].items()):
            for v,b in list(succ[x].items()):
                if a+b>succ[u].get(v,-10**30):succ[u][v]=a+b;pred[v][u]=a+b
        for u in list(pred[x]):succ[u].pop(x,None)
        for v in list(succ[x]):pred[v].pop(x,None)
        succ[x].clear();pred[x].clear()
        maxedges=max(maxedges,sum(map(len,succ)))
    return [(u,v,w) for u in keep for v,w in succ[u].items()],maxedges

def evaldag(n,arcs,b):
    vals=[b.get(v,-10**30) for v in range(n)];ss=[[] for _ in range(n)]
    for u,v,w in arcs:ss[u].append((v,w))
    for u in range(n):
        if vals[u]<-10**25:continue
        for v,w in ss[u]:vals[v]=max(vals[v],vals[u]+w)
    return vals

def run_maxplus(seed=114514,trials=300):
    rng=random.Random(seed);checks=0;growth=[]
    for k in range(trials):
        n=rng.randint(4,35);arcs=[(0,v,0) for v in range(1,n)]
        arcs += [(u,v,rng.randint(0,100)) for u in range(1,n) for v in range(u+1,n) if rng.random()<.14]
        keep={0,n-1}|{v for v in range(1,n-1) if rng.random()<.20}
        reduced,mx=eliminate(n,arcs,keep);growth.append((len(arcs),len(reduced),mx))
        for z in range(8):
            b={v:rng.randint(0,200) for v in keep};f=evaldag(n,arcs,b);r=evaldag(n,reduced,b)
            assert all(f[v]==r[v] for v in keep),(k,b,f,r)
            checks+=1
    return {'domain':'acyclic fixed integer-lag graph response at retained ports; no dynamic bandwidth or official binary64 equivalence claimed','random_graphs':trials,'max_vertices':35,'release_vectors_per_graph':8,'boundary_response_comparisons':checks,'failures':0,'seed':seed}

if __name__=='__main__':
    start=time.perf_counter();out={'ideal_hypercut':run_cut(),'maxplus_elimination':run_maxplus(),'elapsed_seconds':time.perf_counter()-start}
    p=pathlib.Path(__file__).parent/'structure_checks.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
