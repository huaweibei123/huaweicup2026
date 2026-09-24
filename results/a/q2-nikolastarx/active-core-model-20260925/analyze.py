"""Read-only workload/capacity diagnostic; no full plan or evaluator."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.active_core_wave import choose_from_index
from src.q2_nikolastarx.dag_direct import DAGIndex


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases', nargs='+', required=True)
    p.add_argument('--cores', type=int, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    cfg = ROOT/'data/raw/a/official/data/config.txt'
    config = {**read_evaluation_config(cfg), **read_scene_b_config(cfg)}
    rows = []
    started = time.perf_counter()
    for case in args.cases:
        raw = (ROOT/f'data/raw/a/official/data/case_{case}.json').read_bytes()
        selected, detail = choose_from_index(DAGIndex(json.loads(raw)), args.cores, config)
        rows.append({'case': case, 'input_sha256': hashlib.sha256(raw).hexdigest(),
                     'selected': selected, 'detail': detail})
    report = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'config_sha256': hashlib.sha256(cfg.read_bytes()).hexdigest(),
              'source_hashes': {s: hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in (
                  'src/q2_nikolastarx/active_core_wave.py', 'src/q2_nikolastarx/shared_input_wave.py',
                  'src/q2_nikolastarx/component_envelope.py', 'src/q2_nikolastarx/dag_direct.py',
                  'src/q2_nikolastarx/direct.py')},
              'cores': args.cores, 'rows': rows, 'analysis_wall_seconds': time.perf_counter()-started,
              'scope': 'Workload/lifetime extraction and relaxation only; no full plan, solver CLI, or E0/E1/E2.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps({'choices': {r['case']: r['selected'] for r in rows},
                      'analysis_wall_seconds': report['analysis_wall_seconds']}))


if __name__ == '__main__':
    main()
