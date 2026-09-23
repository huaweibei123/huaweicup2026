"""Research-only prepared-task adapter. No official compilation/validation claims.

pack_tasks accepts ACTUAL Step3 prepared tasks, or explicitly synthetic fixtures.
The native kernel replays events; unsupported API numbers must fall back to E1.
"""
from __future__ import annotations
import ctypes as ct
import sys
from dataclasses import dataclass
from pathlib import Path
import numpy as np

PIPES = ('PIPE_MTE2', 'PIPE_MTE3', 'PIPE_M', 'PIPE_V')
I32P=ct.POINTER(ct.c_int32); I64P=ct.POINTER(ct.c_int64); U8P=ct.POINTER(ct.c_uint8)
class Input(ct.Structure):
    _fields_=[('n',ct.c_int32),('t',ct.c_int32),('c',ct.c_int32)]+[(x,I32P) for x in (
        'task_of','pipe','next_pipe','heads','pred_count','succ_off','succ','task_counts','tp_off','tp','sort_rank')]+[
        ('duration',I64P),('ddr',U8P)]+[(x,I32P) for x in ('core_of','order_off','order')]+[
        ('same_wait',ct.c_int64),('cross_wait',ct.c_int64),('max_iter',ct.c_int64),('project_once',ct.c_int32)]
class Output(ct.Structure):
    _fields_=[(x,I64P) for x in ('op_start','op_end','task_start','task_end','stats','audit')]+[('audit_cap',ct.c_int64)]

def ptr(a,kind=I32P): return a.ctypes.data_as(kind)
def array(v,dtype=np.int32):
    a=np.ascontiguousarray(v,dtype=dtype); a.flags.writeable=False; return a

class Unsupported(RuntimeError): pass
class CandidateError(ValueError): pass

@dataclass
class Compiled:
    arrays: dict
    task_ids: tuple
    op_keys: tuple
    index: dict
    total_duration: int
    @property
    def static_bytes(self): return sum(a.nbytes for a in self.arrays.values())


def pack_tasks(tasks, runtime, bandwidth):
    """Compile once, preserving each original (task_id,op_id) sort position.

    Assumes the caller has performed all official graph/plan/Step1--3 checks.
    Succ lists use the current official set iteration; no sorting is introduced.
    """
    tids=tuple(tasks); ti={t:i for i,t in enumerate(tids)}
    keys=tuple((t,o) for t in tids for o in tasks[t]['seq']); ix={k:i for i,k in enumerate(keys)}
    if len(ix)!=len(keys) or len(keys)>=2**31 or len(tids)>=2**29:
        raise Unsupported('duplicate keys or 32-bit index domain exceeded')
    n=len(keys); heads=[-1]*(4*len(tids)); nxt=[-1]*n
    pipes=[]; dur=[]; ddr=[]; indeg=[]; succ=[]; off=[0]; task_of=[]; counts=[]; tp=[]; tp_off=[0]
    for t in tids:
        task=tasks[t]; counts.append(len(task['seq']))
        if not task['seq']: raise Unsupported('empty prepared task')
        tp.extend(ti[p] for p in task['pred_tasks']); tp_off.append(len(tp))
        for p,order in task['pipe_ops'].items():
            if p not in PIPES: raise Unsupported('unknown pipe')
            if order: heads[4*ti[t]+PIPES.index(p)]=ix[t,order[0]]
            for a,b in zip(order,order[1:]): nxt[ix[t,a]]=ix[t,b]
        for o in task['seq']:
            op=task['op_by_id'][o]
            d=runtime._op_duration(op,task['in_tids'],task['out_tids'],task['tensor_by_id'],bandwidth)
            if type(d) is not int or not 1<=d<2**50: raise Unsupported('duration domain')
            dur.append(d); pipes.append(PIPES.index(runtime.op_pipe(op))); task_of.append(ti[t])
            ddr.append(runtime._uses_ddr_bandwidth(op,task['in_tids'],task['out_tids'],task['tensor_by_id']))
            indeg.append(len(task['op_preds'][o]))
            succ.extend(ix[t,s] for s in task['op_succs'][o]);off.append(len(succ))
    rank=[0]*n
    for r,k in enumerate(sorted(keys)): rank[ix[k]]=r
    arrays={k:array(v) for k,v in dict(task_of=task_of,pipe=pipes,next_pipe=nxt,heads=heads,
        pred_count=indeg,succ_off=off,succ=succ,task_counts=counts,tp_off=tp_off,tp=tp,sort_rank=rank).items()}
    arrays['duration']=array(dur,np.int64);arrays['ddr']=array(ddr,np.uint8)
    return Compiled(arrays,tids,keys,ix,sum(dur))


