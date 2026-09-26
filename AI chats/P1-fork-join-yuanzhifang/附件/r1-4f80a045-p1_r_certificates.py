#!/usr/bin/env python3
"""P1 model-R certificates. This is NOT E0 and NOT a submission solver.

All modeled nodes use one PIPE_V, all listed dependencies are preserved,
COPY/memory/DDR are absent, core-switch=100, inter-core Task lag=1000.
Within a Task, any legal FIFO has the same duration (sum of node durations).
No claim about the user's machine, actual E0, or official-file verification.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict, deque
from itertools import groupby
import argparse
import json
import random

P, SWITCH, CROSS, ADD = 524, 100, 1000, 13

@dataclass(frozen=True)
class Node:
    name: str
    duration: int
    predecessors: tuple[str, ...] = ()

@dataclass(frozen=True)
class Task:
    name: str
    core: int
    nodes: tuple[str, ...]


def evaluate_r(nodes: list[Node], tasks: list[Task], orders: list[list[str]]) -> dict:
    """Validate exact cover and the augmented DAG; recompute exact R timing."""
    nd = {n.name: n for n in nodes}
    td = {t.name: t for t in tasks}
    if len(nd) != len(nodes) or len(td) != len(tasks):
        raise ValueError('Duplicate node or Task ID')
    owner = {}
    for t in tasks:
        if not t.nodes or not 0 <= t.core < len(orders):
            raise ValueError('Empty Task or invalid core')
        for x in t.nodes:
            if x not in nd or x in owner:
                raise ValueError('Invalid or duplicate assignment')
            owner[x] = t.name
    if set(owner) != set(nd):
        raise ValueError('Partition does not cover all nodes')
    flat = [x for order in orders for x in order]
    if len(flat) != len(tasks) or set(flat) != set(td):
        raise ValueError('Each Task must occur exactly once in core orders')
    # Validate the underlying compute DAG too, including internal Task edges.
    ni = {x: 0 for x in nd}
    ns = defaultdict(list)
    for n in nodes:
        if n.duration <= 0:
            raise ValueError('Durations must be positive')
        for u in n.predecessors:
            if u not in nd:
                raise ValueError('Unknown predecessor')
            ns[u].append(n.name); ni[n.name] += 1
    nq = deque(x for x in nd if not ni[x]); visited = 0
    while nq:
        u = nq.popleft(); visited += 1
        for v in ns[u]:
            ni[v] -= 1
            if not ni[v]: nq.append(v)
    if visited != len(nodes):
        raise ValueError('Compute graph contains a cycle')
    lag = {}
    def edge(u: str, v: str, delay: int):
        if u != v:
            lag[u, v] = max(delay, lag.get((u, v), 0))
    for n in nodes:
        for u in n.predecessors:
            a, b = owner[u], owner[n.name]
            edge(a, b, CROSS if td[a].core != td[b].core else 0)
    for c, order in enumerate(orders):
        for x in order:
            if td[x].core != c:
                raise ValueError('Core order contradicts Task assignment')
        for u, v in zip(order, order[1:]): edge(u, v, SWITCH)
    indeg = {x: 0 for x in td}
    succ = defaultdict(list)
    for (u, v), delay in lag.items():
        indeg[v] += 1; succ[u].append((v, delay))
    queue = deque(x for x in td if not indeg[x])
    start = {x: 0 for x in td}; end = {}
    duration = {t.name: sum(nd[x].duration for x in t.nodes) for t in tasks}
    while queue:
        u = queue.popleft(); end[u] = start[u] + duration[u]
        for v, delay in succ[u]:
            start[v] = max(start[v], end[u] + delay)
            indeg[v] -= 1
            if not indeg[v]: queue.append(v)
    if len(end) != len(tasks):
        raise ValueError('Task dependency + core-order graph contains a cycle')
    return {'model': 'R only; not E0', 'makespan': max(end.values(), default=0),
            'node_count': len(nodes), 'task_count': len(tasks),
            'core_schedules': orders,
            'tasks': [{'id': t.name, 'core': t.core, 'nodes': list(t.nodes),
                       'start': start[t.name], 'end': end[t.name]} for t in tasks]}


def tiny_counterexample() -> dict:
    nodes = []
    for b in 'ABC':
        for j in range(1, 5):
            nodes.append(Node(f'{b}{j}', P, (f'{b}{j-1}',) if j > 1 else ()))
    nodes += [Node('U', ADD, ('A4', 'B4')), Node('V', ADD, ('U', 'C4'))]
    tasks = [Task('P', 0, ('C1',)), Task('A', 0, tuple(f'A{i}' for i in range(1, 5))),
             Task('B', 1, tuple(f'B{i}' for i in range(1, 5))),
             Task('S', 1, ('C2', 'C3', 'C4')), Task('tail', 1, ('U', 'V'))]
    return evaluate_r(nodes, tasks, [['P', 'A'], ['B', 'S', 'tail']])



def local_reduction_counterexample() -> dict:
    nodes = []
    for b in 'ABCD':
        for j in range(1, 5):
            nodes.append(Node(f'{b}{j}', P, (f'{b}{j-1}',) if j > 1 else ()))
    nodes += [Node('U',ADD,('A4','B4')), Node('V',ADD,('C4','D4')), Node('R',ADD,('U','V'))]
    ab=tuple(f'{b}{j}' for b in 'AB' for j in range(1,5))
    cd=tuple(f'{b}{j}' for b in 'CD' for j in range(1,5))
    all_tail=evaluate_r(nodes,[Task('F0',0,ab),Task('F1',1,cd),Task('T',0,('U','V','R'))],
                        [['F0','T'],['F1']])
    local=evaluate_r(nodes,[Task('F0',0,ab+('U',)),Task('F1',1,cd+('V',)),Task('T',0,('R',))],
                     [['F0','T'],['F1']])
    return {'all_reductions_in_tail':all_tail,'local_pair_reductions':local}


def chain(r: int, b: int, first: int = 1, last: int = 4) -> tuple[str, ...]:
    return tuple(f'r{r}_b{b}_{j}' for j in range(first, last + 1))


def graph(rounds: int, shape: str) -> tuple[list[Node], list[tuple[str, ...]]]:
    if rounds < 1 or shape not in ('balanced', 'comb'):
        raise ValueError('Invalid round count or reduction shape')
    nodes, additions = [], []
    previous = None
    for r in range(rounds):
        for b in range(1, 13):
            for j in range(1, 5):
                pred = (chain(r, b, j-1, j-1)[0],) if j > 1 else ((previous,) if previous else ())
                nodes.append(Node(chain(r, b, j, j)[0], P, pred))
        leaves = [chain(r, b, 4, 4)[0] for b in range(1, 13)]
        ids = []
        def add(u, v):
            name = f'r{r}_a{len(ids)}'
            nodes.append(Node(name, ADD, (u, v))); ids.append(name)
            return name
        if shape == 'comb':
            current = leaves[0]
            for v in leaves[1:]: current = add(current, v)
        else:
            while len(leaves) > 1:
                nxt = [add(leaves[i], leaves[i+1]) for i in range(0, len(leaves)-1, 2)]
                if len(leaves) % 2: nxt.append(leaves[-1])
                leaves = nxt
            current = leaves[0]
        previous = current; additions.append(tuple(ids))
    return nodes, additions


def construction(mode: str, rounds: int = 24, shape: str = 'balanced') -> dict:
    nodes, adds = graph(rounds, shape)
    k = 4 if mode == 'uncut4_fixed_tail' else 5
    tasks, orders = [], [[] for _ in range(k)]
    def task(r, label, c, ns):
        name = f'r{r}_{label}'
        tasks.append(Task(name, c, tuple(ns))); orders[c].append(name)
    def full(r, *branches):
        return sum((chain(r, b) for b in branches), ())
    def sym(r):
        task(r, 'd0', 0, full(r, 1, 2)); task(r, 'x0', 0, chain(r, 11, 3, 4))
        task(r, 'd1', 1, full(r, 3, 4)); task(r, 'x1', 1, chain(r, 12, 3, 4))
        task(r, 'middle', 2, full(r, 5, 6))
        task(r, 'p3', 3, chain(r, 11, 1, 2)); task(r, 'f3', 3, full(r, 7, 8))
        task(r, 'p4', 4, chain(r, 12, 1, 2)); task(r, 'f4', 4, full(r, 9, 10))
        task(r, 'tail', 2, adds[r])
        return 2
    source = None
    for r in range(rounds):
        if mode == 'uncut4_fixed_tail':
            for c in range(4): task(r, f'f{c}', c, full(r, *range(3*c+1, 3*c+4)))
            task(r, 'tail', 0, adds[r]); source = 0
        elif mode == 'split22_fixed_tail' or (mode in ('split31_rotating_tail', 'split31_star_fixed_tail') and r == 0):
            source = sym(r)
        elif mode == 'split31_star_fixed_tail':
            root = source
            c0, c1, c2, c3 = [c for c in range(5) if c != root]
            task(r, 'root_prefixes', root, chain(r, 9, 1, 3) + chain(r, 10, 1, 3))
            task(r, 'root_suffixes', root, chain(r, 11, 2, 4) + chain(r, 12, 2, 4))
            for c, bs, b in [(c0, (1, 2), 9), (c1, (3, 4), 10)]:
                task(r, f'f{c}', c, full(r, *bs))
                task(r, f'z{c}', c, chain(r, b, 4, 4))
            for c, bs, b in [(c2, (5, 6), 11), (c3, (7, 8), 12)]:
                task(r, f'p{c}', c, chain(r, b, 1, 1))
                task(r, f'f{c}', c, full(r, *bs))
            task(r, 'tail', root, adds[r])
        elif mode == 'split31_rotating_tail':
            s, e = source, (source + 1) % 5
            receivers = [c for c in range(5) if c not in (s, e)]
            task(r, 's_prefix', s, chain(r, 10, 1, 3))
            task(r, 's_full', s, full(r, 1, 2))
            task(r, 'e_prefix', e, chain(r, 11, 1, 3) + chain(r, 12, 1, 3))
            task(r, 'e_full', e, full(r, 3))
            for c, bs, split in zip(receivers, [(4, 5), (6, 7), (8, 9)], [10, 11, 12]):
                task(r, f'f{c}', c, full(r, *bs))
                task(r, f'z{c}', c, chain(r, split, 4, 4))
            task(r, 'tail', e, adds[r]); source = e
        elif mode == 'uncut5_rotating_tail':
            s, e = (1, 0) if r == 0 else (source, (source + 1) % 5)
            sequence = [s, e] + [c for c in range(5) if c not in (s, e)]
            branch = 1
            for c, count in zip(sequence, [3, 3, 2, 2, 2]):
                task(r, f'f{c}', c, full(r, *range(branch, branch + count))); branch += count
            task(r, 'tail', e, adds[r]); source = e
        else:
            raise ValueError('Unknown construction')
    out = evaluate_r(nodes, tasks, orders)
    out.update(mode=mode, reduction_shape=shape, rounds=rounds)
    return out


def packing_ok(x: int, offsets: list[int], heavy: int = 48, light: int = 10) -> bool:
    """Necessary core-capacity relaxation, not enumeration of Task plans."""
    dp = [-1] * (heavy + 1); dp[0] = 0
    for offset in offsets:
        capacity = max(0, x - offset)
        options = [min(light, (capacity - P*m)//ADD)
                   for m in range(min(heavy, capacity//P) + 1)]
        nxt = [-1] * (heavy + 1)
        for done, old in enumerate(dp):
            if old < 0: continue
            for m, more in enumerate(options[:heavy-done+1]):
                nxt[done+m] = max(nxt[done+m], min(light, old+more))
        dp = nxt
    return dp[heavy] >= light


def packing_min(offsets: list[int]) -> int:
    if not offsets: raise ValueError('At least one core required')
    low, high = -1, 1
    while not packing_ok(high, offsets): high *= 2
    while high-low > 1:
        mid = (high+low)//2
        if packing_ok(mid, offsets): high = mid
        else: low = mid
    assert packing_ok(high, offsets) and not packing_ok(high-1, offsets)
    return high


def lower_bounds() -> list[dict]:
    out = []
    for k in range(1, 6):
        first = packing_min([0] + [CROSS]*(k-1)) + ADD
        same = packing_min([0] + [2*CROSS]*(k-1)) + ADD
        diff = packing_min([CROSS, CROSS] + [2*CROSS]*(k-2)) + ADD if k >= 2 else None
        later = same if diff is None else min(same, diff)
        out.append(dict(k=k, first_round=first, later_same_core=same,
                        later_different_core=diff, later_round=later,
                        total_24_rounds=first+23*later))
    return out


class PrefixMax:
    """Range-add / range-max tree, including a witness coordinate."""
    def __init__(self, values):
        self.n = len(values)
        self.mx = [0]*(4*self.n); self.lazy = [0]*(4*self.n); self.arg = [0]*(4*self.n)
        def build(v, l, r):
            if l == r: self.mx[v], self.arg[v] = values[l], l; return
            m = (l+r)//2; build(2*v,l,m); build(2*v+1,m+1,r); self.pull(v)
        build(1,0,self.n-1)
    def pull(self,v):
        child = 2*v if self.mx[2*v] >= self.mx[2*v+1] else 2*v+1
        self.mx[v], self.arg[v] = self.mx[child], self.arg[child]
    def push(self,v):
        z = self.lazy[v]
        if z:
            for child in (2*v,2*v+1): self.mx[child] += z; self.lazy[child] += z
            self.lazy[v] = 0
    def add_prefix(self,end,value):
        def go(v,l,r):
            if r <= end: self.mx[v] += value; self.lazy[v] += value; return
            self.push(v); m=(l+r)//2
            go(2*v,l,m)
            if end>m: go(2*v+1,m+1,r)
            self.pull(v)
        go(1,0,self.n-1)
    def max_prefix(self,end):
        def go(v,l,r):
            if r <= end: return self.mx[v],self.arg[v]
            self.push(v); m=(l+r)//2; left=go(2*v,l,m)
            if end<=m: return left
            right=go(2*v+1,m+1,r)
            return left if left[0]>=right[0] else right
        return go(1,0,self.n-1)


def window_bound(items: list[tuple[int, int, int]], k: int) -> dict:
    """items=(certified release, certified EXCLUSIVE tail, resource work).
    The algorithm checks the expression, NOT validity of release/tail inputs.
    Complexity O(n log n), excluding empty selected subsets.
    """
    if k <= 0 or any(r<0 or q<0 or d<=0 for r,q,d in items):
        raise ValueError('Require k>0, r/q>=0, d>0; integer cycle inputs')
    if not items: return dict(bound=0, witness=None)
    qs=sorted({q for r,q,d in items}); pos={q:j for j,q in enumerate(qs)}
    tree=PrefixMax([k*q for q in qs]); highest=-1; best=-1; witness=None
    for release, group in groupby(sorted(items, reverse=True), key=lambda x:x[0]):
        for r,q,d in group:
            j=pos[q]; tree.add_prefix(j,d); highest=max(highest,j)
        score,j=tree.max_prefix(highest)  # Never query empty q-threshold subsets.
        val=release+(score+k-1)//k
        if val>best: best=val; witness=(release,qs[j])
    aa,bb=witness
    work=sum(d for r,q,d in items if r>=aa and q>=bb)
    assert work>0 and best==aa+bb+(work+k-1)//k
    return dict(bound=best,witness=dict(a=aa,b=bb,work=work,capacity=k))


def self_test():
    assert tiny_counterexample()['makespan']==3894
    local=local_reduction_counterexample()
    assert local['all_reductions_in_tail']['makespan']==5231
    assert local['local_pair_reductions']['makespan']==5218
    expected={'uncut4_fixed_tail':201344, 'uncut5_rotating_tail':180644,
              'split22_fixed_tail':178592, 'split31_rotating_tail':169944,
              'split31_star_fixed_tail':166540}
    for shape in ('balanced','comb'):
        for mode,val in expected.items():
            assert construction(mode,24,shape)['makespan']==val
    assert [v['total_24_rounds'] for v in lower_bounds()]==[607080,327198,236476,187575,161020]
    rng=random.Random(20260924)
    for _ in range(160):
        items=[(rng.randrange(10),rng.randrange(10),rng.randrange(1,20)) for _ in range(rng.randrange(1,9))]
        k=rng.randrange(1,6)
        brute=max(aa+bb+(sum(d for r,q,d in items if r>=aa and q>=bb)+k-1)//k
                  for aa in {r for r,q,d in items} for bb in {q for r,q,d in items}
                  if any(r>=aa and q>=bb for r,q,d in items))
        assert window_bound(items,k)['bound']==brute
    assert window_bound([],5)['bound']==0
    try:
        evaluate_r([Node('u',1),Node('x',1,('u',)),Node('v',1,('x',))],
                   [Task('M',0,('u','v')),Task('X',1,('x',))],[['M'],['X']])
    except ValueError as exc:
        assert 'cycle' in str(exc)
    else: raise AssertionError('Illegal contraction not rejected')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',help='Optional JSON path for complete R certificates')
    args=parser.parse_args(); self_test()
    modes=('uncut4_fixed_tail','uncut5_rotating_tail','split22_fixed_tail','split31_rotating_tail','split31_star_fixed_tail')
    data={'scope':'Mathematical model R only. No official E0 or user-machine experiments.',
          'tiny_counterexample':tiny_counterexample(),
          'local_reduction_counterexample':local_reduction_counterexample(),
          'lower_bounds':lower_bounds(),
          'k5_task_granularity_lower_bound':{'first_round':10*P+SWITCH+CROSS+ADD,
              'later_round':9*P+SWITCH+2*CROSS+ADD,
              'total_24_rounds':(10*P+SWITCH+CROSS+ADD)+23*(9*P+SWITCH+2*CROSS+ADD),
              'status':'Proved by case analysis in the accompanying response; not obtained by plan search.'},
          'k5_shared_tail_class_optimum':6483+23*6959,
          'constructions':[construction(m) for m in modes],
          'window_example':window_bound([(0,15,5),(5,5,10),(5,5,10),(5,5,10),(15,0,5)],2)}
    if args.output:
        with open(args.output,'w',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2)
    print(json.dumps({'scope':data['scope'], 'tiny_counterexample':3894,
                      'lower_bounds':data['lower_bounds'],
                      'k5_task_granularity_lower_bound':data['k5_task_granularity_lower_bound'],
                      'k5_shared_tail_class_optimum':data['k5_shared_tail_class_optimum'],
                      'constructions':[{key:c[key] for key in ('mode','makespan','task_count')}
                                       for c in data['constructions']],
                      'window_example':data['window_example']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
