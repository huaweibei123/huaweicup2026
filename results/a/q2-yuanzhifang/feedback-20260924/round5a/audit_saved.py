"""Audit saved round5a bytes and intervals; never imports/runs solver or E0."""
from __future__ import annotations
import gzip
import hashlib
import json
import statistics
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
BASE = Path(__file__).resolve().parent
REL = BASE.relative_to(ROOT).as_posix()
PIPES = ('PIPE_M', 'PIPE_V', 'PIPE_MTE2', 'PIPE_MTE3')
SPEC_COMMIT = 'e6deb8a78b45bda186577b853390fe7632354c2b'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))

def artifact(item):
    data = (ROOT / item['path']).read_bytes()
    assert sha(data) == item['sha256'], item['path']
    return data

def main():
    begin = time.perf_counter()
    ledger = read(f'{REL}/ledger.json')
    spec = read(f'{REL}/spec.json')
    spec_path = f'{REL}-spec.json'
    spec_bytes = (ROOT / spec_path).read_bytes()
    assert sha(spec_bytes) == ledger['spec_sha256']
    assert spec_bytes == subprocess.check_output(['git', 'show', f'{SPEC_COMMIT}:{spec_path}'], cwd=ROOT)
    assert spec == json.loads(spec_bytes)
    feed_path = next(p for p in BASE.glob('board-feed-*.json') if 'preflight' not in p.name)
    feed = json.loads(feed_path.read_text(encoding='utf-8'))
    preflight = read(feed_path.with_name(feed_path.stem+'-preflight.json'))
    assert preflight['returncode'] == 0 and artifact(preflight['feed']) == feed_path.read_bytes()
    assert json.loads(preflight['stdout'])['eligible'] == 30
    by_case = {r['case_id']: r for r in feed['records']}
    assert list(by_case) == spec['cases'] and len(by_case) == 30
    assert ledger['charged_calls'] == dict(solver=30, E0=30, E1=0, E2=0)
    assert ledger['state'] == 'completed' and len(ledger['attempts']) == 30
    assert len(ledger['reservations']) == 60
    assert len({(r['attempt_id'],r['stage']) for r in ledger['reservations']}) == 60
    reservations = {(r['attempt_id'],r['stage']):r for r in ledger['reservations']}
    sources = []
    for path, expected in ledger['source_hashes'].items():
        commit = spec['evaluator_commit'] if path.startswith('data/raw/') else spec['runner_commit'] if path.endswith('/measure.py') else spec['solver_commit']
        assert sha((ROOT/path).read_bytes()) == expected
        assert sha(subprocess.check_output(['git','show',f'{commit}:{path}'],cwd=ROOT)) == expected
        sources.append(dict(path=path,sha256=expected,commit=commit,verified=True))
    official_lines = ''.join(f"{p.removeprefix('data/raw/a/official/')}\t{v}\n" for p,v in sorted(ledger['source_hashes'].items()) if p.startswith('data/raw/'))
    official_sha = sha(official_lines.encode())
    assert sha((ROOT/'data/raw/a/official/data/config.txt').read_bytes()) == 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'
    old_path = 'results/a/q2-yuanzhifang/feedback-20260924/goal-baseline/sources/captain-k2-k5/board-feed-full400.json'
    old = {r['case_id']:r for r in read(old_path)['records'] if r['cores']==4}
    gz_records, cases, stages, baselines = [], [], [], []
    trace_count = artifact_count = 0
    for path in ledger['attempts']:
        run = read(path)
        cid = run['case_id']
        rec = by_case[cid]
        folder = (ROOT/path).parent
        assert run['status']=='ok' and run['failure'] is None
        assert run['source_hashes'] == ledger['source_hashes']
        assert run['calls'] == dict(solver=1,E0=1,E1=0,E2=0)
        assert run['identity'] == rec['identity']
        assert run['identity']['official_sha256'] == official_sha
        assert sha((ROOT/f'data/raw/a/official/data/case_{cid}.json').read_bytes()) == run['identity']['graph_sha256']
        for key in ('solver_commit','runner_commit','evaluator_commit'):
            assert run[key] == spec[key]
        for item in rec['artifacts'].values():
            artifact(item)
            artifact_count += 1
        decoded = {}
        for name, item in run['compression'].items():
            stored = artifact(item['artifact'])
            raw = gzip.decompress(stored)
            assert sha(raw) == item['raw_sha256'] and len(raw)==item['raw_bytes'] and len(stored)==item['stored_bytes']
            assert int.from_bytes(stored[4:8],'little')==0
            decoded[name]=json.loads(raw)
            gz_records.append(dict(path=item['artifact']['path'],stored_sha256=sha(stored),raw_sha256=sha(raw),raw_bytes=len(raw),stored_bytes=len(stored),mtime=0,verified=True))
        result, trace = decoded['result.json'],decoded['trace.json']
        makespan = result['makespan']
        assert makespan == run['metrics']['makespan_cycles'] == rec['metrics']['makespan_cycles'] == trace['otherData']['makespan']
        assert result['num_cores']==4 and result['scene']=='B'
        assert result['data_movement_bytes']==run['metrics']['data_movement_bytes']
        assert rec['metrics']['ddr_bytes']==result['data_movement_bytes']['scheduled_copy_bytes']
        assert rec['metrics']['extra_ddr_bytes']==result['data_movement_bytes']['added_copy_bytes']
        assert rec['metrics']['spill_bytes']==result['data_movement_bytes']['spill_added_copy_bytes']
        assert f'makespan={makespan}' in (folder/'E0.stdout.txt').read_text()
        assert f'makespan: {makespan}' in (folder/'result.txt').read_text()
        for stage in ('solver','E0'):
            st = run['stages'][stage]
            reserved = reservations[(run['attempt_id'],stage)]
            assert st['status']=='ok' and st['returncode']==0 and st['launched']
            assert reserved['state']=='ok' and reserved['launched'] and reserved['actual_wall_seconds']==st['wall_seconds']
            assert reserved['reserved_at'] <= st['started_at'] < st['finished_at']
            assert (folder/f'{stage}.stderr.txt').read_bytes()==b''
            stages.append((st['started_at'],st['finished_at'],cid,stage))
        report=json.loads((folder/'solver.stdout.txt').read_text())
        assert report==rec['parameters']['solver_report'] and report['online_E0_calls']==0
        plan=json.loads(artifact(run['artifacts']['plan']))
        assert set(plan)=={'node_to_subgraph','core_schedules'} and len(plan['core_schedules'])==4
        scheduled=[s for core in plan['core_schedules'] for s in core]
        assert len(set(scheduled))==len(scheduled) and set(scheduled)==set(plan['node_to_subgraph'].values())
        graph=read(f'data/raw/a/official/data/case_{cid}.json')
        eligible={str(op['id']) for op in graph['ops'] if op['op'] not in ('COPY_IN','COPY_OUT')}
        assert set(plan['node_to_subgraph'])==eligible
        trace_ops={(e['args']['core_id'],e['args']['op_id']):(e['cat'],e['ts'],e['ts']+e['dur']) for e in trace['traceEvents'] if e.get('ph')=='X' and e.get('cat') in PIPES}
        result_ops={}
        core_metrics=[]
        for core in result['per_core_timeline']:
            pipes={}
            for p in PIPES:
                ops=sorted((op for op in core['ops'] if op['pipe']==p),key=lambda x:(x['start'],x['end']))
                assert all(a['end']<=b['start'] for a,b in zip(ops,ops[1:])),(cid,core['core_id'],p)
                busy=sum(op['duration'] for op in ops)
                first=ops[0]['start'] if ops else None
                last=ops[-1]['end'] if ops else None
                pipes[p]=dict(op_count=len(ops),busy_cycles=busy,first_start=first,last_end=last,internal_idle_cycles=last-first-busy if ops else 0,total_idle_cycles=makespan-busy)
            for op in core['ops']:
                assert op['end']-op['start']==op['duration'] and 0<=op['start']<=op['end']<=makespan
                result_ops[(core['core_id'],op['op_id'])]=(op['pipe'],op['start'],op['end'])
            core_metrics.append(dict(core_id=core['core_id'],pipes=pipes,copy_counts=dict(Counter(op['op'] for op in core['ops'] if op['op'] in ('COPY_IN','COPY_OUT')))))
        assert trace_ops==result_ops
        assert max(v[2] for v in result_ops.values())==makespan
        trace_count+=len(result_ops)
        baseline_path=f'results/benchmark-board/official-singlecore-20260924/{cid}/run.json'
        baseline=read(baseline_path)
        assert baseline['status']=='ok' and baseline['graph_sha256']==run['identity']['graph_sha256'] and baseline['config_sha256']==run['identity']['config_sha256'] and baseline['official_code_hash']==official_sha
        item=baseline['artifacts']['result.json']
        stored=artifact(item); raw=gzip.decompress(stored)
        assert sha(raw)==item['raw_sha256'] and json.loads(raw)['makespan']==baseline['makespan_cycles']
        baselines.append(dict(case_id=cid,run=baseline_path,result=item['path'],raw_sha256=sha(raw),stored_sha256=sha(stored),makespan_cycles=baseline['makespan_cycles']))
        for key in ('graph_sha256','config_sha256','official_sha256'):
            assert old[cid]['identity'][key]==run['identity'][key]
        cases.append(dict(case_id=cid,makespan_cycles=makespan,singlecore_cycles=baseline['makespan_cycles'],speedup=baseline['makespan_cycles']/makespan,solver_wall_seconds=run['stages']['solver']['wall_seconds'],E0_wall_seconds=run['stages']['E0']['wall_seconds'],route=report['selected'],solver_report=report,data_movement_bytes=result['data_movement_bytes'],old_contiguous_cycles=old[cid]['metrics']['makespan_cycles'],old_over_new=old[cid]['metrics']['makespan_cycles']/makespan,cross_core_transfer_count=len(result['cross_core_transfers']),per_core=core_metrics,trace_ops_verified=len(result_ops)))
    stages.sort()
    assert all(a[1]<=b[0] for a,b in zip(stages,stages[1:])), 'stage overlap'
    assert ledger['started_at']<=stages[0][0] and stages[-1][1]<=ledger['finished_at']
    r4=read('results/a/q2-yuanzhifang/feedback-20260924/round4/measurement-audit.json')
    r4_runs=[read(p) for p in read('results/a/q2-yuanzhifang/feedback-20260924/round4/ledger.json')['attempts']]
    combined={r['case_id']:read(f"results/benchmark-board/official-singlecore-20260924/{r['case_id']}/run.json")['makespan_cycles']/r['metrics']['makespan_cycles'] for r in r4_runs}
    assert not set(combined)&set(by_case) and all(r['solver_commit']==spec['solver_commit'] for r in r4_runs)
    combined.update({c['case_id']:c['speedup'] for c in cases})
    output=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),scope='Read-only audit of saved round5a. No new solver, E0, E1 or E2; no scheduling-helper calls; historical comparison is not a current central-best claim.',command='python -X utf8 -B '+f'{REL}/audit_saved.py',batch={k:ledger[k] for k in ('run_id','started_at','finished_at','state','charged_calls','batch_wall_seconds','preparation','environment')},spec_commit=SPEC_COMMIT,integrity=dict(spec_sha256=ledger['spec_sha256'],sources=sources,gzip_raw_and_stored_verified_count=len(gz_records),gzip_records=gz_records,feed_artifact_reference_hashes_verified=artifact_count,trace_operation_intervals_verified=trace_count,stage_order_single_worker_verified=True,empty_stderr_count=60,baseline_results_verified=baselines),feed=dict(path=feed_path.relative_to(ROOT).as_posix(),sha256=sha(feed_path.read_bytes()),records=30,eligible=30,failed=0),cases=cases,partial_summary=dict(scope='Incomplete fixed-source k4 sample; neither this 30-case nor combined 40-case value is the required full-100 mean.',case_count=30,arithmetic_mean_speedup=statistics.mean(c['speedup'] for c in cases),solver_sum_seconds=sum(c['solver_wall_seconds'] for c in cases),solver_median_seconds=statistics.median(c['solver_wall_seconds'] for c in cases),solver_max_seconds=max(c['solver_wall_seconds'] for c in cases),E0_sum_seconds=sum(c['E0_wall_seconds'] for c in cases),old_contiguous_source_commit='6664a63adc3464d28d1f835d907cdeaea23e6b35',old_contiguous_feed_sha256=sha((ROOT/old_path).read_bytes()),old_contiguous_better=sum(c['old_over_new']>1 for c in cases),old_contiguous_equal=sum(c['old_over_new']==1 for c in cases),old_contiguous_worse=sum(c['old_over_new']<1 for c in cases),combined_R4_A_count=len(combined),combined_R4_A_arithmetic_mean_speedup=statistics.mean(combined.values()),missing_full100_cases=[f'{i:03}' for i in range(1,101) if f'{i:03}' not in combined]),limitations=['A single cold-process observation per case; OS file caches and ordinary background loads uncontrolled.','Wrapper wall includes process launch, wait and durable launch bookkeeping; external E0 is separate.','Preflight preparation and postprocessing are outside solver wall and separately recorded.','Peak RSS unmeasured; no per-core byte attribution is inferred from COPY duration under shared DDR.','Per-pipe busy/idle uses final saved intervals and does not establish a bottleneck cause.','Combined R4+A uses the same solver commit and disjoint cases; B/C remain unmeasured here.'])
    output['audit_wall_seconds']=time.perf_counter()-begin
    (BASE/'measurement-audit.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(audit=f'{REL}/measurement-audit.json',gzip_verified=len(gz_records),trace_ops=trace_count,partial_summary=output['partial_summary']),ensure_ascii=False))

if __name__=='__main__':
    main()
