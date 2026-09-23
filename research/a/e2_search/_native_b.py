"""Pack actual, globally validated Scene B tasks; retain original FIFO/sort order."""
import ctypes as ct
from dataclasses import dataclass
from pathlib import Path
import sys
import numpy as np
from ._native import I32P, I64P, U8P, PIPES, Unsupported, array, ptr

I32_FIELDS = ('slot', 'next_pipe', 'heads', 'pred_count', 'succ_off', 'succ',
              'cross_count', 'cross_off', 'cross_succ', 'sort_rank', 'cache_key')
I64_FIELDS = ('duration', 'hit_duration', 'transfer_bytes')

class InputB(ct.Structure):
    _fields_ = [(x, ct.c_int32) for x in ('n','c','cache_mode','keys')] + [(x, I32P) for x in I32_FIELDS] + [
        (x,I64P) for x in I64_FIELDS] + [('ddr', U8P), ('cross_wait', ct.c_int64), ('max_iter', ct.c_int64), ('cache_capacity', ct.c_int64)]

class OutputB(ct.Structure):
    _fields_ = [(x, I64P) for x in ('op_start', 'op_end', 'memory_path', 'stats', 'final_keys', 'final_sizes', 'events')] + [('event_cap',ct.c_int64)]

@dataclass
class CompiledB:
    arrays: dict
    cores: int
    op_keys: object
    total_duration: int
    cache_keys: tuple
    cache_mode: bool


def pack(tasks, cross_links, runtime, bandwidth, *, cache_bandwidth=None):
    c = len(tasks)
    if tuple(tasks) != tuple(range(c)) or not 1 <= c <= 128:
        raise Unsupported('native Scene B requires 1..128 contiguous cores')
    keys = tuple((t, o) for t in tasks for o in tasks[t]['seq'])
    ix = {k: i for i, k in enumerate(keys)}
    n = len(keys)
    if len(ix) != n or n >= 2**31:
        raise Unsupported('native index domain')
    a = {name: [] for name in I32_FIELDS}
    a.update(heads=[-1]*(4*c), next_pipe=[-1]*n, sort_rank=[0]*n,
             cross_count=[0]*n, succ_off=[0], cross_off=[0])
    duration, ddr, hit_duration, transfer = [], [], [], []
    cache_ids = {}
    for core, task in tasks.items():
        for pipe, order in task['pipe_ops'].items():
            if pipe not in PIPES:
                raise Unsupported('unknown pipe')
            if order:
                a['heads'][4*core+PIPES.index(pipe)] = ix[core, order[0]]
            for x, y in zip(order, order[1:]):
                a['next_pipe'][ix[core, x]] = ix[core, y]
        for oid in task['seq']:
            op = task['op_by_id'][oid]
            d = runtime._op_duration(op, task['in_tids'], task['out_tids'], task['tensor_by_id'], bandwidth)
            if type(d) is not int or not 1 <= d < 2**50:
                raise Unsupported('native duration domain')
            duration.append(d)
            cache_key, size = None, 0
            if cache_bandwidth is not None and op['op'] == 'COPY_IN':
                tids = [tid for tid in task['out_tids'][oid] if task['tensor_by_id'][tid].get('pos') != 'DDR']
                if tids:
                    tensor = task['tensor_by_id'][tids[0]]
                    cache_key, size = tensor.get('logical_tid',tids[0]), tensor['size']
                if cache_key is not None and type(cache_key) not in (int,str):
                    raise Unsupported('cache key domain')
                if type(size) is not int or size < 0:
                    raise Unsupported('cache size domain')
            hid = -1 if cache_key is None else cache_ids.setdefault(cache_key,len(cache_ids))
            a['cache_key'].append(hid)
            transfer.append(size)
            hd = d if hid < 0 else runtime._op_duration(op,task['in_tids'],task['out_tids'],task['tensor_by_id'],cache_bandwidth)
            if type(hd) is not int or not 1 <= hd < 2**50:
                raise Unsupported('native hit duration domain')
            hit_duration.append(hd)
            ddr.append(runtime._uses_ddr_bandwidth(op, task['in_tids'], task['out_tids'], task['tensor_by_id']))
            a['slot'].append(4*core+PIPES.index(runtime.op_pipe(op)))
            a['pred_count'].append(len(task['op_preds'][oid]))
            a['succ'].extend(ix[core, s] for s in task['op_succs'][oid])
            a['succ_off'].append(len(a['succ']))
    cross = [[] for _ in keys]
    for link in cross_links:
        source = ix[link['source_core'], link['source_copy_out_id']]
        target = ix[link['target_core'], link['target_copy_in_id']]
        cross[source].append(target)
        a['cross_count'][target] += 1
    for row in cross:
        a['cross_succ'].extend(row)
        a['cross_off'].append(len(a['cross_succ']))
    for rank, key in enumerate(sorted(keys)):
        a['sort_rank'][ix[key]] = rank
    if max(len(a['succ']), len(a['cross_succ'])) >= 2**31:
        raise Unsupported('native edge domain')
    a = {name: array(value) for name, value in a.items()}
    if sum(transfer) >= 2**50:
        raise Unsupported('cache byte sum domain')
    a['duration'], a['ddr'] = array(duration, np.int64), array(ddr, np.uint8)
    a['hit_duration'], a['transfer_bytes'] = array(hit_duration,np.int64), array(transfer,np.int64)
    return CompiledB(a, c, keys, sum(max(d,h) for d,h in zip(duration,hit_duration)), tuple(cache_ids), cache_bandwidth is not None)


