"""Recheck three Pro4 synthetic mechanisms using only frozen official code.

The downloaded scripts are not executed. Named graph/plan bytes are extracted
from the pinned archived ZIP. Each gets an unmodified E0 CLI run plus a separate
Task-construction observation with a transparent Step2 wrapper.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import zipfile

from search import ROOT, OFFICIAL, confirm, dump, sha
from prototype import read_evaluation_config
import multicore_cut_evaluate_problem_1 as official

ARCHIVE_COMMIT = '96efc94d098c5950c7653088104fba02fb864215'
ARCHIVE_PATH = 'AI chats/20260924-Pro4-算法方案设计/附件/r03-HuaweiCup_R4_Q1_Audit_Patch.zip'
ARCHIVE_SHA256 = '5dca5a51238849c681d5aed3160265e192c0a179168a021ce539fc153f2e2b96'
CASES = ['projection_false_negative', 'probes_v1/internal_split_backed', 'probes_v1/internal_merged_unbacked']


def interval_peak(graph, sequence, capacity):
    """Closed first/last-touch intervals, on the provided pre-spill sequence."""
    positions = {op: i for i, op in enumerate(sequence)}
    tensor_by_id = {t['id']: t for t in graph['tensors']}
    uses = {tid: set() for tid in tensor_by_id}
    for edge in graph['edges']:
        a, b = edge['source'], edge['target']
        if a in positions and b in uses:
            uses[b].add(positions[a])
        if b in positions and a in uses:
            uses[a].add(positions[b])
    peak = {kind: 0 for kind in capacity}
    for i in range(len(sequence)):
        active = {kind: 0 for kind in capacity}
        for tid, slots in uses.items():
            tensor = tensor_by_id[tid]
            if slots and tensor['pos'] in active and min(slots) <= i <= max(slots):
                active[tensor['pos']] += tensor['size']
        for kind in peak:
            peak[kind] = max(peak[kind], active[kind])
    return peak


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    archive_bytes = subprocess.check_output(['git', 'show', ARCHIVE_COMMIT + ':' + ARCHIVE_PATH], cwd=ROOT)
    assert hashlib.sha256(archive_bytes).hexdigest() == ARCHIVE_SHA256
    settings = read_evaluation_config(str(OFFICIAL / 'data/config.txt'))
    hashes = {str(p.relative_to(OFFICIAL)): sha(p) for p in sorted((OFFICIAL / 'code').glob('*.py'))}
    protocol = {'archive_commit': ARCHIVE_COMMIT, 'archive_path': ARCHIVE_PATH,
                'archive_sha256': ARCHIVE_SHA256, 'cases': CASES, 'cli_timeout_seconds': 30,
                'scope': 'Synthetic mechanism replication, not formal-case quality',
                'official_code_hashes_before': hashes, 'config_sha256': sha(OFFICIAL / 'data/config.txt'),
                'python': sys.version, 'platform': platform.platform(),
                'source_sha256': sha(Path(__file__)), 'planned_before_runs': True}
    dump(output / 'protocol.json', protocol)
    (output / 'audit_patch_review.py').write_bytes(Path(__file__).read_bytes())
    rows = []
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        assert archive.testzip() is None
        for name in CASES:
            folder = output / Path(name).name
            folder.mkdir()
            for filename in ['graph.json', 'plan.json']:
                member = 'R4_Q1_Audit/results/' + name + '/' + filename
                (folder / filename).write_bytes(archive.read(member))
            graph, plan = [json.loads((folder / f).read_text()) for f in ['graph.json', 'plan.json']]
            cli = confirm(folder / 'graph.json', folder / 'plan.json', folder / 'e0', 30)
            if cli['status'] != 'ok':
                dump(folder / 'failure.json', cli)
                raise RuntimeError('Official CLI did not succeed: ' + name)
            observations = []
            original = official.step2_spill_insertion

            def observe(actual_graph, sequence, capacity):
                result = original(actual_graph, sequence, capacity)
                compute = {op['id'] for op in actual_graph['ops'] if op['op'] not in {'COPY_IN', 'COPY_OUT'}}
                observations.append({'graph': copy.deepcopy(actual_graph), 'step1': list(sequence),
                                     'actual_peak': interval_peak(actual_graph, sequence, capacity),
                                     'compute_only_peak': interval_peak(actual_graph, [op for op in sequence if op in compute], capacity),
                                     'spill_records': copy.deepcopy(result['spill_records'])})
                return result

            official.step2_spill_insertion = observe
            try:
                tasks, cross, traffic, view = official._build_scene_a_tasks(graph, plan, settings['bandwidth'], settings['capacity'])
            finally:
                official.step2_spill_insertion = original
            assert len(observations) == len(view['subgraph_ids'])
            for task, observation in zip(view['subgraph_ids'], observations):
                observation['task_id'] = task
            result = json.loads((folder / 'e0/result.json').read_text())
            assert traffic == result['data_movement_bytes']
            dump(folder / 'task_observations.json', observations)
            row = {'case': name, 'graph_sha256': sha(folder / 'graph.json'), 'plan_sha256': sha(folder / 'plan.json'),
                   'cli': cli, 'data_movement_bytes': traffic, 'observed_traffic_matches_cli': True,
                   'tasks': [{k: v for k, v in item.items() if k not in {'graph', 'step1'}} for item in observations]}
            rows.append(row)
            print(json.dumps({'case': name, 'makespan': result['makespan'], 'traffic': traffic}), flush=True)
    assert hashes == {str(p.relative_to(OFFICIAL)): sha(p) for p in sorted((OFFICIAL / 'code').glob('*.py'))}
    dump(output / 'summary.json', {'cases': rows, 'official_code_unchanged': True,
                                  'boundary': '3 CLI runs and separate Task construction observations; not a full-engine differential'})


if __name__ == '__main__':
    main()
