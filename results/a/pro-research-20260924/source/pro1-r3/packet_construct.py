"""Structural packet constructors. Heuristic for E0; no evaluation modification.
A max-plus packet profile is exact ONLY for the prescribed compute-only FIFO
and a common external release, not an NPU makespan or memory certificate.
"""
from __future__ import annotations
import collections, heapq, math, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'legacy'))
from scan_cases import views, components
from probe_candidates import strongly_connected, topo_order
from structure_checks import cutsolve
NEG = -10**30

def mat_apply(a,x):
    return [max((w+x[j] for j,w in enumerate(row) if w!=NEG),default=NEG) for row in a]

def packet_profile(nodes,ops,preds,succs):
    """Rows: M clock, V clock, completion; cols: old M, old V, input release.
    Old clocks for an unused pipe remain unchanged. Completion excludes unrelated
    old work on an unused pipe. int64-like bounded Python integers here.
    """
    ns=set(nodes);pp={v:preds[v]&ns for v in ns};ss={v:succs[v]&ns for v in ns}
    order=topo_order(ns,pp,ss,{v:max(1,ops[v]['cycles']) for v in ns})
    resource=[[0,NEG,NEG],[NEG,0,NEG]];end={};out=[NEG]*3
    for v in order:
        if ops[v]['pipe'] not in ('PIPE_M','PIPE_V'):raise ValueError('compute-only profile requires M/V')
        k=0 if ops[v]['pipe']=='PIPE_M' else 1
        sources=[resource[k],[NEG,NEG,0]]+[end[u] for u in pp[v]]
        val=[max(a[j] for a in sources)+max(1,ops[v]['cycles']) for j in range(3)]
        # Preserve -infinity exactly, even after adding a duration.
        val=[NEG if max(a[j] for a in sources)==NEG else val[j] for j in range(3)]
        end[v]=val;resource[k]=val;out=[max(out[j],val[j]) for j in range(3)]
    return resource+[out],order

def legalize_groups(groups,succs):
    bid={v:b for b,ns in enumerate(groups) for v in ns};ss={b:set() for b in range(len(groups))}
    for v in bid:
        for u in succs[v]:
            if bid[v]!=bid[u]:ss[bid[v]].add(bid[u])
    scc=strongly_connected(list(ss),ss)
    return sorted([sorted(v for b in cc for v in groups[b]) for cc in scc],key=min)

def initial_groups(g,kind):
    ops,ts,prod,cons,el,pr,su,ets=views(g)
    if kind=='unit':groups=[[v] for v in sorted(el)]
    elif kind in ('chain','nr','phase'):
        edges=[(u,v) for u in el for v in su[u] if len(su[u])==1 and len(pr[v])==1]
        groups=components(sorted(el),edges)
        if kind in ('nr','phase'):
            refined=[]
            for cl in groups:
                ns=set(cl);local=topo_order(ns,{v:pr[v]&ns for v in ns},{v:su[v]&ns for v in ns},{v:max(1,ops[v]['cycles']) for v in ns})
                piece=[];seen=set();previous=None
                for v in local:
                    pipe=ops[v]['pipe']
                    if piece and pipe!=previous and (kind=='phase' or pipe in seen):
                        refined.append(piece);piece=[];seen=set()
                    piece.append(v);seen.add(pipe);previous=pipe
                if piece:refined.append(piece)
            groups=refined
    elif kind.startswith('cut'):
        th=int(kind[3:]);groups=components(sorted(el),[(u,v) for (u,v),tt in ets.items() if sum(ts[t]['size'] for t in tt)>th])
    elif kind=='component':groups=components(sorted(el),ets)
    else:raise ValueError(kind)
    return legalize_groups(groups,su)

