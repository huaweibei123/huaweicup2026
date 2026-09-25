"""Package fixed Git blobs and three verified old-plan/E0 pairs; no scoring."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[4]
E2 = '603b0741e21c449d3db652ebd67c94f2dc014cc9'
MANIFEST = 'results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json'
HERE = 'results/a/q2-nikolastarx/copyevent-linux-pilot-20260925'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def blob(commit, name):
    return subprocess.check_output(['git', 'show', commit + ':' + name], cwd=ROOT)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--commit', required=True)
    p.add_argument('--raw-root', type=Path, required=True)
    p.add_argument('--old-run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    commit = subprocess.check_output(['git', 'rev-parse', args.commit], cwd=ROOT, text=True).strip()
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', commit,
                                    'src/q2_nikolastarx', 'data/raw/a/official/code'],
                                   cwd=ROOT, text=True).splitlines()
    names = [n for n in names if n.endswith('.py')]
    names += ['pyproject.toml', 'uv.lock', 'README.md', MANIFEST,
              'scripts/e2_linux_native.py', HERE + '/runner.py']
    files = {n: blob(commit, n) for n in names}
    files['fixed-p2-manifest.json'] = files[MANIFEST]
    sources = json.loads(files[MANIFEST])['e2_sources']
    for name, expected in sources.items():
        raw = blob(E2, name)
        if sha(raw) != expected:
            raise ValueError('E2 blob mismatch: ' + name)
        files['e2-src/' + name] = raw
    old = json.loads((args.old_run / 'summary.json').read_bytes())
    assert old['status'] == 'completed' and old['accepted_cells'] == 500
    compare = {}
    for case in ('005', '009', '015'):
        row = next(r for r in old['rows'] if r['case'] == case and r['cores'] == 5)
        graph = (args.raw_root / 'data' / f'case_{case}.json').read_bytes()
        plan = (args.old_run / row['paths']['plan']).read_bytes()
        result = (args.old_run / row['paths']['result']).read_bytes()
        # Completed row fields are the immutable source receipts, not reconstructed scores.
        if sha(graph) != row['graph_sha256']:
            raise ValueError('old graph identity mismatch')
        checks = {'plan_sha256': sha(plan), 'result_sha256': sha(result)}
        for key, digest in checks.items():
            if row.get(key, row['official'].get(key)) != digest:
                raise ValueError('old completed identity mismatch: ' + key)
        files['data/raw/a/official/data/' + f'case_{case}.json'] = graph
        files[f'seeds/{case}-k5.json'] = plan
        files[f'expected/{case}-k5.json'] = result
        compare[case] = {'old_M': json.loads(result)['makespan'],
                         'old_solver_commit': old['solver_commit'], **checks}
    config = (args.raw_root / 'data/config.txt').read_bytes()
    assert sha(config) == row['config_sha256']
    files['data/raw/a/official/data/config.txt'] = config
    manifest = {'scope': 'three-cell Linux E2 validation and cold unified solver pilot',
                'solver_source_commit': commit, 'runner_source_commit': commit,
                'e2_source_commit': E2, 'comparison': compare,
                'old_summary_sha256': sha((args.old_run / 'summary.json').read_bytes()),
                'files': {n: sha(raw) for n, raw in sorted(files.items())}}
    files['capsule-manifest.json'] = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 25, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, raw)
    print(json.dumps({'capsule_sha256': sha(args.output.read_bytes()),
                      'bytes': args.output.stat().st_size, 'files': len(files),
                      'source_commit': commit}))

if __name__ == '__main__':
    main()
