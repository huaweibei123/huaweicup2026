#!/usr/bin/env python3
"""P1 one-cut rotating packets, strict structural subset. NOT an E0 evaluator.

No graph/op IDs are changed in the submitted plan. COPY nodes in local_model()
are explanatory model objects only. Official E0 must reconstruct its own nodes.
Supported fast path: independent, structurally identical serial components,
M(a) -> V+ -> M(c), no excluded-COPY bridges, no shared external tensors.
All arithmetic used by certificates is integer/rational arithmetic.
"""
from __future__ import annotations
import argparse
from collections import defaultdict, deque
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import heapq
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Callable

COPY = {'COPY_IN', 'COPY_OUT'}
PIPES = ('PIPE_MTE2', 'PIPE_MTE3', 'PIPE_M', 'PIPE_V')
FROZEN_COMMIT = '161cdb35de11b0d174a5a0ca149aa36657af2abd'

class Unsupported(ValueError):
    pass

def ceildiv(x: int, y: int) -> int:
    return (x+y-1)//y

def topo(pred, succ):
    deg={u:len(ps) for u,ps in pred.items()}
    ready=[u for u,d in deg.items() if d==0];heapq.heapify(ready)
    order=[]
    while ready:
        u=heapq.heappop(ready);order.append(u)
        for v in succ[u]:
            deg[v]-=1
            if deg[v]==0:heapq.heappush(ready,v)
    if len(order)!=len(pred):raise ValueError('cycle')
    return order

@dataclass
class Views:
    ops: dict
    tensors: dict
    producers: dict
    consumers: dict
    pred: dict
    succ: dict
    in_t: dict
    out_t: dict

def views(graph: dict) -> Views:
    ops={o['id']:o for o in graph['ops']}
    tensors={t['id']:t for t in graph['tensors']}
    if len(ops)!=len(graph['ops']) or len(tensors)!=len(graph['tensors']) or ops.keys()&tensors.keys():
        raise ValueError('non-unique node IDs')
    for o in ops.values():
        if type(o['id']) is not int or o['id']<0 or type(o['cycles']) is not int or o['cycles']<0 or o['pipe'] not in PIPES:
            raise ValueError('bad op')
    for t in tensors.values():
        if type(t['size']) is not int or t['size']<0 or t['pos'] not in {'L1','UB','DDR'}:
            raise ValueError('bad tensor')
    pr=defaultdict(set);co=defaultdict(set)
    pred={u:set() for u in ops};succ={u:set() for u in ops}
    ins={u:set() for u in ops};outs={u:set() for u in ops}
    for e in graph['edges']:
        u,v=e['source'],e['target']
        if u not in ops and u not in tensors or v not in ops and v not in tensors:
            raise ValueError('unknown endpoint')
        if u in ops and v in ops:
            succ[u].add(v);pred[v].add(u)
        elif u in ops:
            pr[v].add(u);outs[u].add(v)
        elif v in ops:
            co[u].add(v);ins[v].add(u)
        else:raise ValueError('tensor-to-tensor edge unsupported')
    for t in tensors:
        for u in pr[t]:
            for v in co[t]:
                succ[u].add(v);pred[v].add(u)
    topo(pred,succ)
    return Views(ops,tensors,pr,co,pred,succ,ins,outs)

