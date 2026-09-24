#!/usr/bin/env python3
"""Three-state synchronous-packet DP for the mathematical port model.

No official evaluator calls. This constructor is NOT validated against E0.
Q is fixed by capacity. States are {0,Q-1,Q} pending returns. Costs retain
actual Step1/FIFO order and shared DDR; no ratio or packet-size sweep.
"""
from __future__ import annotations
import argparse, json, os, time
from pathlib import Path
import archived_r1 as ar
from one_intact_lane import shape
from port_response import compile_local, simulate


def shortest_packet_path(states, normal, drains):
    """normal[j][r,s]=(response+gate, bytes, task-groups).
    drains[j][r] clears pending r without consuming a new block. Positive costs
    make one drain closure per layer sufficient. Caller initializes first gate.
    Returns lexicographically optimal (cycles,bytes,task-groups) and actions.
    """
    def plus(a,b):return tuple(x+y for x,y in zip(a,b))
    # Score here includes one gate per task; caller removes the first gate.
    current={0:((0,0,0),None)}
    def close(j,table):
        result=dict(table)
        for r,(value,path) in table.items():
            if r and r in drains[j]:
                candidate=plus(value,drains[j][r])
                if 0 not in result or candidate < result[0][0]:
                    result[0]=(candidate,(path,('drain',j,r,0)))
        return result
    for j,edges in enumerate(normal):
        current=close(j,current);nxt={}
        for r,(value,path) in current.items():
            for s in states:
                if (r,s) not in edges:continue
                candidate=plus(value,edges[(r,s)])
                if s not in nxt or candidate < nxt[s][0]:
                    nxt[s]=(candidate,(path,('normal',j,r,s)))
        current=nxt
    current=close(len(normal),current)
    if 0 not in current:
        raise ar.Unsupported('no certified symmetric path')
    value,path=current[0];actions=[]
    while path is not None:
        path,action=path;actions.append(action)
    actions.reverse()
    return value,actions


