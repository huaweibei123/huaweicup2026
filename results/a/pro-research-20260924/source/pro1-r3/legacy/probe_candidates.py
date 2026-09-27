"""Exploratory candidate builders, NOT a final competition solver."""
import collections,heapq,math
from scan_cases import views,components
from probe_runner import component_pack

def strongly_connected(nodes,succ):
    pred={i:set() for i in nodes}
    for i in nodes:
        for j in succ[i]:pred[j].add(i)
    seen=set();order=[]
    for root in nodes:
        if root in seen:continue
        seen.add(root);stack=[(root,iter(succ[root]))]
        while stack:
            i,it=stack[-1];j=next(it,None)
            if j is None:order.append(i);stack.pop()
            elif j not in seen:seen.add(j);stack.append((j,iter(succ[j])))
    seen=set();result=[]
    for root in reversed(order):
        if root in seen:continue
        seen.add(root);stack=[root];group=[]
        while stack:
            i=stack.pop();group.append(i)
            for j in pred[i]:
                if j not in seen:seen.add(j);stack.append(j)
        result.append(group)
    return result

def topo_order(nodes,preds,succs,work):
    q=collections.deque(i for i in sorted(nodes) if not preds[i]);degree={i:len(preds[i]) for i in nodes};top=[]
    while q:
        i=q.popleft();top.append(i)
        for j in sorted(succs[i]):
            degree[j]-=1
            if degree[j]==0:q.append(j)
    if len(top)!=len(nodes):raise ValueError('cycle')
    b={}
    for i in reversed(top):b[i]=work[i]+max((b[j] for j in succs[i]),default=0)
    degree={i:len(preds[i]) for i in nodes};q=[(-b[i],i) for i in nodes if not degree[i]];heapq.heapify(q);top=[]
    while q:
        _,i=heapq.heappop(q);top.append(i)
        for j in sorted(succs[i]):
            degree[j]-=1
            if degree[j]==0:heapq.heappush(q,(-b[j],j))
    return top

def make_candidate(g,n,mode,problem):
    ops,ts,prod,cons,eligible,preds,succs,ets=views(g)
    if mode=='component_unit':
        cp=component_pack(g,n,'sum');core={int(i):c for i,c in cp['node_to_subgraph'].items()}
        top=topo_order(eligible,preds,succs,{i:ops[i]['cycles'] for i in eligible})
        mapping={str(i):k for k,i in enumerate(top)};schedules=[[] for _ in range(n)]
        for k,i in enumerate(top):schedules[core[i]].append(k)
        return {'node_to_subgraph':mapping,'core_schedules':schedules}
    if mode.startswith('cut'):
        threshold=int(mode[3:]);groups=components(eligible,[(a,b) for (a,b),tids in ets.items() if sum(ts[t]['size'] for t in tids)>threshold])
    elif mode=='unit':groups=[[i] for i in sorted(eligible)]
    else:raise ValueError(mode)
    bid={i:k for k,group in enumerate(groups) for i in group}
    bs={k:set() for k in range(len(groups))}
    for a,b in ets:
        if bid[a]!=bid[b]:bs[bid[a]].add(bid[b])
    scc=strongly_connected(list(bs),bs)
    groups=[sorted(i for b in sc for i in groups[b]) for sc in scc]
    bid={i:k for k,group in enumerate(groups) for i in group}
    bs={k:set() for k in range(len(groups))};bp={k:set() for k in bs};edgebytes=collections.defaultdict(int)
    for (a,b),tids in ets.items():
        x,y=bid[a],bid[b]
        if x!=y:bs[x].add(y);bp[y].add(x);edgebytes[x,y]+=sum(ts[t]['size'] for t in tids)
    weights={k:sum(ops[i]['cycles'] for i in grp) for k,grp in enumerate(groups)}
    # Conservative scalar compute cost deliberately omits overlap; a probe baseline.
    top=topo_order(bs,bp,bs,weights);cfinish=[0.0]*n;assignment={};finish={};schedules=[[] for _ in range(n)]
    core_inputs=[set() for _ in range(n)]
    input_by_block={k:set() for k in bs}
    for t in ts:
        if not any(i in eligible for i in prod[t]):
            for i in cons[t]:
                if i in eligible:input_by_block[bid[i]].add(t)
    delay=1000 if problem==1 else 500
    for b in top:
        cand=[]
        for c in range(n):
            arrival=max((finish[a]+(delay+2*edgebytes[a,b]/60 if assignment[a]!=c else 0) for a in bp[b]),default=0)
            avail=cfinish[c]+(100 if problem==1 and schedules[c] else 0)
            newread=sum(ts[t]['size'] for t in input_by_block[b] if problem==1 or t not in core_inputs[c])/60
            end=max(avail,arrival)+weights[b]+newread
            cand.append((end,cfinish[c],c))
        end,_,c=min(cand);assignment[b]=c;finish[b]=end;cfinish[c]=end;schedules[c].append(b);core_inputs[c].update(input_by_block[b])
    return {'node_to_subgraph':{str(i):bid[i] for i in sorted(eligible)},'core_schedules':schedules}
