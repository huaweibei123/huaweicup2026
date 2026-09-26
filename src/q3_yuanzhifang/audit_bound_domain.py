"""Read frozen graph bytes and audit bound assumptions; no solution or evaluator."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_SHA = '975cefc85ecc34d529c8f3f4798e9b86a099ea65ede69595708ea40aad0da264'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--graph-dir', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    started_at, started = utc(), time.perf_counter()
    source = Path(__file__).resolve()
    path = source.relative_to(ROOT).as_posix()
    commit = subprocess.check_output(['git', 'log', '-1', '--format=%H', '--', path], cwd=ROOT).decode().strip()
    if subprocess.check_output(['git', 'show', commit+':'+path], cwd=ROOT) != source.read_bytes():
        raise ValueError('freeze audit source before execution')
    raw_manifest = (ROOT / 'docs/a/source-manifest.json').read_bytes()
    if sha(raw_manifest) != MANIFEST_SHA:
        raise ValueError('source manifest differs from previous fixed analysis')
    manifest = json.loads(raw_manifest)
    rows = []
    for item in manifest['files']:
        if not item['path'].startswith('data/case_'):
            continue
        file = args.graph_dir / Path(item['path']).name
        raw = file.read_bytes()
        if sha(raw) != item['sha256'] or len(raw) != item['bytes']:
            raise ValueError('official graph identity mismatch: '+file.name)
        graph = json.loads(raw)
        ops = {op['id']: op for op in graph['ops']}
        tensors = {tensor['id']: tensor for tensor in graph['tensors']}
        producers = defaultdict(set)
        for edge in graph['edges']:
            if edge['source'] in ops and edge['target'] in tensors:
                producers[edge['target']].add(edge['source'])
        multiple = {str(t): sorted(values) for t, values in producers.items() if len(values) > 1}
        bad_ops = [u for u, op in ops.items() if op['op'] not in ('COPY_IN', 'COPY_OUT') and
                   (op['pipe'] not in ('PIPE_M', 'PIPE_V') or type(op['cycles']) is not int or op['cycles'] < 0)]
        rows.append(dict(case_id=file.stem.split('_')[1], graph_sha256=sha(raw), graph_bytes=len(raw),
                         tensors=len(tensors), maximum_original_producers=max(map(len, producers.values()), default=0),
                         multiple_original_producers=multiple, original_compute_guard_violations=bad_ops,
                         original_logical_tid_count=sum('logical_tid' in t for t in tensors.values()),
                         zero_size_tensors=sum(t['size'] == 0 for t in tensors.values()),
                         unique_original_producer_guard=not multiple, computation_guard=not bad_ops))
    if len(rows) != 100 or len({r['case_id'] for r in rows}) != 100:
        raise ValueError('the frozen 100-case domain was not fully audited')
    result = dict(schema='q3-bound-domain-audit-v1', source_commit=commit, source_path=path,
                  source_sha256=sha(source.read_bytes()), source_manifest_sha256=MANIFEST_SHA,
                  started_at=started_at, finished_at=utc(), analysis_wall_seconds=time.perf_counter()-started,
                  calls=dict(solver=0, E0=0, E1=0, E2=0), workers=1,
                  method='Hash each original JSON and count original op-to-tensor producer sets, including COPY nodes.',
                  all_unique_producer_guards_pass=all(r['unique_original_producer_guard'] for r in rows),
                  all_computation_guards_pass=all(r['computation_guard'] for r in rows), rows=rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write('\n')
    print(json.dumps({key: result[key] for key in ('source_commit', 'analysis_wall_seconds',
        'all_unique_producer_guards_pass', 'all_computation_guards_pass', 'calls')}))


if __name__ == '__main__':
    main()
