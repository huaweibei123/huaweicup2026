"""Read-only structural audit of frozen P2 K5 archive; never scores plans."""
from __future__ import annotations

import argparse
from collections import Counter
import gc
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.dag_direct import DAGIndex  # graph indexing only

DEFAULT_ZIP = ROOT / 'data/raw/a/official-cases.zip'
DEFAULT_ARCHIVE = ROOT / 'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee'
PIPES = ('PIPE_M', 'PIPE_V', 'PIPE_MTE2', 'PIPE_MTE3')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_file(path):
    raw = path.read_bytes()
    data = gzip.decompress(raw) if path.suffix == '.gz' else raw
    return json.loads(data), sha(raw), sha(data)


def chains_of(index):
    """Same maximal one-successor/one-predecessor contraction as gap_candidate."""
    chains, seen = [], set()
    for root in index.order:
        if root in seen:
            continue
        chain, u = [], root
        while True:
            assert u not in seen
            seen.add(u)
            chain.append(u)
            if len(index.succ[u]) != 1:
                break
            v = next(iter(index.succ[u]))
            if len(index.pred[v]) != 1:
                break
            u = v
        chains.append(chain)
    assert len(seen) == len(index.ops)
    return chains


def audit_cell(number, graph, plan, result, ledger, hashes):
    index = DAGIndex(graph)
    schedules = plan['core_schedules']
    assert len(schedules) == 5 and result['num_cores'] == 5
    subgraph_owner = {}
    for c, row in enumerate(schedules):
        for sg in row:
            assert sg not in subgraph_owner
            subgraph_owner[sg] = c
    mapping = {int(u): sg for u, sg in plan['node_to_subgraph'].items()}
    assert set(mapping) == set(index.ops)
    owner = {u: subgraph_owner[sg] for u, sg in mapping.items()}
    assert set(owner) == set(index.ops)
    work = [{p: 0 for p in PIPES} for _ in range(5)]
    totals = dict.fromkeys(PIPES, 0)
    for u, c in owner.items():
        pipe, d = index.ops[u]['pipe'], index.duration(u)
        work[c][pipe] += d
        totals[pipe] += d
    chains = chains_of(index)
    component_sizes = [len(comp) for comp in index.components]
    component_owner_counts = [len({owner[u] for u in comp}) for comp in index.components]
    lengths = [len(ch) for ch in chains]
    chain_works = [sum(index.duration(u) for u in ch) for ch in chains]
    chain_pipe_max = {p: max((sum(index.duration(u) for u in ch if index.ops[u]['pipe'] == p)
                              for ch in chains), default=0) for p in PIPES}
    split = sum(len({owner[u] for u in ch}) > 1 for ch in chains)
    split_ops = sum(len(ch) for ch in chains if len({owner[u] for u in ch}) > 1)
    cross_tensor = 0
    tensor_pairs = 0
    for tid in index.tensors:
        ps, cs = index.producers.get(tid, set()), index.consumers.get(tid, set())
        source_cores = {owner[u] for u in ps}
        target_cores = {owner[u] for u in cs}
        if source_cores and target_cores and any(a != b for a in source_cores for b in target_cores):
            cross_tensor += 1
            tensor_pairs += len({(tid, a, b) for a in source_cores for b in target_cores if a != b})
    import math
    balanced_lb = max(math.ceil(totals[p] / 5) for p in PIPES)
    actual_peak = max(work[c][p] for c in range(5) for p in PIPES)
    makespan = result['makespan']
    assert isinstance(makespan, int) and makespan >= actual_peak
    if ledger.get('graph_sha256') != hashes['graph_sha256']:
        raise ValueError(f'{number:03d}: raw graph SHA differs from ledger')
    return {
        'case': f'{number:03d}', 'source_sha256': hashes,
        'strategy': ledger['detail'].get('selected_strategy'),
        'selected': ledger['detail'].get('selected'),
        'makespan_cycles': makespan,
        'added_ddr_bytes': result['data_movement_bytes'].get('added_copy_bytes'),
        'eligible_ops': len(index.ops), 'component_count': len(index.components),
        'largest_component_ops': max(component_sizes),
        'multi_core_component_count': sum(n > 1 for n in component_owner_counts),
        'chain_count': len(chains),
        'chain_length_max': max(lengths), 'chain_length_median': statistics.median(lengths),
        'chain_total_work_max': max(chain_works), 'chain_pipe_work_max': chain_pipe_max,
        'split_chain_count': split, 'split_chain_ops': split_ops,
        'used_compute_cores': sum(any(work[c].values()) for c in range(5)),
        'pipe_work_by_core': work, 'total_pipe_work': totals,
        'balanced_compute_lb_cycles': balanced_lb,
        'current_compute_peak_cycles': actual_peak,
        'makespan_minus_compute_peak_cycles': makespan - actual_peak,
        'compute_peak_minus_balanced_lb_cycles': actual_peak - balanced_lb,
        'cross_tensor_count': cross_tensor, 'cross_tensor_core_pairs': tensor_pairs,
        'official_cross_core_transfer_count': len(result.get('cross_core_transfers', [])),
        'selected_detail': {'active_cores': ledger['detail'].get('baseline_detail', {}).get('active_cores'),
                            'shared_external_bytes': ledger['detail'].get('baseline_detail', {}).get('shared_external_bytes')},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cases-zip', type=Path, default=DEFAULT_ZIP)
    ap.add_argument('--archive', type=Path, default=DEFAULT_ARCHIVE)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--verify-report', action='store_true', help='verify saved identities without DAG indexing')
    args = ap.parse_args()
    if args.verify_report:
        report_path = args.out/'report.json'
        report_bytes = report_path.read_bytes()
        report = json.loads(report_bytes)
        checks = 0
        source_zip = zipfile.ZipFile(args.cases_zip)
        for row in report['cells']:
            n = row['case']
            raw_graph = source_zip.read(f'data/case_{n}.json')
            cell = next(args.archive.glob(f'cases-*/{n}-k5'))
            hashes = row['source_sha256']
            receipt = json.loads((cell/'cell.json').read_bytes())
            run = json.loads((cell/'run.json').read_bytes())
            ledger = json.loads((cell/'online-ledger.json').read_bytes())
            plan, plan_gz, plan_json = read_file(cell/'plan.json.gz')
            result, result_gz, result_json = read_file(cell/'result.json.gz')
            assert plan and result
            expected = (
                (hashes['graph_sha256'], sha(raw_graph)),
                (hashes['graph_sha256'], receipt['graph_sha256']),
                (hashes['graph_sha256'], run['accepted_row']['graph_sha256']),
                (hashes['graph_sha256'], ledger['graph_sha256']),
                (hashes['plan_json_sha256'], receipt['plan_sha256']),
                (hashes['plan_json_sha256'], run['accepted_row']['plan_sha256']),
                (hashes['plan_json_sha256'], ledger['plan_sha256']),
                (hashes['result_json_sha256'], receipt['official']['result_sha256']),
                (hashes['result_json_sha256'], run['accepted_row']['official']['result_sha256']),
                (hashes['plan_gz_sha256'], plan_gz),
                (hashes['plan_json_sha256'], plan_json),
                (hashes['result_gz_sha256'], result_gz),
                (hashes['result_json_sha256'], result_json),
            )
            if any(a != b for a, b in expected):
                raise ValueError(f'identity mismatch for {n}')
            checks += len(expected)
        source_zip.close()
        receipt = {'status': 'ok', 'scope': 'saved bytes and frozen identities only; no DAG or scoring',
                   'cell_count': len(report['cells']), 'identity_checks': checks,
                   'report_sha256': sha(report_bytes), 'archive': str(args.archive),
                   'actual_cases_zip_argument': str(args.cases_zip),
                   'note': 'raw graph bytes, saved plan/result bytes and cell/run/ledger frozen identities were checked; no DAG indexing'}
        (args.out/'identity-readback.json').write_text(json.dumps(receipt, indent=2)+'\n')
        print(json.dumps(receipt, indent=2))
        return
    cells = sorted(args.archive.glob('cases-*/*-k5'))
    if len(cells) != 100:
        raise ValueError(f'expected exactly 100 K5 cells, got {len(cells)}')
    rows = []
    with zipfile.ZipFile(args.cases_zip) as z:
        for cell in cells:
            number = int(cell.name.split('-')[0])
            raw_graph = z.read(f'data/case_{number:03d}.json')
            graph = json.loads(raw_graph)
            plan, plan_file_sha, plan_json_sha = read_file(cell/'plan.json.gz')
            result, result_file_sha, result_json_sha = read_file(cell/'result.json.gz')
            ledger, ledger_file_sha, _ = read_file(cell/'online-ledger.json')
            hashes = {'graph_sha256': sha(raw_graph), 'plan_gz_sha256': plan_file_sha,
                      'plan_json_sha256': plan_json_sha, 'result_gz_sha256': result_file_sha,
                      'result_json_sha256': result_json_sha, 'ledger_sha256': ledger_file_sha}
            rows.append(audit_cell(number, graph, plan, result, ledger, hashes))
            del graph, plan, result, ledger, raw_graph
            gc.collect()
    if [r['case'] for r in rows] != [f'{n:03d}' for n in range(1, 101)]:
        raise ValueError('K5 case coverage is incomplete or duplicated')
    def summary(key):
        vals = [r[key] for r in rows]
        return {'min': min(vals), 'median': statistics.median(vals), 'max': max(vals)}
    aggregate = {
        'count': len(rows), 'strategy_counts': dict(Counter(r['strategy'] for r in rows)),
        'split_chain_count': summary('split_chain_count'),
        'component_count': summary('component_count'),
        'multi_core_component_count': summary('multi_core_component_count'),
        'used_compute_cores': summary('used_compute_cores'),
        'chain_total_work_max': summary('chain_total_work_max'),
        'compute_peak_minus_balanced_lb_cycles': summary('compute_peak_minus_balanced_lb_cycles'),
        'makespan_minus_compute_peak_cycles': summary('makespan_minus_compute_peak_cycles'),
        'cross_tensor_count': summary('cross_tensor_count'),
    }
    report = {'scope': 'frozen saved K5 originals only; no solver/evaluator',
              'source_cases_zip': 'data/raw/a/official-cases.zip',
              'source_archive': 'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee',
              'definitions': {
                  'eligible': 'original ops excluding COPY_IN and COPY_OUT; contracted precedence from DAGIndex',
                  'chain': 'maximal directed path whose internal edges have outdegree/in-degree one',
                  'work': 'sum max(1, original cycles) by original pipe; excludes prepared COPY and spill',
                  'balanced_compute_lb': 'max over original pipes of ceil(total original pipe work/5); hypothetical only',
                  'residual': 'Makespan minus maximum per-core original pipe work; descriptive, not waiting attribution',
                  'cross_tensor': 'physical tensor with original producer and consumer on differing cores',
              }, 'aggregate': aggregate, 'cells': rows}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(aggregate, indent=2))


if __name__ == '__main__':
    main()
