"""One frozen three-cell mechanism batch, first failure stops; no automatic continuation."""
from pathlib import Path
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx import evaluate_feedback as common
from src.q2_nikolastarx import evaluate_matrix as matrix


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--runner-commit', required=True)
    p.add_argument('--run', action='store_true')
    args = p.parse_args()
    home = Path(__file__).resolve().parent
    manifest_path = home / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for path in (manifest_path, Path(__file__).resolve()):
        rel = path.relative_to(ROOT).as_posix()
        if path.read_bytes() != common.git_bytes(args.runner_commit, rel):
            raise ValueError('Unfrozen driver input: ' + rel)
    cells = []
    for name in manifest['protocols']:
        path = ROOT / name
        protocol = matrix.read(path)
        actual = matrix.validate_protocol(protocol)
        if len(actual) != 1:
            raise ValueError('Only single-cell protocols allowed')
        matrix.frozen_inputs(protocol, path, manifest['source_commit'], args.runner_commit)
        if (ROOT / protocol['output_prefix']).exists():
            raise ValueError('Output already exists; never resume or repeat automatically')
        cells.extend(actual)
    if [list(v) for v in cells] != manifest['cells']:
        raise ValueError('Cell allocation mismatch')
    if not args.run:
        print(json.dumps({'preflight': 'ok', 'cells': cells, 'dispatched': 0}))
        return
    output = home / 'run'
    output.mkdir(exist_ok=False)
    started = time.perf_counter()
    deadline = started + manifest['aggregate_wall_seconds'] - 5.0
    summary = {'source_commit': manifest['source_commit'], 'runner_commit': args.runner_commit,
               'started_at': common.utc(), 'status': 'running', 'cells': []}
    matrix.save(output / 'batch.json', summary)
    for name, (case, cores) in zip(manifest['protocols'], cells):
        key = f'{case}-k{cores}'
        argv = [sys.executable, '-B', '-m', 'src.q2_nikolastarx.evaluate_matrix', 'run',
                '--protocol', name, '--source-commit', manifest['source_commit'],
                '--runner-commit', args.runner_commit]
        receipt = common.monitored(argv, output / (key + '-driver'), deadline,
                                   manifest['rss_observation_stop_bytes'])
        record = {'cell': key, 'driver': receipt}
        run_path = output / key / key / 'run.json'
        if run_path.exists():
            record['attempt'] = matrix.read(run_path)
        row = record.get('attempt', {})
        record['accepted'] = (receipt.get('status') == 'ok' and not receipt.get('surviving_pids')
            and row.get('status') == 'ok'
            and row.get('calls') == {'solver': 1, 'E0': 1, 'E1': 0, 'E2': 0}
            and not matrix.stop_dispatch_reason(row))
        summary['cells'].append(record)
        matrix.save(output / 'batch.json', summary)
        print(json.dumps({'cell': key, 'accepted': record['accepted'],
                          'calls': row.get('calls'), 'status': row.get('status')}), flush=True)
        if not record['accepted']:
            summary['status'] = 'stopped_first_failure'
            break
    else:
        summary['status'] = 'completed'
    summary['finished_at'] = common.utc()
    summary['aggregate_wall_seconds'] = time.perf_counter() - started
    matrix.save(output / 'batch.json', summary)
    if summary['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
