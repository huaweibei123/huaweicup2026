#!/usr/bin/env python3
"""Read-only scalar summaries of three existing P2 E0 result.json files."""
import argparse
from collections import defaultdict
from pathlib import Path
import datetime, hashlib, json, math, re
PIPES = ('PIPE_M', 'PIPE_V', 'PIPE_MTE2', 'PIPE_MTE3')
CASES = ('005', '009', '015')

def digest(raw): return hashlib.sha256(raw).hexdigest()
def cycle(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value:
        raise ValueError(f'{label} must be an integral cycle value')
    return int(value)
def summarize(path, case, reference):
    raw = path.read_bytes(); d = json.loads(raw)
    makespan = cycle(d['makespan'], 'makespan'); per_core = []
    for core in d['per_core_timeline']:
        by_pipe = defaultdict(list)
        for op in core.get('ops', []):
            if op.get('pipe') not in PIPES: continue
            start, end = cycle(op['start'],'op.start'), cycle(op['end'],'op.end')
            duration = cycle(op['duration'],'op.duration')
            if end < start or duration != end-start: raise ValueError('op interval/duration mismatch')
            by_pipe[op['pipe']].append((start,end))
        pipes = {}
        for pipe in PIPES:
            ops = sorted(by_pipe[pipe]); busy = sum(e-s for s,e in ops)
            if ops:
                first, last = ops[0][0], max(e for _,e in ops)
                internal = last-first-busy
                overlaps = sum(ops[i][1] > ops[i+1][0] for i in range(len(ops)-1))
                pipes[pipe] = {'busy_cycles':busy,'op_count':len(ops),'leading_idle_cycles':first,
                    'internal_idle_cycles':internal,'trailing_idle_cycles':makespan-last,
                    'whole_run_idle_cycles':makespan-busy,'overlapping_adjacent_pairs':overlaps}
            else:
                pipes[pipe] = {'busy_cycles':0,'op_count':0,'leading_idle_cycles':None,
                    'internal_idle_cycles':None,'trailing_idle_cycles':None,
                    'whole_run_idle_cycles':makespan,'overlapping_adjacent_pairs':0}
        per_core.append({'core':core['core_id'],'pipes':pipes})
    deps=d.get('task_dependencies',[]); trans=d.get('cross_core_transfers',[])
    expected=cycle(d.get('cross_core_copy_delay_cycles',0),'cross-core delay');lags=[];gaps=[];missing=0
    for x in trans:
        if 'copy_out_end' not in x or 'copy_in_release' not in x: missing+=1;continue
        out=cycle(x['copy_out_end'],'copy_out_end'); release=cycle(x['copy_in_release'],'copy_in_release');lags.append(release-out)
        if 'copy_in_start' in x: gaps.append(cycle(x['copy_in_start'],'copy_in_start')-release)
    movement=d.get('data_movement_bytes',{})
    pipe_balance={}
    for pipe in ('PIPE_M','PIPE_V'):
        busy=[x['pipes'][pipe]['busy_cycles'] for x in per_core]
        pipe_balance[pipe]={'per_core_busy_cycles':busy,'min':min(busy),'max':max(busy),
            'max_over_min':max(busy)/min(busy) if min(busy) else None}
    return {'case':case,'source_reference':reference,'result_path':f'{case}-k5/result.json',
        'source_sha256':digest(raw),'makespan_cycles':makespan,'capacity_bytes':d.get('capacity_bytes'),
        'cross_core_copy_delay_cycles':expected,'task_dependencies':len(deps),'cross_core_transfers':len(trans),
        'transfer_lag_cycles':{'identified':len(lags),'missing_fields':missing,'equals_configured_delay':sum(x==expected for x in lags),
          'min':min(lags) if lags else None,'max':max(lags) if lags else None,
          'copy_in_gap_after_release_min':min(gaps) if gaps else None,'copy_in_gap_after_release_max':max(gaps) if gaps else None},
        'movement_bytes':{k:movement.get(k) for k in ('added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes')},
        'independent_compute_pipe_balance':pipe_balance,'per_core':per_core}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run-dir',required=True,type=Path);ap.add_argument('--source-reference',default=None);ap.add_argument('--out-dir',type=Path,default=Path(__file__).parent);a=ap.parse_args()
    ref=a.source_reference or a.run_dir.name
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',ref): raise ValueError('source-reference must be a portable short label')
    cases=[summarize(a.run_dir/f'{c}-k5/result.json',c,ref) for c in CASES]
    out={'scope':'read-only scalar analysis of existing official result artifacts; no trace replay, solver or evaluator',
      'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cases':cases,
      'limitations':['Pipe busy and idle are reported separately; M and V are independent resources, not interchangeable workload.',
       'Leading/internal/trailing idle is relative to [0,M] and does not identify cause or criticality.',
       'A large copy-in start-minus-release gap may be non-critical transfer ordering; it does not prove a makespan stall.',
       'No complete critical path is reconstructed.']}
    a.out_dir.mkdir(parents=True,exist_ok=True);(a.out_dir/'diagnostic.json').write_text(json.dumps(out,indent=2)+'\n')
    lines=['# Hypergap timeline diagnostic','',f"Source reference: `{ref}`; result paths are relative. This script only reads existing `result.json`; no solver, constructor or evaluator is invoked.",'']
    for x in cases:
        lag=x['transfer_lag_cycles']; lines += [f"## {x['case']} · K5",'',f"E0 M {x['makespan_cycles']:,} cycles; added DDR {x['movement_bytes']['added_copy_bytes']:,} B (partition {x['movement_bytes']['partition_added_copy_bytes']:,}, spill {x['movement_bytes']['spill_added_copy_bytes']:,}); dependencies/transfers {x['task_dependencies']}/{x['cross_core_transfers']}; configured cross-core delay {x['cross_core_copy_delay_cycles']} cycles.",
          f"Transfer fields identify {lag['identified']} release lags; {lag['equals_configured_delay']} equal configured delay; {lag['missing_fields']} missing. Observed copy-in start-minus-release gap range: {lag['copy_in_gap_after_release_min']}–{lag['copy_in_gap_after_release_max']} cycles. This gap alone is not evidence of critical stall.",
          f"Independent compute Pipe balance: M max/min {x['independent_compute_pipe_balance']['PIPE_M']['max_over_min']}; V max/min {x['independent_compute_pipe_balance']['PIPE_V']['max_over_min']}.",'', '|core|Pipe|busy|leading idle|internal idle|trailing idle|ops|','|---:|---|---:|---:|---:|---:|---:|']
        for c in x['per_core']:
            for p,v in c['pipes'].items():
                fmt=lambda z:'n/a' if z is None else f'{z:,}'
                lines.append(f"|{c['core']}|{p}|{v['busy_cycles']:,}|{fmt(v['leading_idle_cycles'])}|{fmt(v['internal_idle_cycles'])}|{fmt(v['trailing_idle_cycles'])}|{v['op_count']:,}|")
        lines.append('')
    lines += ['## Evidence limits and next hypothesis','',
      'Confirmed: per-core/per-Pipe busy and idle spans, separate M/V balance, MTE2/MTE3 activity, spill bytes, transfer/dependency counts, and configured 500-cycle release lag where fields expose it. These results do not identify why an idle interval occurred or whether a transfer is critical.',
      '', 'A testable algorithm hypothesis—not an established minimal effective change—is adding per-core PIPE_MTE2/PIPE_MTE3 availability calendars and honoring transfer release timestamps during candidate placement. First compare predicted copy release-to-start timing against these existing results; do not infer benefit from utilization alone.', '']
    (a.out_dir/'README.md').write_text('\n'.join(lines))
    print(json.dumps({'cases':[(x['case'],x['makespan_cycles'],x['movement_bytes'],x['task_dependencies'],x['cross_core_transfers'],x['transfer_lag_cycles']) for x in cases]},separators=(',',':')))
if __name__=='__main__': main()
