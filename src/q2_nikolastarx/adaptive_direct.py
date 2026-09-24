"""One-index, pure-structure P2 router; zero online evaluator calls.

Priority: homogeneous resource-word guard; whole-component capacity envelope
when components >= cores; otherwise tensor DAG EFT. No case IDs or score table.
This is a unified candidate, not a remedy for the known 016-k2/062 failures.
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
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config


def build(graph, cores, config):
    if type(cores) is not int or cores < 1:
        raise ValueError('cores must be a positive integer')
    index = DAGIndex(graph)
    try:
        a, b, lookahead = index.word_descriptor()
    except UnsupportedStructure as error:
        guard_reason = str(error)
    else:
        plan, detail = Index.build(index, cores, 'resource_word')
        return plan, {**detail, 'selected_strategy': 'resource_word',
                      'adaptive_route': 'resource_word', 'index_constructions': 1,
                      'resource_word_guard': True,
                      'word': {'a': a, 'b': b, 'lookahead': lookahead}}
    if len(index.components) >= cores:
        plan, detail = build_from_index(index, cores, config)
        route = 'component_envelope'
    else:
        plan, detail = index.build(cores, bandwidth=config['bandwidth'],
                                   cross_core_delay=config['cross_core_copy_delay_cycles'])
        route = 'dag_eft'
    return plan, {**detail, 'selected_strategy': route, 'adaptive_route': route,
                  'index_constructions': 1, 'resource_word_guard': False,
                  'guard_reason': guard_reason,
                  'routing_condition': 'components >= cores' if route == 'component_envelope'
                                       else 'components < cores',
                  'route_limitations': 'Structural choice only; no official feasibility, score or zero-spill certificate'}


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
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
        plan, detail = build(graph, args.cores, config)
        folder = args.evidence/'adaptive_direct'
        folder.mkdir()
        dump(folder/'plan.json', plan)
        raw = (folder/'plan.json').read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        ledger['attempts'].append({'name': 'adaptive_direct', 'status': 'constructed',
                                  'detail': detail, 'plan_sha256': digest})
        if time.perf_counter() - started > args.wall:
            raise TimeoutError('construction exceeded solver wall limit')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write(raw)
        ledger.update(status='ok', selected='adaptive_direct', plan_sha256=digest,
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
