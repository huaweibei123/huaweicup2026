"""CPU constructive scheduling. Virtual compute clocks select priorities, NOT E0 predictions.
No original graph, official code or configuration is modified.
"""
from __future__ import annotations
import argparse, json, heapq, time, math
from pathlib import Path
from collections import defaultdict, Counter
from graph_features import Graph
CAP={'L1':524288,'UB':131072}

def placement(g:Graph,k:int,kind:str):
    if kind=='component':
        topopos={o:i for i,o in enumerate(g.topo)}
        groups=[sorted(c,key=topopos.get) for c in g.components]
        order=sorted(range(len(groups)),key=lambda i:(-sum(g.duration(o) for o in groups[i]),groups[i][0]))
    elif kind=='topo64':
        groups=[g.topo[i:i+64] for i in range(0,len(g.topo),64)]
        order=list(range(len(groups)))
    elif kind=='chain':
        # Disjoint unbranched paths; placement units, not necessarily final subgraphs.
        root={o:o for o in g.ids}
        def find(o):
            while root[o]!=o: root[o]=root[root[o]];o=root[o]
            return o
        for u in g.topo:
            if len(g.succ[u])==1:
                v=next(iter(g.succ[u]))
                if len(g.pred[v])==1: root[find(v)]=find(u)
        d=defaultdict(list)
        for o in g.topo:d[find(o)].append(o)
        groups=list(d.values());oi={o:i for i,c in enumerate(groups) for o in c}
        seen=set();order=[]
        for o in g.toposort(lambda o:(-g.bottom[o],o)):
            i=oi[o]
            if i not in seen:seen.add(i);order.append(i)
    else: raise ValueError(kind)
    owner={}; clocks=[defaultdict(float) for _ in range(k)]; finish={}
    group_owner={}
    for i in order:
        group=groups[i]; trials=[]
        for c in range(k):
            clock=dict(clocks[c]);local={};copy_cost=0
            for o in group:
                r=0
                for p in g.pred[o]:
                    f=local.get(p,finish.get(p,0))
                    if p in owner and owner[p]!=c:
                        bs=sum(g.ts[t]['size'] for t in g.inputs[o] if p in g.prod[t])
                        f+=500+2*math.ceil(bs/60); copy_cost+=bs
                    r=max(r,f)
                pipe=g.ops[o]['pipe'];f=max(clock.get(pipe,0),r)+g.duration(o)
                clock[pipe]=f;local[o]=f
            trials.append((max(clock.values(),default=0),copy_cost,c,clock,local))
        _,_,c,clock,local=min(trials,key=lambda x:x[:3])
        clocks[c].update(clock);finish.update(local)
        for o in group:owner[o]=c
        group_owner[i]=c
    return owner,groups,group_owner

class Frontier:
    """Exact compute-bucket live footprint; certificate limited to the documented domain."""
    def __init__(self,g,owner,k,capacity):
        self.g=g;self.owner=owner;self.cap=capacity
        self.touch={o:sorted(g.inputs[o]|g.outputs[o]) for o in g.ids}
        self.remaining=[Counter() for _ in range(k)]
        for o in g.ids:self.remaining[owner[o]].update(self.touch[o])
        self.live=[set() for _ in range(k)];self.mem=[Counter() for _ in range(k)]
        self.peak=[Counter() for _ in range(k)];self.forced=0
        self.cert_domain=all(t['pos']!='DDR' for o in g.ids for tid in self.touch[o] for t in [g.ts[tid]])
        # No excluded-copy bridge between eligible operations.
        for o in g.ids:
            direct=set().union(*(g.cons[t]&g.eligible for t in g.outputs[o])) if g.outputs[o] else set()
            if direct!=g.succ[o]:self.cert_domain=False
    def preview(self,o,gamma=1.0):
        c=self.owner[o];m=self.mem[c].copy();release=Counter();io=Counter()
        for t in self.touch[o]:
            pos=self.g.ts[t]['pos'];size=self.g.ts[t]['size']
            if pos=='DDR':pos='UB'
            io[pos]+=size
            if t not in self.live[c]:m[pos]+=size
            if self.remaining[c][t]==1:release[pos]+=size
        overflow=max([max(0,m[p]-max(gamma*self.cap[p],io[p]))/self.cap[p] for p in self.cap])
        pressure=max([m[p]/self.cap[p] for p in self.cap])
        net=sum((m[p]-self.mem[c][p]-release[p])/self.cap[p] for p in self.cap)
        return overflow,pressure,net,m
    def commit(self,o):
        c=self.owner[o];m=self.preview(o)[3]
        for p in self.cap:self.peak[c][p]=max(self.peak[c][p],m[p])
        for t in self.touch[o]:
            p=self.g.ts[t]['pos'];p='UB' if p=='DDR' else p;s=self.g.ts[t]['size']
            if t not in self.live[c]:self.live[c].add(t);self.mem[c][p]+=s
            self.remaining[c][t]-=1
            if self.remaining[c][t]==0:
                self.live[c].remove(t);self.mem[c][p]-=s
    def certificate(self):
        return {'domain_supported':self.cert_domain,'bucket_peak_by_core':[dict(x) for x in self.peak],
                'no_spill_sufficient':self.cert_domain and all(m[p]<=self.cap[p] for m in self.peak for p in self.cap),
                'forced_soft_budget_steps':self.forced}

