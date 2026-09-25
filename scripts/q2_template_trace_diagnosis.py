"""Read existing E0 traces; no construction or evaluation is performed."""
import hashlib
import json
from pathlib import Path
import zipfile


def diagnose(archive):
    rows = []
    with zipfile.ZipFile(archive) as z:
        report = json.loads(z.read('output/report.json'))
        for old in report['rows']:
            case = old['case']
            result = json.loads(z.read(f'output/{case}/result.json'))
            detail = json.loads(z.read(f'inputs/{case}-detail.json'))
            jobs = detail['jobs']
            busy, endpoints = [], []
            for core in result['per_core_timeline']:
                by_pipe = {}
                for op in core['ops']:
                    if op['op'] not in ('COPY_IN', 'COPY_OUT'):
                        by_pipe[op['pipe']] = by_pipe.get(op['pipe'], 0) + op['duration']
                busy.append(by_pipe)
                compute = [op for op in core['ops'] if op['pipe'] == 'PIPE_M']
                endpoints.append([min(op['start'] for op in compute),
                                  max(op['end'] for op in compute)] if compute else None)
            assert all(work % jobs == 0 for core in busy for work in core.values())
            stage = [max(core.values(), default=0) // jobs for core in busy]
            scalar = (sum(stage) + (jobs - 1) * max(stage) +
                      (len(stage) - 1) * result['cross_core_copy_delay_cycles'])
            lower = max(max(core.values(), default=0) for core in busy)
            rows.append(dict(case=case, jobs=jobs, old_makespan=old['old_M'],
                             observed_makespan=result['makespan'],
                             compute_busy_cycles_by_core_pipe=busy,
                             first_last_M_compute_cycles=endpoints,
                             fixed_assignment_compute_lower_bound=lower,
                             lower_bound_exceeds_old_makespan=lower > old['old_M'],
                             scalar_finite_job_proxy_cycles=scalar,
                             scalar_proxy_is_official_bound=False,
                             normalized_minimax=detail['normalized_minimax_work']))
    return dict(archive_sha256=hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
                scope='read-only diagnosis of existing three mechanism probes',
                assumptions=['frozen official PIPE_SLOTS=1',
                             'non-COPY operation durations are fixed compute cycles',
                             'scalar proxy excludes generated COPY and DDR contention'],
                new_constructions=0, E0_calls=0, E2_calls=0, rows=rows)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.output.open('x') as f:
        json.dump(diagnose(args.archive), f, indent=2)
        f.write('\n')
