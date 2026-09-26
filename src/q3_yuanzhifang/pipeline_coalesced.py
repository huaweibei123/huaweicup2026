"""Keep pipeline core ownership while releasing singleton priority buckets.

One subgraph per nonempty stage lets the official Step1 order independent
inputs and operations inside that stage. This is a construction hypothesis;
no COPY, cache or capacity outcome is predicted or overridden here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .construct import SharingIndex, derive_multicore_plan
from .pipeline_stages import build as pipeline_build
from evaluation_validation import read_bandwidth_config


def build(index, cores, bandwidth):
    original, detail = pipeline_build(index, cores, bandwidth)
    if not detail.get('guard'):
        return original, dict(guard=False, selected='pipeline_fallback', fallback=detail)
    inverse = {sg: int(u) for u, sg in original['node_to_subgraph'].items()}
    mapping, schedules = {}, []
    for core, order in enumerate(original['core_schedules']):
        for singleton in order:
            mapping[str(inverse[singleton])] = core
        schedules.append([core] if order else [])
    plan = dict(node_to_subgraph=mapping, core_schedules=schedules)
    # Exact official static validation includes quotient acyclicity. It does
    # not execute Step1/2/3 or establish memory feasibility or performance.
    derive_multicore_plan(index.graph, plan)
    return plan, dict(guard=True, selected='pipeline_coalesced',
                     requested_cores=cores, active_cores=sum(bool(s) for s in schedules),
                     subgraphs=sum(bool(s) for s in schedules),
                     original_singletons=len(mapping), cuts=detail['cuts'],
                     core_ownership='identical to pipeline_stages; one subgraph per nonempty stage',
                     pipeline_reference=detail,
                     assumption='official Step1 decides within-stage order; no fixed-FIFO, spill or quality guarantee')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('graph', type=Path)
    ap.add_argument('--cores', type=int, required=True)
    ap.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[2] /
                    'data/raw/a/official/data/config.txt')
    ap.add_argument('-o', '--output', type=Path, required=True)
    args = ap.parse_args()
    index = SharingIndex(json.loads(args.graph.read_text(encoding='utf-8')))
    plan, meta = build(index, args.cores, read_bandwidth_config(args.config))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps(meta, sort_keys=True))


if __name__ == '__main__':
    main()
