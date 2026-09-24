"""Read-only target graph diagnostics, no plans/scores/evaluator calls."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.q1.sink_peel import peel_packets
from stub_multicore_cut_and_schedule import _build_op_adjacency, _contract_excluded_copy_nodes


def sha(data):
    return hashlib.sha256(data).hexdigest()


def scan():
    archive = ROOT / 'data/raw/a/official-cases.zip'
    code = ROOT / 'src/q1/sink_peel.py'
    rows = []
    with zipfile.ZipFile(archive) as z:
        for case in ('005','016','024','047','048','051','064','069','071','075','082','085','086'):
            member = 'data/case_' + case + '.json'
            raw = z.read(member)
            graph = json.loads(raw)
            ops = {o['id']: o for o in graph['ops'] if o['op'] not in ('COPY_IN','COPY_OUT')}
            _, full = _build_op_adjacency(graph)
            pred, succ = _contract_excluded_copy_nodes(sorted(ops), full)
            waves = peel_packets(ops, pred, succ)
            rows.append({'case_id': case, 'input_member': member, 'input_sha256': sha(raw),
                         'compute_ops': len(ops), 'edges': sum(map(len, succ.values())),
                         'sink_count': sum(not succ[u] for u in ops),
                         'wave_count': len(waves),
                         'useful_parallel_packets': any(len(w) > 1 for w in waves),
                         'k4_task_count_upper_bound': sum(min(4, len(w)) for w in waves),
                         'waves': [{'packets': len(w), 'packet_ops': sorted(map(len,w)),
                                    'work': sum(max(1,ops[u]['cycles']) for p in w for u in p)}
                                   for w in waves]})
    return {'kind': 'static-graph-structure-not-performance',
            'base_commit': '05f8fa0f7e52f5914f14815f6bdbcb851b631556',
            'archive_sha256': sha(archive.read_bytes()),
            'code_sha256': sha(code.read_bytes()), 'scan_script_sha256': sha(Path(__file__).read_bytes()),
            'evaluator_calls': {'E0': 0, 'E1': 0, 'E2': 0},
            'task_compilation_calls': 0, 'public_case_solver_calls': 0,
            'plans_generated': 0, 'parameters': {'max_rounds': 64, 'max_sinks': 64},
            'rows': rows}


if __name__ == '__main__':
    output = Path(__file__).with_name('static_structure.json')
    with output.open('x') as f:
        json.dump(scan(), f, indent=2)
        f.write('\n')
