#!/usr/bin/env python3
"""Small fixed-FIFO/shared-DDR mathematical response model, NOT official E0/E1.

Exact Fraction service; operation retirements are at integer cycles. This is
not a claim of bit-equivalence to the frozen evaluator's binary64/EPS code.
Each task has four FIFO lists. Completed-prefix counters are sufficient for
all predecessor checks. No cross-core task edges are supported here.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Sequence
import archived_r1 as ar

PIPES = ar.PIPES

@dataclass(frozen=True)
class PortOp:
    work: int
    ddr: bool
    need: tuple[int, int, int, int]
    original_id: int = -1

@dataclass(frozen=True)
class Task:
    ports: tuple[tuple[PortOp, ...], ...]
    task_id: int = -1

    def signature(self):
        return tuple(tuple((o.work, o.ddr, o.need) for o in port) for port in self.ports)

    def scaled_ddr(self, multiplicity: int):
        if type(multiplicity) is not int or multiplicity < 1:
            raise ValueError('positive integer multiplicity required')
        return Task(tuple(tuple(replace(o, work=o.work*multiplicity) if o.ddr else o
                                for o in port) for port in self.ports), self.task_id)


def compile_local(local: dict, task_id: int, capacity: dict, bandwidth: int = 60):
    """Boundary-only model compiler, guarded by total distinct virgin bytes.
    reference_step1 is the archived author's transcription, NOT official code.
    Reject multiple producers; every managed tensor must have one producer.
    """
    v = ar.views(local)
    footprint = {p: sum(t['size'] for t in local['tensors'] if t['pos'] == p)
                 for p in capacity}
    if any(footprint[p] > capacity[p] for p in capacity):
        raise ar.Unsupported('virgin-capacity sufficient condition fails')
    for tid, t in v.tensors.items():
        if t['pos'] in capacity and len(v.producers[tid]) != 1:
            raise ar.Unsupported('managed tensor not single-producer')
    seq = ar.reference_step1(local)
    positions = {}
    orders = [[] for _ in PIPES]
    for u in seq:
        p = PIPES.index(v.ops[u]['pipe'])
        positions[u] = (p, len(orders[p]) + 1)
        orders[p].append(u)
    ports = []
    for order in orders:
        port = []
        for u in order:
            need = [0]*4
            for pred in v.pred[u]:
                p, rank = positions[pred]
                need[p] = max(need[p], rank)
            op = v.ops[u]
            ddr = False
            if op['op'] in ar.COPY:
                ts = v.out_t[u] if op['op'] == 'COPY_IN' else v.in_t[u]
                work = max(1, ar.ceildiv(sum(v.tensors[t]['size'] for t in ts), bandwidth))
                ddr = any(v.tensors[t]['pos'] == 'DDR' for t in v.in_t[u] | v.out_t[u])
            else:
                work = max(1, op['cycles'])
            port.append(PortOp(work, ddr, tuple(need), u))
        ports.append(tuple(port))
    return Task(tuple(ports), task_id), footprint


def compile_plan(graph, plan, capacity, bandwidth=60):
    ar.validate_plan_structure(graph, plan)
    mapping = {int(u): t for u, t in plan['node_to_subgraph'].items()}
    owner = {t:k for k,line in enumerate(plan['core_schedules']) for t in line}
    v = ar.views(graph)
    for u in mapping:
        for w in v.succ[u]:
            if w in mapping and owner[mapping[u]] != owner[mapping[w]]:
                raise ar.Unsupported('cross-core edge unsupported by port response model')
    locals_ = ar.local_model(graph, plan, bandwidth)
    compiled = {}; footprints = {}
    for tid, local in locals_.items():
        compiled[tid], footprints[tid] = compile_local(local, tid, capacity, bandwidth)
    return [[compiled[t] for t in line] for line in plan['core_schedules']], footprints


def simulate(lines: Sequence[Sequence[Task]], gate: int = 100, keep_trace: bool = False):
    if type(gate) is not int or gate < 0:
        raise ValueError('nonnegative integer gate required')
    k = len(lines)
    idx = [0]*k; done = [[0]*4 for _ in range(k)]; active = [False]*k
    release = [0]*k; finish = [0]*k
    # Busy slots carry (PortOp, start, fixed_compute_end_or_None).
    busy = [[None]*4 for _ in range(k)]
    remaining = {}  # (core, pipe) -> exact rational DDR work
    now = 0; events = 0; ddr_occupied = 0; total_service = 0
    trace = []; task_trace = []; task_start = [None]*k
    while True:
        events += 1
        if events > 2_000_000:
            raise RuntimeError('model event budget exceeded')
        # All retirements precede activation and issuance.
        for core in range(k):
            for p in range(4):
                item = busy[core][p]
                if item is None:
                    continue
                op, start, end = item
                is_done = remaining[(core,p)] == 0 if op.ddr else end <= now
                if is_done:
                    done[core][p] += 1
                    busy[core][p] = None
                    if op.ddr:
                        del remaining[(core,p)]
                    if keep_trace:
                        trace.append(dict(core=core, task=lines[core][idx[core]].task_id,
                                          pipe=PIPES[p], op_id=op.original_id,
                                          ddr=op.ddr, start=start, end=now, work=op.work))
            if active[core]:
                task = lines[core][idx[core]]
                if all(done[core][p] == len(task.ports[p]) for p in range(4)):
                    task_trace.append(dict(core=core, task=task.task_id,
                                           start=task_start[core], end=now))
                    finish[core] = now
                    idx[core] += 1; active[core] = False
                    release[core] = now + gate
        if all(idx[c] == len(lines[c]) for c in range(k)):
            break
        for core in range(k):
            if not active[core] and idx[core] < len(lines[core]) and release[core] <= now:
                active[core] = True; done[core] = [0]*4; task_start[core] = now
            if not active[core]:
                continue
            task = lines[core][idx[core]]
            for p in range(4):
                if busy[core][p] is not None or done[core][p] == len(task.ports[p]):
                    continue
                op = task.ports[p][done[core][p]]
                if any(done[core][j] < op.need[j] for j in range(4)):
                    continue
                busy[core][p] = (op, now, None if op.ddr else now+op.work)
                if op.ddr:
                    remaining[(core,p)] = Fraction(op.work)
                    total_service += op.work
        nexts = []
        for core in range(k):
            if not active[core] and idx[core] < len(lines[core]) and release[core] > now:
                nexts.append(release[core])
            for item in busy[core]:
                if item is not None and not item[0].ddr:
                    nexts.append(item[2])
        if remaining:
            first = min(remaining.values()) * len(remaining)
            nexts.append(now + ar.ceildiv(first.numerator, first.denominator))
        if not nexts:
            raise RuntimeError('invalid FIFO/dependency model: deadlock')
        nxt = min(nexts)
        if nxt <= now:
            raise RuntimeError('model made no progress')
        elapsed = Fraction(nxt-now)
        if remaining:
            ddr_occupied += nxt-now
        # Fluid completion may occur within a cycle; residual service is
        # redistributed immediately, while operation retirement stays integer.
        while elapsed > 0:
            positive = [key for key,w in remaining.items() if w > 0]
            if not positive:
                break
            dt = min(remaining[key] for key in positive) * len(positive)
            consumed = min(dt, elapsed)
            share = consumed / len(positive)
            for key in positive:
                remaining[key] -= share
            elapsed -= consumed
        now = nxt
    result = dict(kind='fraction_integer_retirement_port_model_NOT_E0',
                  makespan=now, per_core_finish=finish, events=events,
                  service_cycles=total_service, ddr_occupied_union=ddr_occupied,
                  outside_DDR_intervals=now-ddr_occupied, task_intervals=task_trace)
    if keep_trace:
        result['trace'] = trace
    return result


def quotient(lines, gate=100):
    """Fold exactly equal, jointly released task rounds; simulate only tail.
    Equality is checked on actual FIFO/precedence/duration/request signatures,
    not tensor/op IDs or an uncompiled chain shape. Cache only within this call.
    """
    k = len(lines); round_ = 0; total = 0; cache = {}; rows = []
    shortest = min(map(len,lines),default=0)
    while round_ < shortest:
        signatures = [line[round_].signature() for line in lines]
        if any(s != signatures[0] for s in signatures[1:]):
            break
        sig = signatures[0]
        if sig not in cache:
            cache[sig] = simulate([[lines[0][round_].scaled_ddr(k)]], gate=gate)
        response = cache[sig]
        if round_:
            total += gate
        start = total; total += response['makespan']
        rows.append(dict(round=round_, start=start, end=total,
                         service_cycles=response['service_cycles'],
                         task_cycles=response['makespan']))
        round_ += 1
    tail = [line[round_:] for line in lines]
    tail_result = None
    if any(tail):
        tail_result = simulate(tail, gate=gate)
        if round_:
            total += gate
        total += tail_result['makespan']
    return dict(kind='certified_symmetric_quotient_of_port_model_NOT_E0',
                makespan=total, equal_rounds=round_, distinct_round_responses=len(cache),
                explicit_tail_tasks=sum(map(len,tail)),
                explicit_tail_events=0 if tail_result is None else tail_result['events'],
                rounds=rows, tail=tail_result)
