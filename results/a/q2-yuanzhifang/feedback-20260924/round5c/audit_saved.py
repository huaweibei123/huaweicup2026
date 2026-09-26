"""Read-only audit of the interrupted 5C batch; does not run solver or E0."""
import gzip
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[5]
batch = Path(__file__).resolve().parent

def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)

def check_artifact(item):
    raw = (root / item['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == item['sha256']
    return raw

ledger = read(batch / 'ledger.json')
spec = read(batch / 'spec.json')
spec_path = root / 'results/a/q2-yuanzhifang/feedback-20260924/round5c-parallel-spec.json'
assert hashlib.sha256(spec_path.read_bytes()).hexdigest() == ledger['spec_sha256']
assert spec == read(spec_path)
assert ledger['state'] == 'stopped'
assert ledger['charged_calls'] == {'solver': 2, 'E0': 1, 'E1': 0, 'E2': 0}
assert len(ledger['attempts']) == 2 and len(ledger['reservations']) == 3
assert [read(root / name)['case_id'] for name in ledger['attempts']] == ['070', '071']
assert [(r['stage'],r['state']) for r in ledger['reservations']] == [('solver','ok'),('E0','ok'),('solver','ok')]
run70 = read(batch / '070-tensor_packet/run.json')
run71 = read(batch / '071-tensor_packet/run.json')
assert run70['status'] == 'ok' and run70['calls'] == {'solver': 1, 'E0': 1, 'E1': 0, 'E2': 0}
assert run71['status'] == 'running' and run71['calls'] == {'solver': 1, 'E0': 0, 'E1': 0, 'E2': 0}
assert not (batch / '071-tensor_packet/result.json').exists()
for item in run70['artifacts'].values():
    check_artifact(item)
decoded = {}
for name, item in run70['compression'].items():
    packed = check_artifact(item['artifact'])
    raw = gzip.decompress(packed)
    assert len(raw) == item['raw_bytes'] and len(packed) == item['stored_bytes']
    assert hashlib.sha256(raw).hexdigest() == item['raw_sha256']
    assert int.from_bytes(packed[4:8], 'little') == 0
    decoded[name] = json.loads(raw)
assert decoded['result.json']['makespan'] == 36800 == run70['metrics']['makespan_cycles']
assert decoded['trace.json']['otherData']['makespan'] == 36800
base = read(root / 'results/benchmark-board/official-singlecore-20260924/070/run.json')
assert base['graph_sha256'] == run70['identity']['graph_sha256']
assert base['config_sha256'] == run70['identity']['config_sha256']
assert base['official_code_hash'] == run70['identity']['official_sha256']
assert (batch / '071-tensor_packet/case_071_multicore_res.json').exists()
assert (batch / '071-tensor_packet/solver.stderr.txt').read_bytes() == b''
print(json.dumps({'state': ledger['state'], 'T0':ledger['started_at'], 'T1':ledger['finished_at'],
                  'charged_calls':ledger['charged_calls'], 'successfully_evaluated_cases':['070'],
                  'solver_only_incomplete_case':'071', 'unrun_cases':len(spec['cases'])-2,
                  '070_makespan_cycles':36800, '070_speedup':base['makespan_cycles']/36800}, ensure_ascii=False))
