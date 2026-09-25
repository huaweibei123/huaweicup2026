"""One archived 003/k2 seed placement refinement; no official evaluator.

Run once with --raw-root and --seed. The child has a 30-second hard wall limit.
The elapsed time includes read, import, refinement, independent bytes and write,
but excludes original seed construction and is not a cold full solver time.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
EXPECTED_GRAPH = '2c80acfd37edcf811ce76b7e7b1f7194c706bd4d4aa6449e6a19e9eac1028ced'
EXPECTED_CONFIG = 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'
EXPECTED_SEED_GZIP = '7bda0575834302e17ebd324443333dd0b2741292608e55e1fa9f6035fce05ef9'
EXPECTED_SEED_RAW = 'e6c87dd7e78e2b5bfe4e2c55b48583d5cae7c0fdec9198c1ab384c42f30a9c53'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def child(args):
    started = time.perf_counter()
    # direct.py exposes the frozen official code directory to these readers.
    from src.q2_nikolastarx.direct import derive_multicore_plan
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
    from src.q2_nikolastarx.gap_hyperrefine import refine

    graph_path = args.raw_root / 'case_003.json'
    config_path = args.raw_root / 'config.txt'
    graph_raw, config_raw, seed_gzip = (p.read_bytes() for p in
                                        (graph_path, config_path, args.seed))
    seed_raw = gzip.decompress(seed_gzip)
    assert (digest(graph_raw), digest(config_raw), digest(seed_gzip), digest(seed_raw)) == (
        EXPECTED_GRAPH, EXPECTED_CONFIG, EXPECTED_SEED_GZIP, EXPECTED_SEED_RAW)
    graph, seed = json.loads(graph_raw), json.loads(seed_raw)
    config = {**read_evaluation_config(config_path), **read_scene_b_config(config_path)}
    derive_multicore_plan(graph, seed)
    before = mandatory_copy_work(graph, seed, config['bandwidth'])['transfer_bytes']
    assert before == 6351422
    at = time.perf_counter()
    plan, detail = refine(graph, seed, config, region_width=16)
    refine_seconds = time.perf_counter() - at
    derive_multicore_plan(graph, plan)
    after = mandatory_copy_work(graph, plan, config['bandwidth'])['transfer_bytes']
    assert (before, after) == (detail['before_original_copy_bytes'],
                               detail['after_original_copy_bytes'])
    assert after <= before
    plan_raw = encoded(plan)
    packed = gzip.compress(plan_raw, mtime=0)
    (args.output / 'refined-plan.json.gz').write_bytes(packed)
    result = {'case': '003', 'cores': 2, 'source_code_commit': args.source_commit,
              'seed_source_commit': '56962a8946c5ae6976d231fe4b471730b9a171de',
              'graph_sha256': digest(graph_raw), 'config_sha256': digest(config_raw),
              'seed_gzip_sha256': digest(seed_gzip), 'seed_raw_sha256': digest(seed_raw),
              'output_gzip_sha256': digest(packed), 'output_raw_sha256': digest(plan_raw),
              'before_original_copy_bytes': before, 'after_original_copy_bytes': after,
              'refine_seconds': refine_seconds,
              'child_read_import_refine_verify_write_seconds': time.perf_counter() - started,
              'detail': detail, 'calls': {'E0': 0, 'E1': 0, 'E2': 0},
              'scope': 'Archived seed placement only; no seed construction or official scoring.'}
    (args.output / 'result.json').write_bytes(encoded(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-root', required=True, type=Path)
    parser.add_argument('--seed', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.child:
        child(args)
        return
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                   text=True).strip() == args.source_commit
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    receipt = {'status': 'started', 'source_code_commit': args.source_commit,
               'started_at': datetime.now(timezone.utc).isoformat(),
               'budget': {'case': '003', 'cores': 2, 'region_width': 16,
                          'refine_calls': 1, 'workers': 1, 'child_wall_seconds': 30,
                          'retries': 0, 'E0': 0, 'E1': 0, 'E2': 0}}
    (args.output / 'process.json').write_bytes(encoded(receipt))
    command = [sys.executable, '-B', str(Path(__file__).resolve()), '--child',
               '--raw-root', str(args.raw_root), '--seed', str(args.seed),
               '--output', str(args.output), '--source-commit', args.source_commit]
    try:
        run = subprocess.run(command, cwd=ROOT, timeout=30, capture_output=True, text=True)
        receipt.update(status='completed' if run.returncode == 0 else 'failed',
                       returncode=run.returncode)
        (args.output / 'stdout.txt').write_text(run.stdout)
        (args.output / 'stderr.txt').write_text(run.stderr)
    except subprocess.TimeoutExpired as error:
        receipt.update(status='timeout', returncode=None)
        (args.output / 'stdout.txt').write_bytes(error.stdout or b'')
        (args.output / 'stderr.txt').write_bytes(error.stderr or b'')
    receipt.update(finished_at=datetime.now(timezone.utc).isoformat(),
                   harness_seconds=time.perf_counter() - started)
    (args.output / 'process.json').write_bytes(encoded(receipt))
    print(json.dumps({'status': receipt['status'], 'source_code_commit': args.source_commit,
                      'harness_seconds': receipt['harness_seconds']}))
    if receipt['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
