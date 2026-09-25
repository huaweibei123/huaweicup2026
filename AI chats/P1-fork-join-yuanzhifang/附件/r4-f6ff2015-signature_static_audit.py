#!/usr/bin/env python3
"""Static, conditional analysis of saved ports; no compilation or execution.
An orbit of m identical, synchronously activated, isolated-index Tasks stays
symmetric in the exact PS model. Charge m*d to a representative DDR operation.
These bounds are NOT generic P1/E0 bounds, nor an execution equivalence test.
"""
from pathlib import Path
from collections import defaultdict
import json,hashlib,heapq,argparse
from recompute import window

def task_bound(t,m):
    ops={(p,j):x for p,port in enumerate(t['ports']) for j,x in enumerate(port,1)}
    dur={u:x[0]*(m if x[1] else 1) for u,x in ops.items()}
    pred={};succ={u:set() for u in ops}
    for (p,j),x in ops.items():
        assert len(x[2])==4 and type(x[1]) is bool and type(x[0]) is int and x[0]>0
        req={(q,rank) for q,rank in enumerate(x[2]) if rank}
        if j>1:req.add((p,j-1))
        assert req<=ops.keys();pred[p,j]=req
        for u in req:succ[u].add((p,j))
    deg={u:len(req) for u,req in pred.items()};todo=[u for u,d in deg.items() if not d];heapq.heapify(todo);order=[];r={};q={}
    while todo:
        u=heapq.heappop(todo);order.append(u);r[u]=max((r[v]+dur[v] for v in pred[u]),default=0)
        for v in succ[u]:
            deg[v]-=1
            if not deg[v]:heapq.heappush(todo,v)
    assert len(order)==len(ops)
    for u in reversed(order):q[u]=max((dur[v]+q[v] for v in succ[u]),default=0)
    jobs=[(r[u],dur[u],q[u],'%d:%d'%u) for u,x in ops.items() if x[1]]
    cp=max((r[u]+dur[u] for u in ops),default=0);w=window(jobs,1)
    return {'task_id':t['task_id'],'orbit':m,'cp':cp,'window':w,'bound':max(cp,w['bound']),
            'ddr_jobs':len(jobs),'ports_sha256':hashlib.sha256(json.dumps(t['ports'],separators=(',',':')).encode()).hexdigest()}
def main(root,out):
    path=root/'recent/results/a/p1-period7-colab-20260925/run-0534Z/paired-signatures.json';raw=path.read_bytes();data=json.loads(raw);ans={}
    archived=json.loads((root/'recent/results/a/p1-r5-local-audit-20260925/bounds/result.json').read_text())
    for name,v in data['variants'].items():
        tasks={t['task_id']:t for t in v['tasks']};lines=v['core_schedules'];assert len(lines)==5
        assert sorted(tasks)==sorted(t for line in lines for t in line)
        common=0
        while common<min(map(len,lines)) and all(tasks[line[common]]['ports']==tasks[lines[0][common]]['ports'] for line in lines):common+=1
        assert all(len(line)-common<=1 for line in lines)
        orbit={t:5 for line in lines for t in line[:common]};groups=defaultdict(list)
        for c,line in enumerate(lines):
            if len(line)>common:groups[json.dumps(tasks[line[common]]['ports'],separators=(',',':'))].append(c)
        for cs in groups.values():
            for c in cs:orbit[lines[c][common]]=len(cs)
        bounds={t:task_bound(task,orbit[t]) for t,task in tasks.items()}
        cores={str(c):sum(bounds[t]['bound'] for t in line)+data['gate']*max(0,len(line)-1) for c,line in enumerate(lines)}
        lower=max(cores.values());assert lower==archived['variants'][name]['lower_bound']
        ans[name]={'common_rounds':common,'tail_groups':list(groups.values()),'per_core':cores,'lower_bound':lower,
                   'saved_not_rerun_model_makespan':v['expected_model_makespan'],'task_bounds':list(bounds.values())}
    result={'scope':'conditional fixed port signatures / exact PS symmetry; not E0 and not all partitions',
            'source_sha256':hashlib.sha256(raw).hexdigest(),'variants':ans,
            'calls':{'solver':0,'compiler':0,'response_simulator':0,'E0':0,'E1':0,'E2':0},
            'note':'Reconstructed NEW window witnesses from saved ports; original causal_certificates.json absent, so not a byte-for-byte validation of its selected jobs.'}
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({n:{'lower_bound':v['lower_bound'],'tasks':len(v['task_bounds'])} for n,v in ans.items()},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/mnt/data/p1_r4_evidence'));p.add_argument('--out',type=Path,default=Path('/mnt/data/p1_r4_report/signature_static_audit.json'));a=p.parse_args();main(a.root,a.out)
