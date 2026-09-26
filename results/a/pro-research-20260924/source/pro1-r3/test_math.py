#!/usr/bin/env python3
"""Bounded deterministic mathematical checks, not global E0 equivalence proof."""
import argparse,json,random,sys,time
from pathlib import Path
from packet_construct import packet_profile,mat_apply,initial_groups
from cover_fusion import fuse_cover

def graph(n,edges,weights,pipes):
    ts=[{'id':10000+i,'pos':'UB','size':2} for i in range(n)]
    ops=[{'id':i+1,'op':'MATMUL' if pipes[i]=='PIPE_M' else 'RELU','pipe':pipes[i],'cycles':weights[i]} for i in range(n)]
    ed=[{'source':i+1,'target':10000+i} for i in range(n)]+[{'source':10000+u,'target':v+1} for u,v in edges]
    # Public-input graph: original DDR inputs/outputs included for each source/sink.
    nid=20000
    ins={v for u,v in edges};outs={u for u,v in edges}
    for i in range(n):
        if i not in ins:
            ts.extend([{'id':nid,'pos':'DDR','size':2},{'id':nid+1,'pos':'UB','size':2}]);ops.append({'id':nid+2,'op':'COPY_IN','pipe':'PIPE_MTE2','cycles':0});ed.extend([{'source':nid,'target':nid+2},{'source':nid+2,'target':nid+1},{'source':nid+1,'target':i+1}]);nid+=3
        if i not in outs:
            ts.append({'id':nid,'pos':'DDR','size':2});ops.append({'id':nid+1,'op':'COPY_OUT','pipe':'PIPE_MTE3','cycles':0});ed.extend([{'source':10000+i,'target':nid+1},{'source':nid+1,'target':nid}]);nid+=2
    return {'ops':ops,'tensors':ts,'edges':ed}

def main():
    p=argparse.ArgumentParser();p.add_argument('--official',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();sys.dont_write_bytecode=True;sys.path.insert(0,str(a.official/'code'))
    from stub_multicore_cut_and_schedule import derive_multicore_plan
    from evaluation_validation import validate_task_order
    seed=2026092303;rng=random.Random(seed);profiles=0;coarsening=0;cover=0;merges=0;start=time.perf_counter()
    for _ in range(300):
        n=rng.randrange(2,22);ed=[(i,j) for i in range(n) for j in range(i+1,n) if rng.random()<.12];w=[rng.randrange(0,300) for _ in range(n)];pipes=[rng.choice(['PIPE_M','PIPE_V']) for _ in range(n)]
        ops={i:{'id':i,'cycles':w[i],'pipe':pipes[i]} for i in range(n)};pr={i:set() for i in ops};su={i:set() for i in ops}
        for u,v in ed:su[u].add(v);pr[v].add(u)
        mat,order=packet_profile(list(ops),ops,pr,su)
        for rep in range(8):
            x=[rng.randrange(0,10000) for _ in range(3)];cl=x[:2];ends={}
            for v in order:
                k=0 if pipes[v]=='PIPE_M' else 1;t=max(cl[k],x[2],max((ends[u] for u in pr[v]),default=0))+max(1,w[v]);cl[k]=t;ends[v]=t
            assert mat_apply(mat,x)==cl+[max(ends.values())];profiles+=1
        g=graph(n,ed,w,pipes)
        for kind in ['chain','nr']:
            groups=initial_groups(g,kind);mapping={str(v):b for b,ns in enumerate(groups) for v in ns}
            # Reconstruct a common topological block order via original integer op order.
            from probe_candidates import topo_order
            bb={int(v):b for v,b in mapping.items()};pp={b:set() for b in range(len(groups))};ss={b:set() for b in pp}
            for u,v in ed:
                x,y=bb[u+1],bb[v+1]
                if x!=y:ss[x].add(y);pp[y].add(x)
            top=topo_order(ss,pp,ss,{b:1 for b in ss});plan={'node_to_subgraph':mapping,'core_schedules':[top]};validate_task_order(derive_multicore_plan(g,plan));coarsening+=1
        N=rng.randrange(1,6);sched=[[] for _ in range(N)]
        for i in range(n):sched[rng.randrange(N)].append(i)
        plan={'node_to_subgraph':{str(i+1):i for i in range(n)},'core_schedules':sched}
        f,d=fuse_cover(g,plan,5,bool(rng.randrange(2)));validate_task_order(derive_multicore_plan(g,f));cover+=1;merges+=len(d['merges'])
    report={'seed':seed,'graphs':300,'compute_profile_checks':profiles,'chain_or_nr_quotient_checks':coarsening,'cover_contraction_cases':cover,'accepted_contractions_checked':merges,'failures':0,'seconds':time.perf_counter()-start,'scope':'compute profile and task-poset invariants ONLY; no E0 performance/equivalence theorem'}
    a.out.write_text(json.dumps(report,indent=2));print(report)
if __name__=='__main__':main()
