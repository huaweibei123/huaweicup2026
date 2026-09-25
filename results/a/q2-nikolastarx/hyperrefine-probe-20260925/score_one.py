"""One independently scored 003/k2 refinement, with no candidate search."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.evaluate_feedback import monitored


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-root', type=Path, required=True)
    p.add_argument('--seed-e0-directory', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--retimed', action='store_true')
    args = p.parse_args()
    here = Path(__file__).resolve().parent
    probe = here / ('retime-003-k2-v1' if args.retimed else 'run-003-k2-v3')
    meta = json.loads((probe / ('receipt.json' if args.retimed else 'result.json')).read_bytes())
    packed = (probe / ('plan.json.gz' if args.retimed else 'refined-plan.json.gz')).read_bytes()
    raw = gzip.decompress(packed)
    if args.retimed:
        assert sha(raw) == meta['plan_sha256']
    else:
        assert sha(packed) == meta['output_gzip_sha256']
        assert sha(raw) == meta['output_raw_sha256']
    graph, config = args.raw_root / 'case_003.json', args.raw_root / 'config.txt'
    assert sha(graph.read_bytes()) == meta['graph_sha256']
    assert sha(config.read_bytes()) == meta['config_sha256']
    official = json.loads((ROOT / 'docs/a/source-manifest.json').read_bytes())
    for row in official['files']:
        if row['path'].startswith('code/'):
            data = (ROOT / 'data/raw/a/official' / row['path']).read_bytes()
            assert sha(data) == row['sha256'] and len(data) == row['bytes']
    old_raw = (args.seed_e0_directory / 'result.json').read_bytes()
    old = json.loads(old_raw)
    seed = json.loads(gzip.decompress((here.parent / 'pro-r04-review-20260925' /
                                     'static-003-k2/seed-plan.json.gz').read_bytes()))
    assert json.loads((args.seed_e0_directory / 'plan.json').read_bytes()) == seed
    assert old['scene'] == 'B' and old['num_cores'] == 2 and old['makespan'] == 248166
    args.output.mkdir(parents=True, exist_ok=False)
    plan = args.output / 'plan.json'
    plan.write_bytes(raw)
    evidence = {'status': 'starting', 'case': '003', 'cores': 2,
                'refiner_commit': meta.get('source_code_commit', meta.get('constructor_commit')),
                'retimed': args.retimed,
                'runner_commit': subprocess.check_output(
                    ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'graph_sha256': meta['graph_sha256'],
                'config_sha256': meta['config_sha256'],
                'plan_sha256': sha(raw), 'old_result_sha256': sha(old_raw),
                'budget': {'workers': 1, 'E0': 1, 'E1': 0, 'E2': 0,
                           'wall_seconds': 60, 'rss_bytes': 4 << 30, 'retries': 0},
                'calls': {'E0': 0, 'E1': 0, 'E2': 0},
                'scope': 'One archived-seed mechanism probe; not a cold solver or full batch.'}
    save(args.output / 'comparison.json', evidence)
    command = [sys.executable, '-B', str(ROOT / 'data/raw/a/official/code/'
               'multicore_cut_evaluate_problem_2.py'), str(graph), str(plan),
               '--config', str(config), '--output', str(args.output / 'result.json'),
               '--trace-output', str(args.output / 'trace.json'),
               '--log-output', str(args.output / 'official.log')]
    evidence['calls']['E0'] = 1
    save(args.output / 'comparison.json', evidence)
    process = monitored(command, args.output / 'process', time.perf_counter() + 60, 4 << 30)
    evidence['status'] = process['status']
    evidence['evaluation_wall_seconds'] = process['wall_seconds']
    if process['status'] == 'ok':
        result_raw = (args.output / 'result.json').read_bytes()
        result = json.loads(result_raw)
        assert result['scene'] == 'B' and result['num_cores'] == 2
        evidence.update(result_sha256=sha(result_raw),
                        old_makespan=old['makespan'], new_makespan=result['makespan'],
                        old_movement=old['data_movement_bytes'],
                        new_movement=result['data_movement_bytes'])
    save(args.output / 'comparison.json', evidence)
    print(json.dumps(evidence))
    if process['status'] != 'ok':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