def recognize(graph: dict):
    v=views(graph)
    eligible={u for u,o in v.ops.items() if o['op'] not in COPY}
    if not eligible:raise Unsupported('empty compute graph')
    order=topo(v.pred,v.succ)
    before={u:False for u in v.ops};after={u:False for u in v.ops}
    for u in order:
        for w in v.succ[u]:before[w]|=before[u] or u in eligible
    for u in reversed(order):
        for w in v.succ[u]:after[u]|=after[w] or w in eligible
    if any(before[u] and after[u] for u in v.ops if u not in eligible):
        raise Unsupported('excluded-COPY bridge: use frozen fallback')
    pred={u:v.pred[u]&eligible for u in eligible}
    succ={u:v.succ[u]&eligible for u in eligible}
    components=[];seen=set()
    for root in sorted(eligible):
        if root in seen:continue
        group=set();stack=[root];seen.add(root)
        while stack:
            u=stack.pop();group.add(u)
            for w in pred[u]|succ[u]:
                if w not in seen:seen.add(w);stack.append(w)
        p={u:pred[u]&group for u in group};s={u:succ[u]&group for u in group}
        seq=topo(p,s)
        # Unique compute topological order. Skip edges ARE permitted and kept.
        if any(seq[i+1] not in s[seq[i]] for i in range(len(seq)-1)):
            raise Unsupported('component has no certified dependency spine')
        word=[v.ops[u]['pipe'] for u in seq]
        if len(seq)<3 or word[0]!='PIPE_M' or word[-1]!='PIPE_M' or any(x!='PIPE_V' for x in word[1:-1]):
            raise Unsupported('not M -> V+ -> M')
        components.append(seq)
    components.sort(key=lambda c:min(c))
    which={u:i for i,c in enumerate(components) for u in c}
    ct=defaultdict(list)
    for tid,t in v.tensors.items():
        ps=v.producers[tid]&eligible;cs=v.consumers[tid]&eligible
        owners={which[u] for u in ps|cs}
        if len(ps)>1 or len(owners)>1:
            raise Unsupported('multiple compute producers or shared external tensor')
        if owners:ct[next(iter(owners))].append(tid)
    signatures=[]
    for i,chain in enumerate(components):
        index={u:j for j,u in enumerate(chain)}
        tensors=[]
        for tid in ct[i]:
            t=v.tensors[tid];ps=v.producers[tid]&eligible;cs=v.consumers[tid]&eligible
            h=any(v.ops[u]['op']=='COPY_OUT' for u in v.consumers[tid])
            # Internal original output taps are valid for construction, but
            # excluded here to simplify the all-partition cut certificate.
            if ps and cs and h:raise Unsupported('internal original output tap')
            tensors.append((tuple(sorted(index[u] for u in ps)),tuple(sorted(index[u] for u in cs)),
                            'UB' if t['pos']=='DDR' else t['pos'],t['size'],h))
        signatures.append((tuple((v.ops[u]['pipe'],max(1,v.ops[u]['cycles'])) for u in chain),
                           tuple(sorted((index[u],index[w]) for u in chain for w in succ[u])),
                           tuple(sorted(tensors))))
    if any(s!=signatures[0] for s in signatures):raise Unsupported('heterogeneous family: use frozen fallback')
    return v,components,ct,pred,succ

def boundary_counts(graph: dict, plan: dict, bandwidth: int) -> dict:
    """Exact boundary counts of frozen _build_scene_a_tasks, excluding spills."""
    v=views(graph);mp={int(u):t for u,t in plan['node_to_subgraph'].items()}
    scheduled=0;service=0;instances=0;rows=[]
    for tid,t in v.tensors.items():
        ps={mp[u] for u in v.producers[tid] if u in mp}
        cs={mp[u] for u in v.consumers[tid] if u in mp}
        h=any(v.ops[u]['op']=='COPY_OUT' for u in v.consumers[tid])
        ni=len(cs-ps)
        no=sum(h or not cs or bool(cs-{p}) for p in ps)
        count=ni+no
        if count:
            b=max(1,ceildiv(t['size'],bandwidth))
            rows.append({'tensor_id':tid,'copy_in':ni,'copy_out':no,'bytes':count*t['size'],'service':count*b})
            scheduled+=count*t['size'];service+=count*b;instances+=count
    original=0
    for u,o in v.ops.items():
        tids=v.out_t[u] if o['op']=='COPY_IN' else v.in_t[u] if o['op']=='COPY_OUT' else []
        original+=sum(v.tensors[t]['size'] for t in tids)
    return {'boundary_copy_bytes':scheduled,'partition_added_copy_bytes':scheduled-original,
            'original_graph_copy_bytes':original,'boundary_service_cycles':service,'boundary_copy_count':instances,
            'spill_bytes':'not included unless the virgin-capacity certificate passes','by_tensor':rows}

