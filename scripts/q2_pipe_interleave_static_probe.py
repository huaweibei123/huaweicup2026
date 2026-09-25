"""One frozen 072/K5 pipe-interleave static probe; no evaluator calls."""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import q2_selected_plan_static_probe as base

PLAN = ROOT / 'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee/cases-071-080/072-k5/plan.json.gz'
OFFICIAL = ROOT / 'docs/a/source-manifest.json'
LIMITS = {'workers': 1, 'wall_seconds': 30, 'rss_bytes': 1 << 30,
          'E0': 0, 'E1': 0, 'E2': 0, 'retries': 0}


def source_hashes():
    return {**base.sources(), Path(__file__).relative_to(ROOT).as_posix(): base.sha(Path(__file__).read_bytes())}


def projection(plan, pipes):
    inverse = {sg: int(op) for op, sg in plan['node_to_subgraph'].items()}
    owner, pipe_order = {}, {}
    for core, row in enumerate(plan['core_schedules']):
        for sg in row:
            op = inverse[sg]
            owner[op] = core
            pipe_order.setdefault((core, pipes[op]), []).append(op)
    return owner, pipe_order


def rows_follow_global_order(plan, order):
    inverse = {sg: int(op) for op, sg in plan['node_to_subgraph'].items()}
    rank = {op: i for i, op in enumerate(order)}
    if len(rank) != len(order):
        return False
    return all(rank[inverse[a]] < rank[inverse[b]]
               for row in plan['core_schedules'] for a, b in zip(row, row[1:]))


def constructor_count(output, dispatched):
    marker = output / 'constructor-start.json'
    if marker.exists():
        try:
            if json.loads(marker.read_bytes()) == {'constructor_started': 1}:
                return 1
        except (ValueError, OSError):
            pass
        return None
    return None if dispatched else 0


def verify(doc):
    if (doc.get('schema') != 'q2-pipe-static-072-k5-v1' or doc.get('limits') != LIMITS
            or doc.get('source_commit') != base.git_head()
            or doc.get('source_sha256') != source_hashes()):
        raise ValueError('Frozen source/limits differ')
    raw = PLAN.read_bytes()
    if (base.sha(raw) != doc['plan_gzip_sha256']
            or base.sha(gzip.decompress(raw)) != doc['plan_json_sha256']):
        raise ValueError('Archived 072/K5 plan differs')
    for name in ('graph', 'config'):
        if base.sha(Path(doc[name]).read_bytes()) != doc[name + '_sha256']:
            raise ValueError('Official ' + name + ' bytes differ')
    return json.loads(gzip.decompress(raw))


