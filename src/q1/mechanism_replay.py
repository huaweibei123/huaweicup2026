"""Replay exactly the two approved original Pro008 plans under frozen P1 E0.

Preparation is byte-only. Execution never generates plans, searches, or retries.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tarfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / 'data/raw/a/official'
SOURCE = '3a4505d4101e23d54580d15560da3820e02d05da'
PREFIX = 'results/a/pro-research-20260924/'
NAMES = ('components', 'word')
AUTH = 'https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5804640018'
EXPECTED = {
    'graph.json': 'c93bb7ab5deec5112aff0cc001fbd76d001d3de5ea7463fba59b1f1ff2ba3e1d',
    'config.txt': 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9',
    'components/plan.json': '42d690447be9ee709172b62a6b3cab5f3a8d3f7d17aae76f65ee9afd4fd4bc35',
    'word/plan.json': 'fd4cdeb58d89fd507172fc72d3379f3ba7044d7d1ddbd6b2184d04a66d463769',
}


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def blob(path):
    return subprocess.check_output(['git', 'show', f'{SOURCE}:{path}'], cwd=ROOT)


def code_identity():
    manifest = json.loads(blob('docs/a/source-manifest.json'))
    items = sorted((m for m in manifest['files'] if m['path'].startswith('code/')), key=lambda m: m['path'])
    for item in items:
        raw = (OFFICIAL / item['path']).read_bytes()
        assert sha(raw) == item['sha256'] and len(raw) == item['bytes']
    aggregate = sha(''.join(f"{m['path']}\t{m['sha256']}\n" for m in items).encode())
    assert aggregate == manifest['official_code_hash']
    return {'aggregate_sha256': aggregate, 'files': items}


def prepare(output):
    start = time.monotonic()
    output.mkdir(parents=True, exist_ok=False)
    code = code_identity()
    manifest = json.loads(blob(PREFIX + 'pro2-r2-evidence.manifest.json'))
    parts = []
    for part in manifest['parts']:
        raw = blob(PREFIX + part['path'])
        assert len(raw) == part['bytes'] and sha(raw) == part['sha256']
        parts.append(raw)
    packed = b''.join(parts)
    assert len(packed) == manifest['archive_bytes'] and sha(packed) == manifest['archive_sha256']
    members = {m['path']: m for m in manifest['members']}
    selected = {}
    with tarfile.open(fileobj=io.BytesIO(packed), mode='r:xz') as archive:
        for name in NAMES:
            folder = output / name
            folder.mkdir()
            for filename in ['plan.json', 'run.json', 'result.json.gz', 'trace.json.gz', 'log.txt', 'stdout.txt', 'stderr.txt']:
                member = f'runs/resource_word/case_008_p2_{name}/{filename}'
                raw = archive.extractfile(member).read()
                assert len(raw) == members[member]['bytes'] and sha(raw) == members[member]['sha256']
                dest = 'plan.json' if filename == 'plan.json' else 'old_p2_' + filename
                (folder / dest).write_bytes(raw)
                selected[member] = dict(members[member], saved_as=f'{name}/{dest}')
    source_manifest = json.loads(blob('docs/a/source-manifest.json'))
    archive_info = source_manifest['case_archive']
    graph_archive = blob(archive_info['path'])
    assert sha(graph_archive) == archive_info['sha256']
    with zipfile.ZipFile(io.BytesIO(graph_archive)) as archive:
        (output / 'graph.json').write_bytes(archive.read('data/case_008.json'))
    (output / 'config.txt').write_bytes(blob('data/raw/a/official/data/config.txt'))
    for path, expected in EXPECTED.items():
        assert sha((output / path).read_bytes()) == expected
    plans = [json.loads((output / name / 'plan.json').read_bytes()) for name in NAMES]
    def owners(plan):
        core = {g: c for c, order in enumerate(plan['core_schedules']) for g in order}
        return {int(op): core[g] for op, g in plan['node_to_subgraph'].items()}
    assert owners(plans[0]) == owners(plans[1])
    counts = dict(collections.Counter(owners(plans[0]).values()))
    assert counts == {0:216, 1:216, 2:216, 3:216}
    old = []
    for name in NAMES:
        result = json.loads(gzip.decompress((output/name/'old_p2_result.json.gz').read_bytes()))
        old.append({'name':name, 'makespan':result['makespan'], 'data_movement_bytes':result['data_movement_bytes']})
    assert [r['makespan'] for r in old] == [123060,63768]
    assert old[0]['data_movement_bytes'] == old[1]['data_movement_bytes']
    protocol = {'prepared_utc':utc(), 'source_commit':SOURCE, 'authorization':AUTH,
        'input_sha256':EXPECTED, 'official_code':code, 'selected_archive_members':selected,
        'source_archive_sha256':manifest['archive_sha256'], 'same_op_to_core':True,
        'op_counts_per_core':counts, 'mapping_insertion_order_equal':list(plans[0]['node_to_subgraph']) == list(plans[1]['node_to_subgraph']),
        'group_counts':[len({g for g in p['node_to_subgraph'].values()}) for p in plans],
        'old_p2':old, 'max_calls':2, 'per_call_seconds':30, 'outer_seconds':180,
        'stop_launch_seconds':120, 'cleanup_reserve_seconds':60, 'workers':1,
        'retry':False, 'new_e0_calls_during_preparation':0,
        'preparation_seconds_before_manifest_write':time.monotonic()-start,
        'driver_sha256':sha(Path(__file__).read_bytes()), 'python':sys.version, 'platform':platform.platform(),
        'scope':'Stored-plan mechanism replay; not plan construction or whole-solver benchmark'}
    dump(output/'protocol.json', protocol)
    print(json.dumps({'prepared':str(output.relative_to(ROOT)), 'new_e0_calls':0}))


def observations(result):
    per_core = []
    for core in result['per_core_timeline']:
        tasks = core['tasks']
        busy = sum(t['duration'] for t in tasks)
        finish = max([0]+[t['end'] for t in tasks])
        per_core.append({'core':core['core_id'], 'task_count':len(tasks), 'busy_cycles':busy,
                         'finish_cycles':finish, 'idle_to_finish_cycles':finish-busy})
    return {'makespan':result['makespan'], 'data_movement_bytes':result['data_movement_bytes'],
            'task_same_core_wait_cycles':result['task_same_core_wait_cycles'],
            'task_cross_core_wait_cycles':result['task_cross_core_wait_cycles'], 'per_core':per_core}


def run(output):
    protocol = json.loads((output/'protocol.json').read_text())
    assert not (output/'ledger.json').exists(), 'Never rerun or reset a reserved experiment'
    assert protocol['driver_sha256'] == sha(Path(__file__).read_bytes())
    assert code_identity() == protocol['official_code']
    for path, expected in EXPECTED.items():
        assert sha((output/path).read_bytes()) == expected
    t0 = time.monotonic()
    ledger = {'T0_utc':utc(), 'T0_monotonic':t0, 'as_run_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'phase':'running', 'calls':[], 'authorization':AUTH}
    dump(output/'ledger.json', ledger)
    rows = []
    for name in NAMES:
        elapsed = time.monotonic()-t0
        if elapsed >= 120:
            ledger['phase'] = 'stopped_launch_deadline'
            break
        folder = output/name/'p1'; folder.mkdir()
        command = [sys.executable,'-B',str(OFFICIAL/'code/multicore_cut_evaluate_problem_1.py'),
            str(output/'graph.json'),str(output/name/'plan.json'),'--config',str(output/'config.txt'),
            '-o',str(folder/'result.json'),'--trace-output',str(folder/'trace.json'),'--log-output',str(folder/'log.txt')]
        command = [p.replace(str(ROOT)+'/', '') for p in command]
        record = {'name':name, 'reserved_at_utc':utc(), 'reserved_elapsed':elapsed,
                  'charged_calls':1, 'state':'reserved', 'command':[p.replace(str(ROOT)+'/', '') for p in command]}
        ledger['calls'].append(record); dump(output/'ledger.json',ledger)
        started = time.monotonic()
        with (folder/'stdout.txt').open('wb') as stdout, (folder/'stderr.txt').open('wb') as stderr:
            process = subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr,start_new_session=True)
            try:
                rc = process.wait(timeout=30)
                record.update(state='ok' if rc==0 else 'unexpected_failure', returncode=rc)
            except subprocess.TimeoutExpired:
                try:
                    import os
                    os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                record.update(state='timeout',returncode=process.returncode)
        record['wall_seconds'] = time.monotonic()-started
        record['finished_utc'] = utc()
        dump(output/'ledger.json',ledger)
        if record['state'] != 'ok':
            ledger['phase'] = 'stopped_first_failure'
            break
        result = json.loads((folder/'result.json').read_bytes())
        rows.append(dict(name=name,**observations(result)))
        files = {}
        for filename in ['result.json','trace.json','log.txt','stdout.txt','stderr.txt']:
            path = folder/filename; raw = path.read_bytes()
            files[filename] = {'bytes':len(raw),'sha256':sha(raw)}
            if filename.endswith('.json'):
                compressed = gzip.compress(raw,compresslevel=6,mtime=0)
                assert gzip.decompress(compressed) == raw
                dest = path.with_suffix(path.suffix+'.gz'); dest.write_bytes(compressed)
                assert sha(dest.read_bytes()) == sha(compressed)
                files[filename].update(saved_as=dest.name,compressed_sha256=sha(compressed),compressed_bytes=len(compressed))
                path.unlink()
        dump(folder/'files.json',files)
    if len(rows)==2:
        ledger['phase']='complete'
    ledger['charged_calls']=sum(c['charged_calls'] for c in ledger['calls'])
    summary = {'new_p1':rows, 'old_p2_author_results':protocol['old_p2'],
        'controls':{k:protocol[k] for k in ['same_op_to_core','op_counts_per_core','mapping_insertion_order_equal','group_counts']},
        'scope':'Original Pro bytes; group count and mapping order both change. No single-factor attribution. 044 A reused separately.'}
    dump(output/'summary.json',summary)
    lines=['# 原 Pro008 计划迁移到情况 A：有限机制对照','',
        '仅原 components/word 两份计划，保留原始字节与插入顺序；4核，每核216个计算操作。',
        '不是重新构造计划，不是求解器端到端测速；旧P2为作者归档，P1为此次本机官方CLI。','',
        '| 计划 | 本机 P1 Makespan | 作者旧 P2 Makespan |','|---|---:|---:|']
    for row in rows:
        old = next(r for r in protocol['old_p2'] if r['name']==row['name'])
        lines.append(f"| {row['name']} | {row['makespan']} | {old['makespan']} |")
    lines += ['', '完整COPY分项、各核忙/闲时间在summary.json；原始result/trace已逐字节校验后gzip保存。',
        '调用预留、实际T0、命令、每次wall、外层阶段在ledger.json；输入和冻结源码身份在protocol.json。',
        '原方案同时改变子图粒度、core_schedules及mapping插入顺序，不能称单因素排序对照。',
        '本次未调用E1/E2/P2/P3，未新增候选、修改官方程序或重试。','',
        '六字段：目标=核验B构造向A迁移；输入=固定Pro008原计划；输出=官方完整输出/时间账本；',
        '限制=2次E0/单worker/每次30秒/外层180秒；验收=保留输入字节及完成状态；节点=有限机制观察，非最终算法验收。','']
    (output/'REPORT.md').write_text('\n'.join(lines))
    ledger['local_report_complete_utc']=utc()
    ledger['local_wall_seconds']=time.monotonic()-t0
    ledger['local_within_180_seconds']=ledger['local_wall_seconds']<=180
    ledger['delivery_scope']='Local evaluation, lossless compression, report complete; publication receipt separately records elapsed from same T0'
    dump(output/'ledger.json',ledger)
    print(json.dumps({'phase':ledger['phase'],'charged_calls':ledger['charged_calls'],'rows':rows,
                      'local_wall_seconds':ledger['local_wall_seconds']},ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','run'])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if args.mode=='prepare': prepare(output)
    else: run(output)


if __name__=='__main__':
    main()
