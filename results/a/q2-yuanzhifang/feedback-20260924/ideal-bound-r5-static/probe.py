"""Saved K5 tensor/F1 pair diagnostics; no construction or evaluator calls."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from src.q2.feedback.construct import UnsupportedStructure
from src.q2.feedback.ideal_bounds import candidate_lower_bound
from src.q2.feedback.physical_frontier import certificate
from src.q2.feedback.tensor_packet import TensorIndex

BASE = ROOT / 'results/a/q2-yuanzhifang/feedback-20260924'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def checked_candidate(row, case, graph_sha, config_sha):
    path = ROOT / row['run_path']
    run = load(path)
    assert run['status'] == 'ok' and run['cores'] == 5
    assert run['identity']['graph_sha256'] == graph_sha
    assert run['identity']['config_sha256'] == config_sha
    plan_path = path.parent / f'case_{case}_multicore_res.json'
    assert sha(plan_path) == run['identity']['plan_sha256']
    result_path = ROOT / run['artifacts']['result']['path']
    assert sha(result_path) == run['artifacts']['result']['sha256'] == row['result_sha256']
    result = load(result_path)
    assert result['makespan'] == row['makespan_cycles']
    return load(plan_path), result, {
        'run_path': path.relative_to(ROOT).as_posix(), 'run_sha256': sha(path),
        'plan_sha256': sha(plan_path), 'result_sha256': sha(result_path),
        'saved_makespan_cycles': row['makespan_cycles'],
    }


def compact(bound):
    result = {k: v for k, v in bound.items() if k not in ('critical_path_ops', 'critical_path_edges')}
    witness = {'ops': bound['critical_path_ops'], 'edges': bound['critical_path_edges']}
    result['critical_path_summary'] = {
        'op_count': len(witness['ops']),
        'arc_kinds': dict(Counter(e['kind'] for e in witness['edges'])),
        'witness_sha256': hashlib.sha256(json.dumps(witness, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', nargs='+', help='Default: all 100 saved K5 pairs')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    started = time.perf_counter()
    source_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    coverage_paths = [BASE / 'full-coverage' / name / 'coverage.json'
                      for name in ('all500', 'frontier-k5-100')]
    coverages = [{r['case_id']: r for r in load(p)['rows'] if r['cores'] == 5}
                 for p in coverage_paths]
    assert len(coverages[0]) == len(coverages[1]) == 100
    assert coverages[0].keys() == coverages[1].keys()
    cases = sorted(args.cases or coverages[0])
    assert len(set(cases)) == len(cases) and set(cases) <= coverages[0].keys()
    config_path = ROOT / 'data/raw/a/official/data/config.txt'
    config_sha = sha(config_path)
    prior_path = BASE / 'component-ddr-static/static.json'
    cfg = {**load(prior_path)['config'], 'delay': 500}
    assert cfg['config_sha256'] == config_sha
    assert cfg['bandwidth'] == 60 and cfg['delay'] == 500
    rows = []
    for case in cases:
        graph_path = ROOT / f'data/raw/a/official/data/case_{case}.json'
        graph_sha = sha(graph_path)
        index = TensorIndex(load(graph_path))
        row = {'case': case, 'cores': 5, 'graph_sha256': graph_sha, 'config_sha256': config_sha}
        plans = {}
        for name, coverage in zip(('A_tensor', 'B_F1'), coverages):
            plan, saved, identity = checked_candidate(coverage[case], case, graph_sha, config_sha)
            plans[name] = plan
            try:
                bound = candidate_lower_bound(index, plan, cfg['bandwidth'], cfg['delay'])
                movement = saved['data_movement_bytes']
                assert bound['base_copy_bytes'] == movement['scheduled_copy_bytes'] - movement['spill_added_copy_bytes']
                row[name] = {**identity, 'status': 'computed', 'bound': compact(bound),
                             'ideal_bound_above_saved_E0': bound['ideal_lower_bound_cycles'] > saved['makespan']}
            except UnsupportedStructure as error:
                row[name] = {**identity, 'status': 'unsupported', 'reason': str(error)}
        if all(row[name]['status'] == 'computed' for name in plans):
            a = row['A_tensor']['bound']
            b = row['B_F1']['bound']
            upper = a['max_core_compute_work_cycles'] + a['ddr_service_cycles']
            structural = a['whole_components'] and not a['cross_core_links']
            r4_inequality = upper < b['ddr_service_cycles']
            r5_inequality = upper < b['ideal_lower_bound_cycles']
            capacity_checked = structural and r5_inequality
            certified = False
            if capacity_checked:
                cert = certificate(index, plans['A_tensor'], cfg['capacity'])
                assert cert['base_copy_bytes'] == a['base_copy_bytes']
                assert cert['base_copy_count'] == a['base_copy_count']
                certified = cert['certified']
            row['saved_pair_gate'] = {
                'ideal_U_A': upper, 'A_structural_domain': structural,
                'capacity_checked': capacity_checked, 'capacity_certified': certified,
                'R4_choose_A': structural and certified and r4_inequality,
                'R5_choose_A': structural and certified and r5_inequality,
                'extra_R5_trigger': structural and certified and r5_inequality and not r4_inequality,
                'saved_A_minus_B_cycles': row['A_tensor']['saved_makespan_cycles'] - row['B_F1']['saved_makespan_cycles'],
                'certified_A_above_ideal_upper': certified and row['A_tensor']['saved_makespan_cycles'] > upper,
            }
        rows.append(row)
        print(json.dumps({'case': case, 'completed': len(rows), 'total': len(cases),
                          'status': {name: row[name]['status'] for name in plans},
                          'extra_R5_trigger': row.get('saved_pair_gate', {}).get('extra_R5_trigger')}), flush=True)
        del index, plans
    sources = sorted((ROOT / 'src/q2/feedback').glob('*.py'))
    official = [ROOT / 'data/raw/a/official/code' / name for name in (
        'multicore_cut_evaluate_problem_2.py', 'schedule_step2.py', 'schedule_step3.py',
        'stub_multicore_cut_and_schedule.py', 'evaluation_validation.py')]
    summary = {
        'pairs': len(rows),
        'computed_bounds': sum(row[name]['status'] == 'computed' for row in rows for name in ('A_tensor', 'B_F1')),
        'ideal_bound_above_saved_E0': [[row['case'], name] for row in rows for name in ('A_tensor', 'B_F1')
                                     if row[name].get('ideal_bound_above_saved_E0')],
        'R4_trigger_cases': [r['case'] for r in rows if r.get('saved_pair_gate', {}).get('R4_choose_A')],
        'R5_trigger_cases': [r['case'] for r in rows if r.get('saved_pair_gate', {}).get('R5_choose_A')],
        'extra_R5_trigger_cases': [r['case'] for r in rows if r.get('saved_pair_gate', {}).get('extra_R5_trigger')],
        'triggered_saved_pair_regressions': [r['case'] for r in rows if r.get('saved_pair_gate', {}).get('R5_choose_A')
                                           and r['saved_pair_gate']['saved_A_minus_B_cycles'] > 0],
        'certified_A_above_ideal_upper': [r['case'] for r in rows if r.get('saved_pair_gate', {}).get('certified_A_above_ideal_upper')],
    }
    result = {
        'created_at': datetime.now(timezone.utc).isoformat(), 'source_head': source_head,
        'scope': 'Post-hoc static diagnosis of saved candidate pairs. No new algorithm execution, official score, global optimality bound, or floating-point theorem.',
        'new_solver_calls': 0, 'Step2_calls': 0, 'Step3_calls': 0, 'E0_calls': 0,
        'source_hashes': {p.relative_to(ROOT).as_posix(): sha(p) for p in sources + official},
        'input_hashes': {p.relative_to(ROOT).as_posix(): sha(p) for p in coverage_paths + [prior_path, config_path]},
        'probe_sha256': sha(Path(__file__)), 'config': cfg, 'summary': summary, 'rows': rows,
        'script_wall_seconds': time.perf_counter() - started,
    }
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