def child(manifest_path):
    sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    from src.q2_nikolastarx.pipe_interleave_memory import retime
    from src.q2_nikolastarx.dag_direct import DAGIndex
    from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
    from src.q2_nikolastarx.fifo_bound import fixed_fifo_lower_bound
    doc = json.loads(manifest_path.read_bytes())
    seed = verify(doc)
    graph = json.loads(Path(doc['graph']).read_bytes())
    config_path = Path(doc['config'])
    config = {**read_evaluation_config(config_path), **read_scene_b_config(config_path)}
    with (manifest_path.parent / 'constructor-start.json').open('x') as marker:
        json.dump({'constructor_started': 1}, marker)
        marker.write('\n')
    plan, meta = retime(graph, seed, config)
    index = DAGIndex(graph)
    pipes = {op: row['pipe'] for op, row in index.ops.items()}
    before, after = projection(seed, pipes), projection(plan, pipes)
    if before != after:
        raise ValueError('Owner or per-core Pipe FIFO projection changed')
    order = meta['global_topological_order']
    rank = {op: i for i, op in enumerate(order)}
    if len(order) != len(index.ops) or set(order) != set(index.ops):
        raise ValueError('Global dependency order incomplete')
    if not rows_follow_global_order(plan, order):
        raise ValueError('New full core rows disagree with global topological order')
    if any(rank[u] >= rank[v] for u, children in index.succ.items() for v in children):
        raise ValueError('Global dependency cycle/order violation')
    for row in after[1].values():
        if any(rank[u] >= rank[v] for u, v in zip(row, row[1:])):
            raise ValueError('Pipe FIFO global-order violation')
    mandatory = {'before': mandatory_copy_work(graph, seed, config['bandwidth']),
                 'after': mandatory_copy_work(graph, plan, config['bandwidth'])}
    if mandatory['before']['transfer_bytes'] != mandatory['after']['transfer_bytes']:
        raise ValueError('Mandatory cross-core bytes changed')
    fifo = {'before': fixed_fifo_lower_bound(graph, seed),
            'after': fixed_fifo_lower_bound(graph, plan)}
    if (not all(v['supported'] for v in fifo.values()) or
            fifo['before']['makespan_lower_bound_cycles'] !=
            fifo['after']['makespan_lower_bound_cycles']):
        raise ValueError('Fixed FIFO necessary bound changed or unsupported')
    out = manifest_path.parent
    base.save(out / 'plan.json', plan)
    base.save(out / 'meta.json', meta)
    base.save(out / 'mandatory.json', mandatory)
    base.save(out / 'fifo-bound.json', fifo)
    base.save(out / 'static-result.json', {
        'status': 'static_only', 'plan_sha256': base.sha((out / 'plan.json').read_bytes()),
        'owner_pipe_projection_unchanged': True, 'global_dependencies_acyclic': True,
        'mandatory_transfer_bytes': mandatory['after']['transfer_bytes'],
        'fifo_lower_bound_cycles': fifo['after']['makespan_lower_bound_cycles'],
        'capacity_peaks_before': meta['original_peaks'],
        'capacity_peaks_after': meta['new_peaks'],
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
        entries = {x['path']: x for x in json.loads(OFFICIAL.read_bytes())['files']}
        for label, path, key in (('graph', graph, 'data/case_072.json'),
                                 ('config', config, 'data/config.txt')):
            item = entries[key]
            if base.sha(path.read_bytes()) != item['sha256'] or path.stat().st_size != item['bytes']:
                raise ValueError('Official ' + label + ' identity differs')
        out = a.output.resolve()
        if not out.is_relative_to((ROOT / 'output').resolve()):
            raise ValueError('Raw manifest must stay under output/')
        out.mkdir(parents=True, exist_ok=False)
        raw = PLAN.read_bytes()
        base.save(out / 'manifest.json', {
            'schema': 'q2-pipe-static-072-k5-v1', 'source_commit': base.git_head(),
            'source_sha256': source_hashes(), 'graph': str(graph), 'config': str(config),
            'graph_sha256': base.sha(graph.read_bytes()),
            'config_sha256': base.sha(config.read_bytes()),
            'plan_gzip_sha256': base.sha(raw),
            'plan_json_sha256': base.sha(gzip.decompress(raw)),
            'command': [sys.executable, '-B', str(Path(__file__).resolve()), 'run',
                        '--manifest', str(out / 'manifest.json')], 'limits': LIMITS})
        print(out / 'manifest.json')
        return
    if a.manifest is None:
        p.error('run/child need --manifest')
    manifest_path = a.manifest.resolve(strict=True)
    if a.mode == 'child':
        child(manifest_path)
        return
    started = time.perf_counter()
    deadline = started + 30
    out = manifest_path.parent
    base.reserve_attempt(out, manifest_path, started)
    receipt = {'status': 'attempt_reserved', 'manifest_sha256': base.sha(manifest_path.read_bytes()),
               'dispatch_started': False,
               'calls': {'constructor_started': None, 'E0': 0, 'E1': 0, 'E2': 0}}
    try:
        base.save(out / 'receipt.json', receipt)
        verify(json.loads(manifest_path.read_bytes()))
        from src.q2_nikolastarx.evaluate_feedback import monitored
        if time.perf_counter() >= deadline:
            raise TimeoutError('30-second total budget exhausted before dispatch')
        receipt['dispatch_started'] = True
        base.save(out / 'receipt.json', receipt)
        process = monitored([sys.executable, '-B', str(Path(__file__).resolve()), 'child',
                             '--manifest', str(manifest_path)], out / 'process', deadline, 1 << 30)
        receipt['process'] = process
        if constructor_count(out, True) != 1:
            raise RuntimeError('Constructor start is unverified')
        if process['status'] != 'ok' or process.get('surviving_pids'):
            raise RuntimeError('Static child failed or outcome unknown')
        receipt['status'] = 'completed_static_only'
    except BaseException as error:
        receipt.update(status='stopped', error=repr(error))
        raise
    finally:
        receipt['calls']['constructor_started'] = constructor_count(out, receipt['dispatch_started'])
        receipt['wall_seconds'] = time.perf_counter() - started
        base.save(out / 'receipt.json', receipt)


if __name__ == '__main__':
    main()
