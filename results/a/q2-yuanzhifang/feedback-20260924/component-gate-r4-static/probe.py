"""Two saved-plan diagnostics only; never builds a new algorithm plan or runs E0."""
import argparse
import gzip
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from src.q2.feedback.component_gate import consider_alternative
from src.q2.feedback.tensor_packet import TensorIndex


def load(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    base = ROOT / 'results/a/q2-yuanzhifang/feedback-20260924'
    prior = load(base / 'component-ddr-static/static.json')
    frontier = {r['case_id']: r for r in load(base / 'full-coverage/frontier-k5-100/coverage.json')['rows']}
    rows = {}
    for case in ('020', '045'):
        old = prior['cases'][case]['tensor_packet']
        arun = load(ROOT / old['run_path'])
        brun = load(ROOT / frontier[case]['run_path'])
        a_path = ROOT / old['plan_path']
        b_path = (ROOT / frontier[case]['run_path']).parent / f'case_{case}_multicore_res.json'
        graph_path = ROOT / f'data/raw/a/official/data/case_{case}.json'
        assert sha(graph_path) == arun['identity']['graph_sha256'] == brun['identity']['graph_sha256']
        assert sha(a_path) == arun['identity']['plan_sha256']
        assert sha(b_path) == brun['identity']['plan_sha256']
        config_path = ROOT / 'data/raw/a/official/data/config.txt'
        assert sha(config_path) == arun['identity']['config_sha256'] == brun['identity']['config_sha256']
        graph, a, b = load(graph_path), load(a_path), load(b_path)
        cfg = prior['config']
        decision = consider_alternative(TensorIndex(graph), a, b, cfg['bandwidth'], cfg['capacity'])
        for which, run in [('A', arun), ('B', brun)]:
            artifact = run['artifacts']['result']
            result_path = ROOT / artifact['path']
            assert sha(result_path) == artifact['sha256']
            movement = load(result_path)['data_movement_bytes']
            assert decision[which]['base_copy_bytes'] == movement['scheduled_copy_bytes'] - movement['spill_added_copy_bytes']
        rows[case] = {'A_saved_plan': str(a_path.relative_to(ROOT).as_posix()),
                      'B_saved_F1_plan': str(b_path.relative_to(ROOT).as_posix()),
                      'A_plan_sha256': sha(a_path), 'B_plan_sha256': sha(b_path),
                      'graph_sha256': sha(graph_path), 'config_sha256': sha(config_path),
                      'decision': decision, 'base_bytes_match_saved_results': True}
    sources = ['src/q2/feedback/component_gate.py', 'src/q2/feedback/construct.py',
               'src/q2/feedback/tensor_packet.py', 'src/q2/feedback/physical_frontier.py']
    report = {'created_at': datetime.now(timezone.utc).isoformat(),
              'scope': 'Two saved A/F1 pairs; not new solver output, E0 result, or machine theorem',
              'real_solver_calls': 0, 'Step2_calls': 0, 'Step3_calls': 0, 'E0_calls': 0,
              'source_hashes': {p: sha(ROOT / p) for p in sources},
              'probe_sha256': sha(Path(__file__)), 'cases': rows,
              'wall_seconds': time.perf_counter() - started}
    with args.output.open('x', encoding='utf-8', newline='\n') as out:
        json.dump(report, out, indent=2, ensure_ascii=False)
        out.write('\n')
    print(json.dumps({'cases': {c: {'trigger': r['decision']['choose_alternative'],
                                  'U_A': r['decision']['ideal_U_A'], 'L_B': r['decision']['ideal_L_B']}
                               for c, r in rows.items()}, 'wall_seconds': report['wall_seconds']}))


if __name__ == '__main__':
    main()
