"""Audit immutable batch originals without importing or running solver/E0."""
import gzip
import hashlib
import json
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
BASE = Path(__file__).resolve().parent
PIPES = {'PIPE_M', 'PIPE_V', 'PIPE_MTE2', 'PIPE_MTE3'}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def load(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)

def artifact(item):
    raw = (ROOT / item['path']).read_bytes()
    assert sha(raw) == item['sha256'], item['path']
    return raw

def main():
    ledger = load(BASE / 'ledger.json')
    spec = load(BASE / 'spec.json')
    spec_path = ROOT / ledger['runner_argv'][-1]
    assert sha(spec_path.read_bytes()) == ledger['spec_sha256']
    assert spec == load(spec_path)
    assert ledger['state'] == 'completed' and len(ledger['attempts']) == len(spec['cases'])
    n = len(spec['cases'])
    assert ledger['charged_calls'] == dict(solver=n, E0=n, E1=0, E2=0)
    assert len(ledger['reservations']) == 2*n
    feed_path = next(p for p in BASE.glob('board-feed-*.json') if '-preflight' not in p.name)
    feed = load(feed_path)
    check = load(feed_path.with_name(feed_path.stem + '-preflight.json'))
    assert check['returncode'] == 0 and artifact(check['feed']) == feed_path.read_bytes()
    assert json.loads(check['stdout'])['eligible'] == n
    assert len(feed['records']) == n
    by_case = {r['case_id']:r for r in feed['records']}
    assert list(by_case) == spec['cases']
    source_count = 0
    for path, expected in ledger['source_hashes'].items():
        commit = spec['evaluator_commit'] if path.startswith('data/raw/') else spec['runner_commit'] if path.endswith('/measure.py') else spec['solver_commit']
        assert sha((ROOT / path).read_bytes()) == expected
        assert sha(subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)) == expected
        source_count += 1
    reservations = {(r['attempt_id'],r['stage']):r for r in ledger['reservations']}
    assert len(reservations) == 2*n
    intervals, rows = [], []
    gz_count = artifact_count = trace_ops = 0
    for name in ledger['attempts']:
        run = load(ROOT / name)
        case = run['case_id']
        rec = by_case[case]
        folder = (ROOT / name).parent
        assert run['status'] == 'ok' and run['failure'] is None
        assert run['cores'] == spec['cores'] and run['identity'] == rec['identity']
        assert run['calls'] == dict(solver=1,E0=1,E1=0,E2=0)
        assert run['source_hashes'] == ledger['source_hashes']
        for key in ('solver_commit','runner_commit','evaluator_commit'):
            assert run[key] == spec[key]
        assert sha((ROOT / f'data/raw/a/official/data/case_{case}.json').read_bytes()) == run['identity']['graph_sha256']
        for item in rec['artifacts'].values():
            artifact(item)
            artifact_count += 1
        decoded = {}
        for key, item in run['compression'].items():
            stored = artifact(item['artifact'])
            raw = gzip.decompress(stored)
            assert len(raw) == item['raw_bytes'] and len(stored) == item['stored_bytes']
            assert sha(raw) == item['raw_sha256'] and int.from_bytes(stored[4:8], 'little') == 0
            decoded[key] = json.loads(raw)
            gz_count += 1
        result, trace = decoded['result.json'], decoded['trace.json']
        cycles = result['makespan']
        assert cycles == run['metrics']['makespan_cycles'] == rec['metrics']['makespan_cycles'] == trace['otherData']['makespan']
        assert result['num_cores'] == spec['cores'] and result['scene'] == 'B'
        assert result['data_movement_bytes'] == run['metrics']['data_movement_bytes']
        assert f'makespan={cycles}' in (folder / 'E0.stdout.txt').read_text()
        assert (folder / 'solver.stderr.txt').read_bytes() == (folder / 'E0.stderr.txt').read_bytes() == b''
        report = load(folder / 'solver.stdout.txt')
        assert report == rec['parameters']['solver_report'] and report['online_E0_calls'] == 0
        plan = json.loads(artifact(run['artifacts']['plan']))
        assert set(plan) == {'node_to_subgraph','core_schedules'} and len(plan['core_schedules']) == spec['cores']
        scheduled = [s for core in plan['core_schedules'] for s in core]
        assert len(set(scheduled)) == len(scheduled) and set(scheduled) == set(plan['node_to_subgraph'].values())
        for stage in ('solver','E0'):
            actual = run['stages'][stage]
            reserved = reservations[(run['attempt_id'],stage)]
            assert actual['status'] == reserved['state'] == 'ok' and actual['returncode'] == 0
            assert actual['launched'] and reserved['launched']
            assert actual['wall_seconds'] == reserved['actual_wall_seconds']
            assert reserved['reserved_at'] <= actual['started_at'] < actual['finished_at']
            intervals.append((actual['started_at'],actual['finished_at']))
        from_trace = {(e['args']['core_id'],e['args']['op_id']):(e['cat'],e['ts'],e['ts']+e['dur']) for e in trace['traceEvents'] if e.get('ph') == 'X' and e.get('cat') in PIPES}
        from_result = {(core['core_id'],op['op_id']):(op['pipe'],op['start'],op['end']) for core in result['per_core_timeline'] for op in core['ops']}
        assert from_trace == from_result
        assert max(end for _,_,end in from_result.values()) == cycles
        trace_ops += len(from_result)
        base = load(ROOT / f'results/benchmark-board/official-singlecore-20260924/{case}/run.json')
        assert base['status'] == 'ok'
        assert base['graph_sha256'] == run['identity']['graph_sha256']
        assert base['config_sha256'] == run['identity']['config_sha256']
        assert base['official_code_hash'] == run['identity']['official_sha256']
        base_item = base['artifacts']['result.json']
        original = gzip.decompress(artifact(base_item))
        assert sha(original) == base_item['raw_sha256'] and json.loads(original)['makespan'] == base['makespan_cycles']
        rows.append(dict(case_id=case, baseline_cycles=base['makespan_cycles'], makespan_cycles=cycles,
                         speedup=base['makespan_cycles']/cycles, solver_seconds=run['stages']['solver']['wall_seconds'],
                         E0_seconds=run['stages']['E0']['wall_seconds'], data_movement_bytes=result['data_movement_bytes']))
    intervals.sort()
    assert all(a[1] <= b[0] for a,b in zip(intervals,intervals[1:]))
    assert ledger['started_at'] <= intervals[0][0] and intervals[-1][1] <= ledger['finished_at']
    audit = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), scope='Read-only saved originals; no solver/E0/E1/E2 calls',
                 batch=BASE.relative_to(ROOT).as_posix(), started_at=ledger['started_at'], finished_at=ledger['finished_at'],
                 state=ledger['state'], calls=ledger['charged_calls'], wall_seconds=ledger['batch_wall_seconds'],
                 spec_sha256=ledger['spec_sha256'], source_files_verified=source_count, gzip_records_verified=gz_count,
                 feed_artifacts_verified=artifact_count, trace_operations_verified=trace_ops, stage_order_verified=True,
                 feed_path=feed_path.relative_to(ROOT).as_posix(), feed_sha256=sha(feed_path.read_bytes()),
                 cases=n, mean_speedup=statistics.mean(r['speedup'] for r in rows), rows=rows,
                 limitations=['Shared CPU, memory, OS cache; single observation per case', 'External E0 separate from solver wall; preflight/postprocessing separate'])
    (BASE / 'measurement-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:audit[key] for key in ('batch','cases','calls','mean_speedup','gzip_records_verified','trace_operations_verified')},ensure_ascii=False))

if __name__ == '__main__':
    main()
