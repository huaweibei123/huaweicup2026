"""Derive a stopped-attempt receipt; retain every original interrupted byte."""
import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from src.q2.feedback.export_board import record_for
from src.q2.feedback.measure import artifact, read_json, save_json, utc
from src.benchmark_board.protocol import validate_feed

OUT = Path(__file__).resolve().parent
BATCH = OUT.parent / 'round5c'
ledger = read_json(BATCH / 'ledger.json')
spec = read_json(BATCH / 'spec.json')
assert ledger['state'] == 'stopped'
assert ledger['charged_calls'] == {'solver': 2, 'E0': 1, 'E1': 0, 'E2': 0}
original = BATCH / '071-tensor_packet/run.json'
run = copy.deepcopy(read_json(original))
assert run['status'] == 'running' and run['calls']['E0'] == 0
reservation = [r for r in ledger['reservations']
               if r['attempt_id'] == run['attempt_id'] and r['stage'] == 'solver']
assert len(reservation) == 1 and reservation[0]['state'] == 'ok'
assert reservation[0]['launched'] is True
run['status'] = 'failed'
run['finished_at'] = ledger['finished_at']
run['failure'] = {'stage': 'runner bookkeeping', 'reason': ledger['stop_reason'],
                  'exit_code': None, 'elapsed_seconds': ledger['batch_wall_seconds']}
run['stop_reason'] = 'Post-hoc classification of stopped infrastructure attempt; no E0 was launched.'
run['stages'] = {'solver': {'wall_seconds': reservation[0]['actual_wall_seconds'],
                          'status': 'ok', 'evidence': 'stopped ledger solver reservation'}}
plan = BATCH / '071-tensor_packet/case_071_multicore_res.json'
assert set(read_json(plan)) == {'node_to_subgraph', 'core_schedules'}
run['artifacts'] = {'plan': artifact(plan)}
run['identity']['plan_sha256'] = artifact(plan)['sha256']
run['receipt_derivation'] = {
    'created_at': utc(), 'original_run': artifact(original),
    'original_ledger': artifact(BATCH / 'ledger.json'),
    'script': artifact(Path(__file__)),
    'scope': 'Original run lacked persisted stages. Only recorded solver duration and charged calls are recovered. '
             'Finished_at is the actual stopped batch boundary, not an inferred solver exit timestamp. '
             'Exit code and precise solver timestamps remain unknown. No solver or E0 is executed.'}
derived_path = OUT / '071-derived-run.json'
save_json(derived_path, run)
records = [record_for(BATCH / '070-tensor_packet/run.json', spec, ledger, artifact(BATCH / 'ledger.json')),
           record_for(derived_path, spec, ledger, artifact(BATCH / 'ledger.json'))]
for record in records:
    record['notes'].append('The batch stopped on a Windows ledger replace error after 070 succeeded. '
                           '071 is preserved as a failed infrastructure attempt with zero E0. '
                           'The original stopped ledger counts both solver launches; all original files are retained.')
records[1]['parameters']['receipt_derivation'] = run['receipt_derivation']
feed = {'schema_version': 1, 'submission_version': 1, 'records': records}
validate_feed(feed, submission=True)
path = OUT / 'board-feed.json'
save_json(path, feed)
command = [sys.executable, '-X', 'utf8', '-B', 'src/benchmark_board/protocol.py',
           path.relative_to(ROOT).as_posix(), '--submission']
checked = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=60)
save_json(OUT / 'preflight.json', {'command': ['python', *command[1:]], 'returncode': checked.returncode,
                                'stdout': checked.stdout, 'stderr': checked.stderr,
                                'feed': artifact(path), 'checked_at': utc(), 'solver_calls': 0, 'E0_calls': 0})
print(checked.stdout)
if checked.returncode:
    raise SystemExit(checked.returncode)
