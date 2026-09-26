"""Read-only indivisible-job workload certificate; never constructs a plan."""
from collections import defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import time
from urllib.request import urlopen


def sha(value):
    return hashlib.sha256(value).hexdigest()


def certify(graph, cores):
    ops = {o['id']: o for o in graph['ops']}
    tensors = {t['id']: t for t in graph['tensors']}
    eligible = {u: o for u, o in ops.items() if o['op'] not in ('COPY_IN', 'COPY_OUT')}
    incoming, outgoing = defaultdict(list), defaultdict(list)
    for edge in graph['edges']:
        incoming[edge['target']].append(edge['source'])
        outgoing[edge['source']].append(edge['target'])
    # With endpoint-only original COPY nodes there is no excluded-COPY bridge
    # between eligible operations. Reject other shapes rather than silently
    # equating these components with the solver's contracted compute graph.
    for u, op in ops.items():
        if op['op'] == 'COPY_IN':
            if not incoming[u] or any(t not in tensors or tensors[t]['pos'] != 'DDR' or incoming[t]
                                      for t in incoming[u]):
                raise ValueError('non-endpoint original COPY_IN')
        elif op['op'] == 'COPY_OUT':
            if not outgoing[u] or any(t not in tensors or tensors[t]['pos'] != 'DDR' or outgoing[t]
                                      for t in outgoing[u]):
                raise ValueError('non-endpoint original COPY_OUT')
    parent = {u: u for u in eligible}
    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u
    def join(u, v):
        parent[find(v)] = find(u)
    for edge in graph['edges']:
        if edge['source'] in eligible and edge['target'] in eligible:
            join(edge['source'], edge['target'])
    for tid in tensors:
        for u in incoming[tid]:
            if u in eligible:
                for v in outgoing[tid]:
                    if v in eligible:
                        join(u, v)
    groups = defaultdict(list)
    for u in eligible:
        groups[find(u)].append(u)
    certificates = []
    for nodes in sorted(groups.values(), key=min):
        nodes.sort()
        work = {pipe: sum(max(1, eligible[u]['cycles']) for u in nodes if eligible[u]['pipe'] == pipe)
                for pipe in ('PIPE_M', 'PIPE_V')}
        if any(eligible[u]['pipe'] not in work for u in nodes):
            raise ValueError('non M/V eligible operation')
        certificates.append(dict(first_op=nodes[0], last_op=nodes[-1], operations=len(nodes),
                                 operation_ids_sha256=sha(json.dumps(nodes, separators=(',', ':')).encode()),
                                 pipe_work_cycles=work))
    if not certificates or not 1 <= cores <= 5:
        raise ValueError('empty graph or unsupported cores')
    work = certificates[0]['pipe_work_cycles']
    if any(c['pipe_work_cycles'] != work for c in certificates):
        raise ValueError('not equal-work jobs; this pigeonhole certificate does not apply')
    unavoidable = (len(certificates) + cores - 1) // cores
    bounds = {pipe: unavoidable * cycles for pipe, cycles in work.items()}
    return dict(jobs=len(certificates), cores=cores, per_job_pipe_work=work,
                unavoidable_max_jobs_per_core=unavoidable, by_pipe_lower_bound_cycles=bounds,
                whole_job_lower_bound_cycles=max(bounds.values()), components=certificates)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--graph', type=Path, required=True)
    ap.add_argument('--cores', type=int, required=True)
    ap.add_argument('--board-url', required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    started = datetime.now(timezone.utc).isoformat()
    clock = time.perf_counter()
    raw = args.graph.read_bytes()
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / 'docs/a/source-manifest.json').read_bytes())
    expected = next(x for x in manifest['files'] if x['path'] == 'data/' + args.graph.name)
    if sha(raw) != expected['sha256'] or len(raw) != expected['bytes']:
        raise ValueError('graph differs from official manifest')
    result = certify(json.loads(raw), args.cores)
    config_hash = next(x['sha256'] for x in manifest['files'] if x['path'] == 'data/config.txt')
    identity = dict(graph_sha256=sha(raw), config_sha256=config_hash,
                    official_sha256=manifest['official_code_hash'])
    with urlopen(args.board_url, timeout=15) as response:
        snapshot = response.read()
    page = json.loads(snapshot)
    if page.get('next_offset') is not None:
        raise ValueError('comparison response requires pagination')
    matches = [r for r in page['records'] if r.get('eligible') and r.get('status') == 'ok' and
               r.get('problem') == 'P3' and r.get('cores') == args.cores and
               all(r['identity'].get(key) == val for key, val in identity.items())]
    if not matches:
        raise ValueError('no eligible same-identity P3 comparator')
    comparator = min(matches, key=lambda r: (r['metrics']['makespan_cycles'], -r.get('sequence', 0)))
    value = dict(schema='q3-indivisible-job-bound-v1', started_at=started,
                 finished_at=datetime.now(timezone.utc).isoformat(), wall_seconds=time.perf_counter()-clock,
                 driver_sha256=sha(Path(__file__).read_bytes()), input_identity=identity,
                 graph_name=args.graph.name, **result, comparator_record=comparator,
                 bound_exceeds_comparator=result['whole_job_lower_bound_cycles'] > comparator['metrics']['makespan_cycles'],
                 excess_cycles=result['whole_job_lower_bound_cycles'] - comparator['metrics']['makespan_cycles'],
                 board_snapshot_sha256=sha(snapshot), board_url=args.board_url,
                 calls=dict(solver=0, plan=0, derive=0, Step=0, E0=0, E1=0, E2=0),
                 scope='Static graph/workload certificate and member-board readback only; comparator raw E0 artifacts not independently downloaded. Bound applies only when every compute component stays on one core, not arbitrary cuts, partial-job waves, or Pareto efficiency.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: value[key] for key in ('jobs', 'cores', 'per_job_pipe_work',
          'whole_job_lower_bound_cycles', 'bound_exceeds_comparator', 'excess_cycles', 'calls')}))


if __name__ == '__main__':
    main()
