"""Fixed structural P1 construction with a small online exact-score guard.

Input is only the graph, core budget and frozen hardware configuration. No case
name, historical plan or score table participates in candidate generation.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1.bounded_tasks import construct as bounded
from src.q1.heavy_suffix import construct as heavy
from src.q1.sink_peel import construct as sink
from src.q1.component_overload import construct as overload
from src.q1.shared_input_budget import construct as shared_input, _view, _size
from src.q1.fork_frontier import construct as fork_frontier
from src.q1.capacity_return import construct as capacity_return
from stub_multicore_cut_and_schedule import _build_op_adjacency, _contract_excluded_copy_nodes

CONFIG = ROOT / 'data/raw/a/official/data/config.txt'
E1_SOURCE = '5bfe53a29c1ba05167239f51ea937e602f7f85b4'
ALGORITHM_ID = 'q1-unified-structural-guard'
MAX_DISTINCT_CANDIDATES = 6


def event(emit, event_type, **fields):
    if emit is not None:
        emit(dict(event=event_type, monotonic_seconds=time.monotonic(), **fields))


def plan_bytes(plan):
    # Preserve mapping order, task IDs and all numeric types. This is also the
    # exact serialization written by the CLI, not an unproved semantic hash.
    return (json.dumps(plan, separators=(',', ':')) + '\n').encode()


def generate_candidates(graph, cores, emit=None):
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError('cores must be an integer in 1..5')
    began = time.perf_counter()
    candidates, duplicates, construction_failures = [], [], []
    seen = {}

    def add(name, constructor, required=False):
        start = time.perf_counter()
        event(emit, 'candidate_construction_started', name=name)
        try:
            plan, details = constructor()
        except Exception as error:
            if required:
                raise
            construction_failures.append(dict(name=name, error_type=type(error).__name__,
                message=str(error), construction_seconds=time.perf_counter()-start))
            event(emit, 'candidate_construction_failed', **construction_failures[-1])
            return
        raw = plan_bytes(plan)
        key = hashlib.sha256(raw).hexdigest()
        record = dict(name=name, plan_sha256=key,
                      construction_seconds=time.perf_counter()-start, details=details)
        if key in seen:
            duplicates.append(dict(record, duplicate_of=seen[key]))
            event(emit, 'candidate_duplicate', name=name, plan_sha256=key, duplicate_of=seen[key])
        else:
            seen[key] = name
            candidates.append(dict(record, plan=json.loads(raw)))
            event(emit, 'candidate_constructed', name=name, plan_sha256=key,
                  construction_seconds=record['construction_seconds'])
        return plan, details

    bounded_result = add('bounded', lambda: bounded(graph, cores), required=True)
    if cores == 1:
        return candidates, dict(features={'cores': 1}, duplicates=duplicates,
                                construction_failures=construction_failures,
                                generation_seconds=time.perf_counter()-began)
    view = _view(graph)
    component_of = {u: i for i, (nodes, _, _) in enumerate(view['components']) for u in nodes}
    input_components = defaultdict(set)
    for u, tids in view['reads'].items():
        for t in tids:
            input_components[t].add(component_of[u])
    shared = {t for t, cs in input_components.items() if len(cs) > 1}
    external_bytes = _size(view['external'], view)
    features = dict(cores=cores, components=len(view['components']),
                    external_input_bytes=external_bytes,
                    shared_external_input_bytes=_size(shared, view))
    # Whole-component/bounded construction is the common reference. The next
    # alternatives expose parallel work restricted by whole-component packing.
    sink_result = None
    def cached_sink():
        nonlocal sink_result
        if sink_result is None:
            # Store only successful constructions; the next candidate retries
            # a failed fallback within its own add() failure boundary.
            sink_result = sink(graph, cores, fallback_candidate=bounded_result)
        return sink_result

    def make_heavy():
        return heavy(graph, cores, fallback_factory=cached_sink)

    heavy_result = add('heavy-or-sink', make_heavy)
    def make_overload():
        fallback = heavy_result if heavy_result is not None else make_heavy()
        return overload(graph, cores, fallback_candidate=fallback)

    add('overload', make_overload)
    if len(view['components']) >= cores:
        if external_bytes > 524288:
            add('shared-input', lambda: shared_input(graph, cores))
            features['additional_route'] = 'shared-input'
        else:
            features['additional_route'] = 'none'
    else:
        _, full = _build_op_adjacency(graph)
        _, successors = _contract_excluded_copy_nodes(sorted(view['ops']), full)
        forks = sum(len(vs) > 1 for vs in successors.values())
        features['forks'] = forks
        if forks:
            add('fork-frontier', lambda: fork_frontier(graph, cores, grain=4))
            features['additional_route'] = 'fork-frontier'
        else:
            features['additional_route'] = 'none'
    # Necessary cheap shape check only; the candidate's strict recognizer then
    # checks private homogeneous M -> V+ -> M chains and conservative capacity.
    # Failed applicability retains the existing candidates. No graph IDs or
    # recorded case results participate in this route.
    compute_pipes = [op['pipe'] for op in view['ops'].values()]
    if (set(compute_pipes) == {'PIPE_M', 'PIPE_V'}
            and compute_pipes.count('PIPE_M') == 2 * len(view['components'])):
        add('capacity-return', lambda: capacity_return(graph, cores))
        features['return_route'] = 'strict-private-chain-check'
    else:
        features['return_route'] = 'inapplicable-compute-shape'
    # Frontier packing also applies to disconnected chains and in-trees with
    # no fork. Preserve all previous candidate attempts/order; extend the
    # domain at the end so a failed extra score cannot suppress a prior winner.
    # Count an earlier attempted F even if it failed or was byte-deduplicated.
    if features['additional_route'] != 'fork-frontier':
        add('fork-frontier', lambda: fork_frontier(graph, cores, grain=4))
        features['frontier_route'] = 'general-multicore'
    else:
        features['frontier_route'] = 'existing-fork-route'
    if len(candidates) > MAX_DISTINCT_CANDIDATES:
        raise AssertionError('Structural candidate bound exceeded')
    return candidates, dict(features=features, duplicates=duplicates,
                            construction_failures=construction_failures,
                            generation_seconds=time.perf_counter()-began)


def choose(candidates, score, emit=None):
    """Stop at the first scoring failure, retaining an already checked winner.

    The single-candidate fast path needs no online ranking; external official
    validation remains required. score is injected only to test the controller.
    """
    if not candidates:
        raise ValueError('Need a nonempty candidate set')
    if len(candidates) == 1:
        return candidates[0], [], 'single-distinct-plan'
    best, best_key, records = candidates[0], None, []
    for item in candidates:
        event(emit, 'score_attempt_started', name=item['name'], plan_sha256=item['plan_sha256'])
        try:
            record = score(item['plan'])
        except Exception as error:
            record = dict(status='error', error_type=type(error).__name__, message=str(error))
        records.append(dict(name=item['name'], plan_sha256=item['plan_sha256'], **record))
        event(emit, 'score_attempt_returned', **records[-1])
        if record['status'] != 'ok':
            return best, records, 'first-score-failure'
        key = (record['makespan'], record['data_movement_bytes']['scheduled_copy_bytes'])
        if best_key is None or key < best_key:
            best, best_key = item, key
    return best, records, 'all-distinct-plans-scored'


def solve(graph, cores, emit=None):
    began = time.perf_counter()
    candidates, diagnostics = generate_candidates(graph, cores, emit=emit)
    score_started = time.perf_counter()
    if len(candidates) == 1:
        selected, records, reason = choose(candidates, None, emit=emit)
    else:
        from src.eval_exact import P1BatchEvaluator, read_config
        config = read_config(CONFIG)
        # Fixed single worker. Timeouts are failure controls, not search sweeps.
        # Local compilation and global DDR/FIFO/gates are charged online.
        with P1BatchEvaluator(graph, workers=1, cache_bytes=16 << 20,
                              timeout_seconds=60, startup_timeout_seconds=10,
                              max_tasks_per_worker=MAX_DISTINCT_CANDIDATES) as evaluator:
            def score(plan):
                return next(evaluator.evaluate_batch([plan], full=False, **config))
            selected, records, reason = choose(candidates, score, emit=emit)
    diagnostics.update(algorithm_id=ALGORITHM_ID, variant='structural-six-plan-general-frontier-v4',
                       selected=selected['name'], stop_reason=reason,
                       candidates=[{k:v for k,v in c.items() if k != 'plan'} for c in candidates],
                       online_scores=records, online_score_attempts=len(records),
                       actual_e1_calls=sum(r.get('worker_pid') is not None for r in records),
                       e1_source_commit=E1_SOURCE,
                       online_scoring_seconds=time.perf_counter()-score_started,
                       solve_function_seconds=time.perf_counter()-began,
                       scope='E1 ranking is not external E0 acceptance; no full-matrix claim')
    return selected['plan'], diagnostics


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('graph', type=Path)
    p.add_argument('--cores', type=int, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--diagnostics', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists() or args.diagnostics.exists():
        raise FileExistsError('Refuse to overwrite existing solver artifacts')
    def emit(record):
        print(json.dumps(record), flush=True)
    event(emit, 'solver_input_started', cores=args.cores)
    plan, info = solve(json.loads(args.graph.read_bytes()), args.cores, emit=emit)
    for path in (args.output, args.diagnostics):
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as out:
        out.write(plan_bytes(plan))
    with args.diagnostics.open('x') as out:
        json.dump(info, out, indent=2)
        out.write('\n')
    event(emit, 'solver_completed', algorithm_id=ALGORITHM_ID, selected=info['selected'],
          actual_e1_calls=info['actual_e1_calls'], online_score_attempts=info['online_score_attempts'])


if __name__ == '__main__':
    main()