def validate_plan_structure(graph,plan):
    v=views(graph);mp={int(u):t for u,t in plan['node_to_subgraph'].items()}
    eligible={u for u,o in v.ops.items() if o['op'] not in COPY}
    if set(plan)!={'node_to_subgraph','core_schedules'} or set(mp)!=eligible:raise ValueError('bad plan coverage')
    tasks=set(mp.values());flat=[t for line in plan['core_schedules'] for t in line]
    if len(flat)!=len(set(flat)) or set(flat)!=tasks:raise ValueError('bad task coverage')
    p={t:set() for t in tasks};s={t:set() for t in tasks}
    # Exact nearest-eligible contraction, only in this verification routine.
    for u in eligible:
        seen=set();stack=list(v.succ[u])
        while stack:
            w=stack.pop()
            if w in eligible:
                a,b=mp[u],mp[w]
                if a!=b:s[a].add(b);p[b].add(a)
            elif w not in seen:seen.add(w);stack.extend(v.succ[w])
    for line in plan['core_schedules']:
        for a,b in zip(line,line[1:]):s[a].add(b);p[b].add(a)
    return topo(p,s)

def encode(components, original_ops, cores, packet, cut_count, whole_packet, cut_position=None):
    """Whole components first, then per-core rotating prefix/return packets."""
    if not 1<=cores<=5 or packet<1 or whole_packet<1:raise ValueError('bad parameters')
    nc=len(components);cut_count=max(0,min(nc,cut_count))
    bins=[[] for _ in range(cores)]
    for i,c in enumerate(components):bins[i%cores].append((i,c))
    mapping={};orders=[[] for _ in range(cores)];next_task=0
    def emit(core,nodes):
        nonlocal next_task
        if nodes:
            orders[core].append(next_task)
            for u in nodes:
                if u in mapping:raise AssertionError('duplicate compute node')
                mapping[u]=next_task
            next_task+=1
    for k,chains in enumerate(bins):
        split=[c for i,c in chains if i<cut_count]
        intact=[c for i,c in chains if i>=cut_count]
        for b in range(0,len(intact),whole_packet):emit(k,[u for c in intact[b:b+whole_packet] for u in c])
        batches=[split[b:b+packet] for b in range(0,len(split),packet)]
        def pos(c):return len(c)-1 if cut_position is None else cut_position
        for j in range(len(batches)+1):
            cur=batches[j] if j<len(batches) else []
            prev=batches[j-1] if j else []
            emit(k,[u for c in cur for u in c[:pos(c)]]+[u for c in prev for u in c[pos(c):]])
    return {'node_to_subgraph':{o['id']:mapping[o['id']] for o in original_ops if o['op'] not in COPY},
            'core_schedules':orders}

def local_model(graph,plan,bandwidth):
    """Boundary-only transcription, NOT calling the official compiler/E0.
    IDs for generated model COPYs follow the frozen collision-avoidance rule.
    """
    v=views(graph);mp={int(u):t for u,t in plan['node_to_subgraph'].items()}
    nodes=defaultdict(list);touched=defaultdict(set)
    for u,t in mp.items():nodes[t].append(u)
    for tid in v.tensors:
        for task in {mp[u] for u in v.producers[tid]|v.consumers[tid] if u in mp}:touched[task].add(tid)
    used=set(v.ops)|set(v.tensors)
    oi=max(list(v.ops)+[0])+1;ti=max(list(v.tensors)+[10000])+1
    def ids():
        nonlocal oi,ti
        while ti in used:ti+=1
        d=ti;used.add(d);ti+=1
        while oi in used:oi+=1
        c=oi;used.add(c);oi+=1
        return d,c
    direct_by_task=defaultdict(list)
    for e in graph['edges']:
        u,w=e['source'],e['target']
        if u in mp and w in mp and mp[u]==mp[w]:direct_by_task[mp[u]].append(dict(e))
    result={}
    for task in sorted(nodes):
        members=set(nodes[task]);ops=[dict(v.ops[u]) for u in sorted(members)];tensors=[];edges=[]
        for tid in sorted(touched[task]):
            t=dict(v.tensors[tid]);ps=v.producers[tid]&members;cs=v.consumers[tid]&members
            eligible_cs=v.consumers[tid]&mp.keys()
            h=any(v.ops[u]['op']=='COPY_OUT' for u in v.consumers[tid])
            inp=bool(cs) and not ps
            out=bool(ps) and (h or not eligible_cs or bool(eligible_cs-members))
            if t['pos']=='DDR':t['pos']='UB'
            tensors.append(t)
            edges.extend({'source':u,'target':tid} for u in sorted(ps))
            edges.extend({'source':tid,'target':u} for u in sorted(cs))
            for is_input,on in [(True,inp),(False,out)]:
                if not on:continue
                d,c=ids();tensors.append({'id':d,'pos':'DDR','size':t['size']})
                ops.append({'id':c,'op':'COPY_IN' if is_input else 'COPY_OUT',
                            'pipe':'PIPE_MTE2' if is_input else 'PIPE_MTE3',
                            'cycles':max(1,ceildiv(t['size'],bandwidth))})
                pairs=[(d,c),(c,tid)] if is_input else [(tid,c),(c,d)]
                edges.extend({'source':a,'target':b} for a,b in pairs)
        edges.extend(direct_by_task[task])
        result[task]={'ops':ops,'tensors':tensors,'edges':edges}
    return result

