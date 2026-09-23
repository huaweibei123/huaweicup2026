"""Publish a byte-verified case044 A/B input index; never invoke an evaluator."""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = '13d6b0298f944d3c0bfdf3172191f1ac25a50379'
BASE = f'https://github.com/huaweibei123/huaweicup2026/blob/{SOURCE}/'
PROFILE = 'results/a/q1-profile-refine-20260924'
TRACE = 'results/a/q1-trace-analysis-20260924'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(path):
    return subprocess.check_output(['git', 'show', f'{SOURCE}:{path}'], cwd=ROOT)


def identity(path, data):
    return {'path': path, 'bytes': len(data), 'sha256': sha(data), 'url': BASE + path}


def archive_members(archive_path, selected):
    manifest_path = archive_path.replace('.tar.xz', '.manifest.json')
    manifest_bytes = blob(manifest_path)
    manifest = json.loads(manifest_bytes)
    raw = blob(archive_path)
    assert sha(raw) == manifest['sha256'] and len(raw) == manifest['bytes']
    expected = {m['path']: m for m in manifest['members']}
    content, identities = {}, []
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:xz') as archive:
        for name in selected:
            content[name] = archive.extractfile(name).read()
            item = expected[name]
            assert sha(content[name]) == item['sha256']
            assert len(content[name]) == item['bytes']
            identities.append(dict(item))
    return content, {'archive': identity(archive_path, raw),
                     'manifest': identity(manifest_path, manifest_bytes),
                     'verified_members': identities}


