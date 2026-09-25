"""Recover the rejected r05 raw plan from frozen starts/owner metadata only.

No matching/rebuild, Step2, E0 or E2 call. Requires the original witness,
seed mapping, and graph; SHA checks prevent mixing runs.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import derive_multicore_plan
from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_gzip(path):
    raw = Path(path).read_bytes()
    decoded = gzip.decompress(raw)
    return json.loads(decoded), digest(decoded), digest(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--out', type=Path,
                        default=ROOT / 'results/a/q2-nikolastarx/pro-r05-recovered-20260925')
    args = parser.parse_args()
    base = ROOT / 'results/a/q2-nikolastarx'
    evidence = base / 'pro-r05-probe-20260925/run-v2'
    seed_dir = base / 'pro-r04-review-20260925/static-003-k2'
    result_path = evidence / 'result.json'
    result_raw = result_path.read_bytes()
    result = json.loads(result_raw)
    witness_path = seed_dir / 'seed-witness.json.gz'
    seed_path = seed_dir / 'seed-plan.json.gz'
    witness, witness_sha, witness_gz_sha = read_gzip(witness_path)
    seed, seed_sha, seed_gz_sha = read_gzip(seed_path)
    returned_seed, _, returned_gz_sha = read_gzip(evidence / 'plan.json.gz')
    graph_raw = args.graph.read_bytes()
    graph = json.loads(graph_raw)
    assert digest(graph_raw) == result['graph_sha256']
    config_raw = args.config.read_bytes()
    assert digest(config_raw) == result['config_sha256']
    from evaluation_validation import read_evaluation_config
    config = read_evaluation_config(args.config)
    assert seed_sha == result['seed_plan_sha256']
    assert witness_sha == result['seed_witness_sha256']
    assert returned_seed == seed and result['detail']['returned'] == 'seed'
    assert returned_gz_sha == result['plan_gzip_sha256']
    source = ROOT / 'src/q2_nikolastarx/ready_exchange.py'
    assert digest(source.read_bytes()) == result['source_sha256']['src/q2_nikolastarx/ready_exchange.py']
    adapter_at_commit = subprocess.check_output(
        ['git', 'show', result['source_commit'] + ':src/q2_nikolastarx/ready_exchange_candidate.py'],
        cwd=ROOT)
    adapter_sha = digest(adapter_at_commit)
    assert adapter_sha == result['source_sha256']['src/q2_nikolastarx/ready_exchange_candidate.py']
    index = DAGIndex(graph)
    packets = []
    for chain in witness['chains']:
        run, pipe = [], None
        for u in chain:
            new_pipe = index.ops[u]['pipe']
            assert new_pipe in {'PIPE_M', 'PIPE_V'}
            if run and new_pipe != pipe:
                packets.append(run)
                run = []
            run.append(u)
            pipe = new_pipe
        if run:
            packets.append(run)
    detail = result['detail']
    assert len(packets) == detail['packet_count']
    flat = [u for packet in packets for u in packet]
    assert len(flat) == len(set(flat)) == len(index.ops)
    assert set(flat) == set(index.ops)
    owner = {int(k): v for k, v in detail['rebuilt_owner'].items()}
    starts = {int(k): v for k, v in detail['rebuilt_starts'].items()}
    assert set(owner) == set(range(len(packets)))
    assert set(starts) == set(index.ops)
    assert all(type(s) is int and s >= 0 for s in starts.values())
    op_owner = {u: owner[j] for j, packet in enumerate(packets) for u in packet}
    cores = len(seed['core_schedules'])
    assert all(type(c) is int and 0 <= c < cores for c in op_owner.values())
    mapping = seed['node_to_subgraph']
    assert set(map(int, mapping)) == set(index.ops)
    rows = [[] for _ in range(cores)]
    for u in sorted(index.ops, key=lambda u: (starts[u], u)):
        rows[op_owner[u]].append(mapping[str(u)])
    plan = {'node_to_subgraph': dict(mapping), 'core_schedules': rows}
    derive_multicore_plan(graph, plan)
    bytes_rebuilt = mandatory_copy_work(graph, plan, config['bandwidth'])['transfer_bytes']
    assert bytes_rebuilt == detail['pre_step2_bytes_rebuilt']
    output = args.out
    output.mkdir(parents=True, exist_ok=True)
    plan_json = (json.dumps(plan, ensure_ascii=False, sort_keys=True,
                            separators=(',', ':')) + '\n').encode()
    plan_path = output / 'recovered-raw-plan.json.gz'
    with plan_path.open('wb') as raw_stream:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw_stream,
                           mtime=0) as stream:
            stream.write(plan_json)
    receipt = {
        'kind': 'artifact_recovery_of_rejected_raw_plan',
        'not_new_constructor_or_score': True,
        'source_commit': result['source_commit'],
        'graph_sha256': result['graph_sha256'],
        'config_sha256': digest(config_raw),
        'run_v2_result_sha256': digest(result_raw),
        'source_ready_exchange_sha256': digest(source.read_bytes()),
        'source_adapter_at_commit_sha256': adapter_sha,
        'seed_witness_json_sha256': witness_sha,
        'seed_witness_gzip_sha256': witness_gz_sha,
        'seed_plan_json_sha256': seed_sha,
        'seed_plan_gzip_sha256': seed_gz_sha,
        'returned_seed_gzip_sha256': returned_gz_sha,
        'packets': len(packets), 'eligible_ops': len(index.ops), 'cores': cores,
        'recovered_plan_json_sha256': digest(plan_json),
        'recovered_plan_gzip_sha256': digest(plan_path.read_bytes()),
        'independent_pre_step2_transfer_bytes': bytes_rebuilt,
        'meta_pre_step2_transfer_bytes': detail['pre_step2_bytes_rebuilt'],
        'checks': ['source hashes', 'witness/packet/op coverage', 'seed mapping',
                   'owner/start coverage', 'official structural derive',
                   'independent mandatory-copy bytes'],
        'scope': 'Recovered discarded raw plan; no E0/E2 result or Makespan claim.',
    }
    (output / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False,
                                                     indent=2, sort_keys=True) + '\n')
    print(json.dumps({'plan': str(plan_path), 'receipt': str(output / 'receipt.json'),
                      'packets': len(packets), 'ops': len(index.ops)}))


if __name__ == '__main__':
    main()
