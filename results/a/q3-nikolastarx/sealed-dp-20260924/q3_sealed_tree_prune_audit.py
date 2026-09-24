"""Compare three fixed unscored plans with saved successful E0 incumbents."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
from src.q3.construct import Index
from src.q3.pipe_bound import analyze
from q3_sealed_tree_prototype import _guard

root = Path.cwd()
output = Path(__file__).resolve().with_name('q3-sealed-tree-cases')
summary_path = output / 'summary.json'
summary = json.loads(summary_path.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
publication = subprocess.check_output(['git', 'rev-parse', 'f44a7548^{commit}'], text=True).strip()
batch_relative = 'results/a/q3-nikolastarx/release-20260924/run/batch.json'
batch_path = root / batch_relative
batch_bytes = subprocess.check_output(['git', 'show', publication + ':' + batch_relative])
assert hashlib.sha256(batch_bytes).hexdigest() == sha(batch_path)
batch = json.loads(batch_bytes)
verified_sources = {}
for stage in batch['stages']:
    for path, expected in stage['source_input_sha256'].items():
        if path.startswith('data/raw/a/official/code/') or path in {
            'data/raw/a/official/data/config.txt', 'src/q3/construct.py', 'src/q3/pipe_bound.py'}:
            assert sha(root / path) == expected, path
            verified_sources[path] = expected
assert sha(Path(__file__).resolve().with_name('q3_sealed_tree_prototype.py')) == summary['prototype_sha256']
records = []
for row in summary['records']:
    case = row['case']
    candidates = [r for r in batch['records'] if r['case_id'] == case and r['cores'] == 5
                  and r['variant'] == 'release-place-e0']
    assert len(candidates) == 1
    old = candidates[0]
    assert old['status'] == 'ok'
    assert old['identity']['graph_sha256'] == row['graph_sha256']
    assert old['identity']['config_sha256'] == summary['config_sha256']
    for artifact in old['artifacts'].values():
        assert sha(root / artifact['path']) == artifact['sha256']
    official = json.loads(gzip.decompress((root / old['artifacts']['result']['path']).read_bytes()))
    assert official['problem'] == 3
    assert official['cross_core_copy_delay_cycles'] == summary['delay'] == 500
    assert official['makespan'] == old['makespan_cycles']
    graph_path = root / f'data/raw/a/official/data/case_{case}.json'
    assert sha(graph_path) == row['graph_sha256']
    graph = json.loads(graph_path.read_text())
    _guard(Index(graph))
    plan_path = output / f'{case}-k5-plan.json'
    assert sha(plan_path) == row['plan_sha256']
    bound = analyze(graph, json.loads(plan_path.read_text()), summary['delay'])
    assert bound['with_cross_core_delay']['lower_bound_cycles'] == row['L_delay']
    gap = row['L_delay'] - official['makespan']
    assert gap > 0
    record = {'case': case, 'cores': 5, 'status': 'bound_pruned_research',
              'candidate_plan_sha256': row['plan_sha256'], 'graph_sha256': row['graph_sha256'],
              'config_sha256': summary['config_sha256'], 'H_template': row['H'],
              'candidate_L500': row['L_delay'], 'candidate_official_makespan': None,
              'incumbent_official_makespan': official['makespan'], 'strict_exclusion_gap_cycles': gap,
              'incumbent_solver_commit': batch['solver_commit'],
              'incumbent_result': old['artifacts']['result'], 'incumbent_plan': old['artifacts']['plan'],
              'bound_guards_verified': ['singleton original M/V', 'integer max(1, cycles)',
                  'original dependencies equal contracted edges', 'unique original tensor producer',
                  'frozen config delay500', 'acyclic original+pipe-FIFO graph'],
              'new_official_evaluations': 0,
              'conclusion': 'This exact fixed plan cannot improve incumbent Makespan. No E0 needed; not a rejection of the full mathematical family or a Pareto dominance claim.'}
    row.update({'decision': record['status'], 'incumbent_official_makespan': official['makespan'],
                'strict_exclusion_gap_cycles': gap})
    records.append(record)
audit = {'schema': 'q3-sealed-fixed-plan-pruning-audit-v1', 'new_official_evaluations': 0,
         'scope': 'Exactly three fixed k5 plans, 002/062/063. No other budgets, tree order or template variants tested.',
         'prototype_sha256': summary['prototype_sha256'],
         'script_sha256': sha(Path(__file__)),
         'incumbent_publication_commit': publication,
         'incumbent_batch': {'path': batch_relative, 'sha256': sha(batch_path)},
         'verified_frozen_source_sha256': verified_sources,
         'records': records, 'all_strictly_excluded': True}
audit_path = output / 'pruning-audit.json'
audit_path.write_text(json.dumps(audit, indent=2) + '\n')
summary['pruning_audit'] = {'path': 'pruning-audit.json', 'sha256': sha(audit_path)}
summary['interpretation'] = 'All three exact fixed k5 plans have guarded L500 > existing successful E0 incumbent. No new E0, no production integration. H is a template witness only.'
summary_path.write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({'publication_commit': publication, 'all_strictly_excluded': True,
                  'rows': [{k:r[k] for k in ('case','candidate_L500','incumbent_official_makespan',
                                            'strict_exclusion_gap_cycles','status')} for r in records]}, indent=2))
