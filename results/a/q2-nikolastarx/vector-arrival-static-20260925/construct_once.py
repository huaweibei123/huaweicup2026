"""One sequential static CLI call per authorized 016/k2,k4,k5 cell; no E0.

Refuses an existing case directory. The owner controls any later fresh run.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt = {'scope': 'three one-shot static constructions; no official evaluation',
               'started_at': datetime.now(timezone.utc).isoformat(),
               'platform': platform.platform(), 'calls': {'E0': 0, 'E1': 0, 'E2': 0},
               'source_inputs': {}, 'runs': []}
    inputs = ['src/q2_nikolastarx/vector_arrival.py', 'src/q2_nikolastarx/vector_lanes.py',
              'src/q2_nikolastarx/direct.py', 'tests/q2_nikolastarx/test_vector_arrival.py',
              'data/raw/a/official/data/case_016.json', 'data/raw/a/official/data/config.txt']
    for name in inputs:
        receipt['source_inputs'][name] = sha(ROOT/name)
    assert receipt['source_inputs']['src/q2_nikolastarx/vector_lanes.py'] == '1dbccbc915c78f491d74faa57aceff3038e0d4667d1bd65ba7c30243aec5c3ec'
    for k in (2, 4, 5):
        folder = OUT/f'016-k{k}'
        folder.mkdir(exist_ok=False)
        relative = folder.relative_to(ROOT)
        cmd = ['.venv/bin/python', '-B', '-m', 'src.q2_nikolastarx.vector_arrival',
               'data/raw/a/official/data/case_016.json', '--cores', str(k),
               '--output', str(relative/'plan.json'), '--evidence', str(relative/'online'), '--wall', '30']
        start = time.perf_counter()
        run = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=60)
        wall = time.perf_counter()-start
        record = {'command': cmd, 'returncode': run.returncode, 'process_wall_seconds': wall,
                  'stdout': run.stdout, 'stderr': run.stderr, 'cores': k}
        (folder/'cli.json').write_text(json.dumps(record, indent=2)+'\n')
        if run.returncode:
            receipt['runs'].append(record)
            (OUT/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
            raise SystemExit('CLI failed; no retry')
        ledger = json.loads((folder/'online/solver.json').read_text())
        assert ledger['status'] == 'ok' and ledger['calls'] == {'E0': 0, 'E1': 0, 'E2': 0}
        duplicate = folder/'online/vector_arrival/plan.json'
        assert duplicate.read_bytes() == (folder/'plan.json').read_bytes()
        # Retain one plan, with verified byte alias; preserve ledger bytes exactly.
        (folder/'online/solver.json').rename(folder/'solver.json')
        duplicate.unlink()
        duplicate.parent.rmdir()
        (folder/'online').rmdir()
        detail = ledger['attempts'][0]['detail']
        record.update(plan_sha256=sha(folder/'plan.json'), solver_sha256=sha(folder/'solver.json'),
            duplicated_plan_alias='online/vector_arrival/plan.json -> plan.json (byte-verified before removing duplicate)',
            ledger_relocation='online/solver.json -> solver.json (rename, unchanged bytes)',
            internal_wall_seconds=ledger['internal_wall_seconds'],
            fixed_plan_bound=detail['fixed_plan_bound']['makespan_lower_bound_cycles'],
            listed_proxy_makespan=detail['listed_proxy_makespan_cycles'])
        receipt['runs'].append(record)
        print(k, record['plan_sha256'], 'LB', record['fixed_plan_bound'],
              'proxy', record['listed_proxy_makespan'], 'process_s', wall)
        (OUT/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
    for name, value in receipt['source_inputs'].items():
        assert sha(ROOT/name) == value
    receipt['synthetic_test_evidence'] = {
        'command': '.venv/bin/python -B -m unittest tests.q2_nikolastarx.test_vector_arrival -v',
        'observed_tests': 9, 'observed_result': 'OK',
        'scope': 'already run before this script, not rerun by this receipt'}
    (OUT/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')


if __name__ == '__main__':
    main()