def reference_step1(graph):
    """Independent transcription of the read Step1; NOT a frozen source file."""
    v=views(graph);order=topo(v.pred,v.succ)
    depth={}
    for u in order:depth[u]=max((depth[p]+1 for p in v.pred[u]),default=0)
    def key(u):return (v.ops[u]['op']!='COPY_IN',depth[u],-u)
    def startkey(u):return (v.ops[u]['op']!='COPY_OUT',depth[u],-u)
    stack=sorted((u for u in order if not v.succ[u]),key=startkey);seen=set();seq=[]
    while stack:
        u=stack[-1]
        if u in seen:stack.pop();continue
        ps=[p for p in v.pred[u] if p not in seen]
        if ps:stack.extend(sorted(ps,key=key))
        else:seen.add(u);seq.append(u);stack.pop()
    if len(seq)!=len(v.ops):raise AssertionError('Step1 transcription coverage')
    return seq

def task_profile(local,bandwidth,copy_factor=1,copy_slack=0):
    """Fixed-FIFO max-plus response. DDR requests given independent latencies.
    factor=1 is a RELAXATION unless resulting DDR intervals are disjoint;
    factor=2*K, slack=1 is a conservative upper envelope in the stated model.
    """
    v=views(local);seq=reference_step1(local);end={};start={};last={};rows=[]
    for u in seq:
        o=v.ops[u];p=o['pipe'];pred=set(v.pred[u])
        if p in last:pred.add(last[p])
        s=max((end[x] for x in pred),default=0)
        if o['op'] in COPY:
            tids=v.out_t[u] if o['op']=='COPY_IN' else v.in_t[u]
            d=max(1,ceildiv(sum(v.tensors[t]['size'] for t in tids),bandwidth))
            dur=copy_factor*d+copy_slack
        else:dur=max(1,o['cycles'])
        start[u]=s;end[u]=s+dur;last[p]=u
        rows.append({'op_id':u,'op':o['op'],'pipe':p,'start':s,'end':s+dur,'duration':dur})
    return {'cycles':max(end.values(),default=0),'seq':seq,'ops':rows}

def model_plan(graph,plan,bandwidth,capacity,gate):
    validate_plan_structure(graph,plan)
    vv=views(graph);mp={int(u):t for u,t in plan['node_to_subgraph'].items()}
    owner={t:k for k,order in enumerate(plan['core_schedules']) for t in order}
    if any(owner[mp[u]]!=owner[mp[w]] for u in mp for w in vv.succ[u] if w in mp):
        raise Unsupported('model_plan only covers same-core chain partitions; cross-core gates require another model')
    local=local_model(graph,plan,bandwidth);k=len(plan['core_schedules'])
    profiles={};totals={};virgin=True
    for task,g in local.items():
        totals[task]={pos:sum(t['size'] for t in g['tensors'] if t['pos']==pos) for pos in capacity}
        virgin &= all(totals[task][p]<=capacity[p] for p in capacity)
        profiles[task]=task_profile(g,bandwidth)
    timeline=[];endcore=[];uppercore=[]
    for core,order in enumerate(plan['core_schedules']):
        now=up=0
        for i,task in enumerate(order):
            if i:now+=gate;up+=gate
            timeline.extend(dict(row,core=core,task=task,start=row['start']+now,end=row['end']+now)
                            for row in profiles[task]['ops'])
            now+=profiles[task]['cycles']
            up+=task_profile(local[task],bandwidth,2*k,1)['cycles']
        endcore.append(now);uppercore.append(up)
    ddr=sorted((r['start'],r['end']) for r in timeline if r['op'] in COPY)
    disjoint=all(ddr[i][0]>=ddr[i-1][1] for i in range(1,len(ddr)))
    mv_overlap=0
    for core in range(k):
        ms=sorted((r['start'],r['end']) for r in timeline if r['core']==core and r['pipe']=='PIPE_M')
        vs=sorted((r['start'],r['end']) for r in timeline if r['core']==core and r['pipe']=='PIPE_V')
        i=j=0
        while i<len(ms) and j<len(vs):
            mv_overlap+=max(0,min(ms[i][1],vs[j][1])-max(ms[i][0],vs[j][0]))
            if ms[i][1]<=vs[j][1]:i+=1
            else:j+=1
    return {'kind':'middle_model_NOT_E0','cycles':max(endcore,default=0),'upper_envelope_cycles':max(uppercore,default=0),
            'virgin_capacity_certificate':bool(virgin),'all_DDR_intervals_disjoint_in_relaxation':disjoint,
            'conditional_exact_model':bool(virgin and disjoint),
            'M_V_overlap_cycles_sum_over_cores':mv_overlap,'capacity_sum_by_task':totals,'timeline':timeline,
            'boundary':boundary_counts(graph,plan,bandwidth)}

