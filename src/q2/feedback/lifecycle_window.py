"""One bounded shared-input lifecycle candidate on capacity-window rejected cores."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from .capacity_window import build as capacity_build, footprint, memory_window
from .construct import ROOT, derive_multicore_plan
from .tensor_packet import TensorIndex


def build(index, cores, bandwidth, delay, capacity):
    """Keep the capacity plan except for certified, previously rejected cores."""
    base, original = capacity_build(index, cores, bandwidth, delay, capacity)
    # In particular, an alias or packet override must keep its exact plan.
    if original['selected'] != 'capacity_window':
        return base, {'selected': 'lifecycle_window_guard_unchanged',
                      'base_selected': original['selected'], 'online_E0_calls': 0}

    mapping = base['node_to_subgraph']
    inverse = {sg: int(u) for u, sg in mapping.items()}
    schedules = [list(schedule) for schedule in base['core_schedules']]
    details = []
    for core, schedule in enumerate(schedules):
        old = original['core_details'][core]
        sequence = [inverse[sg] for sg in schedule]
        record = {'original_width': old['window'], 'changed': False,
                  'group_count': 0, 'group_widths': []}
        if not sequence:
            record['reason'] = 'empty core'
        elif old['window'] >= 1:
            record['reason'] = 'capacity window already admitted this core'
        else:
            jobs = list(dict.fromkeys(index.owner[u] for u in sequence))
            if set(sequence) != {u for j in jobs for u in index.components[j]}:
                record['reason'] = 'component is not wholly assigned to this core'
            else:
                counts = Counter(t for j in jobs for t in index.external_by_job[j])
                shared = {t for t, count in counts.items() if count > 1}
                groups = {}
                for j in jobs:
                    signature = tuple(sorted(index.external_by_job[j] & shared))
                    groups.setdefault(signature, []).append(j)
                record['group_count'] = len(groups)
                candidate = []
                for group in groups.values():
                    width, _ = memory_window(index, group, capacity)
                    record['group_widths'].append(width)
                    if width < 1:
                        record['reason'] = 'a group cannot admit one job'
                        break
                    revised, _ = index.pipe_window(group, width, prefer_fill=False)
                    candidate.extend(revised)
                else:
                    peak = footprint(index, candidate)
                    record['full_bucket_footprint_bytes'] = peak
                    if any(peak[pool] > capacity[pool] for pool in capacity):
                        record['reason'] = 'full sequence exceeds capacity'
                    else:
                        schedules[core] = [mapping[str(u)] for u in candidate]
                        record['changed'] = candidate != sequence
                        record['reason'] = 'certified full sequence' if record['changed'] else 'candidate equals base'
        details.append(record)

    answer = {'node_to_subgraph': mapping, 'core_schedules': schedules}
    derive_multicore_plan(index.graph, answer)
    return answer, {'selected': 'lifecycle_window',
                    'base_selected': original['selected'], 'cores': cores,
                    'core_details': details, 'online_E0_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--config', type=Path, default=ROOT / 'data/raw/a/official/data/config.txt')
    parser.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args()
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    config = {**read_evaluation_config(args.config), **read_scene_b_config(args.config)}
    plan, meta = build(TensorIndex(json.loads(args.graph.read_bytes())), args.cores,
                       config['bandwidth'], config['cross_core_copy_delay_cycles'], config['capacity'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, separators=(',', ':')) + '\n',
                           encoding='utf-8', newline='\n')
    print(json.dumps(meta, sort_keys=True))


if __name__ == '__main__':
    main()