def ideal_split(nodes,ops,ts,prod,cons,preds,succs,query_limit=10):
    """Anchored ideal-cut price search for approximate half-work. Uses ordinary
    repeated maxflow, NOT the fast parametric algorithm; missed balances allowed.
    Returned split chosen by work balance then cut bytes among evaluated cuts.
    """
    vs=sorted(nodes);ns=set(vs);idx={v:i for i,v in enumerate(vs)}
    edges=[(idx[u],idx[v]) for u in vs for v in succs[u] if v in ns]
    pp={v:preds[v]&ns for v in vs};ss={v:succs[v]&ns for v in vs}
    w={v:max(1,ops[v]['cycles']) for v in vs};top=topo_order(ns,pp,ss,w)
    tail={}
    for v in reversed(top):tail[v]=w[v]+max((tail[u] for u in ss[v]),default=0)
    first=top[0]
    # A descendant sink anchor on a longest continuation; incompatible closure is avoided.
    last=first
    while ss[last]:last=max(ss[last],key=lambda u:(tail[u],-u))
    if first==last and len(vs)>1:last=next(v for v in reversed(top) if v!=first)
    nets=[]
    for t in ts:
        pins=sorted({idx[v] for v in prod[t]+cons[t] if v in ns})
        if len(pins)>1:nets.append((tuple(pins),max(1,math.ceil(2*ts[t]['size']/60))*32))
    mw=max(tail.values());weights=[w[v] for v in vs];total=sum(weights)
    d=[-round(32*tail[v]/mw)*w[v] for v in vs]
    # Deterministic bounded price bisection; fixed anchors imposed by dominating unary.
    cuts={};lo=-2;hi=34;queries=0
    for _ in range(query_limit):
        lam=(lo+hi)/2
        unary=[round(d[i]+lam*weights[i]) for i in range(len(vs))]
        big=1+sum(abs(x) for x in unary)+sum(c for _,c in nets)
        unary[idx[first]]-=big;unary[idx[last]]+=big
        oldlim=sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(max(oldlim,4*(len(vs)+2*len(nets)+2)))
            _,S=cutsolve(len(vs),edges,nets,unary)
        finally:sys.setrecursionlimit(oldlim)
        queries+=1
        if not S or len(S)==len(vs):break
        assert idx[first] in S and idx[last] not in S
        mass=sum(weights[i] for i in S)
        crossing=sum(c for pin,c in nets if any(i in S for i in pin) and any(i not in S for i in pin))
        cuts[S]=(abs(mass-total/2),crossing)
        if mass>total/2:lo=lam
        else:hi=lam
    if not cuts:return None,queries
    S=min(cuts,key=lambda a:(cuts[a],tuple(sorted(a))))
    return ([vs[i] for i in sorted(S)],[v for i,v in enumerate(vs) if i not in S]),queries

def make_packets(g,kind,n,ideal_query_limit=8):
    groups=initial_groups(g,'component' if kind=='ideal' else kind);diag={'ideal_flow_calls':0}
    if kind=='ideal':
        ops,ts,prod,cons,el,pr,su,ets=views(g);target=sum(max(1,ops[v]['cycles']) for v in el)/(2*n)
        result=[];queue=list(groups)
        while queue:
            block=queue.pop(0)
            if len(block)>2 and sum(max(1,ops[v]['cycles']) for v in block)>target and len(result)+len(queue)<4*n:
                split,k=ideal_split(block,ops,ts,prod,cons,pr,su,ideal_query_limit);diag['ideal_flow_calls']+=k
                if split and min(map(len,split))>0:queue=list(split)+queue;continue
            result.append(block)
        groups=legalize_groups(result,su)
    diag['packets']=len(groups);diag['packet_sizes']=sorted(map(len,groups),reverse=True)
    return groups,diag

