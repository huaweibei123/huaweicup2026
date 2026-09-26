"""Build a fixed-source Pro evidence pack and audit saved optimality gaps.

No solver, preparation, benchmark, or evaluator is invoked.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import statistics
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[5]
SOLVER = 'c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f'
AUDIT = '1c00079aadbd071de62db17686d5ba3fed1da0f2'
MEMBER = '178a3673bd238b20772211427b8134b6db35f5af'
THEORY = 'b6aa25f02413d02892cbbabd33c993093bc18565'
LATEST = '39a191604b841be257d3bc75d3ea28e088ce33ba'
PAIR = 'e6ae3699870c78b11c8c47b0fa9001249a428e1c'
DDR = '70f2e8bd8e850f1d49c924a86b654b29c24e087f'
PAPER = '615b1a5f7913a97fff8924cfec9936d3d303c6fc'
CONFIG_SHA = 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-directory', required=True, type=Path)
    args = ap.parse_args()
    out = args.output_directory.resolve()
    out.mkdir(parents=True, exist_ok=False)
    files = {}
    entries = []

    def add(commit, source, dest=None):
        dest = dest or source
        assert dest not in files
        raw = subprocess.check_output(['git', 'show', f'{commit}:{source}'], cwd=ROOT)
        files[dest] = raw
        entries.append({'path': dest, 'source_commit': commit, 'source_path': source,
                        'bytes': len(raw), 'sha256': sha(raw),
                        'url': f'https://github.com/huaweibei123/huaweicup2026/blob/{commit}/{source}'})
        return raw

    bounds_raw = add(SOLVER, 'results/a/q2-nikolastarx/goal-20260924/global-bounds.json')
    report = json.loads(add(AUDIT, 'results/a/q2-nikolastarx/hypergap-full500-audit-20260925/report.json'))
    summary_raw = add(AUDIT, 'results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json')
    assert sha(bounds_raw) == report['bounds_certificate_sha256']
    assert sha(summary_raw) == report['summary_sha256']
    bounds = json.loads(bounds_raw)
    summary = json.loads(summary_raw)
    assert summary['status'] == 'completed' and summary['accepted_cells'] == 500
    assert summary['solver_commit'] == SOLVER and not summary['in_flight']
    baseline_raw = add(MEMBER, 'results/a/q2-yuanzhifang/feedback-20260924/full-coverage/all500/per-cell.csv')
    baseline_rows = list(csv.DictReader(io.StringIO(baseline_raw.decode('utf-8-sig'))))
    denominator = {}
    for row in baseline_rows:
        case, base = row['case_id'], int(row['baseline_cycles'])
        assert base > 0 and denominator.get(case, base) == base
        denominator[case] = base
    bound_map = {}
    for record in bounds['records']:
        case = record['graph_file'].removeprefix('case_').removesuffix('.json')
        assert record['supported'] and record['precedence_supported']
        for item in record['by_core_count']:
            bound_map[case, item['cores']] = (item['makespan_lower_bound_cycles'], record['graph_sha256'])
    current = {(r['case'], r['cores']): r for r in summary['rows']}
    grid = {(f'{i:03}', k) for i in range(1, 101) for k in range(1, 6)}
    assert set(current) == set(bound_map) == grid and len(summary['rows']) == 500
    cells = []
    for case, k in sorted(grid):
        r = current[case, k]
        lower, graph_sha = bound_map[case, k]
        assert r['graph_sha256'] == graph_sha and r['config_sha256'] == CONFIG_SHA
        assert r['status'] == 'accepted' and not r['request_in_flight']
        makespan, base = r['official']['makespan'], denominator[case]
        assert type(makespan) is int and type(lower) is int and 0 < lower <= makespan
        cells.append({'case': case, 'cores': k, 'baseline_cycles': base,
                      'lower_bound_cycles': lower, 'makespan_cycles': makespan,
                      'speedup': base/makespan, 'speedup_ceiling': base/lower,
                      'possible_speedup_gain': base/lower-base/makespan,
                      'possible_mean_gain_contribution': (base/lower-base/makespan)/100,
                      'possible_relative_makespan_reduction_pct': 100*(1-lower/makespan),
                      'relative_suboptimality_upper_bound_pct': 100*(makespan/lower-1),
                      'certified_within_5pct': Fraction(makespan, lower) <= Fraction(105,100),
                      'graph_sha256': graph_sha})
    by_core = []
    for k in range(1, 6):
        rows = [r for r in cells if r['cores'] == k]
        score = statistics.fmean(r['speedup'] for r in rows)
        ceiling = statistics.fmean(r['speedup_ceiling'] for r in rows)
        expected = report['core_comparison'][str(k)]
        assert abs(score-expected['new_mean_B_over_M']) < 1e-12
        assert abs(ceiling-expected['relaxation_ceiling_mean_B_over_LB']) < 1e-12
        close = sum(r['certified_within_5pct'] for r in rows)
        assert close == expected['certified_within_5pct_of_optimum_count']
        remaining = [r['possible_relative_makespan_reduction_pct'] for r in rows]
        top = sorted(rows, key=lambda r: (-r['possible_mean_gain_contribution'],r['case']))[:10]
        by_core.append({'cores':k, 'n':100, 'observed_mean_speedup':score,
                        'mean_speedup_ceiling':ceiling, 'maximum_mean_speedup_gain':ceiling-score,
                        'maximum_relative_mean_speedup_gain_pct':100*(ceiling/score-1),
                        'mean_of_per_case_makespan_reduction_caps_pct':statistics.fmean(remaining),
                        'median_of_per_case_makespan_reduction_caps_pct':statistics.median(remaining),
                        'certified_within_5pct_count':close,
                        'top10_gap_contributors':top})
    derived = {'scope':'Saved-data arithmetic only; bounds remain subject to their documented proof/domain.',
               'current_solver':SOLVER, 'result_commit':AUDIT, 'bounds_commit':SOLVER,
               'config_sha256':CONFIG_SHA, 'by_core':by_core,
               'claims':{'attainability_proved':False, 'global_optimality_proved':False,
                         'current_DDR_bound_used_as_time_bound':False,
                         'new_constructor_solver_prepare_E0_E1_E2_calls':0},
               'interpretation':'For every cell L <= OPT <= M, so S <= S_opt <= A/L; all score means are means of ratios. Gap is an upper cap, not a promised gain. Mean score gain percentage is not mean Makespan reduction.'}
    audit_bytes = (json.dumps(derived, ensure_ascii=False, indent=2)+'\n').encode()
    (Path(__file__).with_name('gap-audit.json')).write_bytes(audit_bytes)
    files['DERIVED/gap-audit.json'] = audit_bytes
    csv_stream = io.StringIO(newline='')
    writer = csv.DictWriter(csv_stream, fieldnames=list(cells[0]), lineterminator='\n')
    writer.writeheader(); writer.writerows(cells)
    csv_bytes = csv_stream.getvalue().encode()
    Path(__file__).with_name('gap-cells.csv').write_bytes(csv_bytes)
    files['DERIVED/gap-cells.csv'] = csv_bytes
    for name in ('OPTIMALITY_BOUNDS.md','FIFO_BOUND.md','ADAPTIVE_SEMANTIC.md','ACTIVE_CORE_WAVE.md'):
        add(SOLVER, 'docs/a/q2-nikolastarx/'+name)
    for name in ('global_bounds.py','fifo_bound.py','hypergraph_cost.py','binary_hypercut.py',
                 'adaptive_hypergap_guarded.py','gap_candidate.py','gap_hyperrefine.py','gap_retime.py','active_core_wave.py'):
        add(SOLVER, 'src/q2_nikolastarx/'+name)
    for name in ('contest_io.py','evaluation_validation.py','multicore_cut_evaluate_problem_1.py',
                 'multicore_cut_evaluate_problem_2.py','schedule_step1.py','schedule_step2.py','schedule_step3.py',
                 'singlecore_evaluate.py','stub_multicore_cut_and_schedule.py'):
        raw = add(SOLVER, 'data/raw/a/official/code/'+name)
        if name in bounds['official_source_sha256']:
            assert sha(raw) == bounds['official_source_sha256'][name]
    config = add(SOLVER, 'data/raw/a/official/data/config.txt')
    assert sha(config) == CONFIG_SHA
    assert sha(files['src/q2_nikolastarx/global_bounds.py']) == bounds['certificate_source_sha256']
    add(AUDIT, 'results/a/q2-nikolastarx/hypergap-full500-audit-20260925/RESULTS.md')
    for name in ('PRO_C01_REVIEW.md','PRO_R07_REVIEW.md'):
        add(THEORY, 'docs/a/q2-nikolastarx/'+name)
    add(LATEST, 'results/a/q2-nikolastarx/receiver-closure-069-static-20260925/README.md')
    add(PAIR, 'results/a/q2-nikolastarx/pro-r05-official-pair-20260925/README.md')
    add(PAIR, 'results/a/q2-nikolastarx/pro-r05-official-pair-20260925/verification.json')
    add(DDR, 'results/a/q2-nikolastarx/secondary-ddr-full500-20260925/README.md')
    add(DDR, 'results/a/q2-nikolastarx/secondary-ddr-full500-20260925/report.json')
    add(PAPER, 'paper/sections/a-q2.md')
    add(PAPER, 'paper/sections/a-q2-evidence.md')
    request = (ROOT/'docs/a/q2/feedback/PRO_UPPER_BOUND_REQUEST_20260925.md').read_bytes()
    files['P2-R4-REQUEST.md'] = request
    for path in ('P2-R4-REQUEST.md','DERIVED/gap-audit.json','DERIVED/gap-cells.csv'):
        entries.append({'path':path, 'source':'this preparation; frozen inputs in this manifest',
                        'bytes':len(files[path]), 'sha256':sha(files[path])})
    manifest = {'created_at':datetime.now(timezone.utc).isoformat(), 'owner_session':'yuanzhifang30-sudo/s-eb28fa11a5664fdfbdd29b3d6e38ca24',
                'purpose':'P2 round 4: proof of speedup ceiling, quantifiable gap and iteration guarantees',
                'entries':entries, 'not_included':'All 100 original graphs and all raw E0 results are not duplicated here. Fixed source indices/500 summary and bound certificates are supplied. Original two graphs from the earlier upload may still be available.',
                'new_evaluator_calls':0}
    manifest_bytes=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    files['MANIFEST.json']=manifest_bytes
    Path(__file__).with_name('input-manifest.json').write_bytes(manifest_bytes)
    bundle=out/'P2-R4-upper-bound-evidence.zip'
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for path,raw in files.items():
            z.writestr(path,raw)
    with zipfile.ZipFile(bundle) as z:
        assert z.testzip() is None and len(z.infolist()) == len(files)
        for path,raw in files.items(): assert z.read(path)==raw
    receipt={'bundle':bundle.name,'bytes':bundle.stat().st_size,'sha256':sha(bundle.read_bytes()),
             'members':len(files),'input_manifest_sha256':sha(manifest_bytes),
             'gap_audit_sha256':sha(audit_bytes),'gap_cells_sha256':sha(csv_bytes),
             'created_at':manifest['created_at'],'input_source_entries':len(entries),
             'scope':derived['scope'],'not_included':manifest['not_included']}
    Path(__file__).with_name('bundle-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'bundle_path':str(bundle),'receipt':receipt,
                     'summary':[{key:r[key] for key in ('cores','observed_mean_speedup','mean_speedup_ceiling','maximum_mean_speedup_gain','maximum_relative_mean_speedup_gain_pct','certified_within_5pct_count')} for r in by_core]}))

if __name__ == '__main__':
    main()