def validate_orders(comp, orders):
    """Typed-API check for exact coverage plus task DAG AND all core-order edges.

    Not a substitute for official RAW graph/plan validation or exact error text.
    """
    ids={t:i for i,t in enumerate(comp.task_ids)}; seen=set(); dense=[]; off=[0]; cores=[-1]*len(ids)
    edges=[set() for _ in ids]; a=comp.arrays
    for target in range(len(ids)):
        for j in range(a['tp_off'][target],a['tp_off'][target+1]): edges[int(a['tp'][j])].add(target)
    for c,order in enumerate(orders):
        prev=None
        for task in order:
            if type(task) is not int or task not in ids or task in seen: raise CandidateError('unknown/duplicate task')
            seen.add(task);t=ids[task];cores[t]=c;dense.append(t)
            if prev is not None:edges[prev].add(t)
            prev=t
        off.append(len(dense))
    if seen!=set(ids):raise CandidateError('missing task')
    indeg=[0]*len(ids)
    for row in edges:
        for t in row:indeg[t]+=1
    ready=[t for t,x in enumerate(indeg) if x==0];visited=0
    while ready:
        t=ready.pop();visited+=1
        for s in edges[t]:
            indeg[s]-=1
            if indeg[s]==0:ready.append(s)
    if visited!=len(ids):raise CandidateError('union task-order cycle')
    return array(cores),array(off),array(dense)

_LIB=None
def get_lib():
    global _LIB
    if _LIB is None:
        suffix = '.dll' if sys.platform == 'win32' else '.so'
        _LIB=ct.CDLL(str(Path(__file__).parent/('native/libreplay'+suffix)))
        _LIB.replay.argtypes=[ct.POINTER(Input),ct.POINTER(Output)];_LIB.replay.restype=ct.c_int
    return _LIB

def score(comp, orders, *, same_wait=100, cross_wait=1000, max_iter=1_000_000, audit=False, project_once=False):
    """Costs include candidate validation, fresh buffers, ctypes and native replay.

    Returns dense op/task timing arrays, not an official full result object.
    """
    if any(type(x) is not int or x<0 for x in (same_wait,cross_wait)) or type(max_iter) is not int or max_iter<1:
        raise Unsupported('integer wait/max_iter domain required; use E1')
    c=len(orders); n=len(comp.op_keys);t=len(comp.task_ids)
    if not 1<=c<=128:raise Unsupported('prototype resource cap: 1..128 cores')
    # A deliberately generous preflight bound; it rejects, never truncates.
    bound=comp.total_duration*(4*c+1)+(same_wait+cross_wait+1)*t+4*n
    if bound>=2**50:raise Unsupported('conservative binary64/int64 time bound exceeded')
    core,off,order=validate_orders(comp,orders)
    inp=Input();inp.n=n;inp.t=t;inp.c=c
    for name,a in comp.arrays.items():setattr(inp,name,ptr(a,I64P if name=='duration' else U8P if name=='ddr' else I32P))
    inp.core_of=ptr(core);inp.order_off=ptr(off);inp.order=ptr(order)
    inp.same_wait=same_wait;inp.cross_wait=cross_wait;inp.max_iter=max_iter;inp.project_once=int(project_once)
    arrays={name:np.empty(size,dtype=np.int64) for name,size in (
        ('op_start',n),('op_end',n),('task_start',t),('task_end',t),('stats',8))}
    # Python sum over NumPy uint8 can itself accumulate in uint8 and wrap.
    # Count the 0/1 mask without a narrow accumulator on real graphs (>255 DDR ops).
    logcap=int(np.count_nonzero(comp.arrays['ddr']))*(3+8*c) if audit else 0
    logs=np.empty(logcap,dtype=np.int64)
    out=Output(**{k:ptr(v,I64P) for k,v in arrays.items()},audit=ptr(logs,I64P) if audit else I64P(),audit_cap=logcap)
    status=get_lib().replay(ct.byref(inp),ct.byref(out))
    if status:raise Unsupported(f'native status={status}; run E1 for exact classification')
    arrays['makespan']=int(arrays['stats'][0]); arrays['audit']=logs[:int(arrays['stats'][5])]
    return arrays
