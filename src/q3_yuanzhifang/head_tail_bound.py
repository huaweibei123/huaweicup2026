"""Plan-independent head/tail workload bounds for original M/V operations.

Optimize the full upper-right head/tail threshold family in O(k V log V).
No placement, solution construction or official evaluator is called.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import heapq
import json
import math
from pathlib import Path
import subprocess
import time

from .baseline import ROOT
from multicore_cut_evaluate_problem_1 import _original_tensor_views
from evaluation_validation import read_bandwidth_config


class PrefixMax:
    def __init__(self, values):
        self.n = len(values)
        self.maximum = [0] * (4 * self.n)
        self.where = [0] * (4 * self.n)
        self.lazy = [0] * (4 * self.n)

        def init(node, left, right):
            if right-left == 1:
                self.maximum[node], self.where[node] = values[left], left
            else:
                mid = (left+right)//2
                init(node*2, left, mid)
                init(node*2+1, mid, right)
                self.pull(node)
        init(1, 0, self.n)

    def pull(self, node):
        a, b = node*2, node*2+1
        chosen = a if self.maximum[a] >= self.maximum[b] else b
        self.maximum[node], self.where[node] = self.maximum[chosen], self.where[chosen]

    def push(self, node):
        for child in (node*2, node*2+1):
            self.maximum[child] += self.lazy[node]
            self.lazy[child] += self.lazy[node]
        self.lazy[node] = 0

    def add_prefix(self, end, value):
        def add(node, left, right):
            if right <= end:
                self.maximum[node] += value
                self.lazy[node] += value
                return
            self.push(node)
            mid = (left+right)//2
            add(node*2, left, mid)
            if end > mid:
                add(node*2+1, mid, right)
            self.pull(node)
        add(1, 0, self.n)

    def query_prefix(self, end):
        def query(node, left, right):
            if right <= end:
                return self.maximum[node], -self.where[node]
            self.push(node)
            mid = (left+right)//2
            value = query(node*2, left, mid)
            if end > mid:
                value = max(value, query(node*2+1, mid, right))
            return value
        value, negative_index = query(1, 0, self.n)
        return value, -negative_index


def energy_bound(points, cores):
    """points=(head, tail, duration), all nonnegative integers, duration>0."""
    if (type(cores) is not int or cores < 1
            or any(any(type(v) is not int for v in (h, t, w))
                   or h < 0 or t < 0 or w <= 0 for h, t, w in points)):
        raise ValueError('positive cores/work and nonnegative heads/tails required')
    if not points:
        return dict(bound=0, head=0, tail=0, work=0, operations=0)
    tails = sorted({t for _, t, _ in points})
    positions = {t: i for i, t in enumerate(tails)}
    tree = PrefixMax([cores*t for t in tails])
    groups = defaultdict(list)
    for h, t, w in points:
        groups[h].append((t, w))
    best, max_index = None, 0
    for h in sorted(groups, reverse=True):
        for t, w in groups[h]:
            index = positions[t]
            tree.add_prefix(index+1, w)
            max_index = max(max_index, index)
        # Larger thresholds can have an empty set: they provide no bound.
        value, index = tree.query_prefix(max_index+1)
        candidate = (h + (value+cores-1)//cores, h, tails[index])
        if best is None or candidate[0] > best[0]:
            best = candidate
    bound, head, tail = best
    selected = [w for h, t, w in points if h >= head and t >= tail]
    return dict(bound=bound, head=head, tail=tail, work=sum(selected), operations=len(selected))


def graph_points(graph, bandwidth):
    all_ops = {o['id']: o for o in graph['ops']}
    ops = {u: o for u, o in all_ops.items() if o['op'] not in ('COPY_IN', 'COPY_OUT')}
    if any(o['pipe'] not in ('PIPE_M', 'PIPE_V') or type(o['cycles']) is not int
           or o['cycles'] < 0 for o in ops.values()):
        raise ValueError('proved guard requires nonnegative integer M/V computation')
    if bandwidth <= 0:
        raise ValueError('positive bandwidth required')
    producers, consumers, direct = _original_tensor_views(graph)
    # The proof tracks each tensor through its one original definition and
    # any official spill incarnations. Multiple writers need a separate proof
    # about the backing selected by Step2; reject rather than extrapolate.
    if any(len(writers) > 1 for writers in producers.values()):
        raise ValueError('bound proof requires at most one original producer per tensor')
    pred = {u: set() for u in ops}
    for t, readers in consumers.items():
        for u in readers & ops.keys():
            pred[u].update((producers[t] & ops.keys()) - {u})
    for edge in direct:
        u, v = edge['source'], edge['target']
        if u in ops and v in ops:
            pred[v].add(u)
    succ = {u: set() for u in ops}
    for v, ps in pred.items():
        for u in ps:
            succ[u].add(v)
    head, tail = dict.fromkeys(ops, 0), dict.fromkeys(ops, 0)
    io_guard = all('logical_tid' not in t for t in graph['tensors'])
    if io_guard:
        for t in graph['tensors']:
            ps = producers[t['id']] & ops.keys()
            cs = consumers[t['id']] & ops.keys()
            service = max(1, math.ceil(t['size']/bandwidth))
            if cs and not ps:
                for u in cs:
                    head[u] = max(head[u], service)
            if ps and (not cs or any(all_ops[u]['op'] == 'COPY_OUT'
                                     for u in consumers[t['id']])):
                for u in ps:
                    tail[u] = max(tail[u], service)
    duration = {u: max(1, o['cycles']) for u, o in ops.items()}
    degree = {u: len(ps) for u, ps in pred.items()}
    ready = [u for u, d in degree.items() if not d]
    heapq.heapify(ready)
    order = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in succ[u]:
            head[v] = max(head[v], head[u]+duration[u])
            degree[v] -= 1
            if not degree[v]:
                heapq.heappush(ready, v)
    if len(order) != len(ops):
        raise ValueError('original eligible dependency cycle')
    for u in reversed(order):
        tail[u] = max([tail[u]] + [duration[v]+tail[v] for v in succ[u]])
    points = defaultdict(list)
    for u, o in ops.items():
        points[o['pipe']].append((head[u], tail[u], duration[u]))
    return points, io_guard


def analyze(graph, bandwidth, cores=range(1, 6)):
    points, io_guard = graph_points(graph, bandwidth)
    rows = []
    for k in cores:
        by_pipe = {p: energy_bound(values, k) for p, values in points.items()}
        rows.append(dict(cores=k, lower_bound_cycles=max(
            (v['bound'] for v in by_pipe.values()), default=0),
            by_pipe=by_pipe, unaliased_io_guard=io_guard))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--graph-dir', type=Path, required=True)
    ap.add_argument('--config', type=Path, default=ROOT / 'data/raw/a/official/data/config.txt')
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    started = time.perf_counter()
    code_path = Path(__file__).resolve()
    source_path = code_path.relative_to(ROOT).as_posix()
    source_commit = subprocess.check_output(
        ['git', 'log', '-1', '--format=%H', '--', source_path], cwd=ROOT).decode().strip()
    if subprocess.check_output(['git', 'show', source_commit+':'+source_path], cwd=ROOT) != code_path.read_bytes():
        raise ValueError('freeze source bytes before analysis')
    frozen = json.loads((ROOT/'docs/a/source-manifest.json').read_bytes())
    for item in frozen['files']:
        if item['path'].startswith('code/') or item['path'] == 'data/config.txt':
            path = ROOT/'data/raw/a/official'/item['path']
            if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('frozen official source/config mismatch: '+item['path'])
    graph_hashes = {Path(i['path']).name: i['sha256'] for i in frozen['files']
                    if i['path'].startswith('data/case_')}
    bw = read_bandwidth_config(args.config)
    rows = []
    for path in sorted(args.graph_dir.glob('case_*.json')):
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != graph_hashes[path.name]:
            raise ValueError('frozen graph mismatch: '+path.name)
        rows.extend(dict(case_id=path.stem.split('_')[1],
                         graph_sha256=hashlib.sha256(raw).hexdigest(), **r)
                    for r in analyze(json.loads(raw), bw))
        if len(rows) % 50 == 0:
            print(json.dumps(dict(cases=len(rows)//5, elapsed_seconds=time.perf_counter()-started)), flush=True)
    data = dict(method='original M/V head-tail interval workload necessary bound; no optimum claim',
                source_commit=source_commit, source_path=source_path,
                source_sha256=hashlib.sha256(code_path.read_bytes()).hexdigest(),
                official_code_hash=frozen['official_code_hash'],
                config_sha256=hashlib.sha256(args.config.read_bytes()).hexdigest(),
                analysis_wall_seconds=time.perf_counter()-started, solver_calls=0, E0_calls=0, rows=rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    print(json.dumps(dict(rows=len(rows), analysis_wall_seconds=time.perf_counter()-started)))


if __name__ == '__main__':
    main()
