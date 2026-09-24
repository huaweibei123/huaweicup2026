"""Read one existing vector_split E0 result/trace; never build or evaluate."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def read(path):
    if path.suffix == '.gz':
        with gzip.open(path, 'rt') as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hist(values):
    return [{'value': v, 'count': n} for v, n in sorted(Counter(values).items())]


def csv_write(name, rows):
    with (OUT/name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    args = parser.parse_args()
    run = args.run_dir
    files = ['final/result.json.gz', 'final/trace.json.gz', 'plan.json',
             'online/vector_split/plan.json', 'online/solver.json', 'run.json']
    manifest = read(run/'manifest.json')
    for name in files:
        assert sha(run/name) == manifest[name]['sha256']
    result, trace, plan, ledger = (read(run/name) for name in
        ('final/result.json.gz', 'final/trace.json.gz', 'plan.json', 'online/solver.json'))
    assert (run/'plan.json').read_bytes() == (run/'online/vector_split/plan.json').read_bytes()
    detail = ledger['attempts'][0]['detail']
    static = read(ROOT/'results/a/q2-nikolastarx/vector-split-static-20260925/report.json')
    assert sha(run/'plan.json') == static['plan_sha256']
    graph_path = ROOT/'data/raw/a/official/data/case_016.json'
    assert sha(graph_path) == static['input_sha256']
    graph = read(graph_path)
    ops = {x['id']: x for x in graph['ops'] if x['op'] not in ('COPY_IN', 'COPY_OUT')}
    producer, consumers = {}, defaultdict(list)
    for edge in graph['edges']:
        a, b = edge['source'], edge['target']
        if a in ops:
            assert b not in producer
            producer[b] = a
        if b in ops:
            consumers[a].append(b)
    inverse = {sg: int(u) for u, sg in plan['node_to_subgraph'].items()}
    sequences = [[inverse[sg] for sg in seq] for seq in plan['core_schedules']]
    owner = {u: c for c, seq in enumerate(sequences) for u in seq}
    assert set(owner) == set(ops)
    stage_of, current_stage = {}, 0
    roots_by_id = {x['root_op']: x['stage'] for x in detail['stage_detail']}
    # Frozen input has ascending op IDs within each complete stage.
    for u in sorted(ops):
        stage_of[u] = current_stage
        if u in roots_by_id:
            assert roots_by_id[u] == current_stage
            current_stage += 1
    assert current_stage == detail['stages']
    events, pipe = {}, defaultdict(list)
    for core in result['per_core_timeline']:
        c = core['core_id']
        for e in core['ops']:
            events[c, e['op_id']] = e
            pipe[c, e['pipe']].append(e)
    previous_pipe = {}
    for key, values in pipe.items():
        values.sort(key=lambda e: (e['start'], e['op_id']))
        for a, b in zip(values, values[1:]):
            assert a['end'] <= b['start']
            previous_pipe[key[0], b['op_id']] = a
    trace_ops = {(e['args']['core_id'], e['args']['op_id']): (e['ts'], e['ts']+e['dur'], e['args']['pipe'])
                 for e in trace['traceEvents'] if e.get('ph') == 'X' and 'op_id' in e.get('args', {})}
    assert trace_ops == {key: (e['start'], e['end'], e['pipe']) for key, e in events.items()}
    for c, seq in enumerate(sequences):
        assert seq == [e['op_id'] for e in pipe[c, 'PIPE_V']]
    root_ends = [events[s['root_core'], s['root_op']]['end'] for s in detail['stage_detail']]
    bound_ends = detail['fixed_plan_bound']['stage_root_end']
    stages = [{'stage': s, 'root_end': end, 'root_period': '' if not s else end-root_ends[s-1],
               'bound_root_end': bound_ends[s],
               'bound_root_period': '' if not s else bound_ends[s]-bound_ends[s-1]}
              for s, end in enumerate(root_ends)]
    transfers_by_producer = defaultdict(list)
    for t in result['cross_core_transfers']:
        transfers_by_producer[producer[t['tensor_id']]].append(t)
    rows = []
    length = detail['chain_length']
    for t in result['cross_core_transfers']:
        if t['size'] != detail['vector_bytes']:
            continue
        p, c = producer[t['tensor_id']], consumers[t['tensor_id']][0]
        stage, sender, receiver = stage_of[p], t['source_core'], t['target_core']
        assert owner[p] == sender and owner[c] == receiver and stage_of[c] == stage
        seq = [u for u in sequences[receiver] if stage_of[u] == stage]
        before = seq[:seq.index(c)]
        assert len(before) == detail['whole_lanes_per_core']*length
        op2, whole_last = before[-length+1], before[-1]
        suffix_last = seq[-1]
        last_leaf_transfer, = [x for x in transfers_by_producer[suffix_last]
                               if x['target_core'] == detail['fixed_root_core']]
        copyout, copyin = events[sender, t['source_copy_out_id']], events[receiver, t['target_copy_in_id']]
        previous_mte2 = previous_pipe.get((receiver, t['target_copy_in_id']))
        suffix = events[receiver, c]
        sender_seq = [u for u in sequences[sender] if stage_of[u] == stage]
        mid_index = length//2 + 2
        sender_mid, sender_previous = sender_seq[mid_index], sender_seq[mid_index-1]
        whole_end = events[receiver, whole_last]['end']
        op2_end = events[receiver, op2]['end']
        prior_end = previous_mte2['end'] if previous_mte2 else 0
        rows.append({'stage': stage, 'tensor': t['tensor_id'], 'sender': sender, 'receiver': receiver,
            'prefix_last_op': p, 'prefix_end': events[sender,p]['end'],
            'sender_first_whole_op3': sender_mid,
            'sender_first_whole_op3_start': events[sender,sender_mid]['start'],
            'sender_V_gap_before_whole_op3': events[sender,sender_mid]['start']-events[sender,sender_previous]['end'],
            'sender_op3_start_minus_copy_out_end': events[sender,sender_mid]['start']-copyout['end'],
            'copy_out_id': t['source_copy_out_id'], 'copy_out_start': copyout['start'],
            'copy_out_end': copyout['end'], 'copy_out_duration': copyout['duration'],
            'copy_in_id': t['target_copy_in_id'], 'copy_in_release': t['copy_in_release'],
            'copy_in_start': copyin['start'], 'copy_in_end': copyin['end'], 'copy_in_duration': copyin['duration'],
            'wait_after_release': copyin['start']-t['copy_in_release'],
            'previous_MTE2_op': '' if previous_mte2 is None else previous_mte2['op_id'],
            'previous_MTE2_end': prior_end,
            'wait_beyond_release_and_MTE2_predecessor': copyin['start']-max(t['copy_in_release'],prior_end),
            'second_whole_op2': op2, 'second_whole_op2_end': op2_end,
            'copy_start_minus_op2_end': copyin['start']-op2_end,
            'same_core_ops_ending_at_copy_start': ';'.join(str(u) for (core,u),e in events.items()
                if core == receiver and e['end'] == copyin['start']),
            'whole_last_op': whole_last, 'whole_end': whole_end,
            'suffix_first_op': c, 'suffix_start': suffix['start'], 'suffix_last_op': suffix_last,
            'suffix_end': events[receiver,suffix_last]['end'],
            'copy_finish_after_whole_end': copyin['end']-whole_end,
            'suffix_gap': suffix['start']-whole_end,
            'unexplained_suffix_delay': suffix['start']-max(copyin['end'],whole_end),
            'receiver_first_start': events[receiver,seq[0]]['start'],
            'root_input_copy_end': last_leaf_transfer['copy_in_end'],
            'root_tail_after_leaf_copy': root_ends[stage]-last_leaf_transfer['copy_in_end']})
    assert len(rows) == detail['planned_large_crossing_pairs']
    steady = [x for x in rows if x['stage']]
    hist_fields = ('wait_after_release', 'copy_out_duration', 'copy_in_duration',
                   'wait_beyond_release_and_MTE2_predecessor', 'copy_start_minus_op2_end',
                   'copy_finish_after_whole_end', 'suffix_gap', 'unexplained_suffix_delay',
                   'sender_V_gap_before_whole_op3', 'sender_op3_start_minus_copy_out_end')
    gap = result['makespan']-detail['fixed_plan_bound']['makespan_lower_bound_cycles']
    first_gap = root_ends[0]-bound_ends[0]
    period_gap = sum((root_ends[s]-root_ends[s-1])-(bound_ends[s]-bound_ends[s-1]) for s in range(1,len(root_ends)))
    final_copy = result['makespan']-root_ends[-1]
    assert gap == first_gap+period_gap+final_copy
    # On every steady stage the receiver-3 path is tight through final root V FIFO.
    critical_rows = [x for x in steady if x['receiver'] == 3]
    for row in critical_rows:
        s = row['stage']
        assert row['receiver_first_start']-root_ends[s-1] == 505
        assert row['whole_end']-row['receiver_first_start'] == 4192
        assert row['suffix_gap'] == 49 and row['suffix_end']-row['suffix_start'] == 1048
        assert row['root_input_copy_end']-row['suffix_end'] == 502
        assert row['root_tail_after_leaf_copy'] == 91
    summary = {'scope': 'existing single E0 readback; 0 new solvers/E0/E1/E2',
        'reader_sha256': sha(Path(__file__).resolve()), 'input_sha256': sha(graph_path),
        'source_commit': static['source_commit'], 'plan_sha256': sha(run/'plan.json'),
        'read_file_sha256': {name:sha(run/name) for name in files},
        'result_trace_equal_op_intervals': len(events),
        'makespan_cycles': result['makespan'], 'movement_bytes': result['data_movement_bytes'],
        'memory_peak_by_core': result['memory_peak_by_core'],
        'root_period_histogram': hist(x['root_period'] for x in stages[1:]),
        'fixed_bound_period_histogram': hist(x['bound_root_period'] for x in stages[1:]),
        'gap_to_fixed_bound': gap, 'gap_decomposition': {'first_root': first_gap, 'subsequent_periods': period_gap, 'final_copy_out': final_copy},
        'large_transfer_count': len(rows), 'steady_large_transfer_count': len(steady),
        'steady_copy_start_has_only_op2_as_same_core_completion': all(
            x['same_core_ops_ending_at_copy_start'] == str(x['second_whole_op2']) for x in steady),
        'steady_histograms': {key:hist(x[key] for x in steady) for key in hist_fields},
        'first_stage_large_transfers': [x for x in rows if not x['stage']],
        'stage100_large_transfers': [x for x in rows if x['stage']==100],
        'steady_critical_path': '505 broadcast + 4192 whole chains + 49 wait + 1048 suffix + 502 scalar transfer + 91 root V tail = 6387',
        'credit_edges_available_in_result_or_trace': False,
        'attribution_limit': 'Late COPY start matches the proposed WAR predecessor exactly, but exports omit full credit edges; timing alone cannot prove which memory edge caused readiness.'}
    csv_write('large_transfers.csv', rows)
    csv_write('stage_roots.csv', stages)
    (OUT/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ('makespan_cycles','result_trace_equal_op_intervals','root_period_histogram',
        'gap_decomposition','steady_histograms')},indent=2))


if __name__ == '__main__':
    main()
