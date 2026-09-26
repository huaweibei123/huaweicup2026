"""Audit saved P2 trace diagnostics for the paper without constructing/evaluating plans."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[5]
SOURCE = '7c9b648dfaad134215fcc09c0a3258861cdd4c72'
SUMMARY_COMMIT = '1c00079aadbd071de62db17686d5ba3fed1da0f2'
REPORT = 'results/a/q2-nikolastarx/k5-utilization-20260925/report.json'
SUMMARY = 'results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json'
SELECTED = ('005', '086', '088')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def union_length(intervals):
    total = 0
    end = None
    for start, stop in sorted(intervals):
        if stop <= start:
            continue
        if end is None or start >= end:
            total += stop - start
        elif stop > end:
            total += stop - end
        end = stop if end is None else max(end, stop)
    return total


def main():
    inputs = []

    def frozen(commit, path):
        raw = subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)
        inputs.append({'commit': commit, 'path': path, 'bytes': len(raw), 'sha256': sha(raw)})
        return raw

    report_raw = frozen(SOURCE, REPORT)
    report = json.loads(report_raw)
    summary_raw = frozen(SUMMARY_COMMIT, SUMMARY)
    summary = json.loads(summary_raw)
    assert sha(summary_raw) == report['inputs']['summary_sha256']
    assert summary['status'] == 'completed' and summary['accepted_cells'] == 500
    summary_cells = {(r['case'], r['cores']): r for r in summary['rows']}
    rows = {r['case']: r for r in report['all_cells']}
    assert len(rows) == len(report['all_cells']) == 100
    assert set(rows) == {f'{i:03}' for i in range(1, 101)}
    for case, row in rows.items():
        assert row['M'] == summary_cells[case, 5]['official']['makespan']
        cores = row['pipe_busy_cycles_per_core']
        assert len(cores) == len({c['core'] for c in cores}) == 5
        assert 0 <= row['copy_active_union_cycles'] <= row['M']
        assert row['copy_active_union_over_M'] == row['copy_active_union_cycles'] / row['M']
        for pipe in ('PIPE_M', 'PIPE_V'):
            assert sum(c[pipe] for c in cores) == row['pipe_busy_cycles_across_cores'][pipe]
            assert max(c[pipe] for c in cores) <= row['M']
            assert row['pipe_max_core_busy_over_M'][pipe] == max(c[pipe] for c in cores) / row['M']

    feeds = []
    for group in ('cases-001-010', 'cases-081-090'):
        name = f'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee/{group}/board-feed.json'
        raw = frozen(SOURCE, name)
        pinned = next(x for x in report['inputs']['feed_files'] if x['path'] == name)
        assert sha(raw) == pinned['sha256']
        feeds.extend(json.loads(raw)['records'])
    selected = []
    for case in SELECTED:
        feed = next(r for r in feeds if r['case_id'] == case and r['cores'] == 5)
        artifact = feed['artifacts']['result']
        raw = frozen(SOURCE, artifact['path'])
        assert sha(raw) == artifact['sha256'] == rows[case]['result_sha256']
        result_raw = gzip.decompress(raw)
        data = json.loads(result_raw)
        assert data['scene'] == 'B' and data['num_cores'] == 5
        assert data['makespan'] == rows[case]['M']
        # Audit both compressed archival identity and original result identity when available.
        assert sha(result_raw) == summary_cells[case, 5]['official']['result_sha256']
        intervals = []
        core_work = {}
        for core in data['per_core_timeline']:
            work = {'PIPE_M': 0, 'PIPE_V': 0}
            pipe_intervals = {'PIPE_M': [], 'PIPE_V': []}
            for op in core['ops']:
                start, end = op['start'], op['end']
                assert 0 <= start <= end <= data['makespan']
                if op['pipe'] in work:
                    work[op['pipe']] += end - start
                    pipe_intervals[op['pipe']].append((start, end))
                if op['op'] in ('COPY_IN', 'COPY_OUT'):
                    intervals.append((start, end))
            for pipe in work:
                assert work[pipe] == union_length(pipe_intervals[pipe]), 'overlapping same-Pipe events'
            core_work[core['core_id']] = work
        assert len(core_work) == 5
        for core in rows[case]['pipe_busy_cycles_per_core']:
            assert core_work[core['core']] == {p: core[p] for p in ('PIPE_M', 'PIPE_V')}
        assert union_length(intervals) == rows[case]['copy_active_union_cycles']
        assert len(intervals) == rows[case]['copy_event_count']
        selected.append(rows[case])
    recomputed = {
        'copy_active_union_ratio_mean': statistics.fmean(r['copy_active_union_over_M'] for r in rows.values()),
        'max_core_M_busy_ratio_mean': statistics.fmean(r['pipe_max_core_busy_over_M']['PIPE_M'] for r in rows.values()),
        'max_core_V_busy_ratio_mean': statistics.fmean(r['pipe_max_core_busy_over_M']['PIPE_V'] for r in rows.values()),
    }
    pairs = [('copy_active_union_ratio_mean', 'COPY_active_union_over_M'),
             ('max_core_M_busy_ratio_mean', 'PIPE_M_max_core_busy_over_M'),
             ('max_core_V_busy_ratio_mean', 'PIPE_V_max_core_busy_over_M')]
    for ours, theirs in pairs:
        assert abs(recomputed[ours] - report['all_k5'][theirs]['mean']) < 1e-12
    output = {
        'source_commit': SOURCE, 'inputs': inputs,
        'summary_crosschecked_cells': 100, 'raw_trace_recomputed_cases': list(SELECTED),
        'selected': selected, 'report_aggregate_recomputed': recomputed,
        'new_calls': {'solver': 0, 'Step2': 0, 'Step3': 0, 'E0': 0, 'E1': 0, 'E2': 0},
        'limits': ['100-row coverage, metrics and arithmetic checked against fixed summary; raw intervals independently recomputed only for the three named cases.',
                   'COPY-active time union is not byte-rate DDR utilization and does not establish critical-path causality.',
                   'Examples were already selected in development; they are not a holdout or new algorithm result.'],
    }
    path = Path(__file__).with_name('trace-diagnosis-check.json')
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': path.relative_to(ROOT).as_posix(), 'sha256': sha(path.read_bytes()),
                      'selected': [{'case': x['case'], 'M': x['M'], 'copy_ratio': x['copy_active_union_over_M'],
                                    'max_M_ratio': x['pipe_max_core_busy_over_M']['PIPE_M'], 'copy_events': x['copy_event_count']}
                                   for x in selected], 'new_calls': output['new_calls']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
