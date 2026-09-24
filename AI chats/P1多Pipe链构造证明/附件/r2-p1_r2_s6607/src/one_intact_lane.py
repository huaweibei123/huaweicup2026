#!/usr/bin/env python3
"""One new P1 candidate: identical mixed packets, one intact lane per packet.
This module generates only node_to_subgraph/core_schedules and diagnostics.
It calls no official evaluator. No q/s sweep, case ID, or historical lookup.
"""
from __future__ import annotations
from pathlib import Path
import argparse, json, os, time
import archived_r1 as ar
from port_response import compile_plan, quotient


def shape(graph, cores, capacity):
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError('cores must be integer in 1..5')
    v, chains, _, _, _ = ar.recognize(graph)
    def footprint(nodes):
        touched=set()
        for u in nodes:
            touched.update(v.in_t[u] | v.out_t[u])
        return {p:sum(v.tensors[t]['size'] for t in touched
                      if ('UB' if v.tensors[t]['pos']=='DDR' else v.tensors[t]['pos'])==p)
                for p in capacity}
    pref=footprint(chains[0][:-1]);ret=footprint(chains[0][-1:]);whole=footprint(chains[0])
    mixed={p:pref[p]+ret[p] for p in capacity}
    q=min([(len(chains)+cores-1)//cores]+
          [capacity[p]//mixed[p] for p in capacity if mixed[p]])
    if q < 1:
        raise ar.Unsupported('no virgin-capacity packet')
    return chains, q, dict(prefix=pref, return_=ret, whole=whole, mixed=mixed)


def construct(graph, cores, capacity):
    chains,Q,fp=shape(graph,cores,capacity)
    if Q < 2:
        raise ar.Unsupported('one intact lane leaves no return lane')
    rounds=len(chains)//(cores*Q)
    if rounds < 1:
        raise ar.Unsupported('no full symmetric round; retain old candidate')
    bins=[chains[k::cores] for k in range(cores)]
    orders=[[] for _ in range(cores)];mp={};task=0
    def emit(k,nodes):
        nonlocal task
        if not nodes:return
        orders[k].append(task)
        for u in nodes:
            if u in mp:raise AssertionError('duplicate node')
            mp[u]=task
        task+=1
    for k,chainlist in enumerate(bins):
        previous=[]
        for j in range(rounds):
            block=chainlist[j*Q:(j+1)*Q]
            intact=block[0];new=block[1:]
            emit(k, list(intact)+[u for c in new for u in c[:-1]]+
                    [c[-1] for c in previous])
            previous=new
        emit(k,[c[-1] for c in previous])
        emit(k,[u for c in chainlist[rounds*Q:] for u in c])
    plan={'node_to_subgraph':{o['id']:mp[o['id']] for o in graph['ops'] if o['op'] not in ar.COPY},
          'core_schedules':orders}
    ar.validate_plan_structure(graph,plan)
    details=dict(algorithm='one-intact-lane-v1',Q=Q,return_lanes=Q-1,intact_lanes=1,
                 full_rounds=rounds,cut_chains=cores*rounds*(Q-1),chains=len(chains),
                 footprint=fp,capacity=capacity,
                 scope='Candidate only; port-model certificates are not E0 acceptance')
    return plan,details


def allcut(graph,cores,capacity):
    chains,Q,fp=shape(graph,cores,capacity)
    plan=ar.encode(chains,graph['ops'],cores,packet=Q,cut_count=len(chains),whole_packet=1)
    return plan,dict(algorithm='capacity-derived-all-cut-reference',Q=Q,chains=len(chains),footprint=fp)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('graph',type=Path);p.add_argument('--cores',type=int,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--reference',action='store_true',help='All-cut reference, not a search')
    args=p.parse_args()
    if args.output_dir.exists():raise FileExistsError('refuse to overwrite artifacts')
    args.output_dir.mkdir(parents=True)
    start=time.perf_counter();g=json.loads(args.graph.read_bytes())
    cap={'L1':524288,'UB':131072}
    plan,details=(allcut if args.reference else construct)(g,args.cores,cap)
    raw=(json.dumps(plan,separators=(',',':'))+'\n').encode()
    with (args.output_dir/'plan.json').open('xb') as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    details['read_to_plan_fsync_seconds']=time.perf_counter()-start
    ts=time.perf_counter();lines,footprints=compile_plan(g,plan,cap,60)
    details['model_compile_seconds']=time.perf_counter()-ts
    ts=time.perf_counter();response=quotient(lines,100)
    details['model_response_seconds']=time.perf_counter()-ts
    details['model_response']=response
    details['boundary']=ar.boundary_counts(g,plan,60)
    # Keep compact diagnostics; full boundary list is separately recoverable.
    details['boundary'].pop('by_tensor',None)
    details['all_task_virgin_capacity_checked']=True
    details['footprints']=footprints
    details['official_calls']={'E0':0,'E1':0,'E2':0}
    with (args.output_dir/'model.json').open('x') as f:json.dump(details,f,indent=2)
    print(json.dumps({k:details[k] for k in ('algorithm','Q','read_to_plan_fsync_seconds',
          'model_compile_seconds','model_response_seconds','boundary')}|{'model_makespan':response['makespan'],
          'equal_rounds':response['equal_rounds'],'distinct_responses':response['distinct_round_responses']}))

if __name__=='__main__':main()