_LIB = None
def get_lib():
    global _LIB
    if _LIB is None:
        suffix = '.dll' if sys.platform == 'win32' else '.so'
        library = ct.CDLL(str(Path(__file__).parent / ('native/libreplay_bc'+suffix)))
        library.replay_bc_abi.argtypes = []
        library.replay_bc_abi.restype = ct.c_int
        if library.replay_bc_abi() != 1:
            raise Unsupported('native Scene BC ABI version mismatch')
        library.replay_bc.argtypes = [ct.POINTER(InputB), ct.POINTER(OutputB)]
        library.replay_bc.restype = ct.c_int
        _LIB = library
    return _LIB


def score(comp, *, cross_core_copy_delay, max_iter, cache_capacity=0, debug=False):
    if type(cross_core_copy_delay) is not int or cross_core_copy_delay < 0 or type(max_iter) is not int or not 1 <= max_iter < 2**63:
        raise Unsupported('native integer delay/iteration domain')
    n = len(comp.op_keys)
    if comp.total_duration*(4*comp.cores+1)+(cross_core_copy_delay+1)*n+4*n >= 2**50:
        raise Unsupported('native conservative time bound exceeded')
    if type(cache_capacity) is not int or not 0 <= cache_capacity < 2**50:
        raise Unsupported('native cache capacity domain')
    nk = len(comp.cache_keys)
    inp = InputB(n=n, c=comp.cores, cache_mode=int(comp.cache_mode), keys=nk,
                 cross_wait=cross_core_copy_delay, max_iter=max_iter, cache_capacity=cache_capacity)
    for name, value in comp.arrays.items():
        setattr(inp, name, ptr(value, I64P if name in I64_FIELDS else U8P if name == 'ddr' else I32P))
    result = {name: np.empty(size, np.int64) for name, size in (('op_start', n), ('op_end', n), ('memory_path',n),
              ('stats', 16), ('final_keys',nk), ('final_sizes',nk))}
    logs = np.empty(15*n if debug and comp.cache_mode else 0,np.int64)
    out = OutputB(**{k: ptr(v, I64P) for k, v in result.items()},events=ptr(logs,I64P) if len(logs) else I64P(),event_cap=len(logs))
    status = get_lib().replay_bc(ct.byref(inp), ct.byref(out))
    if status:
        raise Unsupported(f'native Scene B status={status}; official fallback required')
    result['makespan'] = int(result['stats'][0])
    if comp.cache_mode:
        s = [int(x) for x in result['stats']]
        result['cache_stats'] = dict(copy_in_hits=s[6],copy_in_misses=s[7],hit_bytes=s[8],miss_bytes=s[9],
                                    hits=s[6],accesses=s[6]+s[7],hit_rate=s[8]/(s[8]+s[9]) if s[8]+s[9] else 0.0)
        if debug:
            result['cache_final_entries'] = [dict(tensor_id=comp.cache_keys[int(result['final_keys'][i])],
                                                 size_bytes=int(result['final_sizes'][i])) for i in range(s[11])]
            result['cache_used_bytes_final'] = s[10]
            events, i = [], 0
            while i < s[5]:
                kind,now,op,key,size,used,count = (int(x) for x in logs[i:i+7]); i += 7
                core, oid = comp.op_keys[op]
                event = dict(time=now,event=('miss','hit','insert')[kind],tensor_id=comp.cache_keys[key],
                             size_bytes=size,core_id=core,op_id=oid)
                if kind == 2:
                    event.update(used_bytes=used,evicted_tensor_ids=[comp.cache_keys[int(k)] for k in logs[i:i+count]])
                else:
                    event['op'] = 'COPY_IN'
                events.append(event); i += count
            result['cache_events'] = events
    return result
