"""Read six frozen 016 results; no solver, official imports, or evaluation calls.

The longest paths are lower bounds for fixed singleton plans, not rescoring.
Run from any cwd: python3 path/to/analyze.py
"""
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import heapq
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    if path.suffix == '.gz':
        with gzip.open(path, 'rt') as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def histogram(values):
    return [{'value': v, 'count': n} for v, n in sorted(Counter(values).items())]


def write_csv(name, rows):
    with (OUT / name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    graph_path = ROOT / 'data/raw/a/official/data/case_016.json'
    graph = read(graph_path)
    allops = {x['id']: x for x in graph['ops']}
    ops = {u: x for u, x in allops.items() if x['op'] not in ('COPY_IN', 'COPY_OUT')}
    tensors = {x['id']: x for x in graph['tensors']}
    assert len(ops) == 17995 and {x['pipe'] for x in ops.values()} == {'PIPE_V'}
    producers, consumers = defaultdict(set), defaultdict(set)
    for e in graph['edges']:
        a, b = e['source'], e['target']
        assert (a in allops and b in tensors) or (a in tensors and b in allops)
        if a in allops:
            producers[b].add(a)
        else:
            consumers[a].add(b)
    assert all(len(p) <= 1 for p in producers.values())
    tensor_edges = {}
    preds, succs = defaultdict(set), defaultdict(set)
    for t in tensors:
        for p in producers[t] & ops.keys():
            for c in consumers[t] & ops.keys():
                tensor_edges[p, c] = t
                preds[c].add(p)
                succs[p].add(c)
    # The frozen graph has increasing compute IDs and a unique fork at each
    # nonfinal scalar root. This is a diagnostic guard, not a general recognizer.
    assert all(p < c for p, c in tensor_edges)
    stage = {}
    for u in sorted(ops):
        stage[u] = max((stage[p] + int(len(succs[p]) > 1) for p in preds[u]), default=0)
    roots = {stage[u]: u for u in ops if len(succs[u]) != 1}
    assert len(roots) == 305 and set(Counter(stage.values()).values()) == {59}
    assert all(len(succs[u]) in (0, 1, 12) for u in ops)
    duration = {u: max(1, x['cycles']) for u, x in ops.items()}
    all_pipes, all_stages, all_stage_ops, summaries = [], [], [], []
    manifest = {'scope': 'existing results only; no solver/E0/E1/E2', 'inputs': {}}
    source_paths = [graph_path, ROOT / 'data/raw/a/official/data/config.txt',
                    ROOT / 'src/q2_nikolastarx/vector_lanes.py',
                    ROOT / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py',
                    ROOT / 'data/raw/a/official/code/schedule_step3.py']
    for variant in ('direct', 'vector'):
        for k in (2, 4, 5):
            folder = ROOT / f'results/a/q2-nikolastarx/{variant}-pilot-20260924/run/016-k{k}'
            paths = [folder/'plan.json', folder/'final/result.json.gz', folder/'final/trace.json.gz']
            source_paths.extend(paths)
            plan, result, trace = (read(p) for p in paths)
            assert result['num_cores'] == k
            sg_to_op = {sg: int(u) for u, sg in plan['node_to_subgraph'].items()}
            assert len(sg_to_op) == len(ops) and set(sg_to_op.values()) == set(ops)
            seqs = [[sg_to_op[sg] for sg in seq] for seq in plan['core_schedules']]
            owner = {u: c for c, seq in enumerate(seqs) for u in seq}
            assert len(owner) == len(ops)
            events, pipe_events = {}, defaultdict(list)
            for core in result['per_core_timeline']:
                c = core['core_id']
                for e in core['ops']:
                    assert (c, e['op_id']) not in events
                    events[c, e['op_id']] = e
                    pipe_events[c, e['pipe']].append(e)
            trace_events = {}
            for e in trace['traceEvents']:
                a = e.get('args', {})
                if e.get('ph') == 'X' and 'op_id' in a:
                    key = (a['core_id'], a['op_id'])
                    assert key not in trace_events
                    trace_events[key] = (e['ts'], e['ts'] + e['dur'], a['pipe'])
            assert trace_events == {key: (e['start'], e['end'], e['pipe']) for key, e in events.items()}
            compute = {u: events[owner[u], u] for u in ops}
            assert all(compute[u]['duration'] == duration[u] for u in ops)
            # Check the bound's retained edges against these actual executions,
            # independently of whether the resulting scalar bound is tight.
            for (p, c), t in tensor_edges.items():
                lag = 0
                if owner[p] != owner[c]:
                    size, bandwidth = tensors[t]['size'], result['bandwidth_bytes_per_cycle']
                    lag = result['cross_core_copy_delay_cycles'] + 2 * max(1, (size+bandwidth-1)//bandwidth)
                assert compute[p]['end'] + lag <= compute[c]['start']
            for c, seq in enumerate(seqs):
                assert seq == [e['op_id'] for e in sorted(pipe_events[c, 'PIPE_V'], key=lambda e: e['start'])]
            for (c, pipe), values in sorted(pipe_events.items()):
                values.sort(key=lambda e: (e['start'], e['op_id']))
                assert all(a['end'] <= b['start'] for a, b in zip(values, values[1:]))
                busy = sum(e['duration'] for e in values)
                gaps = [b['start']-a['end'] for a, b in zip(values, values[1:])]
                all_pipes.append(dict(variant=variant, cores=k, core=c, pipe=pipe,
                    op_count=len(values), busy_cycles=busy, first_start=values[0]['start'],
                    last_end=values[-1]['end'], internal_idle_cycles=sum(gaps),
                    max_internal_gap=max(gaps, default=0),
                    idle_over_whole_makespan=result['makespan']-busy))
            root_ends = [compute[roots[s]]['end'] for s in range(len(roots))]
            for s, root in sorted(roots.items()):
                values = [u for u in range(13+59*s, 13+59*(s+1))]
                assert all(stage[u] == s for u in values)
                all_stages.append(dict(variant=variant, cores=k, stage=s, root=root,
                    root_core=owner[root], root_start=compute[root]['start'], root_end=compute[root]['end'],
                    period_from_previous_root='' if s == 0 else root_ends[s]-root_ends[s-1],
                    first_compute_start=min(compute[u]['start'] for u in values)))
                if s == 100:
                    for u in values:
                        all_stage_ops.append(dict(variant=variant, cores=k, stage=s, op=u,
                            op_name=ops[u]['op'], core=owner[u], start=compute[u]['start'],
                            end=compute[u]['end'], duration=duration[u],
                            predecessor_ops=';'.join(map(str, sorted(preds[u])))))
            # Only mandatory retained tensor and submitted singleton FIFO edges.
            arc = {u: {} for u in ops}
            for (p, c), t in tensor_edges.items():
                arc[p][c] = dict(tensor=t, cross=owner[p] != owner[c], kind='tensor')
            for seq in seqs:
                for p, c in zip(seq, seq[1:]):
                    arc[p].setdefault(c, dict(tensor=None, cross=False, kind='FIFO'))
            indegree = Counter(c for values in arc.values() for c in values)
            ready = [u for u in ops if not indegree[u]]
            heapq.heapify(ready)
            topological = []
            while ready:
                u = heapq.heappop(ready)
                topological.append(u)
                for c in arc[u]:
                    indegree[c] -= 1
                    if not indegree[c]:
                        heapq.heappush(ready, c)
            assert len(topological) == len(ops)
            bounds = []
            for mode in ('compute_only', 'cross_delay', 'cross_delay_and_min_copy'):
                start, parent = {u: 0 for u in ops}, {}
                for p in topological:
                    for c, info in arc[p].items():
                        lag = 0
                        if info['cross'] and mode != 'compute_only':
                            lag = result['cross_core_copy_delay_cycles']
                            if mode == 'cross_delay_and_min_copy':
                                size, bandwidth = tensors[info['tensor']]['size'], result['bandwidth_bytes_per_cycle']
                                lag += 2 * max(1, (size + bandwidth - 1)//bandwidth)
                        value = start[p] + duration[p] + lag
                        if value > start[c]:
                            start[c], parent[c] = value, (p, lag)
                end = {u: start[u]+duration[u] for u in ops}
                sink = max(ops, key=lambda u: (end[u], -u))
                path, v = [], sink
                while True:
                    path.append(v)
                    if v not in parent:
                        break
                    v = parent[v][0]
                path.reverse()
                lag_sum = sum(parent[u][1] for u in path[1:])
                compute_sum = sum(duration[u] for u in path)
                assert compute_sum + lag_sum == end[sink] <= result['makespan']
                bounds.append(dict(mode=mode, lower_bound=end[sink], sink=sink,
                    gap_to_observed=result['makespan']-end[sink],
                    path_compute_work=compute_sum, path_lag_sum=lag_sum,
                    path_cross_edges=sum(arc[p][c]['cross'] for p,c in zip(path,path[1:])),
                    path_compute_nodes=len(path), path_sha256=hashlib.sha256(json.dumps(path).encode()).hexdigest(),
                    root_period_histogram=histogram(end[roots[s]]-end[roots[s-1]] for s in range(1,len(roots))),
                    path_stage100=[dict(op=u, core=owner[u], bound_start=start[u], bound_end=end[u],
                        prev=None if u not in parent else parent[u][0],
                        prev_lag=0 if u not in parent else parent[u][1]) for u in path if stage[u] == 100]))
            transfers = []
            for x in result['cross_core_transfers']:
                t = x['tensor_id']
                pp = producers[t] & ops.keys()
                assert len(pp) == 1
                p = next(iter(pp))
                cc = sorted(c for c in consumers[t] & ops.keys() if owner[c] == x['target_core'])
                assert cc and owner[p] == x['source_core']
                co = events[x['source_core'], x['source_copy_out_id']]
                ci = events[x['target_core'], x['target_copy_in_id']]
                assert x['copy_in_release']-x['copy_out_end'] == result['cross_core_copy_delay_cycles']
                transfers.append(dict(tensor=t, size=x['size'], producer=p, producer_stage=stage[p],
                    consumer_ops=cc, source_core=x['source_core'], target_core=x['target_core'],
                    producer_end=compute[p]['end'], copy_out_id=x['source_copy_out_id'],
                    copy_out_start=co['start'], copy_out_end=co['end'],
                    copy_in_id=x['target_copy_in_id'], copy_in_release=x['copy_in_release'],
                    copy_in_start=ci['start'], copy_in_end=ci['end'],
                    out_wait_after_producer=co['start']-compute[p]['end'],
                    in_wait_after_release=ci['start']-x['copy_in_release'],
                    first_consumer_start=min(compute[c]['start'] for c in cc)))
            summaries.append(dict(variant=variant, cores=k, makespan=result['makespan'],
                movement=result['data_movement_bytes'], memory_peak=result['memory_peak_by_core'],
                result_trace_op_intervals_equal=True, checked_op_intervals=len(events),
                retained_compute_edges_observed_valid=True,
                submitted_compute_order_equals_executed_V_FIFO=True,
                first_root_end=root_ends[0], final_root_end=root_ends[-1],
                root_period_histogram=histogram(b-a for a,b in zip(root_ends, root_ends[1:])),
                pipe_work=[p for p in all_pipes if p['variant'] == variant and p['cores'] == k],
                fixed_plan_bounds=bounds, transfer_count=len(transfers),
                transfer_in_wait_histogram=histogram(t['in_wait_after_release'] for t in transfers),
                transfer_out_wait_histogram=histogram(t['out_wait_after_producer'] for t in transfers),
                stage100_transfers=[t for t in transfers if t['producer_stage'] == 100 or
                    any(stage[u] == 100 for u in t['consumer_ops'])],
                largest_in_waits=sorted(transfers, key=lambda t: (-t['in_wait_after_release'], t['copy_in_id']))[:5]))
    for p in source_paths:
        manifest['inputs'][str(p.relative_to(ROOT))] = dict(bytes=p.stat().st_size, sha256=digest(p))
    manifest['analysis_source_sha256'] = digest(Path(__file__).resolve())
    (OUT/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (OUT/'summary.json').write_text(json.dumps(summaries, indent=2)+'\n')
    write_csv('pipe_work.csv', all_pipes)
    write_csv('stages.csv', all_stages)
    write_csv('stage100_ops.csv', all_stage_ops)
    for s in summaries:
        print(s['variant'], s['cores'], 'makespan', s['makespan'], 'fixed_bounds',
              [b['lower_bound'] for b in s['fixed_plan_bounds']], 'matched_intervals', s['checked_op_intervals'])


if __name__ == '__main__':
    main()
