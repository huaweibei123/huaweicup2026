"""Freeze/run one 069/K5 prepared-contract and RCX probe; no final evaluator.

The builder performs official local Step1/2/3 preparation once. That work is
explicitly counted; the saved full500 E0 trace is read, never recomputed here.
Run mode requires a separately admitted resource window, not just a manifest.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import pickle
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import q2_selected_plan_static_probe as base

CELL = ROOT / 'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee/cases-061-070/069-k5'
LIMITS = {'workers': 1, 'wall_seconds': 30, 'rss_bytes': 512 << 20,
          'scene_b_prepare': 1, 'constructor': 1, 'E0': 0, 'E1': 0,
          'E2': 0, 'retries': 0}


def sources():
    names = [Path(__file__), ROOT / 'scripts/q2_selected_plan_static_probe.py',
             *(ROOT / 'src/q2_nikolastarx').glob('*.py'),
             *(ROOT / 'data/raw/a/official/code').glob('*.py')]
    return {p.relative_to(ROOT).as_posix(): base.sha(p.read_bytes())
            for p in sorted(names) if not p.name.startswith('._')}


def payload(path):
    raw = path.read_bytes()
    return gzip.decompress(raw) if path.suffix == '.gz' else raw


def verify(m):
    if (m['schema'] != 'q2-rcx-069-k5-v1' or m['limits'] != LIMITS
            or m['source_commit'] != base.git_head()
            or m['source_sha256'] != sources()):
        raise ValueError('Frozen source/limits changed')
    row = json.loads((CELL / 'run.json').read_bytes())['accepted_row']
    for kind, digest in [('graph', row['graph_sha256']),
                         ('config', row['config_sha256']),
                         ('plan', row['plan_sha256']),
                         ('result', row['official']['result_sha256'])]:
        raw = payload(Path(m['inputs'][kind]['path']))
        if base.sha(raw) != digest or digest != m['inputs'][kind]['sha256']:
            raise ValueError('Saved input identity mismatch: ' + kind)
    return row


def write_gzip(path, value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     allow_nan=False).encode()
    path.write_bytes(gzip.compress(raw, mtime=0))


def child(path):
    sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import (
        read_scene_b_config, _build_scene_b_tasks)
    from src.q2_nikolastarx.prepared_trace_contract import capture, audit
    from src.q2_nikolastarx.receiver_closure_exchange import construct
    m = json.loads(path.read_bytes())
    row = verify(m)
    out = path.parent
    graph = json.loads(payload(Path(m['inputs']['graph']['path'])))
    plan = json.loads(payload(Path(m['inputs']['plan']['path'])))
    result = json.loads(payload(Path(m['inputs']['result']['path'])))
    config_path = Path(m['inputs']['config']['path'])
    config = {**read_evaluation_config(config_path), **read_scene_b_config(config_path)}
    with (out / 'prepare-start.json').open('x') as stream:
        json.dump({'scene_b_prepare_started': 1}, stream)
    start = time.perf_counter()
    prepared = _build_scene_b_tasks(graph, plan, config['bandwidth'], config['capacity'])
    tasks, links, cross, traffic, _ = prepared
    prepare_seconds = time.perf_counter() - start
    if traffic != row['official']['movement'] or cross != row['official']['cross_task_traffic']:
        raise ValueError('Fresh preparation differs from saved E0 traffic')
    # Only our freshly built objects are serialized. Never unpickle a remote
    # attachment or arbitrary file to execute this probe.
    (out / 'prepared.pickle').write_bytes(pickle.dumps(prepared, protocol=5))
    contract = capture(tasks, links)
    write_gzip(out / 'contract.json.gz', contract)
    checked = audit(contract, result)
    base.save(out / 'trace-contract-audit.json', checked)
    if not checked['consistent']:
        raise ValueError('Prepared/trace contract mismatch; no construction')
    with (out / 'constructor-start.json').open('x') as stream:
        json.dump({'constructor_started': 1}, stream)
    start = time.perf_counter()
    candidate, meta = construct(graph, plan, config, checked['critical_cross_links'])
    constructor_seconds = time.perf_counter() - start
    base.save(out / 'candidate-meta.json', meta)
    if candidate is not None:
        base.save(out / 'candidate-plan.json', candidate)
    base.save(out / 'probe-result.json', {
        'status': 'candidate_unscored' if candidate is not None else 'no_candidate',
        'prepare_seconds': prepare_seconds, 'constructor_seconds': constructor_seconds,
        'seed_makespan': result['makespan'], 'candidate_makespan': None,
        'calls': {'scene_b_prepare': 1, 'constructor': 1, 'E0': 0, 'E1': 0, 'E2': 0},
        'local_step1_step2_step3_are_included_in_prepare': True,
        'prepared_pickle_sha256': base.sha((out / 'prepared.pickle').read_bytes()),
        'no_official_improvement_claim': True})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('freeze', 'run', 'child'))
    p.add_argument('--graph', type=Path)
    p.add_argument('--config', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--manifest', type=Path)
    a = p.parse_args()
    if a.mode == 'freeze':
        if not all((a.graph, a.config, a.output)):
            p.error('freeze needs graph/config/output')
        out = a.output.resolve()
        if not out.is_relative_to((ROOT / 'output').resolve()):
            raise ValueError('Host-specific manifest must stay under output/')
        paths = {'graph': a.graph.resolve(strict=True),
                 'config': a.config.resolve(strict=True),
                 'plan': CELL / 'plan.json.gz', 'result': CELL / 'result.json.gz'}
        m = {'schema': 'q2-rcx-069-k5-v1', 'limits': LIMITS,
             'source_commit': base.git_head(), 'source_sha256': sources(),
             'inputs': {k: {'path': str(v), 'sha256': base.sha(payload(v))}
                        for k, v in paths.items()}}
        verify(m)
        out.mkdir(parents=True, exist_ok=False)
        base.save(out / 'manifest.json', m)
        print(out / 'manifest.json')
        return
    if a.manifest is None:
        p.error('run/child needs manifest')
    path = a.manifest.resolve(strict=True)
    if a.mode == 'child':
        child(path)
        return
    start = time.perf_counter()
    out = path.parent
    base.reserve_attempt(out, path, start)
    receipt = {'status': 'attempt_reserved', 'manifest_sha256': base.sha(path.read_bytes()),
               'counts_are_from_child_markers_not_dispatch': True}
    try:
        base.save(out / 'receipt.json', receipt)
        verify(json.loads(path.read_bytes()))
        from src.q2_nikolastarx.evaluate_feedback import monitored
        if time.perf_counter() >= start + LIMITS['wall_seconds']:
            raise TimeoutError('Probe deadline reached before child dispatch')
        process = monitored([sys.executable, '-B', str(Path(__file__).resolve()),
                             'child', '--manifest', str(path)],
                            out / 'process', start + LIMITS['wall_seconds'], LIMITS['rss_bytes'])
        receipt['process'] = process
        if process['status'] != 'ok' or process.get('surviving_pids'):
            raise RuntimeError('Probe failed or process status unknown')
        receipt['status'] = 'completed_unscored'
    except BaseException as error:
        receipt.update(status='stopped', error=repr(error))
        raise
    finally:
        receipt.update(wall_seconds=time.perf_counter() - start,
                       prepare_started=int((out / 'prepare-start.json').exists()),
                       constructor_started=int((out / 'constructor-start.json').exists()),
                       E0=0, E1=0, E2=0)
        base.save(out / 'receipt.json', receipt)


if __name__ == '__main__':
    main()
