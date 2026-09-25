"""Read-only verification of a stopped Linux batch; never reports full-grid means."""
import hashlib
import json
from pathlib import Path
import statistics
import zipfile

HERE = Path(__file__).resolve().parent
ZIP_SHA = '03f8516b31cb229b7f2ea2bb4c812f0719b0ed0e889e5e9fbcfe4a00789f2c05'
MANIFEST_SHA = 'eadb56e50e211d8830bcc03cad2af52eadac6cad07536a5f46d9bd933a159943'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def metric(r):
    return {k: r[k] for k in ('makespan', 'cross_task_traffic', 'data_movement_bytes')}


def main():
    raw = (HERE / 'results.zip').read_bytes()
    require(sha(raw) == ZIP_SHA, 'ZIP differs')
    with zipfile.ZipFile(HERE / 'results.zip') as z:
        load = lambda n: json.loads(z.read(n))
        manifest = load('setup/capsule-manifest.json')
        require(sha(z.read('setup/capsule-manifest.json')) == MANIFEST_SHA, 'manifest differs')
        summary = load('output/summary.json')
        require(summary['solver_commit'] == '295ec9cf4351b77f5c6fffe8fbb23e8bc8d2f323'
                and summary['runner_source_commit'] == '4b08468fd14a939ce259b0560e3ec27816f675a5', 'source differs')
        require(summary['status'] == 'stopped_first_failure' and not summary['in_flight']
                and summary['accepted_cells'] == 66 and len(summary['rows']) == 67,
                'terminal coverage differs')
        seen, good, bad, walls = set(), [], [], []
        total_attempts = total_native = independent = 0
        expected_sources = {Path(p).name: h for p, h in manifest['solver_sources'].items()}
        for row in summary['rows']:
            key = (row['case'], row['cores'])
            require(key not in seen, 'duplicate cell'); seen.add(key)
            folder = f'output/{key[0]}-k{key[1]}/'
            ledger = load(folder + 'online/solver.json')
            require(sha(z.read(folder + 'online/solver.json')) == row['solver_ledger_sha256'], 'ledger differs')
            require(ledger['solver_source_sha256'] == expected_sources, 'solver source differs')
            require(ledger['solver_checkout_commit'] == summary['capsule_runtime_head'], 'runtime head differs')
            require(ledger['graph_sha256'] == manifest['files'][f'data/raw/a/official/data/case_{key[0]}.json']
                    and ledger['config_sha256'] == manifest['files']['data/raw/a/official/data/config.txt'], 'input differs')
            require(ledger['source']['native_binary_sha256'] == summary['native_binary_sha256'], 'native source differs')
            calls = ledger['calls']; total_attempts += calls['E2_api_attempted']; total_native += calls['native_returns']
            independent += row['calls']['E0_independent_started']
            require(calls['E2_api_attempted'] <= 4, 'call cap exceeded')
            if row['status'] != 'accepted':
                bad.append({'case': key[0], 'cores': key[1], 'request_in_flight': ledger['request_in_flight'],
                            'possible_E0_fallback_calls': ledger['possible_E0_fallback_calls'],
                            'confirmed_E0_fallback': calls['E0_fallback'], 'calls': calls})
                continue
            require(ledger['status'] == 'ok' and not ledger['request_in_flight']
                    and not ledger['possible_E0_fallback_calls'] and calls['E0_fallback'] == 0,
                    'accepted cell has uncertainty')
            plan_raw = z.read(folder + 'plan.json'); plan = json.loads(plan_raw)
            require(sha(plan_raw) == ledger['plan_sha256'] == row['plan_sha256'], 'plan hash differs')
            key_hash = sha(json.dumps(plan, sort_keys=True, allow_nan=False).encode())
            selected = [a['record'] for a in ledger['attempts'] if a['plan_sha256'] == key_hash]
            truth_raw = z.read(folder + 'result.json'); truth = json.loads(truth_raw)
            require(sha(truth_raw) == row['result_sha256'], 'E0 hash differs')
            require(truth['scene'] == 'B' and truth['num_cores'] == key[1], 'E0 scenario differs')
            require(len(selected) == 1 and selected[0]['route'] == 'native'
                    and metric(selected[0]) == metric(truth) == row['official'], 'E2/E0 differs')
            for stage in ('solver-process', 'e0-process'):
                process = load(folder + stage + '/process.json')
                require(process['status'] == 'ok' and process['exit_code'] == 0
                        and not process['surviving_pids'], 'process not terminal')
            good.append({'case': key[0], 'cores': key[1], 'M': truth['makespan'],
                         'solver_wall_seconds': row['solver_wall_seconds']})
            walls.append(row['solver_wall_seconds'])
        require((total_attempts, total_native, independent) == (207, 206, 66), 'call sum differs')
        require(len(bad) == 1 and bad[0]['case'] == '014' and bad[0]['cores'] == 2
                and bad[0]['request_in_flight'] and bad[0]['possible_E0_fallback_calls'] == 1,
                'failed cell uncertainty differs')
        outer = load('setup/outer-terminal.json')
        require(outer['exit_code'] == 1 and not outer['surviving_pids'], 'outer process not terminal')
        result = {'status': 'partial_originals_verified', 'full500': False,
                  'accepted': len(good), 'started': len(seen), 'not_started': 500 - len(seen),
                  'calls': {'E2_attempted': total_attempts, 'native_returns': total_native,
                            'confirmed_E0_fallback': 0, 'possible_E0_fallback': 1, 'independent_E0': independent},
                  'failed': bad, 'solver_wall_completed_seconds': {
                      'mean': statistics.fmean(walls), 'max': max(walls)},
                  'outer_wall_seconds': outer['wall_seconds'], 'accepted_rows': good,
                  'full_grid_means_computed': False, 'result_zip_sha256': ZIP_SHA}
        (HERE / 'audit-report.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({k: v for k, v in result.items() if k != 'accepted_rows'}))


if __name__ == '__main__':
    main()
