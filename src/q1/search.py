"""Budgeted Q1 search using the separately pinned exact batch evaluator.

Proposal generation and evaluation run in bounded child processes. E0 confirms
the final incumbent and the stub separately, outside the search budget.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import platform
import random
import subprocess
import sys
import time

from prototype import (ROOT, OFFICIAL, fixed_blocks, place_by_local_duration,
                       read_evaluation_config, read_scene_a_config, generate_multicore_plan)
from structure import structural_partition, fuse_covers, topological
from stub_multicore_cut_and_schedule import derive_multicore_plan, _build_op_adjacency, _contract_excluded_copy_nodes
from evaluation_validation import validate_task_order

EVALUATOR_COMMIT = "5bfe53a29c1ba05167239f51ea937e602f7f85b4"


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan_key(plan):
    # Keep mapping insertion order: it belongs to the exact compilation context.
    # A coarser permutation equivalence requires a separate proof.
    return hashlib.sha256(json.dumps(plan, separators=(',', ':')).encode()).hexdigest()


def proposal(args):
    graph = json.loads(args.graph.read_text())
    settings = read_evaluation_config(str(OFFICIAL / "data/config.txt"))
    waits = read_scene_a_config(str(OFFICIAL / "data/config.txt"))
    if args.kind == "official_stub":
        plan = generate_multicore_plan(graph, num_cores=args.cores, seed=args.seed)
    elif args.kind == "single":
        nodes = [op['id'] for op in graph['ops'] if op['op'] not in {'COPY_IN', 'COPY_OUT'}]
        plan = {'node_to_subgraph': {v: 0 for v in nodes}, 'core_schedules': [[0]] + [[] for _ in range(args.cores - 1)]}
    elif args.kind in ("chain", "component", "fixed64"):
        plan = (fixed_blocks(graph, args.cores, args.seed, 64) if args.kind == "fixed64"
                else structural_partition(graph, args.cores, args.kind))
        plan = place_by_local_duration(graph, plan, settings, waits)
    else:
        plan = json.loads(args.parent.read_text())
        if args.kind.startswith("fuse"):
            plan, _ = fuse_covers(graph, plan, 128, args.kind == "fuse_protected")
        else:
            rng = random.Random(args.seed)
            orders = plan['core_schedules']
            if args.kind == "move":
                source = rng.choice([k for k, order in enumerate(orders) if order])
                task = rng.choice(orders[source])
                destination = rng.randrange(args.cores)
                orders[source].remove(task)
                orders[destination].insert(rng.randrange(len(orders[destination]) + 1), task)
            elif args.kind == "swap":
                choices = [k for k, order in enumerate(orders) if len(order) >= 2]
                if not choices:
                    raise ValueError("No adjacent pair to swap")
                order = orders[rng.choice(choices)]
                i = rng.randrange(len(order) - 1)
                order[i], order[i + 1] = order[i + 1], order[i]
            elif args.kind == "split":
                view = derive_multicore_plan(graph, plan)
                choices = [t for t, nodes in view['nodes_by_subgraph'].items() if len(nodes) >= 2]
                if not choices:
                    raise ValueError("No splittable Task")
                task = rng.choice(choices)
                nodes = view['nodes_by_subgraph'][task]
                eligible = sorted(view['mapping'])
                _, full = _build_op_adjacency(graph)
                _, successors = _contract_excluded_copy_nodes(eligible, full)
                local = {v: successors[v] & set(nodes) for v in nodes}
                order = topological(nodes, local)
                cut = rng.randrange(1, len(order))
                new_task = max(view['subgraph_ids']) + 1
                for v in order[cut:]:
                    plan['node_to_subgraph'][str(v)] = new_task
                for core in orders:
                    if task in core:
                        core.insert(core.index(task) + 1, new_task)
                        break
    validate_task_order(derive_multicore_plan(graph, plan))
    dump(args.output, plan)


def confirm(graph, plan, folder, timeout):
    folder.mkdir()
    command = [sys.executable, '-B', str(OFFICIAL / 'code/multicore_cut_evaluate_problem_1.py'),
               str(graph), str(plan), '--config', str(OFFICIAL / 'data/config.txt'),
               '-o', str(folder / 'result.json'), '--trace-output', str(folder / 'trace.json'),
               '--log-output', str(folder / 'summary.log')]
    start = time.monotonic()
    try:
        process = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
        (folder / 'stdout.txt').write_text(process.stdout)
        (folder / 'stderr.txt').write_text(process.stderr)
        result = json.loads((folder / 'result.json').read_text()) if process.returncode == 0 else None
        return {'status': 'ok' if result else 'error', 'returncode': process.returncode,
                'makespan': result['makespan'] if result else None, 'seconds': time.monotonic() - start}
    except subprocess.TimeoutExpired:
        return {'status': 'timeout', 'seconds': time.monotonic() - start}


def search(args):
    overall_start = time.monotonic()
    args.output.mkdir(parents=True, exist_ok=False)
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.evaluator_root, text=True).strip()
    if actual != EVALUATOR_COMMIT or subprocess.check_output(
            ['git', 'status', '--porcelain', '--untracked-files=no'], cwd=args.evaluator_root):
        raise ValueError('Exact evaluator must use the pinned, clean tracked tree')
    sys.path.insert(0, str(args.evaluator_root.resolve()))
    from src.eval_exact import P1BatchEvaluator, read_config
    graph = json.loads(args.graph.read_text())
    config = read_config(str(OFFICIAL / 'data/config.txt'))
    rng = random.Random(args.seed)
    records, seen, incumbent = [], set(), None
    attempts = evaluations = 0
    deadline = overall_start + args.budget
    proposal_seconds = evaluation_seconds = 0.0
    known = None
    if args.seed_plan:
        known = args.output / 'known_seed.json'
        known.write_bytes(args.seed_plan.read_bytes())
    methods = ['official_stub'] + (['known_seed'] if known else []) + ['single', 'chain', 'component', 'fixed64', 'fuse_protected', 'fuse_free']
    checkpoint = args.output / 'best_plan.json'
    with P1BatchEvaluator(graph, workers=1, cache_bytes=16 << 20,
                          timeout_seconds=args.candidate_timeout, startup_timeout_seconds=5,
                          max_tasks_per_worker=256) as pool:
        while evaluations < args.candidates and attempts < args.candidates * 4:
            # Reserve worst-case proposal + worker startup + one evaluation.
            if deadline - time.monotonic() < 2 * args.candidate_timeout + 5:
                break
            kind = methods.pop(0) if methods else ('split' if attempts % 8 == 0 else rng.choice(['move', 'move', 'swap']))
            folder = args.output / f'{attempts:03d}_{kind}'
            folder.mkdir()
            plan_path = folder / 'plan.json'
            row = {'attempt': attempts, 'kind': kind, 'parent': incumbent['attempt'] if incumbent else None}
            attempts += 1
            start = time.monotonic()
            if kind == 'known_seed':
                plan_path.write_bytes(known.read_bytes())
            else:
                if kind.startswith('fuse') or kind in ('move', 'swap', 'split'):
                    if incumbent is None:
                        row['status'] = 'no_parent'; records.append(row); continue
                command = [sys.executable, '-B', str(Path(__file__).resolve()), 'propose', str(args.graph),
                           str(plan_path), '--kind', kind, '--cores', str(args.cores), '--seed', str(rng.randrange(2**31)),
                           '--parent', str(checkpoint)]
                # Baseline seed remains fixed and independent of proposal history.
                if kind == 'official_stub':
                    command[command.index('--seed') + 1] = str(args.seed)
                try:
                    process = subprocess.run(command, text=True, capture_output=True, timeout=args.candidate_timeout)
                    (folder / 'proposal.stderr.txt').write_text(process.stderr)
                    if process.returncode:
                        row.update(status='proposal_rejected', returncode=process.returncode)
                except subprocess.TimeoutExpired:
                    row['status'] = 'proposal_timeout'
            row['proposal_seconds'] = time.monotonic() - start
            proposal_seconds += row['proposal_seconds']
            if 'status' in row:
                records.append(row); continue
            plan = json.loads(plan_path.read_text())
            key = plan_key(plan)
            row['plan_sha256'] = sha(plan_path)
            if key in seen:
                row['status'] = 'duplicate'; records.append(row); continue
            seen.add(key)
            start = time.monotonic()
            result = list(pool.evaluate_batch([plan], full=False, **config))[0]
            evaluation_seconds += time.monotonic() - start
            evaluations += 1
            row.update(result)
            row['evaluation_number'] = evaluations
            if result['status'] == 'ok' and (incumbent is None or result['makespan'] < incumbent['makespan']):
                incumbent = copy.deepcopy(row)
                checkpoint.write_bytes(plan_path.read_bytes())
            records.append(row)
            dump(args.output / 'progress.json', {'evaluations': evaluations, 'attempts': attempts, 'incumbent': incumbent})
    search_seconds = time.monotonic() - overall_start
    final = confirm(args.graph, checkpoint, args.output / 'e0_best', args.confirm_timeout) if incumbent else {'status': 'no_incumbent'}
    stub = args.output / '000_official_stub/plan.json'
    baseline = confirm(args.graph, stub, args.output / 'e0_baseline', args.confirm_timeout) if stub.exists() else {'status': 'no_plan'}
    matches = final['status'] == 'ok' and incumbent is not None and final['makespan'] == incumbent['makespan']
    source = args.output / 'source'
    source.mkdir()
    for name in ('search.py', 'prototype.py', 'structure.py'):
        (source / name).write_bytes(Path(__file__).with_name(name).read_bytes())
    report = {'problem': 1, 'graph': str(args.graph.relative_to(ROOT)), 'graph_sha256': sha(args.graph),
              'config_sha256': sha(OFFICIAL / 'data/config.txt'), 'evaluator_commit': actual,
              'python': sys.version, 'platform': platform.platform(), 'uv_lock_sha256': sha(ROOT / 'uv.lock'),
              'code_base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'source_hashes': {p.name: sha(p) for p in source.iterdir()},
              'parameters': {'cores': args.cores, 'seed': args.seed, 'candidates': args.candidates, 'budget_seconds': args.budget,
                             'candidate_timeout': args.candidate_timeout, 'confirm_timeout': args.confirm_timeout, 'workers': 1, 'cache_bytes': 16 << 20},
              'seed_plan_sha256': sha(known) if known else None,
              'attempts': attempts, 'evaluations': evaluations, 'incumbent': incumbent, 'records': records,
              'search_seconds': search_seconds, 'proposal_seconds': proposal_seconds, 'evaluation_seconds': evaluation_seconds,
              'total_seconds': time.monotonic() - overall_start,
              'e0_best': final, 'e0_baseline': baseline, 'e0_confirms_selected_makespan': matches,
              'budget_scope': 'Search includes IO, candidate subprocesses and exact worker lifecycle; E0 final/baseline confirmations have separate limits. OS cleanup is not hard realtime.',
              'scope': 'Public development search; no held-out or universal optimality claim'}
    dump(args.output / 'summary.json', report)
    print(json.dumps({k: report[k] for k in ('graph','attempts','evaluations','search_seconds','e0_best','e0_baseline','e0_confirms_selected_makespan')}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('propose')
    p.add_argument('graph', type=Path); p.add_argument('output', type=Path)
    p.add_argument('--kind', required=True, choices=['official_stub','single','chain','component','fixed64','fuse_protected','fuse_free','move','swap','split'])
    p.add_argument('--cores', type=int, default=4); p.add_argument('--seed', type=int, default=0); p.add_argument('--parent', type=Path)
    p = sub.add_parser('search')
    p.add_argument('graph', type=Path); p.add_argument('output', type=Path)
    p.add_argument('--evaluator-root', type=Path, required=True); p.add_argument('--seed-plan', type=Path)
    p.add_argument('--cores', type=int, default=4); p.add_argument('--seed', type=int, default=0)
    p.add_argument('--candidates', type=int, default=32); p.add_argument('--budget', type=float, default=60)
    p.add_argument('--candidate-timeout', type=float, default=5); p.add_argument('--confirm-timeout', type=float, default=30)
    args = parser.parse_args()
    if args.cores < 1:
        parser.error('cores must be positive')
    args.graph, args.output = args.graph.resolve(), args.output.resolve()
    if args.command == 'search':
        if min(args.candidates, args.budget, args.candidate_timeout, args.confirm_timeout) <= 0:
            parser.error('search limits must be positive')
        search(args)
    else:
        proposal(args)


if __name__ == '__main__':
    main()
