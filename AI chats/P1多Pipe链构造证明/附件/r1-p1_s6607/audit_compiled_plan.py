#!/usr/bin/env python3
"""Read-only frozen compiler audit. NOT EXECUTED in this delivered study.

Calls _build_scene_a_tasks once (including official Step1/2/3), but does NOT
call evaluate_scene_a/E0. Exports actual memory edges and a FIXED-PLAN lower
bound. The output is emphatically NOT a universal original-problem lower bound.
"""
import argparse,hashlib,heapq,json,sys,time
from pathlib import Path
from integrate_frozen import verify_checkout
from p1_phase_cut import FROZEN_COMMIT,atomic_json

def longest(nodes,edges,duration):
    pred={u:set() for u in nodes};succ={u:set() for u in nodes}
    for u,v in edges:pred[v].add(u);succ[u].add(v)
    degree={u:len(ps) for u,ps in pred.items()};ready=[u for u in nodes if not degree[u]];heapq.heapify(ready)
    end={};parent={}
    while ready:
        u=heapq.heappop(ready)
        p=max(pred[u],key=lambda p:(end[p],-p)) if pred[u] else None
        parent[u]=p;end[u]=(end[p] if p is not None else 0)+duration[u]
        for v in succ[u]:
            degree[v]-=1
            if not degree[v]:heapq.heappush(ready,v)
    if len(end)!=len(nodes):raise ValueError('augmented graph cycle')
    last=max(nodes,key=lambda u:(end[u],-u));path=[];u=last
    while u is not None:path.append(u);u=parent[u]
    return end[last],list(reversed(path))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('graph',type=Path);ap.add_argument('plan',type=Path);ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();root=a.repo.resolve();verify_checkout(root)
    sys.path.insert(0,str(root/'data/raw/a/official/code'))
    from multicore_cut_evaluate_problem_1 import _build_scene_a_tasks
    from schedule_step3 import _op_duration,_uses_ddr_bandwidth
    graph=json.loads(a.graph.read_text());plan=json.loads(a.plan.read_text())
    t=time.perf_counter();tasks,cross,traffic,view=_build_scene_a_tasks(graph,plan,60,{'L1':524288,'UB':131072});compile_wall=time.perf_counter()-t
    outputs={};lam={};ddr=0
    for ident,task in tasks.items():
        edges={(u,v) for v,ps in task['op_preds'].items() for u in ps}
        fifo={(u,v) for order in task['pipe_ops'].values() for u,v in zip(order,order[1:])};edges|=fifo
        durations={u:_op_duration(o,task['in_tids'],task['out_tids'],task['tensor_by_id'],60) for u,o in task['op_by_id'].items()}
        lam[ident],witness=longest(list(task['op_by_id']),edges,durations)
        ddr+=sum(durations[u] for u,o in task['op_by_id'].items() if _uses_ddr_bandwidth(o,task['in_tids'],task['out_tids'],task['tensor_by_id']))
        outputs[ident]={'core_id':task['core_id'],'seq':task['seq'],'pipe_orders':task['pipe_ops'],
            'memory_dependencies':task['step3']['memory_dependencies'],'execution_edges':task['graph']['edges'],
            'exclusive_durations':durations,'fixed_task_relaxed_longest_path':lam[ident],
            'longest_path_op_ids':witness,'standalone_compiler_makespan_NOT_a_universal_bound':task['step3']['makespan']}
    pred={t:{} for t in tasks};succ={t:set() for t in tasks}
    def edge(u,v,w):pred[v][u]=max(pred[v].get(u,0),w);succ[u].add(v)
    for u,v in view['dependency_pairs']:edge(u,v,1000 if tasks[u]['core_id']!=tasks[v]['core_id'] else 0)
    for order in view['core_orders'].values():
        for u,v in zip(order,order[1:]):edge(u,v,100)
    deg={t:len(ps) for t,ps in pred.items()};ready=[t for t,d in deg.items() if not d];heapq.heapify(ready);end={}
    while ready:
        u=heapq.heappop(ready);end[u]=lam[u]+max((end[p]+w for p,w in pred[u].items()),default=0)
        for v in succ[u]:
            deg[v]-=1
            if not deg[v]:heapq.heappush(ready,v)
    if len(end)!=len(tasks):raise ValueError('Task+core-order cycle')
    out={'kind':'FIXED_PLAN_compiler_audit_NOT_universal_bound_NOT_E0','frozen_commit':FROZEN_COMMIT,
         'graph_sha256':hashlib.sha256(a.graph.read_bytes()).hexdigest(),'plan_sha256':hashlib.sha256(a.plan.read_bytes()).hexdigest(),
         'actual_calls':{'official_Task_build_including_Step1_2_3':1,'E0':0,'E1':0,'E2':0},
         'compile_wall_seconds_NOT_complete_process_wall':compile_wall,'traffic':traffic,'tasks':outputs,
         'fixed_plan_DDR_service_bound':ddr,'fixed_plan_gate_path_bound':max(end.values(),default=0),
         'fixed_plan_lower_bound':max(ddr,max(end.values(),default=0))}
    atomic_json(a.output,out)
if __name__=='__main__':main()
