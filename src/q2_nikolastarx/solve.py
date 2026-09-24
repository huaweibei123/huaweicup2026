"""Four structural P2 proposals with official E0 incumbent protection.

This is a bounded portfolio, not an approximate evaluator or a parameter grid.
Every E0 dispatch is recorded, including invalid/timeout/error. Exact equality
keeps the earlier incumbent. No successful E0 means no final plan is published.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

from .baseline import contiguous_plan, OFFICIAL, ROOT
from .direct import Index
from .packets import GraphIndex
from .bounds import assigned_pipe_lower_bound


def utc():
    return datetime.now(timezone.utc).isoformat()


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def construct(graph, cores, name):
    if name == 'contiguous':
        return contiguous_plan(graph, cores), {'selected_strategy': name}
    if name == 'chain_critical':
        idx = GraphIndex(graph, cores)
        assignment, _, order = idx.packet_assignment('chain', 'critical', 1)
        return idx.plan(assignment, order), {'selected_strategy': name}
    return Index(graph).build(cores, name)


def solve(graph_path, config, cores, output, evidence, timeout=60, wall=240,
          prune_bounds=False):
    started = time.perf_counter()
    evidence.mkdir(parents=True, exist_ok=False)
    record = {'started_at': utc(), 'calls': {'E0': 0, 'E1': 0, 'E2': 0},
              'attempts': [], 'prune_bounds': prune_bounds,
              'budget': {'max_E0': 4, 'wall_seconds': wall,
              'evaluation_timeout_seconds': timeout}, 'status': 'running'}
    ledger = evidence / 'solver.json'
    dump(ledger, record)
    graph = json.loads(graph_path.read_text())
    best = None
    seen = {}
    for name in ('contiguous', 'chain_critical', 'affine_eighth', 'guarded_reentry'):
        if time.perf_counter() - started >= wall - 3:
            record['stop_reason'] = 'wall_budget'
            break
        item = {'name': name, 'status': 'constructing', 'started_at': utc()}
        record['attempts'].append(item)
        folder = evidence / name
        folder.mkdir()
        try:
            plan, detail = construct(graph, cores, name)
        except Exception as error:
            item.update(status='construction_error', error=repr(error))
            dump(ledger, record)
            continue
        plan_path = folder / 'plan.json'
        dump(plan_path, plan)
        digest = hashlib.sha256(plan_path.read_bytes()).hexdigest()
        item.update(plan_sha256=digest, detail=detail,
                    construction_elapsed_seconds=time.perf_counter() - started)
        if digest in seen:
            item.update(status='duplicate', duplicate_of=seen[digest])
            dump(ledger, record)
            continue
        seen[digest] = name
        if prune_bounds:
            lower = assigned_pipe_lower_bound(graph, plan)
            item['assigned_pipe_lower_bound_cycles'] = lower
            if lower is not None and best is not None and lower >= best[0]:
                item.update(status='bound_pruned', incumbent_name=best[1],
                            incumbent_makespan_cycles=best[0],
                            prune_reason='assigned_pipe_work_cannot_strictly_improve')
                dump(ledger, record)
                continue
        remaining = wall - (time.perf_counter() - started) - 3
        if remaining <= 0:
            item['status'] = 'not_evaluated'
            record['stop_reason'] = 'wall_budget'
            break
        result = folder / 'result.json'
        command = [sys.executable, '-B', str(OFFICIAL / 'multicore_cut_evaluate_problem_2.py'),
                   str(graph_path), str(plan_path), '--config', str(config),
                   '-o', str(result), '--trace-output', str(folder / 'trace.json'),
                   '--log-output', str(folder / 'official.log')]
        item.update(status='dispatching', argv=[os.path.relpath(p, ROOT) if p.startswith(str(ROOT)) else p for p in command])
        record['calls']['E0'] += 1
        dump(ledger, record)
        launch = time.perf_counter()
        with (folder / 'stdout.txt').open('w') as out, (folder / 'stderr.txt').open('w') as err:
            process = subprocess.Popen(command, stdout=out, stderr=err, start_new_session=True)
            try:
                code = process.wait(timeout=min(timeout, remaining))
                item.update(status='official_error' if code else 'ok', exit_code=code)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                item.update(status='timeout', exit_code=process.returncode)
        item['evaluation_wall_seconds'] = time.perf_counter() - launch
        item['finished_at'] = utc()
        if item['status'] == 'ok':
            try:
                data = json.loads(result.read_text())
                score = data['makespan']
                if type(score) not in (int, float) or not 0 < score < float('inf'):
                    raise ValueError('invalid score')
                item['makespan_cycles'] = score
                item['data_movement_bytes'] = data['data_movement_bytes']
                if best is None or score < best[0]:
                    best = (score, name, plan_path, result)
            except Exception as error:
                item.update(status='result_error', error=repr(error))
        dump(ledger, record)
    if best is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise FileExistsError(output)
        shutil.copyfile(best[2], output)
        record.update(status='ok', selected=best[1], makespan_cycles=best[0],
                      plan_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                      selected_result=str(best[3].relative_to(evidence)))
    else:
        record['status'] = 'failed'
    record.setdefault('stop_reason', 'fixed_structural_candidates_exhausted')
    record.update(finished_at=utc(), internal_wall_seconds=time.perf_counter()-started)
    dump(ledger, record)
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('graph', type=Path)
    p.add_argument('--config', type=Path, default=ROOT/'data/raw/a/official/data/config.txt')
    p.add_argument('--cores', type=int, default=4)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--evaluation-timeout', type=float, default=60)
    p.add_argument('--wall', type=float, default=240)
    p.add_argument('--prune-bounds', action='store_true',
                   help='Skip candidates whose certified pipe work cannot improve the incumbent')
    a = p.parse_args()
    r = solve(a.graph.resolve(), a.config.resolve(), a.cores, a.output.resolve(),
              a.evidence.resolve(), a.evaluation_timeout, a.wall, a.prune_bounds)
    print(json.dumps({k:r[k] for k in ('status','calls','internal_wall_seconds')}))
    if r['status'] != 'ok':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
