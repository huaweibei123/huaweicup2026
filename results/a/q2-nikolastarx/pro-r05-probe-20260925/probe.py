"""One frozen-seed R05 reconstruction, without any evaluator calls."""
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
SOURCE = '1ff472bc60db45069c588280bef52826ed1e0385'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    args.output.mkdir(parents=True, exist_ok=False)
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', SOURCE,
                                    'src/q2_nikolastarx'], cwd=ROOT, text=True).splitlines()
    source_hashes = {}
    for name in paths:
        if name.endswith('.py'):
            raw = (ROOT / name).read_bytes()
            expected = subprocess.check_output(['git', 'show', SOURCE + ':' + name], cwd=ROOT)
            if raw != expected:
                raise ValueError('Source drift: ' + name)
            source_hashes[name] = sha(raw)
    source = json.loads((ROOT / 'docs/a/source-manifest.json').read_bytes())
    files = {r['path']: r for r in source['files']}
    graph_raw, config_raw = args.graph.read_bytes(), args.config.read_bytes()
    assert sha(graph_raw) == files['data/case_003.json']['sha256']
    assert sha(config_raw) == files['data/config.txt']['sha256']
    for name in files:
        if name.startswith('code/'):
            assert sha((ROOT / 'data/raw/a/official' / name).read_bytes()) == files[name]['sha256']
    seed_dir = ROOT / 'results/a/q2-nikolastarx/pro-r04-review-20260925/static-003-k2'
    seed_raw = gzip.decompress((seed_dir / 'seed-plan.json.gz').read_bytes())
    witness_raw = gzip.decompress((seed_dir / 'seed-witness.json.gz').read_bytes())
    from src.q2_nikolastarx import direct  # Install the frozen official module path.
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    from src.q2_nikolastarx.ready_exchange_candidate import build_from_seed
    config = {**read_evaluation_config(args.config), **read_scene_b_config(args.config)}
    (args.output / 'constructor-started.json').write_text(json.dumps({
        'source_commit': SOURCE, 'constructor': 1, 'E0': 0, 'E1': 0, 'E2': 0,
        'graph_sha256': sha(graph_raw), 'config_sha256': sha(config_raw)
    }, indent=2) + '\n')
    at = time.perf_counter()
    plan, detail = build_from_seed(json.loads(graph_raw), json.loads(seed_raw),
                                  json.loads(witness_raw), 2, config)
    construct_seconds = time.perf_counter() - at
    plan_raw = (json.dumps(plan, sort_keys=True, allow_nan=False) + '\n').encode()
    plan_gz = gzip.compress(plan_raw, mtime=0)
    assert gzip.decompress(plan_gz) == plan_raw
    (args.output / 'plan.json.gz').write_bytes(plan_gz)
    result = {'source_commit': SOURCE, 'source_sha256': source_hashes,
              'graph_sha256': sha(graph_raw), 'config_sha256': sha(config_raw),
              'seed_plan_sha256': sha(seed_raw), 'seed_witness_sha256': sha(witness_raw),
              'plan_sha256': sha(plan_raw), 'plan_gzip_sha256': sha(plan_gz),
              'construct_seconds': construct_seconds,
              'read_import_construct_verify_write_seconds': time.perf_counter()-started,
              'calls': {'constructor': 1, 'E0': 0, 'E1': 0, 'E2': 0}, 'detail': detail,
              'scope': 'one preselected real-graph mechanism test, no official performance result'}
    (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in detail.items() if not isinstance(v, (list, dict))}))
    print(json.dumps({'construct_seconds': construct_seconds, 'calls': result['calls']}))


if __name__ == '__main__':
    main()