def frontier_order(g,owner,k,gamma=1.0,lookahead=8, memory_guard=True, priority='asap'):
    f=Frontier(g,owner,k,CAP);deg={o:len(g.pred[o]) for o in g.ids}
    release=defaultdict(float);end={};clock=defaultdict(float)
    heaps=defaultdict(list)
    for o in g.ids:
        if deg[o]==0:heapq.heappush(heaps[(owner[o],g.ops[o]['pipe'])],(0,-g.bottom[o],o))
    order=[]
    while len(order)<len(g.ids):
        inspected=[]
        for resource,h in heaps.items():
            items=[heapq.heappop(h) for _ in range(min(lookahead,len(h)))]
            for item in items:
                r,nb,o=item;start=max(clock[resource],r)
                ov,press,net,_=f.preview(o,gamma)
                # Lexicographic hard soft-capacity preference, then idle avoidance.
                # Clocks ignore real copies/DDR/Step3 memory reuse; only a proposal heuristic.
                if priority=='memory':score=(ov if memory_guard else 0, start+max(0,net)*64, nb,net,o)
                else:score=(ov if memory_guard else 0,start,nb,net,o)
                inspected.append((score,resource,item))
        if not inspected:raise ValueError('No ready compute node')
        score,res,item=min(inspected,key=lambda x:x[0]);o=item[2]
        for _,rr,it in inspected:
            if it[2]!=o:heapq.heappush(heaps[rr],it)
        if f.preview(o,gamma)[0]>0:f.forced+=1
        start=max(clock[res],item[0]);end[o]=start+g.duration(o);clock[res]=end[o]
        f.commit(o);order.append(o)
        for v in sorted(g.succ[o]):
            delay=0
            if owner[v]!=owner[o]:
                bs=sum(g.ts[t]['size'] for t in g.outputs[o] if v in g.cons[t])
                delay=500+2*math.ceil(bs/60)
            release[v]=max(release[v],end[o]+delay);deg[v]-=1
            if deg[v]==0:heapq.heappush(heaps[(owner[v],g.ops[v]['pipe'])],(release[v],-g.bottom[v],v))
    cert=f.certificate();cert['virtual_compute_finish']=max(end.values(),default=0)
    return order,cert

def plan_singleton(g,owner,order,k):
    sg={o:i for i,o in enumerate(g.ids)}
    schedules=[[] for _ in range(k)]
    for o in order:schedules[owner[o]].append(sg[o])
    return {'node_to_subgraph':{str(o):sg[o] for o in g.ids},'core_schedules':schedules}

