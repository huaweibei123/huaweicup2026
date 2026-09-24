#!/usr/bin/env python3
"""Universal resource-window and cut-or-serialize certificates (NOT E0).

The resource jobs are constructed only from necessary work and retained original
non-COPY dependencies. Candidate-specific FIFO/memory/Task edges are NEVER used.
Cut-or-serialize has the strict recognizer's additional scope, documented below.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from fractions import Fraction
from bisect import bisect_right
import hashlib, json
from p1_phase_cut import views, topo, COPY, PIPES, ceildiv, recognize, encode, boundary_counts, cut_table

@dataclass(frozen=True)
class Job:
    uid: str
    r: int
    d: int
    q: int

class PrefixAddMax:
    """Range-add, range-max segment tree; integer values and argmax witnesses."""
    def __init__(self, values):
        self.n=len(values)
        self.mx=[0]*(4*self.n); self.lazy=[0]*(4*self.n); self.arg=[0]*(4*self.n)
        def build(v,l,r):
            if r-l==1:self.mx[v]=values[l];self.arg[v]=l;return
            m=(l+r)//2;build(v*2,l,m);build(v*2+1,m,r);self.pull(v)
        build(1,0,self.n)
    def pull(self,v):
        a,b=v*2,v*2+1
        best=a if (self.mx[a],-self.arg[a])>=(self.mx[b],-self.arg[b]) else b
        self.mx[v]=self.mx[best];self.arg[v]=self.arg[best]
    def apply(self,v,d):self.mx[v]+=d;self.lazy[v]+=d
    def push(self,v):
        if self.lazy[v]:
            self.apply(v*2,self.lazy[v]);self.apply(v*2+1,self.lazy[v]);self.lazy[v]=0
    def prefix_add(self,end,delta):
        def rec(v,l,r):
            if l>=end:return
            if r<=end:self.apply(v,delta);return
            self.push(v);m=(l+r)//2;rec(v*2,l,m);rec(v*2+1,m,r);self.pull(v)
        rec(1,0,self.n)
    def prefix_max(self,end):
        def rec(v,l,r):
            if l>=end:return None
            if r<=end:return self.mx[v],self.arg[v]
            self.push(v);m=(l+r)//2;a=rec(v*2,l,m);b=rec(v*2+1,m,r)
            if a is None:return b
            if b is None:return a
            return max((a,b),key=lambda z:(z[0],-z[1]))
        return rec(1,0,self.n)

def validate_jobs(jobs,capacity):
    if type(capacity) is not int or capacity<1:raise ValueError('capacity must be a positive integer')
    if len({j.uid for j in jobs})!=len(jobs):raise ValueError('job UIDs must be unique')
    if any(any(type(x) is not int or x<0 for x in (j.r,j.q)) or type(j.d) is not int or j.d<1 for j in jobs):
        raise ValueError('jobs require nonnegative integer r,q and positive integer d')

def energetic_bound(jobs:list[Job],capacity:int):
    """max r0+q0+ceil(sum{d: r>=r0,q>=q0}/capacity), O(J log J).
    Excludes empty subsets; all thresholds and certificate arithmetic are exact.
    """
    validate_jobs(jobs,capacity)
    if not jobs:return {'bound':0,'capacity':capacity,'empty':True}
    qs=sorted({j.q for j in jobs}); tree=PrefixAddMax([capacity*q for q in qs])
    ordered=sorted(jobs,key=lambda j:(-j.r,j.uid));i=0;max_active_q=-1;best=None
    while i<len(ordered):
        r=ordered[i].r
        while i<len(ordered) and ordered[i].r==r:
            j=ordered[i];tree.prefix_add(bisect_right(qs,j.q),j.d)
            max_active_q=max(max_active_q,j.q);i+=1
        value,index=tree.prefix_max(bisect_right(qs,max_active_q))
        bound=r+ceildiv(value,capacity)
        candidate={'bound':bound,'capacity':capacity,'r_threshold':r,'q_threshold':qs[index]}
        if best is None or bound>best['bound']:best=candidate
    selected=[j for j in jobs if j.r>=best['r_threshold'] and j.q>=best['q_threshold']]
    best.update({'selected_count':len(selected),'selected_work':sum(j.d for j in selected)})
    return best

def verify_energetic(jobs,certificate):
    """O(J) verification of a witness, not trusting the optimizing implementation."""
    c=certificate['capacity'];validate_jobs(jobs,c)
    if certificate.get('empty'):return not jobs and certificate['bound']==0
    r,q=certificate['r_threshold'],certificate['q_threshold']
    selected=[j for j in jobs if j.r>=r and j.q>=q]
    return bool(selected) and all((certificate['selected_count']==len(selected),
        certificate['selected_work']==sum(j.d for j in selected),
        certificate['bound']==r+q+ceildiv(sum(j.d for j in selected),c)))

def brute_energetic(jobs,capacity):
    validate_jobs(jobs,capacity)
    return max((r+q+ceildiv(sum(j.d for j in jobs if j.r>=r and j.q>=q),capacity)
        for r in {j.r for j in jobs} for q in {j.q for j in jobs}
        if any(j.r>=r and j.q>=q for j in jobs)),default=0)

def universal_jobs(graph,bandwidth):
    """Necessary jobs from frozen P1 boundary predicates, not COPY contraction.
    Construction follows Q1_LOWER_BOUNDS.md at the specified frozen commit.
    """
    if type(bandwidth) is not int or bandwidth<1:raise ValueError('positive integer bandwidth required')
    v=views(graph);eligible={u for u,o in v.ops.items() if o['op'] not in COPY}
    pr={u:v.pred[u]&eligible for u in eligible};su={u:v.succ[u]&eligible for u in eligible}
    order=topo(pr,su);d={u:max(1,v.ops[u]['cycles']) for u in eligible}
    ps={t:v.producers[t]&eligible for t in v.tensors};cs={t:v.consumers[t]&eligible for t in v.tensors}
    inputs=[t for t in v.tensors if not ps[t] and cs[t]]
    outputs=[t for t in v.tensors if ps[t] and (not cs[t] or any(v.ops[u]['op']=='COPY_OUT' for u in v.consumers[t]))]
    b={t:max(1,ceildiv(v.tensors[t]['size'],bandwidth)) for t in set(inputs)|set(outputs)}
    r=dict.fromkeys(eligible,0);q=dict.fromkeys(eligible,0)
    for t in inputs:
        for u in cs[t]:r[u]=max(r[u],b[t])
    for t in outputs:
        for u in ps[t]:q[u]=max(q[u],b[t])
    for u in order:r[u]=max([r[u]]+[r[w]+d[w] for w in pr[u]])
    for u in reversed(order):q[u]=max([q[u]]+[d[w]+q[w] for w in su[u]])
    resources={p:[] for p in PIPES};resources['DDR']=[]
    for u in sorted(eligible):resources[v.ops[u]['pipe']].append(Job('op:'+str(u),r[u],d[u],q[u]))
    for t in sorted(inputs):
        j=Job('necessary_input:'+str(t),0,b[t],max(d[u]+q[u] for u in cs[t]))
        resources['PIPE_MTE2'].append(j);resources['DDR'].append(j)
    for t in sorted(outputs):
        j=Job('necessary_output:'+str(t),max(r[u]+d[u] for u in ps[t]),b[t],0)
        resources['PIPE_MTE3'].append(j);resources['DDR'].append(j)
    cp=max((r[u]+d[u]+q[u] for u in eligible),default=0)
    return resources,cp

def general_certificate(graph,cores,bandwidth):
    if type(cores) is not int or not 1<=cores<=5:raise ValueError('1..5 cores')
    resources,cp=universal_jobs(graph,bandwidth)
    certificates={name:energetic_bound(jobs,1 if name=='DDR' else cores) for name,jobs in resources.items()}
    result={'kind':'universal_lower_bound_NOT_a_plan','cores':cores,'bandwidth':bandwidth,
        'critical_path_bound':cp,'resources':certificates,
        'bound':max([cp]+[c['bound'] for c in certificates.values()])}
    return result

def verify_general(graph,certificate):
    resources,cp=universal_jobs(graph,certificate['bandwidth'])
    if cp!=certificate['critical_path_bound']:return False
    for name,jobs in resources.items():
        c=certificate['resources'][name]
        if c['capacity']!=(1 if name=='DDR' else certificate['cores']) or not verify_energetic(jobs,c):return False
    return certificate['bound']==max([cp]+[c['bound'] for c in certificate['resources'].values()])

def homogeneous_cut_or_serialize(n:int,ell:int,delta:int,d0:int,cores:int, m_work:int=0):
    """Universal only under the accompanying intact-chain FIFO-lock theorem.
    Also charges the unavoidable M blocking interval of each intact chain:
    min_s max(ell*ceil((n-s)/K), ceil((n*m_work+(n-s)*(ell-m_work))/K), d0+delta*s).
    m_work=0 gives the weaker intact-count version (aggregate term redundant). O(log n).
    """
    if not (n>=0 and ell>=1 and delta>=0 and d0>=0 and 1<=cores<=5 and 0<=m_work<=ell):raise ValueError('bad inputs')
    def f(s):return max(ell*ceildiv(n-s,cores),ceildiv(n*m_work+(n-s)*(ell-m_work),cores))
    def g(s):return d0+delta*s
    lo,hi=0,n
    while lo<hi:
        mid=(lo+hi)//2
        if f(mid)<=g(mid):hi=mid
        else:lo=mid+1
    candidates=sorted({0,n,lo,max(0,lo-1)})
    s=min(candidates,key=lambda s:(max(f(s),g(s)),s))
    return {'bound':max(f(s),g(s)),'minimizer_cut_count':s,'N':n,'chain_compute_cycles':ell,
        'minimum_internal_cut_service':delta,'necessary_service':d0,'cores':cores,
        'crossing':lo,'checked_counts':candidates,'per_chain_M_work':m_work,
        'per_intact_chain_unavoidable_M_blocking':ell-m_work}

def strict_family_cut_certificate(graph,cores,bandwidth):
    v,chains,_,_,_=recognize(graph)
    ell=sum(max(1,v.ops[u]['cycles']) for u in chains[0])
    interface=cut_table(graph,chains[0],bandwidth)
    delta=min(row['universal_extra_service_min'] for row in interface)
    whole=encode(chains,graph['ops'],cores,1,0,len(chains))
    d0=boundary_counts(graph,whole,bandwidth)['boundary_service_cycles']
    m_work=sum(max(1,v.ops[u]['cycles']) for u in chains[0] if v.ops[u]['pipe']=='PIPE_M')
    cert=homogeneous_cut_or_serialize(len(chains),ell,delta,d0,cores,m_work)
    cert.update({'scope':'independent homogeneous M-V+-M spines, no COPY bridges, no shared tensors, no internal output taps',
                 'interface_table':interface})
    return cert

def heterogeneous_dual(lengths,deltas,d0,cores,base_resource_work=0):
    """Exact maximization of a concave dual bound, O(N log N), rational witness.
    Scope: disjoint necessary resource blocking and disjoint extra cut services.
    Use lengths=b_i and base_resource_work=W_M for the stronger M-blocking bound;
    lengths=ell_i, base_resource_work=0 gives the weaker intact-span bound.
    """
    if len(lengths)!=len(deltas) or not 1<=cores<=5 or d0<0:raise ValueError('bad parameters')
    events=[]
    for ell,delta in zip(lengths,deltas):
        if ell<1 or delta<0:raise ValueError('bad chain data')
        point=Fraction(cores*delta,ell+cores*delta)
        events.append((point,Fraction(ell,cores)+delta))
    events.sort();slope=sum((Fraction(e,cores) for e in lengths),Fraction(base_resource_work,cores)-d0);value=Fraction(d0)
    best=value;alpha=Fraction(0);prev=Fraction(0);i=0
    while i<len(events):
        x=events[i][0];value+=slope*(x-prev)
        if value>best:best=value;alpha=x
        while i<len(events) and events[i][0]==x:slope-=events[i][1];i+=1
        prev=x
    value+=slope*(1-prev)
    if value>best:best=value;alpha=Fraction(1)
    return {'bound':ceildiv(best.numerator,best.denominator),'rational_bound':str(best),'alpha':str(alpha)}
