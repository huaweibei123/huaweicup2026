"""One structural pass over frozen cases, no E0/E1/E2 or final score claims."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from .construct import ROOT
from .tensor_packet import TensorIndex
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cores', type=int, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    start = time.perf_counter()
    started = datetime.now(timezone.utc).isoformat()
    config_path = ROOT / 'data/raw/a/official/data/config.txt'
    config = {**read_evaluation_config(config_path), **read_scene_b_config(config_path)}
    manifest = json.loads((ROOT / 'docs/a/source-manifest.json').read_bytes())
    expected = {r['path']: r['sha256'] for r in manifest['files']}
    assert hashlib.sha256(config_path.read_bytes()).hexdigest() == expected['data/config.txt']
    rows = []
    for number in range(1, 101):
        case = f'{number:03d}'
        raw = (ROOT / f'data/raw/a/official/data/case_{case}.json').read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == expected[f'data/case_{case}.json']
        begun = time.perf_counter()
        index = TensorIndex(json.loads(raw))
        plan, meta = index.build_tensor_plan(args.cores, config['bandwidth'], config['cross_core_copy_delay_cycles'])
        serialized = (json.dumps(plan, separators=(',', ':')) + '\n').encode()
        rows.append({'case_id': case, 'cores': args.cores, 'graph_sha256': digest,
                     'plan_sha256': hashlib.sha256(serialized).hexdigest(),
                     'in_process_construct_seconds': time.perf_counter() - begun,
                     'details': meta})
    result = {'scope': 'One in-process structural construction per graph; plans not retained, no scores or E0/E1/E2; timings exclude process start and are not solver benchmark walls',
              'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
              'wall_seconds': time.perf_counter() - start, 'constructed': len(rows),
              'new_E0_calls': 0, 'new_E1_calls': 0, 'new_E2_calls': 0,
              'config_sha256': expected['data/config.txt'],
              'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                for name in ['src/q2/feedback/construct.py', 'src/q2/feedback/tensor_packet.py', 'src/q2/feedback/scan_tensor_packet.py']},
              'routes': dict(Counter(row['details']['selected'] for row in rows)), 'rows': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write('\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'rows'}))


if __name__ == '__main__':
    main()
