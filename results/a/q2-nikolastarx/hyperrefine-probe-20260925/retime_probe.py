"""One fixed-owner retiming of the already frozen 003/k2 regional cut."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.gap_retime import retime
from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
from src.q2_nikolastarx.fifo_bound import fixed_fifo_lower_bound
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    signal.alarm(30)  # This local mechanism probe targets POSIX only.
    here = Path(__file__).resolve().parent
    original = here / 'run-003-k2-v3'
    info = json.loads((original / 'result.json').read_bytes())
    source = gzip.decompress((original / 'refined-plan.json.gz').read_bytes())
    assert hashlib.sha256(source).hexdigest() == info['output_raw_sha256']
    graph_raw = (args.raw_root / 'case_003.json').read_bytes()
    config_path = args.raw_root / 'config.txt'
    assert hashlib.sha256(graph_raw).hexdigest() == info['graph_sha256']
    assert hashlib.sha256(config_path.read_bytes()).hexdigest() == info['config_sha256']
    config = {**read_evaluation_config(config_path), **read_scene_b_config(config_path)}
    args.output.mkdir(parents=True, exist_ok=False)
    record = {'status': 'started', 'calls': {'retime': 1, 'E0': 0, 'E1': 0, 'E2': 0},
              'budget': {'retime': 1, 'wall_seconds': 30, 'workers': 1, 'retries': 0},
              'graph_sha256': info['graph_sha256'], 'config_sha256': info['config_sha256'],
              'source_plan_sha256': info['output_raw_sha256'],
              'constructor_commit': '69b9d26ef972dfe1c8606a891ef8f89a6e896fec',
              'scope': 'Reuses the archived cut placement; not a cold full solver.'}
    save(args.output / 'receipt.json', record)
    graph, plan = json.loads(graph_raw), json.loads(source)
    before = fixed_fifo_lower_bound(graph, plan)
    at = time.perf_counter()
    result, meta = retime(graph, plan, config)
    record['retime_seconds'] = time.perf_counter() - at
    after = fixed_fifo_lower_bound(graph, result)
    record['original_copy_bytes'] = mandatory_copy_work(graph, result, config['bandwidth'])['transfer_bytes']
    assert record['original_copy_bytes'] == info['after_original_copy_bytes']
    raw = (json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n').encode()
    (args.output / 'plan.json.gz').write_bytes(gzip.compress(raw, mtime=0))
    record.update(status='completed', plan_sha256=hashlib.sha256(raw).hexdigest(),
                  before_fixed_fifo_bound=before['makespan_lower_bound_cycles'],
                  after_fixed_fifo_bound=after['makespan_lower_bound_cycles'],
                  static_finish_cycles=meta['static_finish_cycles'],
                  wall_seconds=time.perf_counter()-started)
    (args.output / 'witness.json.gz').write_bytes(gzip.compress(json.dumps(meta).encode(), mtime=0))
    save(args.output / 'receipt.json', record)
    print(json.dumps(record))


if __name__ == '__main__':
    main()