def plan_groups(g,owner,groups,go,k):
    mp={o:i for i,grp in enumerate(groups) for o in grp}
    # Coarse chains/components topological rank, not arbitrary component-ID grouping.
    pred={i:set() for i in range(len(groups))};succ={i:set() for i in pred}
    for o in g.ids:
        for v in g.succ[o]:
            if mp[o]!=mp[v]:pred[mp[v]].add(mp[o]);succ[mp[o]].add(mp[v])
    deg={i:len(p) for i,p in pred.items()}
    heap=[(-max(g.bottom[o] for o in groups[i]),i) for i in pred if deg[i]==0];heapq.heapify(heap)
    schedules=[[] for _ in range(k)];count=0
    while heap:
        _,i=heapq.heappop(heap);schedules[go[i]].append(i);count+=1
        for v in sorted(succ[i]):
            deg[v]-=1
            if deg[v]==0:heapq.heappush(heap,(-max(g.bottom[o] for o in groups[v]),v))
    if count!=len(groups):raise ValueError('coarse quotient cycle')
    return {'node_to_subgraph':{str(o):mp[o] for o in g.ids},'core_schedules':schedules}

def stage_order(g,owner,groups,k,gamma=1.0,lookahead=8,tail_first=False):
    """General heterogeneous resource stages: no assumed M-V-M template or equal durations."""
    pos={o:i for i,o in enumerate(g.topo)}
    stages=[];chain_edges=[]
    for group in groups:
        previous=None
        for o in sorted(group,key=pos.get):
            if previous is None or g.ops[stages[previous][-1]]['pipe']!=g.ops[o]['pipe']:
                new=len(stages);stages.append([])
                if previous is not None:chain_edges.append((previous,new))
                previous=new
            stages[previous].append(o)
    parent={o:i for i,s in enumerate(stages) for o in s}
    pred={i:set() for i in range(len(stages))};succ={i:set() for i in pred}
    for o in g.ids:
        for v in g.succ[o]:
            a,b=parent[o],parent[v]
            if a!=b:pred[b].add(a);succ[a].add(b)
    for a,b in chain_edges:pred[b].add(a);succ[a].add(b)
    deg={i:len(p) for i,p in pred.items()}
    dur={i:sum(g.duration(o) for o in st) for i,st in enumerate(stages)}
    resources={i:(owner[st[0]],g.ops[st[0]]['pipe']) for i,st in enumerate(stages)}
    # Accurate stage-DAG tails by its own topological ordering.
    ds=deg.copy();hh=[i for i in ds if ds[i]==0];heapq.heapify(hh);top=[]
    while hh:
        i=heapq.heappop(hh);top.append(i)
        for v in sorted(succ[i]):
            ds[v]-=1
            if ds[v]==0:heapq.heappush(hh,v)
    if len(top)!=len(stages):raise ValueError('stage quotient cycle')
    bottom={}
    for i in reversed(top):bottom[i]=dur[i]+max((bottom[v] for v in succ[i]),default=0)
    f=Frontier(g,owner,k,CAP)
    summaries={};mandatory={}
    for i,st in enumerate(stages):
        uses=Counter();first={};last={};mandatory[i]=Counter()
        for j,o in enumerate(st):
            io=Counter()
            for t in f.touch[o]:
                uses[t]+=1;first.setdefault(t,j);last[t]=j
                p=g.ts[t]['pos'];p='UB' if p=='DDR' else p;io[p]+=g.ts[t]['size']
            for p in CAP:mandatory[i][p]=max(mandatory[i][p],io[p])
        summaries[i]=(uses,first,last)
    def preview(i):
        c=resources[i][0];uses,first,last=summaries[i];delta=defaultdict(lambda:[Counter(),Counter()])
        for t,count in uses.items():
            p=g.ts[t]['pos'];p='UB' if p=='DDR' else p;s=g.ts[t]['size']
            if t not in f.live[c]:delta[first[t]][0][p]+=s
            if f.remaining[c][t]==count:delta[last[t]][1][p]+=s
        m=f.mem[c].copy();peak=m.copy()
        for j in sorted(delta):
            a,b=delta[j]
            for p in CAP:
                m[p]+=a[p];peak[p]=max(peak[p],m[p]);m[p]-=b[p]
        ov=max(max(0,peak[p]-max(gamma*CAP[p],mandatory[i][p]))/CAP[p] for p in CAP)
        net=sum((m[p]-f.mem[c][p])/CAP[p] for p in CAP)
        return ov,net
    heaps=defaultdict(list);release=defaultdict(float);end={};clock=defaultdict(float)
    active=defaultdict(list)
    for i in deg:
        if deg[i]==0:heapq.heappush(heaps[resources[i]],(0,-bottom[i],i))
    order=[]
    while len(order)<len(g.ids):
        inspected=[]
        for res,h in heaps.items():
            if tail_first:
                while h and h[0][0]<=clock[res]:
                    r,nb,i=heapq.heappop(h)
                    heapq.heappush(active[res],(-nb,r,i))
                for _ in range(min(lookahead,len(active[res]))):
                    b,r,i=heapq.heappop(active[res]);ov,net=preview(i)
                    inspected.append(((ov,clock[res],b,net,stages[i][0]),res,(r,-b,i),'active'))
            for _ in range(min(lookahead,len(h))):
                item=heapq.heappop(h);r,nb,i=item;ov,net=preview(i)
                score=(ov,max(r,clock[res]),-nb if tail_first else nb,net,stages[i][0])
                inspected.append((score,res,item,'pending'))
        if not inspected:raise ValueError('stage schedule stalled')
        score,res,item,_=min(inspected,key=lambda x:x[0]);i=item[2]
        for _,rr,it,location in inspected:
            if it[2]!=i:
                if location=='active':heapq.heappush(active[rr],(-it[1],it[0],it[2]))
                else:heapq.heappush(heaps[rr],it)
        if score[0]>0:f.forced+=1
        end[i]=max(clock[res],item[0])+dur[i];clock[res]=end[i]
        for o in stages[i]:f.commit(o);order.append(o)
        for v in sorted(succ[i]):
            delay=0
            if resources[v][0]!=res[0]:
                touched=set()
                for o in stages[i]:
                    for t in g.outputs[o]:
                        if any(parent.get(x)==v for x in g.cons[t]):touched.add(t)
                delay=500+2*math.ceil(sum(g.ts[t]['size'] for t in touched)/60)
            release[v]=max(release[v],end[i]+delay);deg[v]-=1
            if deg[v]==0:heapq.heappush(heaps[resources[v]],(release[v],-bottom[v],v))
    cert=f.certificate();cert.update(stages=len(stages),virtual_compute_finish=max(end.values(),default=0))
    return order,cert

