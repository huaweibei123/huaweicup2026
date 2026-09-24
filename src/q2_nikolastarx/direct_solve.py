"""Single-pass P2 router: guarded resource word, otherwise tensor-aware DAG.

No evaluator or per-case result is consulted. Structural validation is not an
official performance certificate; the benchmark launches final E0 separately.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from .baseline import ROOT
from .dag_direct import DAGIndex
from .direct import Index, UnsupportedStructure
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def build(graph, cores, config):
    index = DAGIndex(graph)
    try:
        a, b, lookahead = index.word_descriptor()
    except UnsupportedStructure as reason:
        plan, detail = index.build(
            cores, bandwidth=config['bandwidth'],
            cross_core_delay=config['cross_core_copy_delay_cycles'])
        return plan, {**detail, 'selected_strategy': 'dag_eft',
                      'resource_word_guard': False, 'guard_reason': str(reason)}
    plan, detail = Index.build(index, cores, 'resource_word')
    return plan, {**detail, 'selected_strategy': 'resource_word',
                  'resource_word_guard': True, 'word': {'a': a, 'b': b,
                                                     'lookahead': lookahead}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--config', type=Path, default=ROOT/'data/raw/a/official/data/config.txt')
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--wall', type=float, default=240)
    parser.add_argument('--evaluation-timeout', type=float, default=60,
                        help='Unused compatibility argument: this solver never scores')
    args = parser.parse_args()
    started = time.perf_counter()
    args.evidence.mkdir(parents=True, exist_ok=False)
    ledger = {'status': 'running', 'calls': {'E0': 0, 'E1': 0, 'E2': 0},
              'attempts': [], 'started_at': datetime.now(timezone.utc).isoformat(),
              'validation_scope': 'Official derive_multicore_plan structural validation only'}
    try:
        graph = json.loads(args.graph.read_text())
        config = {**read_evaluation_config(str(args.config)),
                  **read_scene_b_config(str(args.config))}
        plan, detail = build(graph, args.cores, config)
        folder = args.evidence/'structural_router'
        folder.mkdir()
        dump(folder/'plan.json', plan)
        digest = hashlib.sha256((folder/'plan.json').read_bytes()).hexdigest()
        ledger['attempts'].append({'name': 'structural_router',
                                  'status': 'constructed', 'detail': detail,
                                  'plan_sha256': digest})
        if time.perf_counter() - started > args.wall:
            raise TimeoutError('construction exceeded solver wall limit')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as stream:
            stream.write((folder/'plan.json').read_bytes())
        ledger.update(status='ok', selected='structural_router', plan_sha256=digest,
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