def prepare():
    start = time.monotonic()
    source_manifest = json.loads(blob('docs/a/source-manifest.json'))
    code = sorted((m for m in source_manifest['files'] if m['path'].startswith('code/')),
                  key=lambda m: m['path'])
    for item in code:
        raw = blob('data/raw/a/official/' + item['path'])
        assert sha(raw) == item['sha256'] and len(raw) == item['bytes']
    code_hash = sha(''.join(f"{m['path']}\t{m['sha256']}\n" for m in code).encode())
    assert code_hash == source_manifest['official_code_hash']
    case_archive = source_manifest['case_archive']
    zip_bytes = blob(case_archive['path'])
    assert sha(zip_bytes) == case_archive['sha256']
    assert len(zip_bytes) == case_archive['bytes']
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        graph_bytes = archive.read('data/case_044.json')
    graph = json.loads(graph_bytes)
    config_path = 'data/raw/a/official/data/config.txt'
    config = blob(config_path)
    parent_path = PROFILE + '/case044/seed.json'
    child_path = TRACE + '/044_bad_merge/plan.json'
    parent_bytes, child_bytes = blob(parent_path), blob(child_path)
    parent, child = json.loads(parent_bytes), json.loads(child_bytes)
    old_summary = json.loads(blob(PROFILE + '/case044/summary.json'))
    old_protocol = json.loads(blob(PROFILE + '/protocol.json'))
    trace_protocol = json.loads(blob(TRACE + '/protocol.json'))
    old_request = json.loads(blob(TRACE + '/044_bad_merge/request.json'))
    assert sha(graph_bytes) == old_summary['graph_sha256'] == old_request['graph_sha256']
    assert sha(config) == old_protocol['config_sha256'] == trace_protocol['config_sha256']
    assert sha(parent_bytes) == old_summary['seed_sha256']
    assert sha(child_bytes) == old_request['plan_sha256']
    assert set(parent) == set(child) == {'node_to_subgraph', 'core_schedules'}
    assert list(parent['node_to_subgraph']) == list(child['node_to_subgraph'])
    assert len(parent['core_schedules']) == len(child['core_schedules']) == 4
    assert parent['core_schedules'][0].index(10) == parent['core_schedules'][0].index(8) + 1
    for op, group in parent['node_to_subgraph'].items():
        assert child['node_to_subgraph'][op] == (8 if group == 10 else group)
    assert child['core_schedules'] == [[g for g in s if g != 10]
                                       for s in parent['core_schedules']]

    def assignment(plan):
        owner = {g: c for c, s in enumerate(plan['core_schedules']) for g in s}
        return {int(op): owner[g] for op, g in plan['node_to_subgraph'].items()}

    owners = assignment(parent)
    assert owners == assignment(child)
    assert set(owners) == {op['id'] for op in graph['ops']
                           if op['op'] not in {'COPY_IN', 'COPY_OUT'}}
    assert set(owners.values()) == {0}
    original_candidate, candidate_ref = archive_members(
        PROFILE + '/case044/candidate-plans.tar.xz', ['round0/candidate1/plan.json'])
    assert child_bytes == original_candidate['round0/candidate1/plan.json']
    parent_names = ['e0_seed/' + n for n in
                    ['result.json', 'trace.json', 'summary.log', 'stdout.txt', 'stderr.txt']]
    child_names = ['044_bad_merge/' + n for n in ['result.json', 'trace.json', 'summary.log']]
    parent_payload, parent_ref = archive_members(PROFILE + '/case044/execution-evidence.tar.xz', parent_names)
    child_payload, child_ref = archive_members(TRACE + '/execution-evidence.tar.xz', child_names)
    results = [json.loads(parent_payload['e0_seed/result.json']),
               json.loads(child_payload['044_bad_merge/result.json'])]
    assert [r['makespan'] for r in results] == [116227, 126094]
    assert results[0]['data_movement_bytes'] == old_summary['records'][0]['result']['data_movement_bytes']
    assert results[1]['data_movement_bytes'] == old_request['expected_previous_e1']['data_movement_bytes']
    for result in results:
        assert [c['core_id'] for c in result['per_core_timeline'] if c['tasks']] == [0]
    return {
        'prepared_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source_commit': SOURCE, 'session': 'nikolastarx/s-8ee33b891eb94c529bf5be94bb5d8894',
        'authorization': 'https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5804514746',
        'new_e0_calls': 0, 'new_e1_e2_calls': 0, 'experiment_started': False,
        'graph': {'restored_path': 'data/raw/a/official/data/case_044.json',
                  'bytes': len(graph_bytes), 'sha256': sha(graph_bytes),
                  'archive': identity(case_archive['path'], zip_bytes), 'member': 'data/case_044.json'},
        'config': identity(config_path, config),
        'official_code': {'source_manifest': BASE + 'docs/a/source-manifest.json',
                          'verified_files': len(code), 'aggregate_sha256': code_hash},
        'plans': {'parent': identity(parent_path, parent_bytes), 'child': identity(child_path, child_bytes)},
        'edit': {'kind': 'same_core_adjacent_merge', 'tasks': [8, 10],
                 'node_mapping_key_order_preserved': True, 'same_op_to_core': True,
                 'op_counts_per_core': dict(collections.Counter(owners.values())),
                 'configured_cores': 4, 'active_cores': [0],
                 'scope': 'Single-active-core mechanism control, not a best four-core Q2 solution'},
        'child_original_candidate_archive': candidate_ref,
        'existing_q1_e0': {
            'parent': {'evidence': parent_ref, 'makespan': results[0]['makespan'],
                       'data_movement_bytes': results[0]['data_movement_bytes']},
            'child': {'evidence': child_ref, 'makespan': results[1]['makespan'],
                      'data_movement_bytes': results[1]['data_movement_bytes']},
            'reuse': 'Both A results and full traces are available at these exact input/plan identities; do not rerun only to fill budget'},
        'pending': ['Fang coordination fixes T0, assigned calls and cleanup reserve before new evaluation',
                    'Q2 verifies case008 original files; missing 008 does not block this 044 pair',
                    'No B execution or score is claimed by this input check'],
        'verification_seconds_before_report_write': time.monotonic() - start,
        'timing_scope': 'Read-only Git/archive/byte checks; no plan generation or solver performance experiment',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output must not already exist')
    index = prepare()
    args.output.mkdir(parents=True)
    (args.output / 'inputs.json').write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n')
    lines = ['# 044 A/B 共同机制输入：零 E0 字节核验', '',
             f'全部原件固定在 `{SOURCE}`。本次未生成新计划，未启动实验，E0/E1/E2 新调用均为 0。', '',
             '原图、配置、计划与完整结果的 SHA、大小和固定链接见 [inputs.json](inputs.json)。', '',
             '| 对象 | SHA-256 |', '|---|---|',
             f"| case_044.json | `{index['graph']['sha256']}` |",
             f"| config.txt | `{index['config']['sha256']}` |"]
    for name, plan in index['plans'].items():
        lines.append(f"| {name} plan | `{plan['sha256']}` |")
    lines += ['', '父计划→仅合并 Task 8/10；逐操作核归属、mapping 键顺序均保持。配置4核，实际仅core0有工作。',
              '既有 A 完整 E0 为116227→126094 cycles，两份 trace/result 已逐成员校验，可直接复用；不是本次新测成绩。',
              'B 的同核合并不等于 A 的 Task 边界消失；其 COPY 分桶、spill/FIFO 和结果须由匹配 B E0 验证，失败也保留。', '',
              'Fang协调汇总固定输入、T0/分工及收尾预留后启动新调用；本清单不是已启动回执。008由Q2核查，未在此补造。', '',
              '本次六字段：目标=固定可交换044原件；输入=上述13d6提交；输出=本清单与inputs.json；',
              '限制=零新评价/单活跃核；验收=来源、归属、原始字节和已有结果绑定检查通过；节点=准备完成，待协调落实执行。', '',
              '重做本项只读核验（输出须是新目录）：', '',
              '```sh', 'uv run python -B src/q1/mechanism_inputs.py --output results/a/new-mechanism-input-check', '```', '']
    (args.output / 'README.md').write_text('\n'.join(lines))
    print(json.dumps({'output': str(args.output), 'new_e0_calls': 0,
                      'same_op_to_core': True, 'source_commit': SOURCE}))


if __name__ == '__main__':
    main()
