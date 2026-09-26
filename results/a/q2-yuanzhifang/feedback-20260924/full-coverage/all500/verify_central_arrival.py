"""Read-only HTTP comparison of this fixed matrix with its admitted records."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = 'e64723bdf99669c44f76d8e90ab0379a8578522e'
    table_path = Path(__file__).with_name('per-cell.csv')
    with table_path.open(encoding='utf-8', newline='') as handle:
        table = {(row['case_id'], int(row['cores'])): row for row in csv.DictReader(handle)}
    assert len(table) == 500
    raw = urllib.request.urlopen(args.url, timeout=25).read()
    data = json.loads(raw)
    observed = datetime.now(timezone.utc).isoformat()
    seen, checked = set(), []
    for cell in data['cells']:
        record = cell.get('best')
        assert record and record['status'] == 'ok' and record['eligible'] is True
        assert record['problem'] == 'P2' and record['algorithm_id'] == 'q2-tensor-packet'
        assert record['solver_commit'] == source
        key = (record['case_id'], record['cores'])
        assert key in table and key not in seen
        seen.add(key)
        saved = table[key]
        assert record['metrics']['makespan_cycles'] == float(saved['makespan_cycles'])
        assert record['artifacts']['run']['path'] == saved['run_path']
        assert record['artifacts']['result']['sha256'] == saved['result_sha256']
        assert record['baseline_verified'] is True
        ratio = float(saved['baseline_cycles']) / float(saved['makespan_cycles'])
        assert abs(record['metrics']['baseline_speedup'] - ratio) < 1e-12
        checked.append({
            'case_id': key[0], 'cores': key[1], 'record_id': record['id'],
            'attempt_id': record['attempt_id'], 'run_id': record['run_id'],
            'run_path': saved['run_path'], 'result_sha256': saved['result_sha256'],
            'makespan_cycles': record['metrics']['makespan_cycles'],
            'baseline_speedup': ratio,
        })
    assert seen == set(table)
    by_core = {}
    for core in range(1, 6):
        rows = [row for row in checked if row['cores'] == core]
        assert len(rows) == 100
        by_core[str(core)] = {
            'count': len(rows),
            'arithmetic_mean_B_over_M': sum(row['baseline_speedup'] for row in rows) / len(rows),
            'exactly_one': sum(row['baseline_speedup'] == 1 for row in rows),
        }
    runtime = data['runtime']
    output = {
        'observed_at': observed, 'endpoint': args.url,
        'response_sha256': hashlib.sha256(raw).hexdigest(),
        'api_as_of': data['as_of'], 'all_board_record_count': data['record_count'],
        'snapshot_id': runtime.get('snapshot_id'), 'snapshot_generated_at': runtime.get('generated_at'),
        'solver_commit': source, 'matched': len(checked), 'mismatches': 0,
        'scope': 'Read-only match of HTTP admitted records to the saved fixed matrix; no evaluator calls or new signature verification.',
        'run_ids': sorted({row['run_id'] for row in checked}),
        'by_core': by_core, 'checked': sorted(checked, key=lambda row: (row['cores'], row['case_id'])),
    }
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: output[key] for key in ('snapshot_id', 'matched', 'mismatches', 'by_core')}))


if __name__ == '__main__':
    main()
