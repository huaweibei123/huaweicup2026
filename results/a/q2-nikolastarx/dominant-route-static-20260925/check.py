"""One diagnostic DAG construction, no official evaluation or online search."""
from pathlib import Path
import argparse
from collections import Counter
import gzip
import hashlib
import json
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.fifo_bound import fixed_fifo_lower_bound
from src.q2_nikolastarx.component_envelope import _private_peak
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config

DATA = '571536962b3f6ad9468584a0e5ae04398e684543'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True)
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    def deadline(*_):
        raise TimeoutError('20 second static diagnostic limit')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(20)
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    graph_path = ROOT / f'data/raw/a/official/data/case_{args.case}.json'
    graph_bytes = graph_path.read_bytes()
    graph = json.loads(graph_bytes)
    config_path = ROOT / 'data/raw/a/official/data/config.txt'
    config = {**read_evaluation_config(config_path), **read_scene_b_config(config_path)}
    feed = json.loads(gzip.decompress((ROOT / 'results/a/q2-nikolastarx/semantic500-review-20260925/semantic-feed-500.json.gz').read_bytes()))
    row = next(r for r in feed['records'] if r['case_id'] == args.case and r['cores'] == args.cores)
    assert hashlib.sha256(graph_bytes).hexdigest() == row['identity']['graph_sha256']
    ref = row['artifacts']['plan']
    old_bytes = subprocess.check_output(['git', 'show', DATA + ':' + ref['path']], cwd=ROOT)
    assert hashlib.sha256(old_bytes).hexdigest() == ref['sha256']
    index = DAGIndex(graph)
    plan, detail = index.build(args.cores, bandwidth=config['bandwidth'],
                               cross_core_delay=config['cross_core_copy_delay_cycles'])
    by_sg = {v: int(k) for k, v in plan['node_to_subgraph'].items()}
    seqs = [[by_sg[s] for s in seq] for seq in plan['core_schedules']]
    peaks = [_private_peak(index, seq, {t for u in seq for t in index.inputs[u] + index.outputs[u]}) for seq in seqs]
    component_work = [Counter() for _ in index.components]
    for j, nodes in enumerate(index.components):
        for u in nodes:
            component_work[j][index.ops[u]['pipe']] += index.duration(u)
    report = dict(case=args.case, cores=args.cores, graph_sha256=row['identity']['graph_sha256'],
                  source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  prior_data_commit=DATA, prior_metrics=row['metrics'],
                  prior_fixed_fifo_bound=fixed_fifo_lower_bound(graph,json.loads(old_bytes)),
                  candidate_fixed_fifo_bound=fixed_fifo_lower_bound(graph,plan),
                  component_work=[dict(x) for x in component_work],
                  original_compute_touch_peak_by_core=peaks, diagnostic=detail,
                  construction_calls=1, E0=0, E1=0, E2=0,
                  note='No measured candidate score. Raw touch omits expanded COPY/spill/credit edges; no zero-spill certificate.')
    (args.output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    report['diagnostic_wall_seconds'] = time.perf_counter()-started
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'case':args.case, 'old_M':row['metrics']['makespan_cycles'],
                      'candidate_proxy':detail['predicted_finish_cycles'], 'peaks':peaks,
                      'wall':report['diagnostic_wall_seconds'], 'new_E0':0}))
    signal.alarm(0)

if __name__ == '__main__':
    main()
