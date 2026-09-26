"""Recheck archived R05 E0 evidence and full500 DDR statistics without scoring."""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[5]
LATEST = '70f2e8bd8e850f1d49c924a86b654b29c24e087f'
PAIR_COMMIT = 'e6ae3699870c78b11c8c47b0fa9001249a428e1c'
PAIR = 'results/a/q2-nikolastarx/pro-r05-official-pair-20260925'
DDR = 'results/a/q2-nikolastarx/secondary-ddr-full500-20260925/report.json'
GRID = {(f'{i:03}', k) for i in range(1, 101) for k in range(1, 6)}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    inputs = []

    def frozen(commit, path):
        raw = subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)
        inputs.append({'commit': commit, 'path': path, 'bytes': len(raw), 'sha256': sha(raw)})
        return raw

    report = json.loads(frozen(LATEST, DDR))
    src = report['sources']
    summary_raw = frozen(LATEST, src['summary_path'])
    assert sha(summary_raw) == src['summary_sha256']
    summary = json.loads(summary_raw)
    assert summary['status'] == 'completed' and summary['accepted_cells'] == 500
    assert summary['solver_commit'] == report['current_solver'] == 'c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f'
    prior_raw = frozen(LATEST, src['summary_path'].replace('completed-summary.json', 'report.json'))
    assert sha(prior_raw) == src['prior_full_audit_sha256']
    assert json.loads(prior_raw)['summary_sha256'] == sha(summary_raw)
    old_raw = frozen(src['previous_feed_commit'], src['previous_feed_path'])
    assert sha(old_raw) == src['previous_feed_sha256']
    old_rows = json.loads(old_raw)['records']
    assert {r['solver_commit'] for r in old_rows} == set(report['previous_solver']) == {
        '2794ceba93acc1f7fc119154f61082511843d4b3'}
    old = {(r['case_id'], r['cores']): r for r in old_rows}
    current = {(r['case'], r['cores']): r for r in summary['rows']}
    published = {(r['case'], r['cores']): r for r in report['cells']}
    assert len(old_rows) == len(summary['rows']) == len(report['cells']) == 500
    assert set(old) == set(current) == set(published) == GRID
    rows = []
    for key in sorted(GRID):
        o, n = old[key], current[key]
        assert o['status'] == 'ok' and o['problem'] == 'P2' and n['status'] == 'accepted'
        assert o['evaluator']['route'] == 'E0'
        assert o['identity']['graph_sha256'] == n['graph_sha256']
        assert o['identity']['config_sha256'] == n['config_sha256']
        om, nm = o['metrics'], n['official']['movement']
        assert nm['added_copy_bytes'] == nm['partition_added_copy_bytes'] + nm['spill_added_copy_bytes']
        assert nm['added_copy_bytes'] == nm['scheduled_copy_bytes'] - nm['original_graph_copy_bytes']
        assert om['ddr_bytes'] - om['extra_ddr_bytes'] == nm['original_graph_copy_bytes']
        assert om['extra_ddr_bytes'] >= om['spill_bytes'] >= 0
        row = {'case': key[0], 'cores': key[1], 'old_makespan': om['makespan_cycles'],
               'new_makespan': n['official']['makespan'], 'old_extra': om['extra_ddr_bytes'],
               'new_extra': nm['added_copy_bytes'], 'old_spill': om['spill_bytes'],
               'new_spill': nm['spill_added_copy_bytes'],
               'old_partition': om['extra_ddr_bytes'] - om['spill_bytes'],
               'new_partition': nm['partition_added_copy_bytes']}
        assert row == published[key]
        rows.append(row)

    def relation(new, old):
        return 'improved' if new < old else 'same' if new == old else 'regressed'

    def aggregate(items, expected):
        names = ('old_extra', 'new_extra', 'old_spill', 'new_spill', 'old_partition', 'new_partition')
        totals = {name: sum(r[name] for r in items) for name in names}
        cross = dict(Counter(relation(r['new_makespan'], r['old_makespan']) + '_M__' +
                             relation(r['new_extra'], r['old_extra']) + '_DDR' for r in items))
        spill_count = sum(r['new_spill'] > 0 for r in items)
        zero_extra = sum(r['new_extra'] == 0 for r in items)
        change = 100 * Fraction(totals['new_extra'] - totals['old_extra'], totals['old_extra'])
        assert totals == expected['totals_bytes'] and cross == expected['comparison']
        assert spill_count == expected['new_nonzero_spill_cells']
        assert zero_extra == expected['new_zero_extra_cells']
        assert len(items) == expected['cells']
        assert abs(float(change) - expected['extra_change_pct']) < 1e-10
        for name, total in totals.items():
            assert total / len(items) == expected['mean_bytes'][name]
            assert total / len(items) / 2**20 == expected['mean_MiB'][name]
        return {'totals_bytes': totals, 'comparison': cross, 'nonzero_spill_cells': spill_count,
                'extra_change_pct': float(change), 'extra_change_pct_exact': str(change)}

    by_core = {str(k): aggregate([r for r in rows if r['cores'] == k], report['by_core'][str(k)])
               for k in range(1, 6)}
    all500 = aggregate(rows, report['all500'])
    totals = all500['totals_bytes']
    net = totals['new_extra'] - totals['old_extra']
    part = totals['new_partition'] - totals['old_partition']
    spill = totals['new_spill'] - totals['old_spill']
    assert part + spill == net
    deltas = {case: sum(r['new_extra'] - r['old_extra'] for r in rows if r['case'] == case)
              for case in sorted({r['case'] for r in rows})}
    top = sorted(deltas.items(), key=lambda x: (-x[1], x[0]))[:10]
    assert top == [(r['case'], r['extra_delta_bytes']) for r in report['largest_increase_cases']]
    shares = {'partition_pct_of_net': 100 * part / net, 'spill_pct_of_net': 100 * spill / net,
              'cases_014_072_pct_of_net': 100 * (deltas['014'] + deltas['072']) / net}

    verification = json.loads(frozen(PAIR_COMMIT, f'{PAIR}/verification.json'))
    zip_raw = frozen(PAIR_COMMIT, f'{PAIR}/result.zip')
    assert len(zip_raw) == verification['archive_bytes'] == 2835556
    assert sha(zip_raw) == verification['archive_sha256'] == 'c90065d9d90aae3be4144080483e3ac394a6ef150f92fc7d4450d81114ba2c66'
    headroom_path = Path(__file__).with_name('r05-headroom-check.json')
    headroom_raw = headroom_path.read_bytes()
    assert sha(headroom_raw) == '1b7e3f7ea1e8e485d52c9a8810339c4d2c38ee4f1e445011b099d244529f5d91'
    headroom = json.loads(headroom_raw)
    static = {r['name']: r for r in headroom['rows']}
    pair_rows = []
    with zipfile.ZipFile(io.BytesIO(zip_raw)) as z:
        infos = z.infolist()
        expected = {r['path']: r for r in verification['all_member_hashes']}
        assert len(infos) == len(expected) == 23 and len(set(z.namelist())) == 23
        assert set(z.namelist()) == set(expected) and sum(i.file_size for i in infos) < 64 * 2**20
        for item in infos:
            raw = z.read(item.filename)  # A complete read verifies the member CRC as well.
            assert len(raw) == expected[item.filename]['bytes']
            assert sha(raw) == expected[item.filename]['sha256']
        batch_raw = z.read('output/batch.json')
        assert batch_raw == frozen(PAIR_COMMIT, f'{PAIR}/batch.json')
        batch = json.loads(batch_raw)
        assert batch['status'] == 'completed' and batch['calls'] == {'E0_reserved': 2, 'E2': 0}
        assert batch['limits']['retries'] == 0 and batch['limits']['workers'] == 1
        manifest_raw = z.read('preparation/manifest.json')
        assert sha(manifest_raw) == batch['manifest_sha256']
        manifest = json.loads(manifest_raw)
        assert manifest['case'] == '003' and manifest['cores'] == 2
        assert manifest['files']['data/raw/a/official/data/case_003.json'] == current['003', 2]['graph_sha256']
        assert manifest['files']['data/raw/a/official/data/config.txt'] == current['003', 2]['config_sha256']
        for path, expected_sha in manifest['files'].items():
            if path.startswith('data/raw/a/official/code/'):
                assert sha(frozen(verification['capsule_source_commit'], path)) == expected_sha
        for row in batch['rows']:
            label = row['label']
            assert label in static and row['status'] == 'verified' and row['E0_reserved'] == 1
            process = row['process']
            assert process['status'] == 'ok' and process['exit_code'] == 0 and not process['surviving_pids']
            plan_raw = z.read(f'output/{label}/plan.json')
            result_raw = z.read(f'output/{label}/result.json')
            assert sha(plan_raw) == row['plan_sha256'] and sha(result_raw) == row['result_sha256']
            old_plan = next(i for i in headroom['inputs'] if i.get('uncompressed_sha256') == sha(plan_raw))
            assert old_plan['commit'] == headroom['source_commit']
            result = json.loads(result_raw)
            trace = json.loads(z.read(f'output/{label}/trace.json'))
            assert isinstance(trace['traceEvents'], list) and trace['traceEvents']
            assert result['scene'] == 'B' and result['num_cores'] == 2
            assert result['makespan'] == row['makespan'] == max(
                op['end'] for core in result['per_core_timeline'] for op in core['ops'])
            movement = result['data_movement_bytes']
            assert movement == row['data_movement_bytes']
            assert movement['scheduled_copy_bytes'] == static[label]['pre_step2_bytes_recomputed']
            assert movement['spill_added_copy_bytes'] == 0
            assert movement['added_copy_bytes'] == movement['partition_added_copy_bytes']
            assert movement['scheduled_copy_bytes'] - movement['original_graph_copy_bytes'] == movement['added_copy_bytes']
            lower = static[label]['fixed_fifo_path_bound']
            pair_rows.append({'label': label, 'makespan': result['makespan'], 'movement': movement,
                              'fixed_fifo_bound': lower, 'relaxation_residual': result['makespan'] - lower,
                              'plan_sha256': sha(plan_raw), 'result_sha256': sha(result_raw)})
    assert {r['label'] for r in pair_rows} == {'seed', 'recovered'} and len(pair_rows) == 2
    pair = {r['label']: r for r in pair_rows}
    sm, rm = pair['seed']['makespan'], pair['recovered']['makespan']
    sb, rb = (pair[k]['movement']['scheduled_copy_bytes'] for k in ('seed', 'recovered'))
    incumbent = current['003', 2]['official']['makespan']
    pair_stats = {'makespan_increase_vs_seed_pct': 100 * (rm - sm) / sm,
                  'copy_reduction_vs_seed_pct': 100 * (sb - rb) / sb,
                  'makespan_increase_vs_current_pct': 100 * (rm - incumbent) / incumbent,
                  'makespan_delta_cycles': rm - sm,
                  'fixed_bound_delta_cycles': pair['recovered']['fixed_fifo_bound'] - pair['seed']['fixed_fifo_bound'],
                  'residual_delta_cycles': pair['recovered']['relaxation_residual'] - pair['seed']['relaxation_residual']}
    assert pair_stats['makespan_delta_cycles'] == pair_stats['fixed_bound_delta_cycles'] + pair_stats['residual_delta_cycles']
    assert abs(pair_stats['makespan_increase_vs_seed_pct'] / 100 - verification['seed_to_raw_makespan_increase_fraction']) < 1e-12
    assert abs(pair_stats['copy_reduction_vs_seed_pct'] / 100 - verification['seed_to_raw_copy_reduction_fraction']) < 1e-12
    output = {'source_commit': LATEST, 'pair_source_commit': PAIR_COMMIT, 'inputs': inputs,
              'full500': {'by_core': by_core, 'all500': all500, 'net_increase_shares': shares,
                          'largest_increase_cases': top},
              'official_pair': {'zip_members_crc_and_hash_verified': 23, 'rows': pair_rows, 'comparison': pair_stats,
                                'archived_E0_calls': 2, 'current_comparator_makespan': incumbent},
              'new_calls_by_this_audit': {'solver': 0, 'constructor': 0, 'Step2': 0, 'Step3': 0, 'E0': 0, 'E1': 0, 'E2': 0},
              'limits': ['Full500 statistics rechecked against pinned feed and previously audited summary; no repeat raw-result audit of all 500 cells.',
                         'R05 ZIP CRCs/hashes, two results/Traces, recorded process exits and input/code manifest identities checked; no official replay or fresh cloud-status query.',
                         'E0 minus a compute/FIFO lower bound is a relaxation residual, not measured DDR stall time.',
                         'Two-plan R05 experiment is not a new full algorithm score; main c665 results remain unchanged.']}
    path = Path(__file__).with_name('official-pair-and-ddr-check.json')
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'output': path.relative_to(ROOT).as_posix(), 'sha256': sha(path.read_bytes()),
                      'pair': pair_stats, 'all500': all500, 'shares': shares}))


if __name__ == '__main__':
    main()
