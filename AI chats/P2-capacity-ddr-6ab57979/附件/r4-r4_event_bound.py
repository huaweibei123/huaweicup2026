#!/usr/bin/env python3
"""Static P2 mandatory-I/O *integer-event* lower bound. No E0/E1/E2.

Usage:
  python r4_event_bound.py --evidence-root EXTRACTED_R4 --graph GRAPH.json \
      --cores 5 --head-budget 32 --output CERTIFICATE.json

This is a new proof-oriented prototype, NOT tested on the absent 100 graphs.
Its COPY lower duration is ONE integer cycle, not ceil(bytes / bandwidth).
No plan, owner, FIFO, spill insertion or Step3 preparation is constructed.
The theorem is conditional on successful frozen E0 execution of feasible plans.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import heapq
import json
from pathlib import Path
import sys

PIPES = ('PIPE_MTE2', 'PIPE_MTE3', 'PIPE_M', 'PIPE_V')
SOURCE_HASHES = {
    'evaluation_validation.py': '103206b8c5c25e37de50cc3193de3989d7c1e01d4a11cc5f509dedd8f9be9a64',
    'stub_multicore_cut_and_schedule.py': '0a3a3b79b5173b466fc05fc8d33b72d11d90b4df78995435853d91c632a35892',
    'multicore_cut_evaluate_problem_1.py': '2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f',
    'multicore_cut_evaluate_problem_2.py': '0b39f84d5ec0a7fba9a4c92a598a9044b97ab79c71393824c1ba130ecfe6c464',
    'schedule_step2.py': '2836baac176f4e0bdd9eec59b8d9ce254e209e5f7a251e23837ab684312fa0c3',
    'schedule_step3.py': '50053db0436f1d166dd75436693ba3af49b5c339576beb6e7299477f6b69fc7a',
}
CONFIG_HASH = 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def packing(nodes, duration, k):
    ordered = sorted(nodes, key=lambda u: (-duration[u], u))
    prefix = [0]
    for u in ordered:
        prefix.append(prefix[-1] + duration[u])
    best = {'kind': 'pipe_total', 'cycles': (prefix[-1]+k-1)//k,
            'work': prefix[-1]}
    for q in range(1, (len(ordered)+k-1)//k + 1):
        m = (q-1)*k+1
        value = prefix[m]-prefix[m-q]
        if value > best['cycles']:
            best = {'kind': 'pipe_indivisible', 'cycles': value, 'q': q, 'm': m}
    if best['kind'] == 'pipe_indivisible':
        q,m = best['q'],best['m']
        best.update(largest_prefix_nodes=ordered[:m], smallest_q_nodes=ordered[m-q:m])
    else:
        best['nodes'] = ordered
    return best


def evaluate_relaxation(duration, pipe, succ, k, head_budget):
    """Integer DAG/pipe inequalities, with explicit maximizing witnesses."""
    pred = {u: set() for u in duration}
    for u in duration:
        for v in succ[u]:
            pred[v].add(u)
    degree = {u: len(pred[u]) for u in duration}
    ready = [u for u in duration if not degree[u]]
    heapq.heapify(ready)
    order, head, previous = [], {}, {}
    while ready:
        u = heapq.heappop(ready)
        parent = max(pred[u], key=lambda v: (head[v]+duration[v], v), default=None)
        head[u] = 0 if parent is None else head[parent]+duration[parent]
        previous[u] = parent
        order.append(u)
        for v in sorted(succ[u]):
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, v)
    if len(order) != len(duration):
        raise ValueError('Relaxation has a cycle')
    tail = {}
    for u in reversed(order):
        tail[u] = max((duration[v]+tail[v] for v in succ[u]), default=0)
    last = max(duration, key=lambda u: (head[u]+duration[u], u), default=None)
    cp = 0 if last is None else head[last]+duration[last]
    path = []
    while last is not None:
        path.append(last); last = previous[last]
    best = {'kind': 'critical_path', 'cycles': cp, 'nodes': path[::-1]}
    scans = 0
    for p in PIPES:
        group = [u for u in duration if pipe[u] == p]
        pack = packing(group, duration, k)
        pack['pipe'] = p
        if pack['cycles'] > best['cycles']:
            best = pack
        # Both old one-sided threshold families: identical mathematical family
        # to global_bounds.py, including full tied threshold groups.
        for axis, left, right in [('head', head, tail), ('tail', tail, head)]:
            ordered = sorted(group, key=lambda u: (-left[u], u))
            total, other, chosen, i = 0, None, [], 0
            while i < len(ordered):
                threshold = left[ordered[i]]
                while i < len(ordered) and left[ordered[i]] == threshold:
                    u = ordered[i]; chosen.append(u); total += duration[u]
                    other = right[u] if other is None else min(other, right[u])
                    i += 1
                value = threshold+(total+k-1)//k+other
                if value > best['cycles']:
                    a,b = (threshold,other) if axis == 'head' else (other,threshold)
                    best = {'kind':'pipe_window', 'pipe':p, 'cycles':value,
                            'head_threshold':a, 'tail_threshold':b,
                            'selected_count':len(chosen), 'work':total}
        # At most head_budget head thresholds, but every tail threshold for
        # each chosen head. Sorting is reused. Every witness remains valid.
        heads = sorted({head[u] for u in group})
        if head_budget and heads:
            if len(heads) > head_budget:
                if head_budget == 1:
                    heads = heads[:1]
                else:
                    heads = [heads[j*(len(heads)-1)//(head_budget-1)]
                             for j in range(head_budget)]
            tails_order = sorted(group, key=lambda u: (-tail[u], u))
            for a in heads:
                scans += 1
                chosen, total, i = [], 0, 0
                while i < len(tails_order):
                    b = tail[tails_order[i]]
                    while i < len(tails_order) and tail[tails_order[i]] == b:
                        u = tails_order[i]
                        if head[u] >= a:
                            chosen.append(u); total += duration[u]
                        i += 1
                    if chosen:
                        value = a+(total+k-1)//k+b
                        if value > best['cycles']:
                            best = {'kind':'pipe_two_threshold_window', 'pipe':p,
                                    'cycles':value, 'head_threshold':a,
                                    'tail_threshold':b, 'selected_count':len(chosen), 'work':total}
    if best['kind'] in ('pipe_window','pipe_two_threshold_window'):
        best['nodes'] = sorted(u for u in duration if pipe[u] == best['pipe']
                               and head[u] >= best['head_threshold']
                               and tail[u] >= best['tail_threshold'])
    return {'lower_bound_cycles':best['cycles'], 'maximizing_witness':best,
            'head':head, 'tail':tail, 'critical_path_cycles':cp,
            'extra_head_scans':scans}


def certify(graph, k, validate_graph, head_budget=32):
    """Use the frozen validator supplied by the caller; never execute a plan."""
    if type(k) is not int or not 1 <= k <= 5:
        raise ValueError('cores must be 1..5')
    if type(head_budget) is not int or not 0 <= head_budget <= 1024:
        raise ValueError('head budget must be 0..1024')
    validate_graph(graph)
    original = {x['id']: x for x in graph['ops']}
    if any(not isinstance(x.get('op'),str) for x in original.values()):
        raise ValueError('op types must be strings')
    tensors = {x['id']:x for x in graph['tensors']}
    if any('logical_tid' in t for t in tensors.values()):
        raise ValueError('prototype conservatively abstains on logical_tid metadata')
    eligible = {u for u,x in original.items() if x['op'] not in ('COPY_IN','COPY_OUT')}
    producers,consumers = defaultdict(set),defaultdict(set)
    direct = []
    for e in graph['edges']:
        a,b = e['source'],e['target']
        if a in original and b in tensors:
            producers[b].add(a)
        elif a in tensors and b in original:
            consumers[a].add(b)
        elif a in eligible and b in eligible:
            direct.append((a,b))
    if any(len(producers[t] & eligible)>1 for t in tensors):
        raise ValueError('precedence proof requires at most one eligible producer')
    key = lambda u: 'op:'+str(u)
    d = {key(u):max(1,original[u]['cycles']) for u in eligible}
    p = {key(u):original[u]['pipe'] for u in eligible}
    succ = {u:set() for u in d}
    for a,b in direct:
        succ[key(a)].add(key(b))
    for tid in tensors:
        for a in producers[tid] & eligible:
            for b in consumers[tid] & eligible:
                succ[key(a)].add(key(b))
    old = evaluate_relaxation(d,p,succ,k,0)
    boundary = []
    for tid,tensor in sorted(tensors.items()):
        ps,cs = producers[tid]&eligible,consumers[tid]&eligible
        if cs and not ps:
            u='in:'+str(tid); d[u]=1; p[u]='PIPE_MTE2'
            succ[u]={key(v) for v in cs}
            boundary.append({'node':u,'role':'input','tensor_id':tid,
                             'bytes':tensor['size'],'consumers':sorted(cs),
                             'event_duration_lower_bound':1})
        final = ps and (not cs or any(original[v]['op']=='COPY_OUT' for v in consumers[tid]))
        if final:
            producer=next(iter(ps)); u='out:'+str(tid)
            d[u]=1; p[u]='PIPE_MTE3'; succ[u]=set(); succ[key(producer)].add(u)
            boundary.append({'node':u,'role':'output','tensor_id':tid,
                             'bytes':tensor['size'],'producer':producer,
                             'event_duration_lower_bound':1})
    new = evaluate_relaxation(d,p,succ,k,head_budget)
    return {'scope':'global_frozen_integer_event_relaxation', 'cores':k,
            'graph_domain':'validated input; unique eligible producer; prototype rejects logical_tid',
            'conditional_on':'successful finite return of the pinned official E0',
            'compute_only_L':old['lower_bound_cycles'],
            'event_io_L':max(old['lower_bound_cycles'],new['lower_bound_cycles']),
            'compute_only_certificate':old, 'augmented_certificate':new,
            'boundary_nodes':boundary, 'duration':d, 'pipe':p,
            'retained_augmented_edges':[[u,v] for u in sorted(succ) for v in sorted(succ[u])],
            'DDR_service_bound_certified':False,
            'evaluator_calls':0, 'plan_constructor_calls':0}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence-root',required=True,type=Path)
    ap.add_argument('--graph',required=True,type=Path)
    ap.add_argument('--cores',required=True,type=int)
    ap.add_argument('--head-budget',type=int,default=32)
    ap.add_argument('--output',required=True,type=Path)
    a=ap.parse_args(); root=a.evidence_root.resolve()
    official=root/'data/raw/a/official/code'
    for name,digest in SOURCE_HASHES.items():
        if sha(official/name)!=digest:
            raise ValueError('frozen source mismatch: '+name)
    if sha(root/'data/raw/a/official/data/config.txt')!=CONFIG_HASH:
        raise ValueError('frozen config mismatch')
    sys.path.insert(0,str(official))
    from evaluation_validation import validate_graph
    result=certify(json.loads(a.graph.read_bytes()),a.cores,validate_graph,a.head_budget)
    result.update(graph_sha256=sha(a.graph),config_sha256=CONFIG_HASH,
                  official_source_sha256=SOURCE_HASHES,
                  certificate_program_sha256=sha(Path(__file__)))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:
        json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'compute_only_L':result['compute_only_L'],
                      'event_io_L':result['event_io_L'],'E0_E1_E2_calls':0}))

if __name__=='__main__':
    main()