def make(g,k,assignment='component',method='frontier',gamma=1.0,lookahead=8):
    owner,groups,go=placement(g,k,assignment)
    if method=='coarse':return plan_groups(g,owner,groups,go,k),{'groups':len(groups)}
    if method=='word':
        from resource_word import homogeneous_word
        if assignment!='component':raise ValueError('word requires whole components')
        order,info=homogeneous_word(g,owner,groups,k);f=Frontier(g,owner,k,CAP)
        for o in order:f.commit(o)
        cert=f.certificate();cert.update(info)
    elif method in {'stage','stage_tail'}:
        order,cert=stage_order(g,owner,groups,k,gamma,lookahead,method=='stage_tail')
    elif method=='id':
        order=g.topo;f=Frontier(g,owner,k,CAP)
        for o in order:f.commit(o)
        cert=f.certificate()
    else:order,cert=frontier_order(g,owner,k,gamma,lookahead,method!='unguarded','memory' if method=='pressure' else 'asap')
    cert.update({'groups':len(groups),'assignment':assignment,'method':method,'gamma':gamma,'lookahead':lookahead})
    return plan_singleton(g,owner,order,k),cert

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('graph',type=Path);p.add_argument('--cores',type=int,default=4)
    p.add_argument('--assignment',choices=['component','chain','topo64'],default='component')
    p.add_argument('--method',choices=['coarse','id','unguarded','frontier','pressure','stage','stage_tail','word'],default='frontier')
    p.add_argument('--gamma',type=float,default=1);p.add_argument('--lookahead',type=int,default=8)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();t=time.perf_counter()
    g=Graph(json.loads(a.graph.read_text()));plan,meta=make(g,a.cores,a.assignment,a.method,a.gamma,a.lookahead)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(plan,separators=(',',':')))
    meta['construct_wall_s']=time.perf_counter()-t;a.output.with_suffix('.meta.json').write_text(json.dumps(meta,indent=2))