def construct(graph,cores,capacity,bandwidth=60,gate=100):
    chains,Q,footprint=shape(graph,cores,capacity)
    rounds=len(chains)//(cores*Q)
    if rounds < 1:raise ar.Unsupported('no full symmetric packet round')
    v=ar.views(graph);eligible={u for u,o in v.ops.items() if o['op'] not in ar.COPY}
    direct={u:[] for u in eligible}
    for e in graph['edges']:
        if e['source'] in eligible and e['target'] in eligible:
            direct[e['source']].append(e['target'])
    base=max(set(v.ops)|set(v.tensors))+1
    bins=[chains[k::cores] for k in range(cores)]
    blocks=[[line[j*Q:(j+1)*Q] for j in range(rounds)] for line in bins]
    states=tuple(sorted({0,Q-1,Q}))

    def members(k,j,r,s,drain=False):
        previous=blocks[k][j-1][-r:] if r else []
        if drain:return [c[-1] for c in previous]
        new=blocks[k][j]
        whole=new[:Q-s];prefix=new[Q-s:] if s else []
        return ([u for c in whole for u in c]+[u for c in prefix for u in c[:-1]]+
                [c[-1] for c in previous])

    def local_graph(nodes):
        """Same boundary predicates and op-comparison order as frozen P1.
        Temporary model COPY IDs preserve order and exceed all original op IDs.
        They never appear in the submitted plan. No official source is edited.
        """
        ns=set(nodes);touched=set()
        for u in ns:touched.update(v.in_t[u]|v.out_t[u])
        ops=[dict(v.ops[u]) for u in sorted(ns)];tensors=[];edges=[];newid=base;copybytes=0
        for tid in sorted(touched):
            t=dict(v.tensors[tid]);ps=v.producers[tid]&ns;cs=v.consumers[tid]&ns
            allcs=v.consumers[tid]&eligible
            h=any(v.ops[u]['op']=='COPY_OUT' for u in v.consumers[tid])
            if t['pos']=='DDR':t['pos']='UB'
            tensors.append(t)
            edges.extend({'source':u,'target':tid} for u in sorted(ps))
            edges.extend({'source':tid,'target':u} for u in sorted(cs))
            for incoming,on in ((True,bool(cs) and not ps),
                                (False,bool(ps) and (h or not allcs or bool(allcs-ns)))):
                if not on:continue
                d,c=newid,newid+1;newid+=2
                tensors.append({'id':d,'pos':'DDR','size':t['size']})
                ops.append({'id':c,'op':'COPY_IN' if incoming else 'COPY_OUT',
                            'pipe':'PIPE_MTE2' if incoming else 'PIPE_MTE3',
                            'cycles':max(1,ar.ceildiv(t['size'],bandwidth))})
                links=((d,c),(c,tid)) if incoming else ((tid,c),(c,d))
                edges.extend({'source':a,'target':b} for a,b in links)
                copybytes+=t['size']
        for u in sorted(ns):
            edges.extend({'source':u,'target':w} for w in direct[u] if w in ns)
        return {'ops':ops,'tensors':tensors,'edges':edges},copybytes

    cache={};profile_rows=[];rejected=[]
    def profile(j,r,s,drain=False):
        tasks=[];bytecounts=[]
        for k in range(cores):
            local,bytes_=local_graph(members(k,j,r,s,drain))
            try:task,_=compile_local(local,-1,capacity,bandwidth)
            except ar.Unsupported as e:
                rejected.append({'j':j,'r':r,'s':s,'drain':drain,'reason':str(e)})
                return None
            tasks.append(task);bytecounts.append(bytes_)
        sig=tasks[0].signature()
        if any(t.signature()!=sig for t in tasks[1:]):
            rejected.append({'j':j,'r':r,'s':s,'drain':drain,'reason':'non-identical compiled FIFO port signatures'})
            return None
        if sig not in cache:cache[sig]=simulate([[tasks[0].scaled_ddr(cores)]],gate)
        ans=cache[sig]
        profile_rows.append({'j':j,'r':r,'s':s,'drain':drain,'response':ans['makespan'],
                             'service':ans['service_cycles'],'bytes':sum(bytecounts)})
        return ans['makespan']+gate,sum(bytecounts),1

    normal=[];drains=[]
    for j in range(rounds+1):
        dr={}
        if j:
            for r in states:
                if r:
                    value=profile(j,r,0,True)
                    if value is not None:dr[r]=value
        drains.append(dr)
        if j==rounds:break
        row={}
        for r in states if j else (0,):
            for s in states:
                value=profile(j,r,s)
                if value is not None:row[(r,s)]=value
        normal.append(row)
    score,actions=shortest_packet_path(states,normal,drains)
    tailtasks=[];tailbytes=0
    for k,line in enumerate(bins):
        nodes=[u for c in line[rounds*Q:] for u in c]
        if nodes:
            local,b=local_graph(nodes);t,_=compile_local(local,-1,capacity,bandwidth)
            tailtasks.append([t]);tailbytes+=b
        else:tailtasks.append([])
    tail=simulate(tailtasks,gate) if any(tailtasks) else None
    model_cycles=score[0]-gate+(gate+tail['makespan'] if tail else 0)
    orders=[[] for _ in range(cores)];mapping={};task_id=0
    for k in range(cores):
        for kind,j,r,s in actions:
            nodes=members(k,j,r,s,kind=='drain')
            if nodes:
                orders[k].append(task_id)
                for u in nodes:
                    if u in mapping:raise AssertionError('duplicate mapping')
                    mapping[u]=task_id
                task_id+=1
        nodes=[u for c in bins[k][rounds*Q:] for u in c]
        if nodes:
            orders[k].append(task_id)
            for u in nodes:mapping[u]=task_id
            task_id+=1
    plan={'node_to_subgraph':{o['id']:mapping[o['id']] for o in graph['ops'] if o['op'] not in ar.COPY},
          'core_schedules':orders}
    ar.validate_plan_structure(graph,plan)
    return plan,dict(algorithm='three-state-renewal-dp-v1',Q=Q,states=states,rounds=rounds,
        model_makespan=model_cycles,model_scheduled_bytes=score[1]+tailbytes,
        transition_profiles=len(profile_rows),unique_response_profiles=len(cache),
        rejected=rejected,actions=actions,profiles=profile_rows,tail=tail,
        scope='Optimal only in the declared, signature-certified synchronous packet class and mathematical model; NOT E0/global optimum')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('graph',type=Path)
    p.add_argument('--cores',type=int,required=True);p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args()
    if args.output_dir.exists():raise FileExistsError('refuse overwrite')
    start=time.perf_counter();g=json.loads(args.graph.read_bytes())
    plan,info=construct(g,args.cores,{'L1':524288,'UB':131072})
    args.output_dir.mkdir(parents=True)
    with (args.output_dir/'plan.json').open('xb') as f:
        f.write((json.dumps(plan,separators=(',',':'))+'\n').encode());f.flush();os.fsync(f.fileno())
    info['read_through_selection_to_plan_fsync_seconds']=time.perf_counter()-start
    info['official_calls']={'E0':0,'E1':0,'E2':0}
    (args.output_dir/'diagnostics.json').write_text(json.dumps(info,indent=2))
    print(json.dumps({k:info[k] for k in ('algorithm','Q','model_makespan','unique_response_profiles','read_through_selection_to_plan_fsync_seconds')}))

if __name__=='__main__':main()
