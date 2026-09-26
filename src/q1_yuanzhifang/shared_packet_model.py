"""Capacity/gate model and direct shared-input job-pipeline constructor.

The default CLI is a read-only diagnostic; --plan emits one submission plan.
No Task compilation or evaluator is invoked by either mode. The
duration proxy ignores official FIFO and shared-DDR contention; it is neither
an official score nor a lower/upper bound on Makespan.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import heapq
import json
import math
from pathlib import Path


class Unsupported(ValueError):
    pass


def model(graph, cores, capacity, bandwidth, same_wait, cross_wait, *, include_jobs=False):
    ops = {o['id']: o for o in graph['ops'] if o['op'] not in ('COPY_IN', 'COPY_OUT')}
    tensors = {t['id']: t for t in graph['tensors']}
    all_ops = {o['id']: o for o in graph['ops']}
    full_pr, full_co = defaultdict(set), defaultdict(set)
    full_pred, full_succ = ({u:set() for u in all_ops} for _ in range(2))
    for e in graph['edges']:
        a,b=e['source'],e['target']
        if a in all_ops and b in tensors: full_pr[b].add(a)
        if a in tensors and b in all_ops: full_co[a].add(b)
        if a in all_ops and b in all_ops: full_pred[b].add(a); full_succ[a].add(b)
    for t in tensors:
        for a in full_pr[t]:
            for b in full_co[t]: full_pred[b].add(a); full_succ[a].add(b)
    degree={u:len(ps) for u,ps in full_pred.items()}
    ready=[u for u in all_ops if not degree[u]]; heapq.heapify(ready)
    full_order=[]; before=dict.fromkeys(all_ops,False); after=dict(before)
    while ready:
        u=heapq.heappop(ready); full_order.append(u)
        for v in full_succ[u]:
            before[v] |= before[u] or u in ops
            degree[v]-=1
            if not degree[v]: heapq.heappush(ready,v)
    if len(full_order)!=len(all_ops): raise Unsupported('cyclic full op graph')
    for u in reversed(full_order):
        for v in full_succ[u]: after[u] |= after[v] or v in ops
    if any(before[u] and after[u] for u in all_ops if u not in ops):
        raise Unsupported('excluded COPY bridge requires a different component model')
    producers, consumers = defaultdict(set), defaultdict(set)
    incident, preds, succs = ({u: set() for u in ops} for _ in range(3))
    original_out = set()
    for e in graph['edges']:
        a, b = e['source'], e['target']
        if a in ops and b in tensors:
            producers[b].add(a); incident[a].add(b)
        if a in tensors and b in ops:
            consumers[a].add(b); incident[b].add(a)
        if a in tensors and b in all_ops and all_ops[b]['op'] == 'COPY_OUT':
            original_out.add(a)
        if a in ops and b in ops:
            succs[a].add(b); preds[b].add(a)
    for t in tensors:
        for a in producers[t]:
            for b in consumers[t]:
                succs[a].add(b); preds[b].add(a)
    degree = {u: len(preds[u]) for u in ops}
    ready = [u for u in ops if not degree[u]]; heapq.heapify(ready)
    depth = dict.fromkeys(ops, 0); order = []
    while ready:
        u = heapq.heappop(ready); order.append(u)
        for v in succs[u]:
            depth[v] = max(depth[v], depth[u]+1); degree[v] -= 1
            if not degree[v]: heapq.heappush(ready, v)
    if len(order) != len(ops): raise Unsupported('cyclic graph')
    unseen, jobs = set(ops), []
    while unseen:
        start = min(unseen); unseen.remove(start); stack, nodes = [start], []
        while stack:
            u = stack.pop(); nodes.append(u)
            for v in preds[u] | succs[u]:
                if v in unseen: unseen.remove(v); stack.append(v)
        jobs.append(sorted(nodes, key=lambda u: (depth[u], u)))
    jobs.sort(key=min)
    if not 2 <= len(jobs) <= 32 or not 1 <= cores <= 5:
        raise Unsupported('requires 2..32 jobs and 1..5 cores')
    length = len(jobs[0]); positions = {u:i for job in jobs for i,u in enumerate(job)}
    def signature(job):
        return [(ops[u]['op'], ops[u]['pipe'], ops[u]['cycles'],
                 sorted(positions[v] for v in preds[u])) for u in job]
    if not 2 <= length <= 256 or any(len(j) != length or
            len({depth[u] for u in j}) != length or signature(j) != signature(jobs[0]) for j in jobs):
        raise Unsupported('requires identical compute signatures with unique dependency depths')
    if any(o['pipe'] not in ('PIPE_M', 'PIPE_V') or o['cycles'] <= 0 for o in ops.values()):
        raise Unsupported('positive M/V compute required')
    owner = {u:i for i,job in enumerate(jobs) for u in job}
    shared = {t for t in tensors if len({owner[u] for u in consumers[t]}) > 1}
    for t in shared:
        if producers[t] or len({positions[u] for u in consumers[t]}) != 1 or \
                len({owner[u] for u in consumers[t]}) != len(jobs):
            raise Unsupported('shared tensors must be external, same-position inputs of all jobs')
    def size(ids, space):
        return sum(tensors[t]['size'] for t in ids
                   if ('UB' if tensors[t]['pos'] == 'DDR' else tensors[t]['pos']) == space)
    def copies(ids):
        return sum(max(1, math.ceil(tensors[t]['size']/bandwidth)) for t in ids)
    if any(t['pos'] not in ('L1', 'UB', 'DDR') for t in tensors.values()):
        raise Unsupported('unknown tensor memory space')
    # Interval tables are graph metadata. Largest job-local footprint is a
    # conservative capacity allowance; all shared tensors are counted once.
    intervals = {}
    for left in range(length):
        for right in range(left+1, length+1):
            shared_ids, mem, incoming, outgoing = set(), Counter(), 0, 0
            for job in jobs:
                ns = set(job[left:right]); touched = set().union(*(incident[u] for u in ns))
                shared_ids.update(touched & shared)
                for space in capacity: mem[space] = max(mem[space], size(touched-shared, space))
                ins = {t for t in touched-shared if consumers[t] & ns and not producers[t] & ns}
                outs = {t for t in touched-shared if producers[t] & ns and
                        (t in original_out or not consumers[t] or consumers[t]-ns)}
                incoming, outgoing = max(incoming, copies(ins)), max(outgoing, copies(outs))
            work = Counter()
            finish = {}
            for u in jobs[0][left:right]:
                work[ops[u]['pipe']] += ops[u]['cycles']
                finish[u] = ops[u]['cycles'] + max((finish.get(v,0) for v in preds[u]), default=0)
            intervals[left,right] = dict(shared={s:size(shared_ids,s) for s in capacity},
                local=dict(mem), work=dict(work), critical=max(finish.values()),
                shared_copy=copies(shared_ids), private_copy=incoming+outgoing)
    def duration(row, batch):
        dominant = max(row['work'].values())
        return max(batch*dominant, row['shared_copy']+batch*row['private_copy']) + \
            max(0, row['critical']-dominant)
    answers = []
    for packets in range(1,len(jobs)+1):
        q, rem = divmod(len(jobs),packets)
        sizes = [q+int(i<rem) for i in range(packets)]; batch=max(sizes)
        dp, parent = {(0,0):(0,0)}, {}
        for stages in range(1,min(cores,length)+1):
            for end in range(stages,length+1):
                choices=[]
                for start in range(end-1,stages-2,-1):
                    row=intervals[start,end]
                    if any(row['shared'][s]+batch*row['local'][s] > capacity[s] for s in capacity):
                        break
                    if (stages-1,start) not in dp: continue
                    peak,total=dp[stages-1,start]; d=duration(row,batch)
                    choices.append((max(peak,d),total+d,start))
                if choices:
                    best=min(choices); dp[stages,end]=best[:2]; parent[stages,end]=best[2]
            if (stages,length) not in dp: continue
            cuts=[length]; end=length
            for s in range(stages,0,-1): end=parent[s,end]; cuts.append(end)
            cuts=list(reversed(cuts)); rows=[intervals[a,b] for a,b in zip(cuts,cuts[1:])]
            finish={}; traffic=0
            for p,bs in enumerate(sizes):
                for s,row in enumerate(rows):
                    before=max(finish[s-1,p]+cross_wait if s else 0,
                               finish[s,p-1]+same_wait if p else 0)
                    finish[s,p]=before+duration(row,bs)
                    traffic+=row['shared_copy']+bs*row['private_copy']
            answers.append(dict(stages=stages,packets=packets,packet_sizes=sizes,cuts=cuts,
                flow_proxy_cycles=finish[stages-1,packets-1], ddr_service_proxy_cycles=traffic,
                cost_proxy_cycles=max(traffic,finish[stages-1,packets-1]),
                max_resident_union_bytes=[{s:r['shared'][s]+batch*r['local'][s] for s in capacity} for r in rows]))
    result = dict(jobs=len(jobs),positions=length,shared_inputs=len(shared),
        alternatives=sorted(answers,key=lambda a:(a['cost_proxy_cycles'],a['stages']*a['packets'],a['cuts'])),
        scope='Static proxy only, no official score or bound; minimax interval DP then flow/DDRs ranking; no actual plan constructed')
    if include_jobs: result['_jobs'] = jobs
    return result


def construct(graph, cores, capacity, bandwidth, same_wait, cross_wait):
    """One selected rectangle plan, with no evaluator or Task compiler."""
    info = model(graph, cores, capacity, bandwidth, same_wait, cross_wait, include_jobs=True)
    jobs = info.pop('_jobs')
    if not info['alternatives']: raise Unsupported('no conservative resident-union partition')
    best = info['alternatives'][0]
    mapping, schedules = {}, [[] for _ in range(cores)]
    offset, tid = 0, 0
    for packet_size in best['packet_sizes']:
        packet = jobs[offset:offset+packet_size]; offset += packet_size
        for stage,(left,right) in enumerate(zip(best['cuts'],best['cuts'][1:])):
            for job in packet:
                for u in job[left:right]: mapping[str(u)] = tid
            schedules[stage].append(tid); tid += 1
    assert offset == len(jobs) and len(mapping) == sum(map(len,jobs))
    info.update(algorithm_id='q1-shared-packet-pipeline',selected=best,tasks=tid,
                scope='One graph-derived rectangle plan; proxy is not an E0 score or bound; external E0 required')
    return dict(node_to_subgraph=mapping,core_schedules=schedules),info


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('graph',type=Path)
    p.add_argument('--cores',type=int,required=True); p.add_argument('--output',type=Path,required=True)
    p.add_argument('--plan',type=Path,help='If supplied, emit one actual plan plus output diagnostics')
    a=p.parse_args(); raw=a.graph.read_bytes()
    if a.output.exists() or (a.plan and (a.plan.exists() or a.plan==a.output)):
        raise FileExistsError('Refuse to overwrite model/plan artifacts')
    if a.plan:
        plan,result=construct(json.loads(raw),a.cores,{'L1':524288,'UB':131072},60,100,1000)
        a.plan.parent.mkdir(parents=True,exist_ok=True)
        with a.plan.open('x',encoding='utf-8') as f: json.dump(plan,f,separators=(',',':')); f.write('\n')
    else:
        result=model(json.loads(raw),a.cores,{'L1':524288,'UB':131072},60,100,1000)
    result['graph_sha256']=hashlib.sha256(raw).hexdigest()
    result['configuration_scope']='Frozen official P1 values; this diagnostic does not accept arbitrary hardware settings'
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2); f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='alternatives'}))
    print(json.dumps(result['alternatives'][:5]))


if __name__=='__main__': main()
