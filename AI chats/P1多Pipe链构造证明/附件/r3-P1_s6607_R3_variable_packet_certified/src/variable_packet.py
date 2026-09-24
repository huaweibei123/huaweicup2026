#!/usr/bin/env python3
"""Capacity-derived variable-q synchronous DP. Research candidate, NOT E0.

Requires a *verified ordered-block chain family*. Compiles one actual Task
representative per full ordered boundary prekey. Keeps original compute IDs.
All selected Tasks are recompiled on the original graph before publication.
Run with --repo pointing to the frozen source checkout (default bundled subset).
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import archived_recognizer as author

ROOT = Path(__file__).resolve().parents[1]

class Unsupported(ValueError):
    pass

def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(',', ':'), sort_keys=True).encode()).hexdigest()

def add(a, b):
    return tuple(x+y for x,y in zip(a,b))

class Family:
    """A sufficient pre-compilation ordered-isomorphism certificate.

    This is not unordered DAG isomorphism. Both original compute ID order and
    original touched-tensor ID order are retained in the key. Boundary COPY
    order is then determined by the frozen sorted-tensor allocator.
    """
    def __init__(self, graph, cores, capacity, bandwidth):
        self.graph, self.cores = graph, cores
        self.capacity, self.bandwidth = capacity, bandwidth
        self.view, self.chains, self.chain_tensors, _, _ = author.recognize(graph)
        v = self.view
        self.eligible = {u for c in self.chains for u in c}
        self.has_out = {tid: any(v.ops[u]['op']=='COPY_OUT' for u in v.consumers[tid]) for tid in v.tensors}
        self.direct = {u: [] for u in self.eligible}
        for e in graph['edges']:
            if e['source'] in self.eligible and e['target'] in self.eligible:
                self.direct[e['source']].append(e)
        self.next_id = max(set(v.ops)|set(v.tensors), default=0)+1
        # Preserve raw-graph validity and the exact adapter's input subset.
        from src.q1.response_compile import _official_modules, _check_original_graph
        _, _, _, validation = _official_modules()
        validation.validate_graph(graph)
        _check_original_graph(graph, capacity)
        self.verify_ordered_family()
        self.bins = [self.chains[k::cores] for k in range(cores)]
        self.B = len(self.chains)//cores
        self.P = self.footprint(self.chains[0][:-1])
        self.R = self.footprint(self.chains[0][-1:])
        self.W = self.footprint(self.chains[0])
        # P is a subset of W; hence q*P <= total new-task footprint.
        self.Qmax = min([self.B]+[capacity[p]//s for p,s in self.P.items() if s])
        self.Rmax = min([self.Qmax]+[capacity[p]//s for p,s in self.R.items() if s])
        if self.B and min(self.Qmax,self.Rmax)<1:
            raise Unsupported('no positive capacity-feasible packet')

    def verify_ordered_family(self):
        v=self.view; patterns=[]
        for i,c in enumerate(self.chains):
            if i and max(self.chains[i-1])>=min(c):
                raise Unsupported('interleaved compute-ID blocks: generic per-edge prekeys needed')
            tids=sorted(self.chain_tensors[i])
            if i and self.chain_tensors[i-1] and tids and max(self.chain_tensors[i-1])>=min(tids):
                raise Unsupported('interleaved tensor-ID blocks: generic per-edge prekeys needed')
            pos={u:j for j,u in enumerate(c)}
            ops=tuple((v.ops[u]['op'],v.ops[u]['pipe'],v.ops[u]['cycles']) for u in c)
            op_order=tuple(pos[u] for u in sorted(c))
            ts=tuple((v.tensors[t]['pos'], v.tensors[t]['size'],
                      tuple(sorted(pos[u] for u in v.producers[t]&self.eligible)),
                      tuple(sorted(pos[u] for u in v.consumers[t]&self.eligible)),self.has_out[t]) for t in tids)
            direct=tuple(sorted((pos[u],pos[e['target']]) for u in c for e in self.direct[u]))
            patterns.append((ops,op_order,ts,direct))
        if any(x!=patterns[0] for x in patterns):
            raise Unsupported('different within-chain ordered descriptors')
        self.family_certificate=dict(kind='ordered-block-isomorphism-sufficient-not-necessary',
            chain_count=len(self.chains), chain_nodes=len(self.chains[0]),
            pattern_sha256=digest(patterns[0]), checked_compute_block_pairs=max(0,len(self.chains)-1),
            checked_tensor_block_pairs=max(0,len(self.chains)-1), private=True,
            original_ids_unchanged=True,
            scope='For every suffix-r/whole-(q-s)/prefix-s Task; not arbitrary reordered members')

    def footprint(self, nodes):
        v=self.view
        tids=set().union(*(v.in_t[u]|v.out_t[u] for u in nodes)) if nodes else set()
        return {p:sum(v.tensors[t]['size'] for t in tids if ('UB' if v.tensors[t]['pos']=='DDR' else v.tensors[t]['pos'])==p) for p in self.capacity}

    def fits(self, r,q,s):
        return all(r*self.R[p]+(q-s)*self.W[p]+s*self.P[p] <= self.capacity[p] for p in self.capacity)

    def members(self, core,n,r,q,s):
        if not 0<=s<=q or not 0<=r<=n:
            raise ValueError('invalid suffix state')
        line=self.bins[core]
        old=line[n-r:n] if r else []
        new=line[n:n+q]
        if len(new)!=q: raise ValueError('chain coverage overflow')
        return ([c[-1] for c in old]+[u for c in new[:q-s] for u in c]+
                [u for c in (new[q-s:] if s else []) for u in c[:-1]])

    def prekey(self, nodes):
        """Full ordered isomorphism key, not a performance fingerprint."""
        v=self.view; ns=set(nodes); ids=sorted(ns); ix={u:i for i,u in enumerate(ids)}
        tids=sorted(set().union(*(v.in_t[u]|v.out_t[u] for u in ns)))
        ts=[]
        for t in tids:
            ps=v.producers[t]&ns; cs=v.consumers[t]&ns
            eligible_cs=v.consumers[t]&self.eligible
            ib=bool(cs) and not ps
            ob=bool(ps) and (self.has_out[t] or not eligible_cs or bool(eligible_cs-ns))
            ts.append((('UB' if v.tensors[t]['pos']=='DDR' else v.tensors[t]['pos']),v.tensors[t]['size'],
                       tuple(sorted(ix[u] for u in ps)), tuple(sorted(ix[u] for u in cs)),bool(ib),bool(ob)))
        return (tuple((v.ops[u]['op'],v.ops[u]['pipe'],v.ops[u]['cycles']) for u in ids),tuple(ts),
                tuple(sorted((ix[u],ix[e['target']]) for u in ids for e in self.direct[u] if e['target'] in ns)))

    def projection(self,nodes):
        """The frozen packet_dp._TaskProjection construction, boundary flags preserved."""
        v=self.view; ns=set(nodes);tids=sorted(set().union(*(v.in_t[u]|v.out_t[u] for u in ns)))
        ops=[dict(v.ops[u]) for u in sorted(ns)]; tensors=[dict(v.tensors[t]) for t in tids]; edges=[]
        extra=self.next_id
        for tid in tids:
            ps=v.producers[tid]&ns;cs=v.consumers[tid]&ns
            edges.extend(dict(source=u,target=tid) for u in sorted(ps))
            edges.extend(dict(source=tid,target=u) for u in sorted(cs))
            outside=(v.consumers[tid]&self.eligible)-ns
            if ps and cs and (outside or self.has_out[tid]):
                ops.append(dict(id=extra,op='COPY_OUT',pipe='PIPE_MTE3',cycles=1))
                tensors.append(dict(id=extra+1,pos='DDR',size=v.tensors[tid]['size']))
                edges.extend((dict(source=tid,target=extra),dict(source=extra,target=extra+1)))
                extra+=2
        for u in sorted(ns): edges.extend(dict(e) for e in self.direct[u] if e['target'] in ns)
        return dict(ops=ops,tensors=tensors,edges=edges)

class Kernel:
    def __init__(self,family,gate,limit=512):
        from src.q1.response_compile import compile_plan
        from src.q1.response_oracle import simulate
        self.f,self.gate,self.limit=family,gate,limit
        self.compile_plan,self.simulate=compile_plan,simulate
        self.cache={};self.response_cache={};self.compiles=0;self.response_calls=0

    def get(self,nodes):
        if not nodes:raise ValueError('empty task')
        f=self.f;key=f.prekey(nodes)
        if key not in self.cache:
            if self.compiles>=self.limit:raise RuntimeError('representative compile budget exhausted')
            self.compiles+=1
            g=f.projection(nodes)
            plan=dict(node_to_subgraph={str(u):0 for u in nodes},core_schedules=[[0]])
            lines,cert=self.compile_plan(g,plan,f.capacity,f.bandwidth)
            task=lines[0][0];traffic=cert['traffic']['scheduled_copy_bytes']
            self.cache[key]=dict(task=task,bytes=traffic,representative_nodes=list(nodes),
                key_sha256=digest(key),signature_sha256=digest(task.signature()))
        return self.cache[key]

    def group(self,nodes):
        item=self.get(nodes);sig=item['task'].signature()
        if sig not in self.response_cache:
            self.response_calls+=1
            self.response_cache[sig]=self.simulate([[item['task'].scaled_ddr(self.f.cores)]],self.gate)
        response=self.response_cache[sig]
        return item,(response['makespan']+self.gate,item['bytes']*self.f.cores,self.f.cores),response

    def suffix(self,n,r,policy):
        f=self.f; all_nodes=[];lines=[];traffic=0
        for k in range(f.cores):
            old=f.members(k,n,r,0,0) if r else []
            remainder=[u for c in f.bins[k][n:] for u in c]
            if policy=='merge':
                nodes=old+remainder
                if any(v>f.capacity[p] for p,v in f.footprint(nodes).items()):return None
                groups=[nodes] if nodes else []
            elif policy=='separate':groups=[x for x in [old,remainder] if x]
            else:raise ValueError('unknown terminal policy')
            items=[self.get(nodes) for nodes in groups]
            lines.append([x['task'] for x in items]);all_nodes.append(groups)
            traffic+=sum(x['bytes'] for x in items)
        if any(lines):
            self.response_calls+=1
            resp=self.simulate(lines,self.gate)
            cost=(resp['makespan']+self.gate,traffic,sum(map(len,lines)))
        else:resp={'makespan':0};cost=(0,0,0)
        return dict(policy=policy,groups=all_nodes,cost=cost,response=resp)

def construct(graph,cores,capacity,bandwidth,gate,compile_limit=512,final_limit=2048):
    from src.q1.response_compile import compile_plan
    from src.q1.response_oracle import quotient
    began=time.perf_counter();f=Family(graph,cores,capacity,bandwidth);kernel=Kernel(f,gate,compile_limit)
    # Entire transition *domain* is capacity-derived. This is not a q/s grid search over E0 scores.
    edges=[]; by_r=defaultdict(list); drains={}
    for r in range(f.Rmax+1):
        if r:
            item,cost,response=kernel.group(f.members(0,r,r,0,0))
            drains[r]=dict(r=r,q=0,s=0,cost=cost,key=item['key_sha256'],response=response)
        for q in range(1,min(f.Qmax,f.B-r)+1):
            for s in range(min(q,f.Rmax)+1):
                if not f.fits(r,q,s):continue
                item,cost,response=kernel.group(f.members(0,r,r,q,s))
                edge=dict(r=r,q=q,s=s,cost=cost,key=item['key_sha256'],response=response)
                edges.append(edge);by_r[r].append(edge)
    profiled=time.perf_counter()
    # dist is an acyclic n,r graph: at fixed n drain r>0 -> 0, then all normal edges increase n.
    dist=[{} for _ in range(f.B+1)];dist[0][0]=((0,0,0),None)
    relaxations=0
    for n in range(f.B+1):
        for r,(cost,path) in list(dist[n].items()):
            if r and r in drains:
                candidate=add(cost,drains[r]['cost']);relaxations+=1
                if 0 not in dist[n] or candidate<dist[n][0][0]:
                    dist[n][0]=(candidate,(path,(n,r,0,0)))
        if n==f.B:break
        for r,(cost,path) in dist[n].items():
            for e in by_r[r]:
                q,s=e['q'],e['s']
                if n+q>f.B:continue
                candidate=add(cost,e['cost']);relaxations+=1
                if s not in dist[n+q] or candidate<dist[n+q][s][0]:
                    dist[n+q][s]=(candidate,(path,(n,r,q,s)))
    terminals=[];best=None
    for r,(cost,path) in dist[f.B].items():
        for policy in ('merge','separate'):
            terminal=kernel.suffix(f.B,r,policy)
            if terminal is None:continue
            end=add(cost,terminal['cost']); key=(end,policy,r)
            terminals.append(dict(r=r,policy=policy,cost=terminal['cost']))
            if best is None or key<best[0]:best=(key,path,terminal)
    if best is None:raise Unsupported('no path to terminal')
    key,path,terminal=best;predicted=key[0][0]-gate
    actions=[]
    while path is not None:path,action=path;actions.append(action)
    actions.reverse()
    mapping={};orders=[[] for _ in range(cores)];expected=[];task_count=0
    for k in range(cores):
        member_groups=[f.members(k,*a) for a in actions]+terminal['groups'][k]
        expected_line=[]
        for nodes in member_groups:
            if not nodes:raise AssertionError('empty emitted Task')
            if task_count>=final_limit:raise RuntimeError('final Task budget exhausted')
            prekey=f.prekey(nodes)
            if prekey not in kernel.cache:
                raise AssertionError('ordered family certificate failed for selected Task')
            item=kernel.cache[prekey];expected_line.append(item['task'].signature())
            orders[k].append(task_count)
            for u in nodes:
                if u in mapping:raise AssertionError('duplicate node')
                mapping[u]=task_count
            task_count+=1
        expected.append(expected_line)
    plan=dict(node_to_subgraph={str(o['id']):mapping[o['id']] for o in graph['ops'] if o['op'] not in author.COPY},core_schedules=orders)
    author.validate_plan_structure(graph,plan)
    optimized=time.perf_counter()
    lines,certificate=compile_plan(graph,plan,capacity,bandwidth)
    for k,line in enumerate(lines):
        if len(line)!=len(expected[k]) or any(t.signature()!=s for t,s in zip(line,expected[k])):
            raise AssertionError('final original-graph compilation differs from cache representative')
    actual=quotient(lines,gate)
    if actual['makespan']!=predicted:raise AssertionError('full plan rational response disagrees with DP')
    if certificate['traffic']['scheduled_copy_bytes']!=key[0][1]:raise AssertionError('full plan DDR bytes disagree with DP')
    verified=time.perf_counter()
    # Keep every representative, not only selected transitions, for independent audit.
    records=[dict(key_sha256=v['key_sha256'],signature_sha256=v['signature_sha256'],
                  representative_nodes=v['representative_nodes'],bytes=v['bytes'],signature=v['task'].signature()) for v in kernel.cache.values()]
    clean=lambda e:{k:v for k,v in e.items() if k!='response'}|{'response_cycles':e['response']['makespan'],
        'service_cycles':e['response']['service_cycles'],'ddr_retirement_union':e['response']['ddr_retirement_union']}
    info=dict(kind='variable-width synchronized rational-model candidate NOT E0',
        algorithm_id='p1-variable-packet-ordered-equivalence-dp',
        family=f.family_certificate,chains=len(f.chains),cores=cores,B=f.B,Qmax=f.Qmax,Rmax=f.Rmax,
        footprints=dict(prefix=f.P,returning=f.R,whole=f.W),capacity=capacity,bandwidth=bandwidth,gate=gate,
        actions=actions,terminal_policy=terminal['policy'],terminal_pending=key[2],
        tasks=task_count,model_makespan=actual['makespan'],traffic=certificate['traffic'],
        representative_compiles=kernel.compiles,final_task_compiles=task_count,
        total_static_task_compiles=kernel.compiles+task_count,
        normal_transitions=len(edges),drain_transitions=len(drains),response_calls=kernel.response_calls,
        unique_group_response_signatures=len(kernel.response_cache),relaxations=relaxations,
        profile_including_parse_function_seconds=profiled-began,dp_and_plan_seconds=optimized-profiled,
        final_verify_seconds=verified-optimized,construct_function_seconds=verified-began,
        edges=[clean(e) for e in edges],drains=[clean(e) for e in drains.values()],terminals=terminals,
        representatives=records,compilation_certificate=certificate,response=actual,
        calls=dict(candidate_constructors=1,E0=0,E1=0,E2=0),
        optimum_scope='Only canonical ordered-block, capacity-certified synchronized paths and the two fixed terminal policies, in Fraction/integer-retirement model')
    return plan,info

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('graph',type=Path);p.add_argument('--cores',type=int,required=True)
    p.add_argument('--repo',type=Path,default=ROOT/'frozen_repo')
    p.add_argument('--output',type=Path,required=True);p.add_argument('--diagnostics',type=Path,required=True)
    a=p.parse_args()
    if not 1<=a.cores<=5:raise ValueError('cores must be 1..5')
    if a.output.exists() or a.diagnostics.exists() or a.output==a.diagnostics:raise FileExistsError('refuse overwrite')
    sys.path.insert(0,str(a.repo.resolve()))
    sys.path.insert(0,str(a.repo.resolve()/'data/raw/a/official/code'))
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    cfg=a.repo/'data/raw/a/official/data/config.txt'
    config=read_evaluation_config(str(cfg));scene=read_scene_a_config(str(cfg))
    began=time.perf_counter();raw=a.graph.read_bytes()
    plan,info=construct(json.loads(raw),a.cores,config['capacity'],config['bandwidth'],scene['task_same_core_wait_cycles'])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    b=(json.dumps(plan,separators=(',',':'))+'\n').encode()
    with a.output.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
    info['read_to_plan_fsync_seconds']=time.perf_counter()-began
    info['plan_sha256']=hashlib.sha256(b).hexdigest();info['graph_sha256']=hashlib.sha256(raw).hexdigest()
    a.diagnostics.parent.mkdir(parents=True,exist_ok=True)
    with a.diagnostics.open('x') as f:json.dump(info,f,indent=2);f.write('\n')
    print(json.dumps({k:info[k] for k in ['model_makespan','traffic','tasks','Qmax','Rmax','representative_compiles','total_static_task_compiles','read_to_plan_fsync_seconds','terminal_policy','terminal_pending']}))
if __name__=='__main__':main()
