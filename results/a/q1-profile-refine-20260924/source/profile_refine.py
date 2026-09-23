"""Budgeted profile-guided Q1 partition refinement and supervised experiment."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import traceback

from search import ROOT, OFFICIAL, EVALUATOR_COMMIT, confirm, dump, plan_key, sha

CASES = ['044', '051', '002']


def journal(folder, record):
    with (folder / 'journal.jsonl').open('a') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def objective(row):
    return row['makespan'], row['data_movement_bytes']['scheduled_copy_bytes']


def run_guarded(command, folder, wall_seconds=125, rss_bytes=1536 << 20):
    """Sample summed RSS of this new process group; stop on either budget.

    Summed RSS counts shared pages repeatedly and is NOT an allocation hard cap.
    Only the newly created experiment process group may be terminated.
    """
    start, peak, status = time.monotonic(), 0, 'running'
    with (folder / 'supervisor.stdout.txt').open('w') as out, (folder / 'supervisor.stderr.txt').open('w') as err:
        process = subprocess.Popen(command, stdout=out, stderr=err, start_new_session=True)
        group = process.pid
        try:
            while process.poll() is None:
                if time.monotonic() - start >= wall_seconds:
                    status = 'wall_budget_exceeded'
                    break
                snapshot = subprocess.check_output(['ps', '-axo', 'pgid=,rss='], text=True, timeout=2)
                current = sum(int(rss) * 1024 for pgid, rss in (line.split() for line in snapshot.splitlines()) if int(pgid) == group)
                peak = max(peak, current)
                if current > rss_bytes:
                    status = 'rss_budget_exceeded'
                    break
                time.sleep(0.1)
            if status == 'running':
                status = 'ok' if process.returncode == 0 else 'process_error'
        except BaseException:
            status = 'supervisor_error'
            raise
        finally:
            # Also reap any child left in this experiment group after an early
            # parent exit. Never signal another task's or shell's process group.
            try:
                os.killpg(group, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=1)
    return {'status': status, 'returncode': process.returncode,
            'wall_seconds': time.monotonic() - start, 'sampled_group_peak_rss_bytes': peak,
            'wall_limit_seconds': wall_seconds, 'rss_stop_threshold_bytes': rss_bytes,
            'rss_scope': 'Sum of case process group RSS, sampled about 100ms plus ps cost; shared pages double-counted, not a hard allocation cap'}


def refine(args):
    folder = args.output
    started = time.monotonic()
    summary = {'case': args.case, 'status': 'started', 'evaluations': 0, 'records': [], 'rounds': []}
    try:
        sys.path.insert(0, str(args.evaluator_root.resolve()))
        from src.eval_exact import P1BatchEvaluator, read_config
        config = read_config(str(OFFICIAL / 'data/config.txt'))
        graph_path = OFFICIAL / f'data/case_{args.case}.json'
        graph = json.loads(graph_path.read_text())
        original = ROOT / f'results/a/q1-guided-moves-20260924/case{args.case}/guided/best_plan.json'
        seed = folder / 'seed.json'
        seed.write_bytes(original.read_bytes())
        summary.update(graph_sha256=sha(graph_path), seed_sha256=sha(seed))
        journal(folder, {'event': 'seed_e0_started'})
        seed_check = confirm(graph_path, seed, folder / 'e0_seed', 30)
        summary['e0_seed'] = seed_check
        if seed_check['status'] != 'ok':
            raise RuntimeError('seed E0 failed')
        seed_result = json.loads((folder / 'e0_seed/result.json').read_text())
        confirmed = folder / 'confirmed_plan.json'
        confirmed.write_bytes(seed.read_bytes())
        incumbent = {k: seed_result[k] for k in ['makespan', 'data_movement_bytes']}
        summary['confirmed_result'] = incumbent
        proposal_parent = folder / 'provisional_plan.json'
        proposal_parent.write_bytes(seed.read_bytes())
        plan = json.loads(seed.read_text())
        seen = {plan_key(plan)}
        search_start = time.monotonic()
        deadline = search_start + 60
        failed = False
        with P1BatchEvaluator(graph, workers=1, cache_bytes=16 << 20, timeout_seconds=10,
                              startup_timeout_seconds=5, max_tasks_per_worker=32) as pool:
            journal(folder, {'event': 'e1_dispatched', 'kind': 'seed', 'plan_sha256': sha(seed)})
            seed_e1 = list(pool.evaluate_batch([plan], full=False, **config))[0]
            summary['evaluations'] += 1
            summary['records'].append({'kind': 'seed', 'result': seed_e1})
            journal(folder, {'event': 'e1_returned', 'kind': 'seed', 'result': seed_e1})
            if seed_e1['status'] != 'ok' or objective(seed_e1) != objective(seed_result) or seed_e1['data_movement_bytes'] != seed_result['data_movement_bytes']:
                raise RuntimeError('seed E1/E0 disagreement or failure')
            for round_index in range(2):
                if deadline - time.monotonic() < 25:
                    summary['stop_reason'] = 'remaining_search_budget'
                    break
                round_dir = folder / f'round{round_index}'
                round_dir.mkdir()
                parent_copy = round_dir / 'parent.json'
                parent_copy.write_bytes(proposal_parent.read_bytes())
                seen_file = round_dir / 'seen.json'
                dump(seen_file, sorted(seen))
                output = round_dir / 'generated.json'
                command = [sys.executable, '-B', str(Path(__file__).with_name('profile_candidates.py')),
                           str(graph_path), str(parent_copy), str(seen_file), str(output)]
                journal(folder, {'event': 'proposal_started', 'round': round_index, 'parent_sha256': sha(parent_copy)})
                proposal_start = time.monotonic()
                try:
                    run = subprocess.run(command, capture_output=True, text=True, timeout=10)
                    (round_dir / 'proposal.stderr.txt').write_text(run.stderr)
                    if run.returncode:
                        raise RuntimeError('proposal process error')
                except (subprocess.TimeoutExpired, RuntimeError) as error:
                    summary['stop_reason'] = type(error).__name__ + ': ' + str(error)
                    journal(folder, {'event': 'proposal_failed', 'round': round_index, 'error': summary['stop_reason']})
                    failed = True
                    break
                generated = json.loads(output.read_text())
                summary['rounds'].append({'round': round_index, 'parent_sha256': sha(parent_copy),
                                          'generation_wall_seconds': time.monotonic() - proposal_start,
                                          'proposals': len(generated['candidates']), 'duplicates': generated['duplicates'],
                                          'guard_rejections': generated['rejected'], 'cover_rejections': generated['cover_rejections']})
                for i, item in enumerate(generated['candidates']):
                    if deadline - time.monotonic() < 15:
                        summary['stop_reason'] = 'remaining_search_budget'
                        break
                    plan = item['plan']
                    seen.add(item['key'])
                    candidate_dir = round_dir / f'candidate{i}'
                    candidate_dir.mkdir()
                    candidate_path = candidate_dir / 'plan.json'
                    dump(candidate_path, plan)
                    dispatch = {'round': round_index, 'candidate': i, 'choice': item['choice'], 'plan_sha256': sha(candidate_path)}
                    journal(folder, dict(event='e1_dispatched', **dispatch))
                    result = list(pool.evaluate_batch([plan], full=False, **config))[0]
                    summary['evaluations'] += 1
                    accepted = result['status'] == 'ok' and objective(result) < objective(incumbent)
                    row = dict(dispatch, result=result, accepted=accepted)
                    summary['records'].append(row)
                    journal(folder, dict(event='e1_returned', **row))
                    if result['status'] != 'ok':
                        failed = True
                        summary['stop_reason'] = 'evaluator_' + result['status']
                        break
                    if accepted:
                        incumbent = {k: result[k] for k in ['makespan', 'data_movement_bytes']}
                        proposal_parent.write_bytes(candidate_path.read_bytes())
                    dump(folder / 'progress.json', {'provisional': incumbent, 'evaluations': summary['evaluations'],
                                                   'confirmed_seed_retained': True})
                if failed:
                    break
        summary['search_seconds'] = time.monotonic() - search_start
        journal(folder, {'event': 'final_e0_started', 'plan_sha256': sha(proposal_parent)})
        final = confirm(graph_path, proposal_parent, folder / 'e0_final', 30)
        summary['e0_final'] = final
        matches = False
        if final['status'] == 'ok':
            result = json.loads((folder / 'e0_final/result.json').read_text())
            matches = objective(result) == objective(incumbent) and result['data_movement_bytes'] == incumbent['data_movement_bytes']
        if matches:
            confirmed.write_bytes(proposal_parent.read_bytes())
            summary['confirmed_result'] = incumbent
        summary.update(status='partial_failure' if failed or not matches else 'ok',
                       final_confirms_provisional=matches, provisional_result=incumbent,
                       confirmed_plan_sha256=sha(confirmed), seed_makespan=seed_result['makespan'])
    except Exception as error:
        summary.update(status='error', error_type=type(error).__name__, message=str(error))
        (folder / 'failure.txt').write_text(traceback.format_exc())
        journal(folder, {'event': 'run_failed', 'error_type': type(error).__name__, 'message': str(error)})
    finally:
        summary['total_seconds'] = time.monotonic() - started
        dump(folder / 'summary.json', summary)
    return summary['status'] == 'ok'


def experiment(args):
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.evaluator_root, text=True).strip()
    if actual != EVALUATOR_COMMIT or subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=args.evaluator_root):
        raise ValueError('Require fixed clean E1 checkout')
    args.output.mkdir(parents=True, exist_ok=False)
    protocol = {'cases': CASES, 'evaluator_commit': actual, 'rounds': 2, 'new_candidates_per_round': 4,
                'max_e1_calls_per_case': 9, 'max_cli_calls_per_case': 2, 'max_local_profile_builds_per_case': 2,
                'search_budget_seconds': 60, 'proposal_timeout_seconds': 10, 'e1_timeout_seconds': 10,
                'worker_startup_timeout_seconds': 5, 'e0_timeout_seconds': 30,
                'outer_case_wall_seconds': 125, 'sampled_process_group_rss_stop_bytes': 1536 << 20,
                'workers': 1, 'cache_bytes': 16 << 20, 'max_merge_ops': 256,
                'objective': 'lexicographic makespan, scheduled_copy_bytes', 'seed': 'deterministic priority and ID tie breaks',
                'failure_policy': 'Stop case on first proposal or evaluator failure; retain E0-confirmed seed; promote only after final E0',
                'scope': 'Three public development cases; baseline versus two-round refinement, no causal ablation or held-out claim',
                'planned_before_runs': True, 'code_base_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'config_sha256': sha(OFFICIAL/'data/config.txt'), 'uv_lock_sha256': sha(ROOT/'uv.lock'),
                'python': sys.version, 'platform': platform.platform()}
    source = args.output / 'source'; source.mkdir()
    for name in ['profile_refine.py','profile_candidates.py','search.py','prototype.py','structure.py']:
        (source/name).write_bytes(Path(__file__).with_name(name).read_bytes())
    protocol['source_hashes'] = {p.name: sha(p) for p in source.iterdir()}
    dump(args.output/'protocol.json', protocol)
    started = time.monotonic()
    results = []
    for case in CASES:
        folder = args.output / ('case'+case); folder.mkdir()
        command = [sys.executable, '-B', str(Path(__file__).resolve()), 'case', '--case', case,
                   '--output', str(folder), '--evaluator-root', str(args.evaluator_root)]
        supervisor = run_guarded(command, folder)
        # A missing child summary is a failure, never an empty successful row.
        summary_path = folder/'summary.json'
        try:
            summary = json.loads(summary_path.read_text()) if summary_path.exists() else {'status':'missing_summary'}
        except json.JSONDecodeError as error:
            summary = {'status': 'malformed_summary', 'error': str(error)}
        journal_path = folder/'journal.jsonl'
        ledger, ledger_errors = [], []
        if journal_path.exists():
            for line_number, line in enumerate(journal_path.read_text().splitlines(), 1):
                if line.strip():
                    try:
                        ledger.append(json.loads(line))
                    except json.JSONDecodeError as error:
                        ledger_errors.append({'line': line_number, 'error': str(error)})
        supervisor['journal_parse_errors'] = ledger_errors
        supervisor['e1_dispatches_from_journal'] = sum(row['event']=='e1_dispatched' for row in ledger)
        supervisor['e1_returns_from_journal'] = sum(row['event']=='e1_returned' for row in ledger)
        supervisor['confirmed_plan_present'] = (folder/'confirmed_plan.json').exists()
        dump(folder/'supervisor.json', supervisor)
        status = summary['status']
        if supervisor['status'] != 'ok' or ledger_errors:
            status = 'supervised_failure'
        row = {'case': case, 'supervisor': supervisor, 'status': status,
               'seed_makespan': summary.get('seed_makespan'), 'confirmed_result': summary.get('confirmed_result'),
               'total_seconds': summary.get('total_seconds')}
        results.append(row)
        dump(args.output/'summary.json', {'cases': results, 'experiment_wall_seconds': time.monotonic()-started})
        print(json.dumps(row), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['experiment','case'])
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--evaluator-root', type=Path, required=True)
    p.add_argument('--case', choices=CASES)
    args = p.parse_args()
    args.output, args.evaluator_root = args.output.resolve(), args.evaluator_root.resolve()
    if args.mode == 'experiment':
        experiment(args)
    else:
        if not args.case:
            p.error('--case required')
        sys.exit(0 if refine(args) else 1)


if __name__ == '__main__':
    main()
