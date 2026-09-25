#!/usr/bin/env python3
"""Summarize existing, pinned complete P2 results; no evaluator is invoked."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'results/a/q2-nikolastarx/hypergap-full500-audit-20260925'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    spec = importlib.util.spec_from_file_location('full500_audit', AUDIT / 'audit.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    summary_raw = (AUDIT / 'completed-summary.json').read_bytes()
    summary = json.loads(summary_raw)
    prior_audit_raw = (AUDIT / 'report.json').read_bytes()
    prior_audit = json.loads(prior_audit_raw)
    audit.require(prior_audit['status'] == 'complete' and prior_audit['cells'] == 500
                  and prior_audit['summary_sha256'] == sha(summary_raw), 'audited summary differs')
    audit.require(summary['status'] == 'completed' and summary['accepted_cells'] == 500
                  and summary['solver_commit'] == audit.SOLVER
                  and summary['runner_commit'] == audit.RUNNER, 'current batch identity differs')
    old = audit.pinned_records(ROOT)  # Includes pinned Git blob SHA and complete grid checks.
    rows = summary['rows']
    audit.require(len(rows) == 500 and {(r['case'], r['cores']) for r in rows} == audit.GRID,
                  'current grid differs')
    values = []
    for r in rows:
        previous = old[r['case'], r['cores']]
        pm = previous['metrics']
        nm = r['official']['movement']
        audit.require(r['status'] == 'accepted'
                      and r['graph_sha256'] == previous['identity']['graph_sha256']
                      and r['config_sha256'] == previous['identity']['config_sha256'],
                      'paired input identity differs')
        audit.require(nm['added_copy_bytes'] == nm['partition_added_copy_bytes'] + nm['spill_added_copy_bytes']
                      == nm['scheduled_copy_bytes'] - nm['original_graph_copy_bytes'],
                      'current movement identity differs')
        audit.require(pm['extra_ddr_bytes'] >= pm['spill_bytes'] >= 0
                      and pm['ddr_bytes'] - pm['extra_ddr_bytes'] == nm['original_graph_copy_bytes'],
                      'previous movement identity differs')
        values.append(dict(case=r['case'], cores=r['cores'],
                           old_makespan=pm['makespan_cycles'], new_makespan=r['official']['makespan'],
                           old_extra=pm['extra_ddr_bytes'], new_extra=nm['added_copy_bytes'],
                           old_spill=pm['spill_bytes'], new_spill=nm['spill_added_copy_bytes'],
                           old_partition=pm['extra_ddr_bytes']-pm['spill_bytes'],
                           new_partition=nm['partition_added_copy_bytes']))

    def compare(new, old):
        return 'improved' if new < old else 'same' if new == old else 'regressed'

    def aggregate(items):
        totals = {name: sum(v[name] for v in items) for name in
                  ('old_extra', 'new_extra', 'old_spill', 'new_spill', 'old_partition', 'new_partition')}
        cross = Counter(compare(v['new_makespan'], v['old_makespan']) + '_M__' +
                        compare(v['new_extra'], v['old_extra']) + '_DDR' for v in items)
        return dict(cells=len(items), totals_bytes=totals,
                    mean_bytes={name: val/len(items) for name, val in totals.items()},
                    mean_MiB={name: val/len(items)/2**20 for name, val in totals.items()},
                    extra_change_pct=100*(totals['new_extra']/totals['old_extra']-1),
                    comparison=dict(sorted(cross.items())),
                    new_zero_extra_cells=sum(v['new_extra'] == 0 for v in items),
                    new_nonzero_spill_cells=sum(v['new_spill'] > 0 for v in items))

    by_case = []
    for case in sorted({v['case'] for v in values}):
        items = [v for v in values if v['case'] == case]
        by_case.append(dict(case=case, extra_delta_bytes=sum(v['new_extra']-v['old_extra'] for v in items)))
    out = dict(schema_version=1, status='complete_existing_result_aggregation',
               scope='One fixed current algorithm, 100 cases at each of 1-5 cores; paired previous fixed algorithm.',
               current_solver=audit.SOLVER, previous_solver=sorted({r['solver_commit'] for r in old.values()}),
               sources=dict(summary_path=str((AUDIT/'completed-summary.json').relative_to(ROOT)),
                            summary_sha256=sha(summary_raw), previous_feed_commit=audit.BASE,
                            previous_feed_path=audit.FEED, previous_feed_sha256=audit.FEED_SHA,
                            prior_full_audit_sha256=sha(prior_audit_raw)),
               verification='Current summary hash matches prior full original-result audit. Pinned previous feed hash, both 500-cell grids, paired graph/config, movement identities rechecked. No new evaluator calls; this aggregation does not repeat original-result parsing.',
               units='Bytes; MiB = 1048576 bytes. Percent is change in the sum (equivalently mean for equal n), not mean of per-cell percentages.',
               by_core={str(k): aggregate([v for v in values if v['cores'] == k]) for k in range(1, 6)},
               all500=aggregate(values),
               largest_increase_cases=sorted(by_case, key=lambda v: v['extra_delta_bytes'], reverse=True)[:10],
               cells=values)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: out[k] for k in ('by_core', 'all500', 'largest_increase_cases')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
