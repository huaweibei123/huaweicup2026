"""P1-only task coarsening at cover relations of the augmented task poset.
Fixed operation/core ownership; legal contraction iff the adjacent core-order
edge has no alternate directed path. Does NOT claim makespan monotonicity.
"""
from __future__ import annotations
import collections,heapq,time

def fuse_cover(graph,plan,max_ops=32,protect_exports=False):
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    view=derive_multicore_plan(graph,plan)
    mapping=dict(view['mapping']);groups={b:set(v) for b,v in view['nodes_by_subgraph'].items()}
    orders=[list(x) for x in plan['core_schedules']]
    owner={b:k for k,o in enumerate(orders) for b in o};edges=set(view['dependency_pairs'])
    for o in orders:edges.update(zip(o,o[1:]))
    succ={b:set() for b in groups};pred={b:set() for b in groups}
    for a,b in edges:succ[a].add(b);pred[b].add(a)
    accepted=[];checks=0;blocked=0;st=time.perf_counter()
    def topology():
        deg={b:len(pred[b]) for b in groups};h=[b for b in groups if deg[b]==0];heapq.heapify(h);top=[]
        while h:
            b=heapq.heappop(h);top.append(b)
            for u in sorted(succ[b]):
                deg[u]-=1
                if not deg[u]:heapq.heappush(h,u)
        if len(top)!=len(groups):raise ValueError('augmented input task graph has cycle')
        return {v:i for i,v in enumerate(top)}
    changed=True
    while changed:
        changed=False;rank=topology()
        for k,o in enumerate(orders):
            j=0
            while j+1<len(o):
                a,b=o[j:j+2]
                if len(groups[a])+len(groups[b])>max_ops:j+=1;continue
                if protect_exports and any(owner[v]!=k for v in succ[a]):j+=1;continue
                checks+=1;seen=set();todo=[v for v in succ[a] if v!=b and rank[v]<=rank[b]];alternate=False
                while todo:
                    v=todo.pop()
                    if v==b:alternate=True;break
                    if v in seen:continue
                    seen.add(v);todo.extend(u for u in succ[v] if u not in seen and rank[u]<=rank[b])
                if alternate:blocked+=1;j+=1;continue
                # Contract b into a; this changes Task gates but not original ops or cores.
                for u in list(pred[b]):succ[u].discard(b)
                for v in list(succ[b]):pred[v].discard(b)
                newpred=(pred[a]|pred[b])-{a,b};newsucc=(succ[a]|succ[b])-{a,b}
                for u in newpred:succ[u].add(a)
                for v in newsucc:pred[v].add(a)
                pred[a]=newpred;succ[a]=newsucc;pred.pop(b);succ.pop(b)
                groups[a].update(groups.pop(b));owner.pop(b)
                o.pop(j+1);accepted.append([a,b]);changed=True
                # Recompute ranks: no unproved incremental locality assumption.
                rank=topology()
            # each successful merge reduces the number of blocks
    for b,ns in groups.items():
        for v in ns:mapping[v]=b
    result={'node_to_subgraph':{str(v):mapping[v] for v in sorted(mapping)},'core_schedules':orders}
    derive_multicore_plan(graph,result)
    return result,{'max_ops':max_ops,'protect_exports':protect_exports,'cover_checks':checks,'alternate_paths_blocked':blocked,'merges':accepted,'packets_after':len(groups),'fusion_seconds':time.perf_counter()-st}
