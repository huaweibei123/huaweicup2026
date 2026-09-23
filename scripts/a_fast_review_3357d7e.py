"""Frozen-head independent checks; invoke with the candidate worktree as cwd."""
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import json
import platform
import random
import subprocess
import sys

ROOT = Path.cwd()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
OUT = args.output
assert not OUT.exists(), 'Use a new output path to preserve prior evidence'
OUT.parent.mkdir(parents=True, exist_ok=True)
HEAD = '3357d7ef9c1ad443dd0799f6ecb5b813df6753b3'
RUN_HEAD = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
subprocess.run(['git', 'merge-base', '--is-ancestor', HEAD, 'HEAD'], check=True)
EXPECTED_SOURCES = {
 'src/eval_exact/_official.py': '65e7ec150e533cfc794901d7de13bc94ef391f3402b9d90e601797d8f4ecd77f',
 'src/eval_exact/problem1.py': 'cd1cb856d9b72513a906b3f0b000032d04ea1c0f657d7421597628e42ae86f6f',
}
for rel, expected in EXPECTED_SOURCES.items():
    assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == expected, rel
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
# E0 is imported directly from the frozen directory, not through candidate code.
import multicore_cut_evaluate_problem_1 as oracle
import evaluation_validation as validation
from src.eval_exact.problem1 import evaluate_scene_a as candidate

CONFIG = ROOT / 'data/raw/a/official/data/config.txt'
cfg = validation.read_evaluation_config(str(CONFIG))
scene = oracle.read_scene_a_config(str(CONFIG))
PARAMS = dict(bandwidth=cfg['bandwidth'], capacity=cfg['capacity'],
              cross_core_wait=scene['task_cross_core_wait_cycles'],
              same_core_wait=scene['task_same_core_wait_cycles'])


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def typed_equal(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def outcome(fun, graph, plan):
    try:
        return {'status': 'ok', 'value': fun(graph, plan, **PARAMS)}
    except Exception as e:
        return {'status': 'exception', 'type': type(e).__name__, 'message': str(e)}


records = []
pool = ROOT / 'results/a/proxy/r20260923-e2-dev64-gzip'
graph = json.loads((ROOT / 'data/raw/a/official/data/case_001.json').read_text())
rows = list(csv.DictReader((pool / 'candidates.csv').open()))
assert len(rows) == 64
for i, row in enumerate(rows):
    plan = json.loads((pool / row['plan_path']).read_text())
    saved = json.loads(gzip.decompress((pool / row['e0_output_path']).read_bytes()))
    e0, e1 = outcome(oracle.evaluate_scene_a, graph, plan), outcome(candidate, graph, plan)
    record = dict(case=row['candidate_id'], family='saved_development_pool',
                  graph_sha256=sha(graph), plan_sha256=sha(plan),
                  e0_status=e0['status'], saved_full_equal=typed_equal(json.loads(json.dumps(e0.get('value'))), saved),
                  e1_full_equal=typed_equal(e0, e1), makespan=e0.get('value', {}).get('makespan'))
    records.append(record)
    assert record['saved_full_equal'] and record['e1_full_equal'], record
    if i % 16 == 15:
        print(json.dumps({'pool_recomputed': i + 1}), flush=True)

# Saved E0 JSON is compared after a standard JSON round trip, matching the
# official public serialization. E0 versus E1 objects above remain type-strict.

# New bipartite micrographs, independent of the contributor's test fixtures.
# Unsorted IDs, fan-out, disconnected input tensors, zero bytes/cycles, ID-space
# adjacency, empty cores and invalid map/quotient variants exercise the rewrite.
for seed in range(60):
    rng = random.Random(900000 + seed)
    n = rng.randrange(2, 10)
    ids = rng.sample(range(10, 90), n)
    graph = {'ops': [], 'tensors': [], 'edges': []}
    for j, op_id in enumerate(ids):
        graph['ops'].append({'id': op_id, 'op': 'RELU', 'pipe': rng.choice(['PIPE_M', 'PIPE_V']), 'cycles': rng.choice([0, 1, 3, 17, 100])})
        tid = 100 + j
        graph['tensors'].append({'id': tid, 'pos': 'UB', 'size': rng.choice([0, 1, 16, 60, 128])})
        graph['edges'].append({'source': tid, 'target': op_id})
        if j and rng.random() < .8:
            graph['edges'].append({'source': ids[rng.randrange(j)], 'target': tid})
        if j + 1 < n and rng.random() < .5:
            graph['edges'].append({'source': tid, 'target': ids[rng.randrange(j + 1, n)]})
    # Unused valid tensor should not appear in any task's local boundary.
    graph['tensors'].append({'id': 9999, 'pos': 'UB', 'size': 0})
    cores = 1 + seed % 5
    schedule = [[] for _ in range(cores)]
    mapping = {}
    for j, op_id in enumerate(ids):
        mapping[str(op_id)] = j
        schedule[rng.randrange(cores)].append(j)
    if seed % 3 == 0:
        schedule.append([])
    plan = {'node_to_subgraph': mapping, 'core_schedules': schedule}
    variants = [('valid_or_official_rejected', plan)]
    bad = json.loads(json.dumps(plan))
    del bad['node_to_subgraph'][str(ids[0])]
    variants.append(('missing_mapping', bad))
    if n >= 3:
        bad = json.loads(json.dumps(plan))
        bad['node_to_subgraph'][str(ids[-1])] = 0
        bad['core_schedules'] = [[x for x in q if x != n - 1] for q in schedule]
        variants.append(('noncontiguous_merge', bad))
    for name, p in variants:
        a, b = outcome(oracle.evaluate_scene_a, graph, p), outcome(candidate, graph, p)
        record = dict(family='generated_micro', seed=900000 + seed, variant=name,
                      graph_sha256=sha(graph), plan_sha256=sha(p), e0_status=a['status'],
                      e1_full_equal=typed_equal(a, b), makespan=a.get('value', {}).get('makespan'),
                      error=a.get('message'))
        records.append(record)
        if not record['e1_full_equal']:
            OUT.with_name('first_difference.json').write_text(json.dumps({'record':record,'graph':graph,'plan':p,'e0':a,'e1':b},ensure_ascii=False,indent=2))
            raise AssertionError(record)

report = dict(candidate_commit=HEAD, run_head=RUN_HEAD, candidate_source_sha256=EXPECTED_SOURCES, python=sys.version, platform=platform.platform(),
              script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              config_sha256=hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
              params=PARAMS, pool_recomputed=64, micro_comparisons=len(records)-64,
              full_mismatches=0, records=records,
              limits=['Finite development checks, not formal equivalence or held-out release acceptance.',
                      'Synthetic accepted/rejected inputs follow frozen implementation behavior; not proof of complete statement domain.',
                      'No timing claim from this script.'])
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['pool_recomputed','micro_comparisons','full_mismatches']}))
