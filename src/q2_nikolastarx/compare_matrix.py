"""Compare immutable local P2 feeds and final evidence; never runs an evaluator.

python -m src.q2_nikolastarx.compare_matrix --run-dir RESULTS/run --output NEW.json
Optional --markdown NEW.md. Existing output files are refused; no --force mode.
--self-test runs only small synthetic offline checks, in a temporary directory.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT = ROOT / 'results/a/q2-nikolastarx/target-audit-20260924'
IDENTITY_KEYS = ('graph_sha256', 'config_sha256', 'official_sha256')
MOVEMENT = {'ddr_bytes': 'scheduled_copy_bytes', 'extra_ddr_bytes': 'added_copy_bytes',
            'spill_bytes': 'spill_added_copy_bytes'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    raw = path.read_bytes()
    if path.suffix == '.gz':
        raw = gzip.decompress(raw)
    return json.loads(raw)


def finite(value, positive=False):
    return type(value) in (int, float) and math.isfinite(value) and (value > 0 if positive else True)


def load_audit(folder, root=ROOT):
    capture = read(folder / 'capture-manifest.json')
    payloads = {}
    for item in capture['responses']:
        stored = (folder / item.get('stored_name', item['name'])).read_bytes()
        if item.get('stored_sha256') and digest(stored) != item['stored_sha256']:
            raise ValueError('Stored audit response hash mismatch: ' + item['name'])
        raw = gzip.decompress(stored) if item.get('stored_name', '').endswith('.gz') else stored
        if digest(raw) != item['sha256']:
            raise ValueError('Raw audit response hash mismatch: ' + item['name'])
        payloads[item['name']] = json.loads(raw)
    history = [r for name, data in payloads.items() if name.startswith('p2-records-') for r in data['records']]
    latest = {}
    for record in history:
        key = record['attempt_id']
        if key not in latest or record['revision'] > latest[key]['revision']:
            latest[key] = record
    fang = {(r['case_id'], r['cores']): r for r in latest.values()
            if r['run_id'] in {'20260924T131640Z-s59ee', '20260924T1325Z-s59ee'}}
    best = {(c['case_id'], c['cores']): c['best'] for c in payloads['p2-cells.json']['cells']}
    bound_file = folder / 'BOUND_INPUT.json'
    checked_bounds = read(folder / 'BOUND_COMPARISON.json')
    if digest(bound_file.read_bytes()) != checked_bounds['bound_input_sha256']:
        raise ValueError('Bound input hash mismatch')
    bounds = {(r['graph_file'][5:8], k['cores']): (r, k) for r in read(bound_file)['records']
              for k in r['by_core_count']}
    baselines = {}
    for baseline in read(folder / 'baseline-verification.json'):
        path = root / baseline['path']
        if not path.exists():
            path = folder / 'baseline-blobs' / baseline['sha256']
        stored = path.read_bytes()
        if digest(stored) != baseline['sha256']:
            raise ValueError('Official singlecore denominator hash mismatch')
        result = json.loads(gzip.decompress(stored))
        if result['scene'] != 'A' or result['makespan'] != baseline['makespan_cycles']:
            raise ValueError('Official singlecore denominator content mismatch')
        case = baseline['case_id']
        if case in baselines and baselines[case]['makespan_cycles'] != baseline['makespan_cycles']:
            raise ValueError('Conflicting singlecore denominators')
        baselines[case] = baseline
    expected = {(f'{c:03d}', k) for c in range(1, 101) for k in range(1, 6)}
    if set(fang) != expected or set(best) != expected or set(bounds) != expected:
        raise ValueError('Frozen audit does not cover the expected 500 cells')
    refs = {}
    for coord in sorted(expected):
        b = baselines[coord[0]]
        g, k = bounds[coord]
        if not g['supported'] or not finite(k['makespan_lower_bound_cycles'], positive=True):
            raise ValueError('Unsupported bound')
        for ref in (fang[coord], best[coord]):
            if not ref['eligible'] or not ref['baseline_verified'] or ref['status'] != 'ok':
                raise ValueError('Unadmitted frozen comparison reference')
            if any(ref['identity'][name] != b[name] for name in IDENTITY_KEYS):
                raise ValueError('Frozen baseline/reference identity mismatch')
        if g['graph_sha256'] != b['graph_sha256']:
            raise ValueError('Frozen bound graph mismatch')
        refs[coord] = {'fang': fang[coord], 'history': best[coord], 'baseline': b,
                       'lower_bound_cycles': k['makespan_lower_bound_cycles']}
    return refs, {'captured_at': capture['captured_at'], 'bound_input_sha256': digest(bound_file.read_bytes()),
                  'comparison_scope': 'Frozen historical winners and Fang fixed contiguous implementation, not a live leaderboard.'}


def artifact(record, name, run_dir, root):
    entry = record.get('artifacts', {}).get(name)
    if not isinstance(entry, dict):
        raise ValueError('Missing ' + name + ' artifact')
    relative = Path(entry['path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Artifact path must be repository-relative')
    path = (root / relative).resolve()
    if not path.is_relative_to(run_dir.resolve()):
        raise ValueError('Artifact outside the specified run: ' + name)
    raw = path.read_bytes()
    if digest(raw) != entry['sha256']:
        raise ValueError('Artifact stored-byte hash mismatch: ' + name)
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw), raw


def compare_record(record, ref, run_dir, root=ROOT, context=None):
    """Retain a failed or unverified record; only validated successes get quality comparisons."""
    metrics = record.get('metrics', {})
    row = {key: record.get(key) for key in ('attempt_id', 'revision', 'run_id', 'algorithm_id', 'variant',
                                           'solver_commit', 'case_id', 'cores', 'status', 'runtime_id')}
    row.update(comparison_status='not_comparable', evidence_errors=[], quality_vs_fang='not_comparable',
               quality_vs_history='not_comparable', reported_metrics=metrics,
               failure=record.get('provenance', {}).get('measurement', {}).get('failure'),
               timing_causal_comparison=False,
               timing_note='Outer wall values are observations from different, potentially shared-machine runs. No causal speedup is asserted.')
    try:
        if record.get('problem') != 'P2' or ref is None:
            raise ValueError('Missing same P2/case/core frozen comparison')
        if any(record.get('identity', {}).get(k) != ref['baseline'][k] for k in IDENTITY_KEYS):
            raise ValueError('Graph/config/official identity mismatch')
        source = record.get('provenance', {}).get('solver', {}).get('source') or {}
        if source.get('commit') != record.get('solver_commit'):
            raise ValueError('Feed solver identity mismatch')
        if context:
            if context['source_commit'] != record['solver_commit']:
                raise ValueError('Run context solver identity mismatch')
            runner_source = record.get('provenance', {}).get('runner', {}).get('source') or {}
            if runner_source.get('commit') != context['runner_commit']:
                raise ValueError('Run context runner identity mismatch')
        receipt, _ = artifact(record, 'run', run_dir, root)
        if record.get('artifacts', {}).get('manifest'):
            artifact(record, 'manifest', run_dir, root)
        if receipt.get('case', receipt.get('case_id')) != record['case_id']:
            raise ValueError('Run receipt case mismatch')
        if receipt.get('cores', record['cores']) != record['cores'] or receipt.get('status') != record['status']:
            raise ValueError('Run receipt core/status mismatch')
        for metric, stage in [('solver_wall_seconds', 'solver'), ('evaluation_wall_seconds', 'final')]:
            wall = receipt.get(stage, {}).get('wall_seconds')
            if wall != metrics.get(metric) or (wall is not None and (not finite(wall) or wall < 0)):
                raise ValueError('Outer process wall mismatch: ' + metric)
            row[metric] = wall
        row['receipt_error'] = receipt.get('error', receipt.get('reason'))
        row['calls'] = receipt.get('calls', record.get('provenance', {}).get('measurement', {}).get('calls'))
        row['comparators'] = {name: {'record_id': ref[name]['id'], 'metrics': ref[name]['metrics'],
                                    'runtime_id': ref[name].get('runtime_id'),
                                    'solver_commit': ref[name]['solver_commit'],
                                    'solver_scope': ref[name].get('provenance', {}).get('measurement', {}).get('solver_scope')}
                              for name in ('fang', 'history')}
        row['lower_bound_cycles'] = ref['lower_bound_cycles']
        if record['status'] != 'ok':
            row['comparison_status'] = 'recorded_non_success'
            return row
        if record.get('evaluator', {}).get('route') != 'E0':
            raise ValueError('Success is not reported from official E0')
        if receipt.get('solver', {}).get('status') != 'ok' or receipt.get('final', {}).get('status') != 'ok':
            raise ValueError('Success lacks successful solver/final process receipts')
        plan, plan_raw = artifact(record, 'plan', run_dir, root)
        if (not isinstance(plan, dict) or set(plan) != {'node_to_subgraph', 'core_schedules'}
                or not isinstance(plan['node_to_subgraph'], dict)
                or not isinstance(plan['core_schedules'], list)
                or any(not isinstance(core, list) for core in plan['core_schedules'])
                or len(plan['core_schedules']) != record['cores']):
            raise ValueError('Final plan schema/core count mismatch')
        if digest(plan_raw) != record['identity'].get('plan_sha256'):
            raise ValueError('Plan identity mismatch')
        result, _ = artifact(record, 'result', run_dir, root)
        score = result.get('makespan')
        if (result.get('scene') != 'B' or result.get('num_cores') != record['cores']
                or result.get('problem') == 3 or result.get('cache_mode') == 'read_only'
                or not finite(score, positive=True)):
            raise ValueError('Final result is not a valid P2 result for this core count')
        if type(score) is not type(metrics.get('makespan_cycles')) or score != metrics['makespan_cycles']:
            raise ValueError('Final Makespan value/type differs from feed')
        if receipt.get('makespan_cycles', score) != score:
            raise ValueError('Final Makespan differs from run receipt')
        if result.get('input_graph', f"case_{record['case_id']}.json") != f"case_{record['case_id']}.json":
            raise ValueError('Final result input graph mismatch')
        movement = result.get('data_movement_bytes', {})
        for metric, official_name in MOVEMENT.items():
            if not finite(movement.get(official_name)) or movement[official_name] != metrics.get(metric):
                raise ValueError('Final movement differs from feed or is missing: ' + metric)
        online = receipt.get('online') or {}
        mode = receipt.get('solver_mode')
        if mode == 'direct':
            if online.get('calls', {}).get('E0') != 0:
                raise ValueError('Direct run contains unknown/nonzero online E0')
        elif mode == 'portfolio':
            if receipt.get('full_online_result_equal') is not True:
                raise ValueError('Portfolio lacks complete online/final result equality')
        elif mode is None and 'online_E0_calls' in receipt:
            if receipt.get('full_result_bytes_equal') is not True:
                raise ValueError('Legacy portfolio lacks complete online/final result equality')
        else:
            raise ValueError('Unknown run format; cannot establish scoring/equality scope')
        row.update(comparison_status='artifacts_verified', metrics=dict(metrics),
                   baseline_cycles=ref['baseline']['makespan_cycles'],
                   baseline_speedup=ref['baseline']['makespan_cycles'] / score,
                   lower_bound_gap_cycles=score-ref['lower_bound_cycles'],
                   relative_suboptimality_upper_bound=score/ref['lower_bound_cycles']-1)
        row['bound_conflict'] = score < ref['lower_bound_cycles']
        for name in ('fang', 'history'):
            reference = ref[name]['metrics']
            previous = reference['makespan_cycles']
            row['quality_vs_' + name] = 'win' if score < previous else 'tie' if score == previous else 'loss'
            row['vs_' + name] = {'new_over_reference_makespan': score/previous,
                                 'reference_over_new_makespan': previous/score,
                                 'makespan_delta_cycles': score-previous,
                                 'extra_ddr_delta_bytes': metrics['extra_ddr_bytes']-reference['extra_ddr_bytes'] if reference.get('extra_ddr_bytes') is not None else None,
                                 'spill_delta_bytes': metrics['spill_bytes']-reference['spill_bytes'] if reference.get('spill_bytes') is not None else None,
                                 'new_solver_wall_seconds': row['solver_wall_seconds'],
                                 'reference_solver_wall_seconds': reference.get('solver_wall_seconds')}
    except (KeyError, TypeError, ValueError, OSError) as error:
        row.update(comparison_status='not_comparable', quality_vs_fang='not_comparable', quality_vs_history='not_comparable')
        for key in ('metrics', 'baseline_cycles', 'baseline_speedup', 'lower_bound_gap_cycles',
                    'relative_suboptimality_upper_bound', 'bound_conflict', 'vs_fang', 'vs_history'):
            row.pop(key, None)
        row['evidence_errors'].append(str(error).replace(str(root), '${REPO_ROOT}'))
    return row


def missing_journal_rows(journal, rows):
    present = {(r['case_id'], r['cores']) for r in rows}
    out = []
    for key, cell in journal.get('cells', {}).items():
        if (cell['case'], cell['cores']) in present:
            continue
        out.append({'case_id': cell['case'], 'cores': cell['cores'], 'attempt_id': None,
                    'status': cell['state'], 'journal_key': key, 'journal_state': cell['state'],
                    'comparison_status': 'not_dispatched' if cell['state'] == 'pending' else 'missing_feed',
                    'quality_vs_fang': 'not_comparable', 'quality_vs_history': 'not_comparable',
                    'charged_E0_reservation': cell.get('charged_E0'),
                    'calls': cell.get('calls'), 'evidence_errors': ['No per-cell feed at capture. A dispatching journal entry is not proof of a currently live process.'],
                    'timing_causal_comparison': False})
    return out


def build_report(run_dir, audit_dir, root=ROOT):
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise ValueError('Input run directory does not exist; no run is started by this tool')
    refs, provenance = load_audit(audit_dir, root)
    feeds = sorted(run_dir.glob('board-feed*.json'))
    journal_path = run_dir/'journal.json'
    journal_raw = journal_path.read_bytes() if journal_path.exists() else None
    journal = json.loads(journal_raw) if journal_raw else {}
    if not feeds and not journal:
        raise ValueError('No existing feeds or dispatch journal')
    context = read(run_dir/'context.json') if (run_dir/'context.json').exists() else None
    attempts = {}; input_files = []; superseded = []
    for feed in feeds:
        raw = feed.read_bytes(); input_files.append({'path': feed.name, 'sha256': digest(raw)})
        for record in json.loads(raw)['records']:
            key = record['attempt_id']; prior = attempts.get(key)
            if prior and prior['revision'] == record['revision'] and prior != record:
                raise ValueError('Conflicting same-attempt/revision feed: ' + key)
            if prior and prior['revision'] != record['revision']:
                superseded.append({'attempt_id': key, 'revision': min(prior['revision'], record['revision'])})
            if not prior or record['revision'] > prior['revision']:
                attempts[key] = record
    rows = [compare_record(r, refs.get((r.get('case_id'), r.get('cores'))), run_dir, root, context)
            for r in attempts.values()]
    for row in rows:
        key = f"{row['case_id']}-k{row['cores']}"
        if journal:
            entry = journal.get('cells', {}).get(key)
            row['journal_state'] = entry.get('state') if entry else None
            if not entry or entry['state'] != row['status']:
                row['evidence_errors'].append('Feed does not match dispatch journal coordinate/state')
                row.update(comparison_status='not_comparable', quality_vs_fang='not_comparable', quality_vs_history='not_comparable')
    rows.extend(missing_journal_rows(journal, rows))
    rows.sort(key=lambda r:(r['cores'], r['case_id'], r.get('attempt_id') or ''))
    stable = journal_raw == (journal_path.read_bytes() if journal_path.exists() else None)
    groups = defaultdict(list)
    for row in rows:
        groups[(row.get('run_id'), row.get('algorithm_id'), row.get('variant'), row.get('solver_commit'), row['cores'])].append(row)
    aggregates = []
    for key, group in sorted(groups.items(), key=lambda pair: str(pair[0])):
        good = [r for r in group if r['comparison_status'] == 'artifacts_verified']
        unique = len({r['case_id'] for r in good}) == len(good)
        full = stable and len(group) == len(good) == 100 and unique and {r['case_id'] for r in good} == {f'{c:03}' for c in range(1,101)}
        aggregates.append({'run_id':key[0], 'algorithm_id':key[1], 'variant':key[2], 'solver_commit':key[3], 'cores':key[4],
                           'reported_attempts':len(group), 'verified_successes':len(good), 'unique_case_count':len({r['case_id'] for r in good}),
                           'full_100_case_mean_established':full,
                           'mean_scope':'full100' if full else 'development-subset-successes-only; not a full100 result',
                           'mean_baseline_speedup':statistics.mean(r['baseline_speedup'] for r in good) if good and unique else None,
                           'paired_fang_mean_baseline_speedup':statistics.mean(r['baseline_cycles']/r['comparators']['fang']['metrics']['makespan_cycles'] for r in good) if good and unique else None,
                           'paired_history_mean_baseline_speedup':statistics.mean(r['baseline_cycles']/r['comparators']['history']['metrics']['makespan_cycles'] for r in good) if good and unique else None,
                           'paired_extra_ddr_delta_bytes_fang_sum':sum(r['vs_fang']['extra_ddr_delta_bytes'] for r in good) if good and all(r['vs_fang']['extra_ddr_delta_bytes'] is not None for r in good) else None,
                           'paired_extra_ddr_delta_bytes_history_sum':sum(r['vs_history']['extra_ddr_delta_bytes'] for r in good) if good and all(r['vs_history']['extra_ddr_delta_bytes'] is not None for r in good) else None,
                           'quality_vs_fang':dict(Counter(r['quality_vs_fang'] for r in group)),
                           'quality_vs_history':dict(Counter(r['quality_vs_history'] for r in group))})
    return {'schema_version':1, 'kind':'P2-evidence-comparison', 'created_at':datetime.now(timezone.utc).isoformat(),
            'comparator_sha256':digest(Path(__file__).read_bytes()), 'audit':provenance, 'feed_inputs':input_files,
            'journal_sha256':digest(journal_raw) if journal_raw else None, 'journal_stable_during_read':stable,
            'expected_journal_cells':len(journal.get('cells',{})) if journal else None,
            'superseded_revisions':superseded, 'rows':rows, 'aggregates':aggregates,
            'counts':{'rows':len(rows), 'statuses':dict(Counter(r['status'] for r in rows)),
                      'comparison_status':dict(Counter(r['comparison_status'] for r in rows)),
                      'bound_conflicts':sum(bool(r.get('bound_conflict')) for r in rows)},
            'comparison_evaluator_calls':{'E0':0,'E1':0,'E2':0},
            'limitations':['Artifact equality is not independent execution, central admission, or scientific acceptance.',
                          'Failed, pending, missing and unverified cells are retained and never imputed as zero.',
                          'Subset means are not full100 means; repeated attempts are not silently selected as winners.',
                          'Shared-machine before/after wall values do not establish causal speedup.',
                          'The lower bound may be loose; positive U/L-1 is an upper error bound, not an achievable gain.']}


def markdown(report):
    lines=['# P2 existing-evidence comparison', '',
           '0 new E0/E1/E2. Frozen comparison time: '+report['audit']['captured_at']+'.',
           'Development-subset results are not a full100 average. Wall values are observations, not causal speedups.', '',
           '| Case/core | Status | Evidence | Makespan | vs Fang | vs history | Extra delta Fang/history | Spill delta Fang/history | Solver wall s | U-L |',
           '|---|---|---|---:|---|---|---:|---:|---:|---:|']
    for r in report['rows']:
        f,h=r.get('vs_fang',{}),r.get('vs_history',{})
        lines.append(f"| {r['case_id']}/{r['cores']} | {r['status']} | {r['comparison_status']} | {r.get('metrics',{}).get('makespan_cycles','NA')} | {r['quality_vs_fang']} | {r['quality_vs_history']} | {f.get('extra_ddr_delta_bytes','NA')}/{h.get('extra_ddr_delta_bytes','NA')} | {f.get('spill_delta_bytes','NA')}/{h.get('spill_delta_bytes','NA')} | {r.get('solver_wall_seconds','NA')} | {r.get('lower_bound_gap_cycles','NA')} |")
    lines += ['', '## Paired aggregates on exactly these successful cases', '',
              '| Cores | Successes | Scope | New mean B/U | Same-case Fang mean | Same-case history mean | vs Fang | vs history |',
              '|---|---:|---|---:|---:|---:|---|---|']
    for group in report['aggregates']:
        lines.append(f"| {group['cores']} | {group['verified_successes']} | {group['mean_scope']} | {group['mean_baseline_speedup']} | {group['paired_fang_mean_baseline_speedup']} | {group['paired_history_mean_baseline_speedup']} | {group['quality_vs_fang']} | {group['quality_vs_history']} |")
    lines += ['', 'Full per-attempt evidence errors, ratios, identities, calls and scope are retained in the JSON.', '']
    return '\n'.join(lines)


def write_new(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(text)


def self_test():
    """Tiny synthetic records only: no production evidence/score is written."""
    import tempfile
    import unittest
    class Checks(unittest.TestCase):
        def setUp(self):
            self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
            self.root=Path(self.tmp.name);self.run=self.root/'run';self.run.mkdir()
            self.ident={k:'a'*64 for k in IDENTITY_KEYS}
            self.ref={'baseline':dict(self.ident,makespan_cycles=300),'lower_bound_cycles':50}
            for name,score in [('fang',120),('history',90)]:
                self.ref[name]={'id':name,'solver_commit':'1'*40,'metrics':{'makespan_cycles':score,'solver_wall_seconds':.1,'extra_ddr_bytes':10,'spill_bytes':2}}
            self.r={'attempt_id':'synthetic','revision':1,'run_id':'synthetic','algorithm_id':'synthetic','variant':'test','solver_commit':'1'*40,'case_id':'001','cores':2,'problem':'P2','status':'ok','identity':dict(self.ident),'evaluator':{'route':'E0'},'provenance':{'solver':{'source':{'commit':'1'*40}}},'metrics':{'makespan_cycles':100,'solver_wall_seconds':.2,'evaluation_wall_seconds':.4,'ddr_bytes':15,'extra_ddr_bytes':5,'spill_bytes':0},'artifacts':{}}
            self.put('plan',{'node_to_subgraph':{'1':0},'core_schedules':[[0],[]]})
            self.r['identity']['plan_sha256']=self.r['artifacts']['plan']['sha256']
            self.receipt={'case':'001','cores':2,'status':'ok','solver_mode':'direct','online':{'calls':{'E0':0}},'solver':{'status':'ok','wall_seconds':.2},'final':{'status':'ok','wall_seconds':.4}}
            self.put('run',self.receipt)
            self.result={'scene':'B','num_cores':2,'makespan':100,'data_movement_bytes':{'scheduled_copy_bytes':15,'added_copy_bytes':5,'spill_added_copy_bytes':0}}
            self.put('result',self.result)
        def put(self,name,value):
            path=self.run/(name+'.json');raw=json.dumps(value).encode();path.write_bytes(raw)
            self.r['artifacts'][name]={'path':path.relative_to(self.root).as_posix(),'sha256':digest(raw)}
        def compare(self):return compare_record(self.r,self.ref,self.run,self.root)
        def test_success_ratios_and_signed_bytes(self):
            out=self.compare();self.assertEqual(out['comparison_status'],'artifacts_verified');self.assertEqual((out['quality_vs_fang'],out['quality_vs_history']),('win','loss'))
            self.assertEqual(out['vs_fang']['extra_ddr_delta_bytes'],-5);self.assertEqual(out['lower_bound_gap_cycles'],50);self.assertFalse(out['timing_causal_comparison'])
        def test_failed_receipt_preserved_without_result(self):
            self.r['status']='timeout';self.receipt['status']='timeout';self.put('run',self.receipt);del self.r['artifacts']['result']
            out=self.compare();self.assertEqual(out['comparison_status'],'recorded_non_success');self.assertEqual(out['solver_wall_seconds'],.2);self.assertEqual(out['quality_vs_fang'],'not_comparable')
        def test_corrupt_result_hash_not_scored(self):
            (self.run/'result.json').write_text('{}');out=self.compare();self.assertEqual(out['quality_vs_fang'],'not_comparable');self.assertTrue(out['evidence_errors'])
        def test_wrong_official_identity_not_scored(self):
            self.r['identity']['official_sha256']='b'*64;self.assertEqual(self.compare()['comparison_status'],'not_comparable')
        def test_below_bound_is_preserved_as_conflict(self):
            self.ref['lower_bound_cycles']=101;out=self.compare();self.assertTrue(out['bound_conflict']);self.assertEqual(out['lower_bound_gap_cycles'],-1)
        def test_journal_unknown_and_pending_not_lost(self):
            rows=missing_journal_rows({'cells':{'001-k2':{'case':'001','cores':2,'state':'pending','charged_E0':0},'002-k2':{'case':'002','cores':2,'state':'dispatching','charged_E0':1}}},[])
            self.assertEqual([r['comparison_status'] for r in rows],['not_dispatched','missing_feed']);self.assertIsNone(rows[1]['calls'])
        def test_dictionary_core_schedules_rejected(self):
            self.put('plan',{'node_to_subgraph':{'1':0},'core_schedules':{'0':[0],'1':[]}})
            self.r['identity']['plan_sha256']=self.r['artifacts']['plan']['sha256']
            self.assertEqual(self.compare()['comparison_status'],'not_comparable')
        def test_legacy_bad_online_equality_rejected(self):
            self.receipt.pop('solver_mode');self.receipt['online_E0_calls']=2;self.receipt['full_result_bytes_equal']=False;self.put('run',self.receipt)
            self.assertEqual(self.compare()['comparison_status'],'not_comparable')
        def test_late_error_cannot_leave_promoted_metrics(self):
            del self.ref['fang']['metrics']['makespan_cycles'];out=self.compare()
            self.assertEqual(out['comparison_status'],'not_comparable');self.assertNotIn('metrics',out);self.assertNotIn('baseline_speedup',out)
        def test_refuse_overwrite(self):
            path=self.run/'new.json';write_new(path,'first')
            with self.assertRaises(FileExistsError):write_new(path,'second')
            self.assertEqual(path.read_text(),'first')
    outcome=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    return 0 if outcome.wasSuccessful() else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path);parser.add_argument('--audit-dir',type=Path,default=DEFAULT_AUDIT)
    parser.add_argument('--output',type=Path);parser.add_argument('--markdown',type=Path)
    parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    if args.self_test:
        return self_test()
    if args.run_dir is None or args.output is None:
        parser.error('--run-dir and --output are required unless --self-test is used')
    outputs=[p.resolve() for p in (args.output,args.markdown) if p is not None]
    if len(outputs)!=len(set(outputs)) or any(p.exists() for p in outputs):
        parser.error('Output paths must be distinct and must not already exist')
    if any(p.is_relative_to(args.run_dir.resolve()) or p.is_relative_to(args.audit_dir.resolve()) for p in outputs):
        parser.error('Write comparisons outside immutable input run and frozen audit directories')
    report=build_report(args.run_dir,args.audit_dir)
    write_new(args.output,json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    if args.markdown:write_new(args.markdown,markdown(report))
    print(json.dumps(report['counts'],ensure_ascii=False))
    return 1 if report['counts']['bound_conflicts'] or any(r['evidence_errors'] and r['comparison_status']!='not_dispatched' for r in report['rows']) or not report['journal_stable_during_read'] else 0


if __name__=='__main__':
    raise SystemExit(main())
