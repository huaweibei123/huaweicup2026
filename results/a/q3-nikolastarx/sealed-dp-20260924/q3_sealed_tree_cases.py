"""Three fixed single-tree inputs; one plan each, static checks only (zero E0)."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from src.q3.construct import Index
from src.q3.pipe_bound import analyze
from evaluation_validation import read_required_settings
from q3_sealed_tree_prototype import construct

root = Path.cwd()
output = Path(__file__).resolve().with_name('q3-sealed-tree-cases')
output.mkdir(exist_ok=True)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
head_start = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
config = root / 'data/raw/a/official/data/config.txt'
delay = read_required_settings(config, 'multicore_scene_b', ('cross_core_copy_delay_cycles',))['cross_core_copy_delay_cycles']
records = []
for case in ('002', '062', '063'):
    source = root / f'data/raw/a/official/data/case_{case}.json'
    started = time.perf_counter()
    source_bytes = source.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    graph = json.loads(source_bytes)
    index = Index(graph)
    p, meta = construct(index, 5, delay)
    plan_path = output / f'{case}-k5-plan.json'
    plan_path.write_text(json.dumps(p, separators=(',', ':')) + '\n')
    read_to_plan = time.perf_counter() - started
    bound_started = time.perf_counter()
    bound = analyze(graph, p, delay)
    bound_time = time.perf_counter() - bound_started
    assert bound['with_cross_core_delay']['lower_bound_cycles'] == meta['abstract_fifo_cycles']
    assert bound['zero_delay']['lower_bound_cycles'] == meta['zero_delay_fifo_cycles']
    assert sha(source) == source_sha256
    (output / f'{case}-k5-meta.json').write_text(json.dumps(meta, indent=2) + '\n')
    (output / f'{case}-k5-pipe-bound.json').write_text(json.dumps(bound, indent=2) + '\n')
    row = {'case': case, 'cores': 5, 'graph_sha256': source_sha256, 'plan_sha256': sha(plan_path),
           'original_compute_ops': len(index.ops), 'used_cores': meta['used_cores'],
           'H': meta['abstract_witness_upper_cycles'], 'L_delay': meta['abstract_fifo_cycles'],
           'L_zero': meta['zero_delay_fifo_cycles'], 'local_D': meta['local_dfs_cycles'],
           'H_by_budget': meta['root_witness_by_budget'], 'template_counts': meta['emitted_template_counts'],
           'cross_compute_edges': meta['cross_core_compute_edges'],
           'read_index_construct_static_validation_write_seconds': read_to_plan,
           'independent_bound_check_seconds': bound_time,
           'official_evaluations': 0, 'official_makespan': None}
    records.append(row)
    print(json.dumps(row), flush=True)
summary = {'schema': 'q3-sealed-tree-three-input-static-v1', 'official_evaluations': 0,
           'HEAD_start': head_start,
           'HEAD_end': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
           'python': sys.version, 'platform': platform.platform(),
           'prototype_sha256': sha(Path(__file__).resolve().with_name('q3_sealed_tree_prototype.py')),
           'script_sha256': sha(Path(__file__)), 'config_sha256': sha(config),
           'delay': delay,
           'dependency_sha256': {p: sha(root / p) for p in ('src/q3/construct.py', 'src/q3/pipe_bound.py',
                     'data/raw/a/official/code/stub_multicore_cut_and_schedule.py',
                     'data/raw/a/official/code/multicore_cut_evaluate_problem_1.py')},
           'records': records,
           'interpretation': 'H is only a template witness, L is guarded static compute lower bound. No official performance or full-memory feasibility claim.'}
(output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