def cut_table(graph,chain,bandwidth):
    """All spine interfaces. A skip tensor contributes throughout its live cut interval."""
    v=views(graph);index={u:i for i,u in enumerate(chain)};n=len(chain)
    bs=[0]*(n+1);ds=[0]*(n+1);external=[0]*(n+1)
    eligible={u for u,o in v.ops.items() if o['op'] not in COPY}
    for tid,t in v.tensors.items():
        ps=v.producers[tid]&index.keys();cs=v.consumers[tid]&index.keys()
        if not cs:continue
        b=max(1,ceildiv(t['size'],bandwidth))
        if ps:
            if len(ps)!=1:raise Unsupported('multi-producer')
            lo=index[next(iter(ps))];hi=max(index[u] for u in cs)
            h=any(v.ops[u]['op']=='COPY_OUT' for u in v.consumers[tid])
            bs[lo]+=t['size'];bs[hi]-=t['size']
            ds[lo]+=(1 if h else 2)*b;ds[hi]-=(1 if h else 2)*b
        elif not (v.producers[tid]&eligible):
            lo=min(index[u] for u in cs);hi=max(index[u] for u in cs)
            external[lo]+=b;external[hi]-=b
    for j in range(1,n):
        bs[j]+=bs[j-1];ds[j]+=ds[j-1];external[j]+=external[j-1]
    return [{'after_index':j,'internal_cut_bytes':bs[j], 'universal_extra_service_min':ds[j],
             'one_cut_extra_service_with_external_duplication':ds[j]+external[j]} for j in range(n-1)]

