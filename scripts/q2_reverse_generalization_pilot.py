"""One frozen five-cell reverse-gap mechanism probe, never a full benchmark."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.evaluate_feedback import monitored, dump, utc

CASES = ('010', '064', '086', '068', '088')
ARCHIVE = ROOT/'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee'
CONFIG = ROOT/'data/raw/a/official/data/config.txt'
E0 = ROOT/'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(raw_root, output):
    if output.exists():
        raise ValueError('fresh freeze path required')
    subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', 'src/q2_nikolastarx',
                    'scripts/q2_reverse_generalization_pilot.py', 'data/raw/a/official/code'],
                   cwd=ROOT, check=True)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    names = subprocess.check_output(['git', 'ls-files', 'src/q2_nikolastarx',
        'scripts/q2_reverse_generalization_pilot.py', 'data/raw/a/official/code'], cwd=ROOT, text=True).splitlines()
    hashes = {n: sha(ROOT/n) for n in names}
    assert 'src/q2_nikolastarx/reverse_gap_candidate.py' in hashes
    cells = []
    for case in CASES:
        graph = raw_root/f'case_{case}.json'
        old = next(ARCHIVE.glob(f'cases-*/{case}-k5'))
        cell = json.loads((old/'cell.json').read_text())
        result_raw = gzip.decompress((old/'result.json.gz').read_bytes())
        plan_raw = gzip.decompress((old/'plan.json.gz').read_bytes())
        assert sha(graph) == cell['graph_sha256']
        assert sha(CONFIG) == cell['config_sha256']
        assert hashlib.sha256(result_raw).hexdigest() == cell['official']['result_sha256']
        assert hashlib.sha256(plan_raw).hexdigest() == cell['plan_sha256']
        cells.append({'case': case, 'cores': 5, 'graph_sha256': sha(graph),
                      'baseline_archive': str(old.relative_to(ROOT)),
                      'baseline_plan_sha256': cell['plan_sha256'],
                      'baseline_result_sha256': cell['official']['result_sha256'],
                      'baseline_M': cell['official']['makespan'],
                      'baseline_added_DDR': cell['official']['movement']['added_copy_bytes']})
    dump(output, {'schema': 'p2-reverse-gap-generalization-five-v1', 'created_at': utc(),
                  'source_commit': source, 'source_hashes': hashes,
                  'config_sha256': sha(CONFIG), 'cells': cells,
                  'limits': {'constructor': 5, 'E0': 5, 'E1': 0, 'E2': 0, 'retry': 0,
                             'workers': 1, 'solver_seconds': 30, 'E0_seconds': 30,
                             'batch_seconds': 180, 'rss_bytes': 536870912},
                  'scope': 'raw-input one candidate vs frozen c665 seed; no online selection/full500 claim'})


def run(frozen, raw_root, output, python):
    m = json.loads(frozen.read_text())
    assert m['schema'] == 'p2-reverse-gap-generalization-five-v1'
    assert [r['case'] for r in m['cells']] == list(CASES)
    assert m['limits'] == {'constructor': 5, 'E0': 5, 'E1': 0, 'E2': 0, 'retry': 0,
                          'workers': 1, 'solver_seconds': 30, 'E0_seconds': 30,
                          'batch_seconds': 180, 'rss_bytes': 536870912}
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'],cwd=ROOT,text=True).strip() == m['source_commit']
    assert all(sha(ROOT/n) == digest for n,digest in m['source_hashes'].items())
    assert sha(CONFIG) == m['config_sha256']
    assert all(sha(raw_root/f"case_{r['case']}.json") == r['graph_sha256'] for r in m['cells'])
    output.mkdir(parents=True, exist_ok=False)
    deadline = time.perf_counter() + 180
    ledger = {'source_commit': m['source_commit'], 'freeze_sha256': sha(frozen),
              'started_at': utc(), 'status': 'running', 'in_flight': None,
              'calls': {'constructor': 0, 'E0': 0, 'E1': 0, 'E2': 0, 'retry': 0}, 'rows': []}
    dump(output/'freeze.json', m)
    try:
        for cell in m['cells']:
            if time.perf_counter() >= deadline:
                raise TimeoutError('batch deadline')
            case = cell['case']; graph = raw_root/f'case_{case}.json'
            folder = output/case; folder.mkdir()
            row = {**cell, 'status': 'constructing'}; ledger['rows'].append(row)
            plan = folder/'plan.json'
            args = [python, '-B', '-m', 'src.q2_nikolastarx.reverse_gap_candidate',
                    str(graph), '--config', str(CONFIG), '--cores', '5',
                    '--output', str(plan), '--evidence', str(folder/'constructor'), '--wall', '30']
            ledger['calls']['constructor'] += 1; ledger['in_flight'] = [case,'constructor']
            dump(output/'ledger.json', ledger)
            row['constructor_process'] = monitored(args,folder/'constructor-process',
                    min(deadline,time.perf_counter()+30),536870912)
            ledger['in_flight'] = None
            if row['constructor_process']['status'] != 'ok':
                raise RuntimeError('constructor failed: stop, no retry or extra scoring')
            row['plan_sha256'] = sha(plan)
            solver = json.loads((folder/'constructor/solver.json').read_text())
            assert solver['status'] == 'ok' and solver['plan_sha256'] == row['plan_sha256']
            assert solver['calls'] == {'E0':0,'E1':0,'E2':0}
            ledger['calls']['E0'] += 1; ledger['in_flight'] = [case,'E0']
            dump(output/'ledger.json',ledger)
            args = [python,'-B',str(E0),str(graph),str(plan),'--config',str(CONFIG),
                    '--output',str(folder/'result.json'),'--trace-output',str(folder/'trace.json'),
                    '--log-output',str(folder/'official.log')]
            row['E0_process'] = monitored(args,folder/'E0-process',
                    min(deadline,time.perf_counter()+30),536870912)
            ledger['in_flight'] = None
            if row['E0_process']['status'] != 'ok':
                raise RuntimeError('E0 failed: preserve unknown, no retry')
            assert sha(plan) == row['plan_sha256']
            result = json.loads((folder/'result.json').read_text())
            assert result['num_cores'] == 5 and type(result['makespan']) is int and result['makespan'] > 0
            row.update(status='evaluated', makespan=result['makespan'],
                       movement=result['data_movement_bytes'], result_sha256=sha(folder/'result.json'),
                       M_change=result['makespan']-cell['baseline_M'])
            dump(output/'ledger.json',ledger)
        ledger['status'] = 'completed'
    except BaseException as e:
        ledger.update(status='stopped',error=repr(e))
        raise
    finally:
        ledger['finished_at'] = utc()
        dump(output/'ledger.json',ledger)


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode',choices=('freeze','run'))
    ap.add_argument('--raw-root',required=True,type=Path)
    ap.add_argument('--freeze',required=True,type=Path)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--python',default=sys.executable)
    a=ap.parse_args()
    if a.mode=='freeze': freeze(a.raw_root.resolve(),a.freeze.resolve())
    else:
        if not a.output: ap.error('--output is required for run')
        run(a.freeze.resolve(),a.raw_root.resolve(),a.output.resolve(),a.python)
