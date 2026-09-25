"""Structural R7 probe; no Task compilation or evaluator invocation."""
import copy
import json
import zipfile
from pathlib import Path

from src.q1.shared_band_proto import construct

ROOT = Path(__file__).resolve().parents[2]
BASE = (ROOT / 'results/a/p1-branch-refine-full500-20260925'
        / '20260925T1525Z-s6607-branch-full500/cells/044-k5/originals/plan.json')
CAP = {'L1': 524288, 'UB': 131072}


def inputs():
    with zipfile.ZipFile(ROOT / 'data/raw/a/official-cases.zip') as archive:
        graph = json.loads(archive.read('data/case_044.json'))
    return graph, json.loads(BASE.read_text())


def test_unique_candidate_has_full_coverage_dag_and_boundary_account():
    graph, baseline = inputs()
    candidate, info = construct(graph, baseline, CAP, 60)
    assert candidate is not baseline
    assert set(candidate) == {'node_to_subgraph', 'core_schedules'}
    assert len(candidate['node_to_subgraph']) == 1364
    assert len(candidate['core_schedules']) == 5
    assert info['task_count'] == 10
    assert info['band_rank_range'] == [48, 75]
    assert info['band_slices'] == [[48, 65], [65, 75]]
    assert info['copy_accounting']['scheduled_copy_bytes_no_spill'] == 1712000
    assert info['copy_accounting']['partition_added_copy_bytes'] == 736544
    assert max(x['L1'] for x in info['task_footprints']) == 505984
    assert info['official_calls'] == info['task_compile_calls'] == 0


def test_insufficient_capacity_returns_supplied_baseline_without_mutation():
    graph, baseline = inputs()
    saved = copy.deepcopy(baseline)
    returned, info = construct(graph, baseline, {'L1': 100000, 'UB': 131072}, 60)
    assert returned is baseline and baseline == saved
    assert info['selected'] == 'baseline'
    assert 'band slices' in info['reason']


def test_broken_shared_identity_fails_closed():
    graph, baseline = inputs()
    # Remove one use of a common read-only tensor. The graph is still a DAG,
    # but the input-identity/alignment condition is no longer satisfied.
    copy_out = next(o['id'] for o in graph['ops'] if o['op'] == 'COPY_IN')
    tid = next(e['target'] for e in graph['edges'] if e['source'] == copy_out)
    consumer = next(e['target'] for e in graph['edges'] if e['source'] == tid)
    graph['edges'] = [e for e in graph['edges']
                      if not (e['source'] == tid and e['target'] == consumer)]
    returned, info = construct(graph, baseline, CAP, 60)
    assert returned is baseline
    assert info['selected'] == 'baseline'
    assert info['official_calls'] == 0

if __name__ == '__main__':
    for test in (test_unique_candidate_has_full_coverage_dag_and_boundary_account,
                 test_insufficient_capacity_returns_supplied_baseline_without_mutation,
                 test_broken_shared_identity_fails_closed):
        test()
        print(f'{test.__name__}: PASS')