def choose_and_construct(graph,cores,bandwidth,capacity,gate=100):
    v,components,ct,_,_=recognize(graph)
    n=len(components);h=len(components[0]);c0=components[0]
    a=max(1,v.ops[c0[0]]['cycles']);c=max(1,v.ops[c0[-1]]['cycles'])
    b=sum(max(1,v.ops[u]['cycles']) for u in c0[1:-1]);ell=a+b+c
    # One representative chain, put in separate prefix and return Tasks.
    # Sum footprints, not estimated peak, is the deliberately conservative guard.
    def footprint(nodes):
        used=set()
        for u in nodes:used |= v.in_t[u]|v.out_t[u]
        return {p:sum(v.tensors[t]['size'] for t in used if ('UB' if v.tensors[t]['pos']=='DDR' else v.tensors[t]['pos'])==p) for p in capacity}
    fp=footprint(c0[:-1]);ft=footprint(c0[-1:]);fw=footprint(c0)
    def cap_for(x):return min((capacity[p]//x[p] for p in capacity if x[p]),default=n)
    qc=cap_for({p:fp[p]+ft[p] for p in capacity});qw=cap_for(fw)
    if qc<1 or qw<1:raise Unsupported('virgin-capacity sufficient condition fails')
    ncore=ceildiv(n,cores)
    # Analytic batch scale; NOT a theorem about best E0 packet size.
    q=max(1,min(qc,ncore,math.isqrt(max(1,ncore*(a+gate)//c))))
    fq=max(q*(a+c),a+b+(q-1)*max(a,b))
    saving=Fraction(q*ell-fq-gate,q)
    whole=encode(components,graph['ops'],cores,1,0,max(1,n))
    d0=boundary_counts(graph,whole,bandwidth)['boundary_service_cycles']
    tab=cut_table(graph,c0,bandwidth)
    delta=tab[-1]['one_cut_extra_service_with_external_duplication']
    if saving<=0:split=0
    else:
        x=Fraction(n*ell-cores*d0,1)/(saving+cores*delta)
        x=max(Fraction(0),min(Fraction(n),x))
        stride=cores*q
        lower=(x.numerator//(x.denominator*stride))*stride
        options={0,n,max(0,min(n,lower)),max(0,min(n,lower+stride))}
        def proxy(s):return max(Fraction(n*ell,cores)-saving*s/cores,Fraction(d0+delta*s))
        split=min(options,key=lambda s:(proxy(s),s))
    plan=encode(components,graph['ops'],cores,q,split,qw)
    model=model_plan(graph,plan,bandwidth,capacity,gate)
    baseline_compute_lb=ceildiv(n,cores)*ell
    info={'kind':'candidate_generation_NOT_E0','algorithm':'p1-one-cut-return-rotation-v1',
          'chains':n,'packet':q,'cut_chains':split,'whole_packet':qw,'a':a,'b':b,'c':c,
          'selection':'at most four break-point/endpoint values of an explicit proxy; no scoring search',
          'proxy_saving_per_cut':str(saving),'delta_service_per_cut':delta,'whole_boundary_service':d0,
          'baseline_complete_component_compute_lower_bound':baseline_compute_lb,
          'conservative_dominance_certificate':bool(model['virgin_capacity_certificate'] and model['upper_envelope_cycles']<baseline_compute_lb),
          'model':model}
    return plan,info

def integrate_construct(graph,cores,bandwidth,capacity,frozen_fallback:Callable,gate=100):
    """Quality-safe wrapper for the stated strict model. Do not replace fallback with historical bests."""
    try:
        plan,info=choose_and_construct(graph,cores,bandwidth,capacity,gate)
        if info['conservative_dominance_certificate']:return plan,info
        reason='no conservative dominance certificate'
    except Unsupported as exc:reason=str(exc)
    plan,base=frozen_fallback(graph,cores)
    return plan,{'selected':'frozen_fixed_fallback','reason':reason,'base':base}

def atomic_json(path:Path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise FileExistsError(str(path))
    tmp=None
    try:
        with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False,encoding='utf-8') as f:
            tmp=Path(f.name);json.dump(value,f,separators=(',',':'));f.write('\n');f.flush();os.fsync(f.fileno())
        # Link gives no-overwrite atomic publication on this local filesystem.
        os.link(tmp,path);tmp.unlink();tmp=None
    finally:
        if tmp is not None and tmp.exists():tmp.unlink()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('graph',type=Path);p.add_argument('--cores',type=int,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--diagnostics',type=Path,required=True)
    p.add_argument('--mode',choices=['auto','whole','return-cut','entry-cut','whole-tasks'],default='auto')
    p.add_argument('--packet',type=int,default=1)
    a=p.parse_args()
    if not 1<=a.cores<=5:raise ValueError('cores outside 1..5')
    config={};section=None
    for line in a.config.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        if line.startswith('['):section=line.strip('[]');config[section]={}
        else:
            key,val=line.split();config[section][key]=int(val)
    cap=config['capacity'];bw=config['bandwidth']['bandwidth'];gate=config['multicore_scene_a']['task_same_core_wait_cycles']
    graph=json.loads(a.graph.read_text())
    if a.mode=='auto':plan,info=choose_and_construct(graph,a.cores,bw,cap,gate)
    else:
        _,comps,_,_,_=recognize(graph);n=len(comps)
        cut=n if a.mode in {'return-cut','entry-cut'} else 0
        pos=1 if a.mode=='entry-cut' else None
        plan=encode(comps,graph['ops'],a.cores,a.packet,cut,1 if a.mode=='whole-tasks' else n,cut_position=pos)
        info={'kind':'fixed_mechanism_microtest_NOT_E0','mode':a.mode,'model':model_plan(graph,plan,bw,cap,gate)}
    validate_plan_structure(graph,plan)
    atomic_json(a.output,plan);atomic_json(a.diagnostics,info)
    print(json.dumps({'plan_keys':sorted(plan),'mode':a.mode,'official_E0_calls':0}))
if __name__=='__main__':main()