def construct(g,n,kind='chain',response=True,merge_core=False,fixed_assignment=None):
    if kind.startswith('window'):
        from window_refine import construct_window
        return construct_window(g,n,int(kind[6:]))
    st=time.perf_counter();ops,ts,prod,cons,el,pr,su,ets=views(g)
    from stub_multicore_cut_and_schedule import _build_op_adjacency,_contract_excluded_copy_nodes
    _,full=_build_op_adjacency(g)
    cp,cs=_contract_excluded_copy_nodes(sorted(el),full)
    if any(cs[v]!=su[v] for v in el):
        raise NotImplementedError('internal excluded COPY bridge: packet cost model unsupported')
    base_diag=None
    if kind in ('refine','phasefix'):
        base,base_diag=construct(g,n,'chain',True)
        sgcore={sg:k for k,order in enumerate(base['core_schedules']) for sg in order}
        fixed_assignment={int(v):sgcore[b] for v,b in base['node_to_subgraph'].items()}
        kind='phase' if kind=='phasefix' else 'nr'
    groups,diag=make_packets(g,kind,n);bid={v:b for b,ns in enumerate(groups) for v in ns}
    bs={b:set() for b in range(len(groups))};bp={b:set() for b in bs}
    for u in el:
        for v in su[u]:
            a,b=bid[u],bid[v]
            if a!=b:bs[a].add(b);bp[b].add(a)
    profiles={};intern={};work={};inputs={b:set() for b in bs};outputs={b:set() for b in bs};tp={}
    for b,ns in enumerate(groups):
        matrix,_=packet_profile(ns,ops,pr,su)
        key=tuple(tuple(row) for row in matrix)
        profiles[b]=intern.setdefault(key,matrix)
        work[b]=mat_apply(profiles[b],[0,0,0])[2] if response else sum(max(1,ops[v]['cycles']) for v in ns)
    for t in ts:
        producers={bid[v] for v in prod[t] if v in el};tp[t]=producers
        for b in producers:outputs[b].add(t)
        for v in cons[t]:
            if v in el and bid[v] not in producers:inputs[bid[v]].add(t)
    order=topo_order(bs,bp,bs,work)
    clocks=[[0,0] for _ in range(n)];read_clock=[0]*n;resident=[set() for _ in range(n)]
    assignment={};finish={};core_orders=[[] for _ in range(n)]
    for b in order:
        candidates=[]
        for k in range(n):
            if fixed_assignment is not None and k!=fixed_assignment[groups[b][0]]:continue
            if fixed_assignment is not None and any(fixed_assignment[v]!=k for v in groups[b]):raise ValueError('packet crosses fixed ownership')
            release=0;read=0
            for a in bp[b]:release=max(release,finish[a]+(500 if assignment[a]!=k else 0))
            for t in inputs[b]:
                owners={assignment[a] for a in tp[t]}
                local=k in owners
                if not local and t not in resident[k]:
                    read+=max(1,math.ceil(ts[t]['size']/60))
                    if owners:
                        release=max(release,max(finish[a] for a in tp[t])+500+max(1,math.ceil(ts[t]['size']/60)))
            r=max(read_clock[k],release)+read if read else release
            clocks_new=mat_apply(profiles[b],clocks[k]+[r]) if response else [max(max(clocks[k]),r)+work[b]]*3
            end=clocks_new[2]
            candidates.append(((end,max(clocks[k]),sum(clocks[k]),k),k,clocks_new, r if read else read_clock[k]))
        _,k,new,rc=min(candidates)
        assignment[b]=k;finish[b]=new[2];clocks[k]=new[:2];read_clock[k]=rc;core_orders[k].append(b)
        resident[k].update(inputs[b]);resident[k].update(outputs[b])
    # Preserve global topological packet order. Numeric SG ID is not a machine ID.
    plan={'node_to_subgraph':{str(v):bid[v] for v in sorted(el)},'core_schedules':core_orders}
    if merge_core:
        # Not generally legal: only retained as explicit ablation when caller validates.
        plan={'node_to_subgraph':{str(v):assignment[bid[v]] for v in sorted(el)},'core_schedules':[[k] if core_orders[k] else [] for k in range(n)]}
    diag.update({'fixed_assignment':fixed_assignment is not None,'base_construction':base_diag,'unique_compute_profiles':len(intern),'mode':kind,'response':response,'construction_seconds':time.perf_counter()-st,'surrogate_finish':max(finish.values(),default=0),
                 'surrogate_is_not_e0_or_bound':True,'core_compute_clocks':clocks,'global_packet_order':order})
    return plan,diag
