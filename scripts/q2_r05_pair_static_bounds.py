"""Compute static necessary bounds for the two frozen R05 plans; no evaluator."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.fifo_bound import fixed_fifo_lower_bound


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads((ROOT / 'results/a/q2-nikolastarx/pro-r05-recovered-20260925/receipt.json').read_text())
    data = args.graph.read_bytes()
    if sha(data) != receipt['graph_sha256']:
        raise ValueError('Frozen graph identity differs')
    graph = json.loads(data)
    current_root = ROOT / 'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee/cases-001-010/003-k2'
    current_cell = json.loads((current_root / 'cell.json').read_bytes())
    current_raw = gzip.decompress((current_root / 'result.json.gz').read_bytes())
    current = json.loads(current_raw)
    if (current_cell['status'] != 'accepted'
            or current_cell['graph_sha256'] != receipt['graph_sha256']
            or current_cell['config_sha256'] != receipt['config_sha256']
            or sha(current_raw) != current_cell['official']['result_sha256']
            or current['scene'] != 'B' or current['num_cores'] != 2
            or current['makespan'] != current_cell['official']['makespan']):
        raise ValueError('Existing official comparator identity differs')
    incumbent = current['makespan']
    plans = {
        'seed': ('results/a/q2-nikolastarx/pro-r04-review-20260925/static-003-k2/seed-plan.json.gz',
                 receipt['seed_plan_json_sha256']),
        'recovered': ('results/a/q2-nikolastarx/pro-r05-recovered-20260925/recovered-raw-plan.json.gz',
                      receipt['recovered_plan_json_sha256']),
    }
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for name, (path, expected) in plans.items():
        data = gzip.decompress((ROOT / path).read_bytes())
        if sha(data) != expected:
            raise ValueError('Frozen plan identity differs: ' + name)
        start = time.perf_counter()
        bound = fixed_fifo_lower_bound(graph, json.loads(data))
        wall = time.perf_counter() - start
        raw = json.dumps(bound, sort_keys=True, separators=(',', ':')).encode()
        (args.output / (name + '-fifo-bound.json.gz')).write_bytes(gzip.compress(raw, mtime=0))
        lower = bound.get('makespan_lower_bound_cycles')
        records.append({
            'name': name, 'plan_json_sha256': expected,
            'supported': bound['supported'], 'fixed_fifo_lower_bound_cycles': lower,
            'assigned_pipe_lower_bound_cycles': bound.get('assigned_pipe_work_lower_bound_cycles'),
            'bound_wall_seconds': wall, 'bound_json_sha256': sha(raw),
            'existing_c665_official_M_cycles': incumbent,
            'rules_out_strict_gain_against_current': lower is not None and lower >= incumbent,
            'maximum_fractional_M_reduction': None if lower is None else max(0, 1-lower/incumbent),
        })
    report = {
        'scope': 'Static necessary bounds only; no constructor, preparation or evaluator call',
        'graph_sha256': receipt['graph_sha256'],
        'bound_source_sha256': sha((ROOT / 'src/q2_nikolastarx/fifo_bound.py').read_bytes()),
        'comparator_result_sha256': sha(current_raw),
        'comparator_plan_sha256': current_cell['plan_sha256'],
        'comparator_scheduled_copy_bytes': current['data_movement_bytes']['scheduled_copy_bytes'],
        'script_sha256': sha(Path(__file__).read_bytes()), 'records': records,
    }
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
