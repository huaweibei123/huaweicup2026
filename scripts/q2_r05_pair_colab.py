"""Package frozen R05 pair locally, or run its one-shot CPU capsule on Colab."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

NAME = 'q2-r05-pair-20260925'
COLAB = Path('/content')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def pack(official_root, capsule):
    root = Path(__file__).resolve().parents[1]
    official_root = official_root.resolve(strict=True)
    source_manifest = official_root.parents[3] / 'docs/a/source-manifest.json'
    manifest = json.loads(source_manifest.read_bytes())
    official = {x['path']: x for x in manifest['files']}
    official_names = ['data/config.txt', 'data/case_003.json'] + sorted(
        p for p in official if p.startswith('code/') and p.endswith('.py'))
    if len(official_names) != 12:
        raise ValueError('Expected config, 003 graph and ten official code files')
    files = {}
    for name in official_names:
        raw = (official_root / name).read_bytes()
        if sha(raw) != official[name]['sha256'] or len(raw) != official[name]['bytes']:
            raise ValueError('Official source mismatch: ' + name)
        files['data/raw/a/official/' + name] = raw
    files['docs/a/source-manifest.json'] = source_manifest.read_bytes()
    plans = {
        'seed': root / 'results/a/q2-nikolastarx/pro-r04-review-20260925/static-003-k2/seed-plan.json.gz',
        'recovered': root / 'results/a/q2-nikolastarx/pro-r05-recovered-20260925/recovered-raw-plan.json.gz',
    }
    source_plans = {}
    for label, path in plans.items():
        raw = path.read_bytes()
        plan = json.loads(gzip.decompress(raw))
        if set(plan) != {'node_to_subgraph', 'core_schedules'} or len(plan['core_schedules']) != 2:
            raise ValueError('Wrong saved plan: ' + label)
        files[f'plans/{label}.json.gz'] = raw
        source_plans[label] = {'path': path.relative_to(root).as_posix(), 'sha256': sha(raw)}
    for name in ('scripts/q2_r05_pair_colab.py', 'scripts/q2_r05_pair_worker.py',
                 'src/q2_nikolastarx/evaluate_feedback.py', 'pyproject.toml', 'uv.lock'):
        files[name] = (root / name).read_bytes()
    doc = {'schema': 'q2-r05-pair-v1', 'case': '003', 'cores': 2,
           'scope': 'saved-plan proxy-rejection audit; no online solver',
           'order': ['seed', 'recovered'], 'source_plans': source_plans,
           'official_source_manifest_sha256': sha(files['docs/a/source-manifest.json']),
           'official_code_hash': manifest['official_code_hash'],
           'limits': {'workers': 1, 'E0': 2, 'E2': 0, 'retries': 0,
                      'stage_seconds': 180, 'batch_seconds': 360,
                      'rss_bytes': 4 << 30, 'child_file_bytes': 64 << 20},
           'files': {name: sha(raw) for name, raw in sorted(files.items())}}
    files['manifest.json'] = encoded(doc)
    out_dir = root / 'results/a/q2-nikolastarx/pro-r05-pair-pilot-20260925'
    out_dir.mkdir(parents=True, exist_ok=True)
    capsule = capsule.resolve()
    capsule.parent.mkdir(parents=True, exist_ok=True)
    if capsule.exists():
        raise FileExistsError('Refusing to overwrite prepared capsule')
    with zipfile.ZipFile(capsule, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            item = zipfile.ZipInfo(name, date_time=(2026, 9, 25, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, raw)
    (out_dir / 'manifest.json').write_bytes(files['manifest.json'])
    prepared = {'status': 'prepared_only', 'capsule_path': capsule.relative_to(root).as_posix(),
                'capsule_sha256': sha(capsule.read_bytes()), 'capsule_bytes': capsule.stat().st_size,
                'manifest_sha256': sha(files['manifest.json']),
                'controller_sha256': sha(files['scripts/q2_r05_pair_colab.py']),
                'worker_sha256': sha(files['scripts/q2_r05_pair_worker.py']),
                'dispatch_state': 'not_dispatched',
                'calls_authority_when_run': 'output/batch.json'}
    (out_dir / 'prepared.json').write_bytes(encoded(prepared))
    print(json.dumps(prepared))


def run():
    capsule = COLAB / (NAME + '.zip')
    expected = os.environ['P2_R05_PAIR_SHA256']
    if sha(capsule.read_bytes()) != expected:
        raise ValueError('Uploaded capsule SHA mismatch')
    root = COLAB / NAME
    root.mkdir(exist_ok=False)
    with zipfile.ZipFile(capsule) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate capsule entries')
        for name in names:
            target = (root / name).resolve()
            if not target.is_relative_to(root.resolve()):
                raise ValueError('Unsafe capsule member')
        archive.extractall(root)
    manifest = json.loads((root / 'manifest.json').read_bytes())
    for name, expected_hash in manifest['files'].items():
        if sha((root / name).read_bytes()) != expected_hash:
            raise ValueError('Capsule file drift: ' + name)
    preparation = {'status': 'preparing', 'capsule_sha256': expected,
                   'stages': [], 'calls_authority': 'output/batch.json',
                   'dispatch_state': 'not_dispatched'}
    def save():
        (root / 'preparation.json').write_bytes(encoded(preparation))
    def command(label, argv, timeout, env=None):
        begin = time.perf_counter()
        p = subprocess.run(argv, cwd=root, capture_output=True, text=True,
                           timeout=timeout, env=env)
        (root / f'{label}-stdout.txt').write_text(p.stdout)
        (root / f'{label}-stderr.txt').write_text(p.stderr)
        preparation['stages'].append({'name': label, 'returncode': p.returncode,
                                      'wall_seconds': time.perf_counter() - begin})
        save()
        if p.returncode:
            raise RuntimeError(label + ' failed')
    save()
    output = COLAB / (NAME + '-output')
    try:
        tools = root / 'runtime-tools'
        command('uv-bootstrap', [sys.executable, '-m', 'pip', 'install', '--target', str(tools),
                                 'uv==0.11.15'], 120)
        env = dict(os.environ, PYTHONPATH=str(tools), UV_CACHE_DIR=str(root / 'uv-cache'),
                   UV_PYTHON_INSTALL_DIR=str(root / 'uv-python'))
        command('uv-sync', [sys.executable, '-m', 'uv', 'sync', '--locked', '--python', '3.12'],
                240, env)
        preparation['status'] = 'running'
        preparation['dispatch_state'] = 'worker_dispatched'
        save()
        command('pair-worker', [str(root / '.venv/bin/python'), '-B',
                                str(root / 'scripts/q2_r05_pair_worker.py'),
                                '--output', str(output)], 370)
        preparation['status'] = 'completed'
    except BaseException as error:
        preparation.update(status='stopped', error=repr(error))
        raise
    finally:
        save()
        result_zip = COLAB / (NAME + '-results.zip')
        with zipfile.ZipFile(result_zip, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
            if output.exists():
                for path in output.rglob('*'):
                    if path.is_file():
                        archive.write(path, 'output/' + path.relative_to(output).as_posix())
            for path in root.iterdir():
                if path.is_file() and path.suffix in ('.json', '.txt'):
                    archive.write(path, 'preparation/' + path.name)
        print(json.dumps({'status': preparation['status'], 'results_sha256':
                          sha(result_zip.read_bytes()), 'results_bytes': result_zip.stat().st_size}))


if __name__ == '__main__' and os.environ.get('P2_R05_PAIR_MODE') == 'run':
    # colab exec injects a cell: no __file__ and kernel-owned sys.argv.
    run()
elif __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', nargs='?', choices=('pack', 'run'))
    p.add_argument('--official-root', type=Path)
    p.add_argument('--capsule', type=Path)
    args = p.parse_args()
    mode = args.mode or os.environ.get('P2_R05_PAIR_MODE')
    if mode == 'pack':
        if args.official_root is None or args.capsule is None:
            p.error('pack requires --official-root and --capsule')
        pack(args.official_root, args.capsule)
    elif mode == 'run' and args.official_root is None and args.capsule is None:
        run()
    else:
        p.error('specify pack or run; P2_R05_PAIR_MODE=run is accepted for Colab')
