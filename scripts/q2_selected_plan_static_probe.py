"""Freeze or run one bounded c665 003/K2 selected-plan static probe; no evaluator."""
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
PLAN = ROOT / 'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee/cases-001-010/003-k2/plan.json.gz'
PLAN_SHA = '6a8fc98c824dca6a21946a55b5875eae6658edd1b5b1f01ba4b6db363783d6a2'
GRAPH_SHA = '2c80acfd37edcf811ce76b7e7b1f7194c706bd4d4aa6449e6a19e9eac1028ced'
CONFIG_SHA = 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def sources():
    names = [Path(__file__), *(ROOT / 'src/q2_nikolastarx').glob('*.py'),
             ROOT / 'data/raw/a/official/code/evaluation_validation.py',
             ROOT / 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py']
    return {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sorted(names)}


def git_head():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def reserve_attempt(output, manifest_path, started):
    if (output / 'receipt.json').exists() or (output / 'attempt.json').exists():
        raise FileExistsError('Prior attempt/receipt exists; retry forbidden')
    marker = {'status': 'reserved', 'manifest_sha256': sha(manifest_path.read_bytes()),
              'started_monotonic': started}
    with (output / 'attempt.json').open('x') as stream:
        json.dump(marker, stream)
        stream.write('\n')
    return marker


def verify(manifest):
    if (manifest['schema'] != 'q2-selected-static-003-k2-v1'
            or manifest['plan_json_sha256'] != PLAN_SHA
            or manifest['graph_sha256'] != GRAPH_SHA
            or manifest['config_sha256'] != CONFIG_SHA
            or manifest.get('source_commit') != git_head()
            or manifest['limits'] != {'workers': 1, 'wall_seconds': 30,
                                      'rss_bytes': 512 << 20, 'E0': 0, 'E1': 0,
                                      'E2': 0, 'retries': 0}):
        raise ValueError('Frozen probe identity/limits differ')
    if sources() != manifest['source_sha256']:
        raise ValueError('Source file set or bytes changed')
    compressed = PLAN.read_bytes()
    if sha(compressed) != manifest['plan_gzip_sha256']:
        raise ValueError('Archived compressed plan changed')
    plan = gzip.decompress(compressed)
    if sha(plan) != PLAN_SHA:
        raise ValueError('Archived selected plan changed')
    for field in ('graph', 'config'):
        path = Path(manifest[field])
        if sha(path.read_bytes()) != manifest[field + '_sha256']:
            raise ValueError('Frozen ' + field + ' changed')
    return plan


def child(manifest_path):
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    from src.q2_nikolastarx.ready_exchange_candidate import build_from_plan
    from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
    from src.q2_nikolastarx.fifo_bound import fixed_fifo_lower_bound
    manifest = json.loads(manifest_path.read_bytes())
    raw = verify(manifest)
    output = manifest_path.parent
    graph = json.loads(Path(manifest['graph']).read_bytes())
    config_path = Path(manifest['config'])
    config = {**read_evaluation_config(config_path), **read_scene_b_config(config_path)}
    seed = json.loads(raw)
    plan, meta = build_from_plan(graph, seed, 2, config, final_proxy_guard=False)
    if meta.get('calls', {'E0': 0, 'E1': 0, 'E2': 0}) != {'E0': 0, 'E1': 0, 'E2': 0}:
        raise ValueError('Unexpected scoring declaration')
    mandatory = {'seed': mandatory_copy_work(graph, seed, config['bandwidth']),
                 'selected': mandatory_copy_work(graph, plan, config['bandwidth'])}
    fifo = fixed_fifo_lower_bound(graph, plan)
    save(output / 'plan.json', plan)
    save(output / 'meta.json', meta)
    save(output / 'mandatory.json', mandatory)
    save(output / 'fifo-bound.json', fifo)
    save(output / 'static-result.json', {'status': 'static_only',
        'plan_sha256': sha((output / 'plan.json').read_bytes()),
        'mandatory_transfer_bytes': {k: v['transfer_bytes'] for k, v in mandatory.items()},
        'fifo_supported': fifo['supported'],
        'fifo_lower_bound_cycles': fifo.get('makespan_lower_bound_cycles'),
        'calls': {'E0': 0, 'E1': 0, 'E2': 0}})


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
            p.error('freeze needs --graph --config --output')
        graph, config = a.graph.resolve(strict=True), a.config.resolve(strict=True)
        if sha(graph.read_bytes()) != GRAPH_SHA or sha(config.read_bytes()) != CONFIG_SHA:
            raise ValueError('Official graph/config bytes differ')
        if sha(gzip.decompress(PLAN.read_bytes())) != PLAN_SHA:
            raise ValueError('Archived plan differs')
        out = a.output.resolve()
        if not out.is_relative_to((ROOT / 'output').resolve()):
            raise ValueError('Raw manifest with host paths must remain under output/')
        out.mkdir(parents=True, exist_ok=False)
        save(out / 'manifest.json', {'schema': 'q2-selected-static-003-k2-v1',
            'graph': str(graph), 'config': str(config),
            'graph_sha256': GRAPH_SHA, 'config_sha256': CONFIG_SHA,
            'plan_gzip_sha256': sha(PLAN.read_bytes()), 'plan_json_sha256': PLAN_SHA,
            'source_sha256': sources(),
            'source_commit': git_head(),
            'command': [sys.executable, '-B', str(Path(__file__).resolve()), 'run',
                        '--manifest', str(out / 'manifest.json')],
            'limits': {'workers': 1, 'wall_seconds': 30, 'rss_bytes': 512 << 20,
                       'E0': 0, 'E1': 0, 'E2': 0, 'retries': 0}})
        print(out / 'manifest.json')
    else:
        if a.manifest is None:
            p.error('run/child need --manifest')
        manifest_path = a.manifest.resolve(strict=True)
        if a.mode == 'child':
            child(manifest_path)
            return
        start = time.perf_counter()
        deadline = start + 30
        output = manifest_path.parent
        reserve_attempt(output, manifest_path, start)
        receipt = {'status': 'attempt_reserved', 'calls': {'constructor': 1,
                   'E0': 0, 'E1': 0, 'E2': 0}, 'manifest_sha256': sha(manifest_path.read_bytes())}
        try:
            save(output / 'receipt.json', receipt)
            manifest = json.loads(manifest_path.read_bytes())
            verify(manifest)
            sys.path.insert(0, str(ROOT))
            from src.q2_nikolastarx.evaluate_feedback import monitored
            if time.perf_counter() >= deadline:
                raise TimeoutError('30-second total budget exhausted before child dispatch')
            process = monitored([sys.executable, '-B', str(Path(__file__).resolve()), 'child',
                                 '--manifest', str(manifest_path)], output / 'process',
                                deadline, 512 << 20)
            receipt['process'] = process
            if process['status'] != 'ok' or process.get('surviving_pids'):
                raise RuntimeError('Static child failed or outcome unknown')
            receipt['status'] = 'completed_static_only'
        except BaseException as error:
            receipt.update(status='stopped', error=repr(error))
            raise
        finally:
            receipt['wall_seconds'] = time.perf_counter() - start
            save(output / 'receipt.json', receipt)


if __name__ == '__main__':
    main()
