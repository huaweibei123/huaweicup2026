"""One structural P2 construction with a diagnosed large-vector-cut repair.

Word -> guarded tree -> existing component/DAG route. Only a recognized vector
stage template whose general plan cuts a non-scalar tensor invokes one whole-
lane repair. No case IDs, stored plans, score tables or online evaluations.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from .baseline import ROOT
from .component_envelope import build_from_index
from .dag_direct import DAGIndex
from .direct import Index, UnsupportedStructure
from . import tree_frontier, tree_paired_leaves, vector_lanes, vector_arrival
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config


def _large_internal_crossings(template, plan):
    sg_owner = {sg: c for c, seq in enumerate(plan['core_schedules']) for sg in seq}
    owner = {int(u): sg_owner[sg] for u, sg in plan['node_to_subgraph'].items()}
    crossings = set()
    for t, ps in template['ep'].items():
        if template['tensors'][t]['size'] <= template['scalar_size']:
            continue
        for p in ps:
            for q in template['ec'][t]:
                if owner[p] != owner[q]:
                    crossings.add((t, owner[p], owner[q]))
    return len(crossings), sum(template['tensors'][t]['size'] for t, _, _ in crossings)


def build(graph, cores, config, *, component_builder=None):
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be a positive integer')
    index = DAGIndex(graph)
    try:
        a, b, lookahead = index.word_descriptor()
    except UnsupportedStructure:
        pass
    else:
        plan, detail = Index.build(index, cores, 'resource_word')
        return plan, {**detail, 'selected_strategy': 'resource_word',
                      'adaptive_route': 'resource_word', 'index_constructions': 1,
                      'base_construct_calls': 1, 'repair_construct_calls': 0,
                      'word': {'a': a, 'b': b, 'lookahead': lookahead}}
    try:
        tree_frontier._guard(index)
    except UnsupportedStructure:
        pass
    else:
        plan, detail = tree_paired_leaves.build_from_index(index, cores, config)
        return plan, {**detail, 'adaptive_route': 'tree_paired_leaves',
                      'index_constructions': 1, 'repair_construct_calls': 0}
    # Preserve the previous general route before considering a diagnosed repair.
    if len(index.components) >= cores:
        plan, detail = (component_builder or build_from_index)(index, cores, config)
        route = detail.get('selected_strategy', 'component_envelope')
    else:
        plan, detail = index.build(cores, bandwidth=config['bandwidth'],
                                  cross_core_delay=config['cross_core_copy_delay_cycles'])
        route = 'dag_eft'
    trigger = {'recognized': False, 'large_crossings': 0, 'large_crossing_bytes': 0}
    try:
        template = vector_lanes.recognize(index)
    except UnsupportedStructure as error:
        trigger['reason'] = str(error)
    else:
        count, size = _large_internal_crossings(template, plan)
        trigger.update(recognized=True, large_crossings=count, large_crossing_bytes=size)
        if count:
            base_route = route
            plan, detail = vector_arrival.build_from_index(index, cores, config)
            route = 'vector_arrival'
            return plan, {**detail, 'adaptive_route': route, 'index_constructions': 1,
                          'base_route': base_route, 'base_construct_calls': 1,
                          'repair_construct_calls': 1, 'repair_trigger': trigger,
                          'route_limitations': 'structural large-vector cut repair; not a guarantee of lower official Makespan or DDR'}
    return plan, {**detail, 'selected_strategy': route, 'adaptive_route': route,
                  'index_constructions': 1, 'base_construct_calls': 1,
                  'repair_construct_calls': 0, 'repair_trigger': trigger,
                  'route_limitations': 'unchanged general plan; no official feasibility/score/zero-spill certificate'}


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main(*, constructor=None, label='adaptive_semantic'):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--config', type=Path, default=ROOT/'data/raw/a/official/data/config.txt')
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--wall', type=float, default=240)
    args = parser.parse_args()
    started = time.perf_counter()
    args.evidence.mkdir(parents=True, exist_ok=False)
    ledger = {'status': 'running', 'calls': {'E0': 0, 'E1': 0, 'E2': 0}, 'attempts': [],
              'started_at': datetime.now(timezone.utc).isoformat(),
              'validation_scope': 'official structural validation only; no E0/Step2/Step3 certificate'}
    try:
        graph = json.loads(args.graph.read_text())
        config = {**read_evaluation_config(args.config), **read_scene_b_config(args.config)}
        plan, detail = (constructor or build)(graph, args.cores, config)
        folder = args.evidence/label
        folder.mkdir()
        dump(folder/'plan.json', plan)
        raw = (folder/'plan.json').read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        ledger['attempts'].append({'name': label, 'status': 'constructed',
                                  'detail': detail, 'plan_sha256': digest})
        if time.perf_counter() - started > args.wall:
            raise TimeoutError('construction exceeded solver wall limit')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(raw)
        ledger.update(status='ok', selected=label, plan_sha256=digest,
                      stop_reason='single_structural_route_completed')
    except Exception as error:
        ledger.update(status='failed', error=repr(error))
    finally:
        ledger.update(finished_at=datetime.now(timezone.utc).isoformat(),
                      internal_wall_seconds=time.perf_counter()-started)
        dump(args.evidence/'solver.json', ledger)
    print(json.dumps({'status': ledger['status'], 'calls': ledger['calls'],
                      'internal_wall_seconds': ledger['internal_wall_seconds']}))
    if ledger['status'] != 'ok':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
