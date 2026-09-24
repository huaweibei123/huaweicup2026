"""Read-only graph diagnostics; no official evaluation or performance scoring."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time

from .direct import Index, UnsupportedStructure


def inspect(path, cores):
    raw = path.read_bytes()
    index = Index(json.loads(raw))
    work = {p: sum(index.duration(u) for u, o in index.ops.items() if o['pipe'] == p)
            for p in ('PIPE_M', 'PIPE_V')}
    end = {}
    for u in index.order:
        end[u] = index.duration(u) + max((end[v] for v in index.pred[u]), default=0)
    critical = max(end.values(), default=0)
    try:
        guard = {'supported': True, 'parameters': index.word_descriptor()}
    except UnsupportedStructure as error:
        guard = {'supported': False, 'reason': str(error)}
    return {'graph_file': path.name,
            'graph_sha256': hashlib.sha256(raw).hexdigest(),
            'ops': len(index.ops), 'components': len(index.components),
            'max_component_ops': max(map(len, index.components), default=0),
            'guard': guard, 'cores': cores, 'compute_work': work,
            'contracted_compute_path': critical,
            'lower_bound_cycles': max(critical, math.ceil(max(work.values()) / cores))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph_directory', type=Path)
    parser.add_argument('--cores', type=int, default=4)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.cores < 1:
        parser.error('cores must be positive')
    started = time.perf_counter()
    records = [inspect(p, args.cores) for p in sorted(args.graph_directory.glob('case_*.json'))]
    data = {'scope': 'static only; no E0/E1/E2; not a holdout', 'records': records,
            'wall_seconds': time.perf_counter() - started}
    with args.output.open('x') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
