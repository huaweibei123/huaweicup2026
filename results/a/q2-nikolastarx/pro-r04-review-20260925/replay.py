"""Replay the archived Pro prototype and test a boundary of its optimality claim.

Synthetic only: no official evaluator, candidate search or official case input.
Original attachments are read-only; all regenerated files go to a temporary copy.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
ARCHIVE = ROOT / 'AI chats/20260924-P2-异构流水与最优性界/附件/r04-P2_r04_tensor_cut.zip'
ARCHIVE_SHA = '73d79552b1f8cd86fb42dcceb711c9110207c5d4e6402db373922728e37fc6c3'


def main():
    started = time.perf_counter()
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == ARCHIVE_SHA
    with tempfile.TemporaryDirectory(prefix='p2-r04-replay-') as temp:
        folder = Path(temp)
        with zipfile.ZipFile(ARCHIVE) as z:
            for name in z.namelist():
                assert name.startswith('p2_r04_tensor_cut/')
                assert not Path(name).is_absolute() and '..' not in Path(name).parts
            z.extractall(folder)
        source = folder / 'p2_r04_tensor_cut'
        checksums = json.loads((source / 'SHA256.json').read_text())
        for name, digest in checksums.items():
            assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest, name
        subprocess.run([sys.executable, '-B', 'test_reuse_corridor.py'], cwd=source,
                       check=True, timeout=30, stdout=subprocess.PIPE, text=True)
        replay = json.loads((source / 'test_results.json').read_text())
        spec = importlib.util.spec_from_file_location('pro_r04_replay', source/'reuse_corridor.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        # Both cores occupy the same M and V slots. No unilateral move fits,
        # but swapping the two V nodes eliminates both cross-core tensors.
        graph = {
            'ops': [{'id': u, 'op': 'COMPUTE', 'pipe': p, 'cycles': 1}
                    for u, p in ((1, 'PIPE_M'), (2, 'PIPE_M'),
                                 (3, 'PIPE_V'), (4, 'PIPE_V'))],
            'tensors': [{'id': t, 'pos': 'UB', 'size': 1} for t in (101, 102, 103, 104)],
            'edges': [{'source': a, 'target': b} for a, b in
                      ((1, 101), (101, 3), (2, 102), (102, 4), (3, 103), (4, 104))]
                     + [{'source': 1, 'target': 4, 'data_size': 0},
                        {'source': 2, 'target': 3, 'data_size': 0}],
        }
        chains = [[1], [2], [3], [4]]
        owner = {0: 0, 1: 1, 2: 1, 3: 0}
        starts = {1: 0, 2: 0, 3: 10, 4: 10}
        lag = {(0, 2): 2, (0, 3): 2, (1, 2): 2, (1, 3): 2}
        mapping = {str(u): u-1 for u in starts}
        _, report = module.repair_gap_witness(graph, chains, owner, starts, lag, 2, mapping)
        assert report['saved_pre_step2_bytes'] == 0
        assert all(p['movable_groups'] == 0 for p in report['pairs'])
        swapped = {0: 0, 1: 1, 2: 0, 3: 1}
        _, swap_report = module.repair_gap_witness(graph, chains, swapped, starts, lag, 2, mapping)
        assert report['pre_step2_bytes_before'] == 6
        assert swap_report['pre_step2_bytes_before'] == 2
        counterexample = {
            'graph': graph, 'chains': chains, 'seed_placement': owner,
            'simultaneous_swap_placement': swapped, 'starts': starts,
            'static_lags': [[a, b, delay] for (a, b), delay in lag.items()],
            'seed_bytes': 6, 'one_way_repair_bytes': 6, 'swap_bytes': 2,
            'same_static_calendar_feasible': True,
            'scope': 'No improving one-way move does not prove optimality among all fixed-calendar assignments.',
        }
    receipt = {
        'archive_sha256': ARCHIVE_SHA, 'checksummed_source_members': len(checksums),
        'python': sys.version, 'wall_seconds': time.perf_counter()-started,
        'author_tests_replayed_locally': replay,
        'additional_scope_counterexample': counterexample,
        'calls': {'E0': 0, 'E1': 0, 'E2': 0},
        'not_official_case_performance': True,
    }
    (OUT/'local-replay.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'author_replay': replay['status'], 'counterexample': '6 -> 2 bytes by swap; one-way blocked',
                      'official_calls': 0, 'wall_seconds': receipt['wall_seconds']}))


if __name__ == '__main__':
    main()
