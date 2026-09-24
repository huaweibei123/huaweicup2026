"""Join existing E0 artifacts to necessary lower bounds; no solver imports."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEST = Path(__file__).resolve().parent
BOUNDS = 'results/a/q2-nikolastarx/goal-20260924/global-bounds.json'
BATCHES = {
    'direct-pilot-20260924': '81219bf923524fb60616e39b5ad2dced67aec3e2',
    'envelope-pilot-20260924': '1e92b165b8609e94191b1be8d1eab7c4f8aa5929',
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    inputs = {}

    def read(path, expected=None):
        raw = (ROOT / path).read_bytes()
        actual = digest(raw)
        if expected is not None and actual != expected:
            raise ValueError('Artifact hash mismatch: ' + path)
        inputs[path] = actual
        return json.loads(gzip.decompress(raw) if path.endswith('.gz') else raw)

    bounds = read(BOUNDS)
    bmap = {r['graph_file'][5:8]: r for r in bounds['records']}
    manifest = read('docs/a/source-manifest.json')
    official_hashes = {}
    for entry in manifest['files']:
        if entry['path'].startswith('code/'):
            raw = (ROOT / 'data/raw/a/official' / entry['path']).read_bytes()
            actual = digest(raw)
            if actual != entry['sha256'] or len(raw) != entry['bytes']:
                raise ValueError('Official manifest mismatch: ' + entry['path'])
            official_hashes[entry['path']] = actual
    official_hash = digest(''.join(f'{k}\t{v}\n' for k, v in sorted(official_hashes.items())).encode())
    config_hash = digest((ROOT / 'data/raw/a/official/data/config.txt').read_bytes())
    for name, expected in bounds['official_source_sha256'].items():
        raw = (ROOT / 'data/raw/a/official/code' / name).read_bytes()
        if digest(raw) != expected:
            raise ValueError('Official source mismatch: ' + name)
    rows = []
    for batch, commit in BATCHES.items():
        feed = read(f'results/a/q2-nikolastarx/{batch}/run/board-feed.json')
        for record in feed['records']:
            if record['status'] != 'ok' or record['evaluator']['route'] != 'E0':
                raise ValueError('Only completed official results qualify')
            if (record['identity']['official_sha256'] != official_hash
                    or record['identity']['config_sha256'] != config_hash):
                raise ValueError('Official code/config identity mismatch')
            evidence = {kind: read(item['path'], item['sha256'])
                        for kind, item in record['artifacts'].items()}
            case, cores = record['case_id'], record['cores']
            bound = bmap[case]
            if not bound['supported'] or not bound['precedence_supported']:
                raise ValueError('Unsupported bound domain')
            graph_path = f'data/raw/a/official/data/case_{case}.json'
            read(graph_path, record['identity']['graph_sha256'])
            if bound['graph_sha256'] != record['identity']['graph_sha256']:
                raise ValueError('Bound/score graph identity mismatch')
            plan = record['artifacts']['plan']
            if plan['sha256'] != record['identity']['plan_sha256']:
                raise ValueError('Score/plan identity mismatch')
            lower = next(b['makespan_lower_bound_cycles']
                         for b in bound['by_core_count'] if b['cores'] == cores)
            upper = evidence['result']['makespan']
            if upper != record['metrics']['makespan_cycles'] or upper < lower:
                raise ValueError('Score mismatch or lower-bound contradiction')
            rows.append({'batch': batch, 'data_commit': commit,
                         'attempt_id': record['attempt_id'], 'case': case, 'cores': cores,
                         'solver_commit': record['solver_commit'],
                         'graph_sha256': record['identity']['graph_sha256'],
                         'lower_bound_cycles': lower, 'observed_makespan_cycles': upper,
                         'exact_gap_cycles': upper - lower,
                         'approximation_factor_upper_bound': upper / lower,
                         'possible_fractional_improvement_upper_bound': (upper - lower) / upper,
                         'certified_optimum_equal': upper == lower})
    output = {'scope': 'Existing 30 official results; zero new solver/E0/E1/E2 calls.',
              'proof_document': 'docs/a/q2-nikolastarx/OPTIMALITY_BOUNDS.md',
              'interpretation': 'L <= OPT <= U. U/L bounds approximation factor; (U-L)/U bounds remaining fractional Makespan gain. Neither proves an attainable gap or optimal solver wall/DDR.',
              'rows': rows, 'inputs_sha256': inputs,
              'script_sha256': digest(Path(__file__).read_bytes())}
    with (DEST / 'audit.json').open('x') as stream:
        json.dump(output, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'rows': len(rows), 'equal': sum(r['certified_optimum_equal'] for r in rows),
                      'calls': {'solver': 0, 'E0': 0, 'E1': 0, 'E2': 0}}))


if __name__ == '__main__':
    main()
