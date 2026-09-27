"""Repackage fixed sources without running any solver or evaluator."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUTPUT = ROOT / 'output/paper-submission-20260927'
PAPER = 'f1e63781adcb6ce7506b5e8297f0213ad57de5bb'


def git_bytes(commit, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{commit}:{path}'])


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    files = {
        'source-code-v10.zip': git_bytes(PAPER, 'paper/manuscript-v1/checkpoints/v13-public/attachments/v10/source-code-v10.zip'),
        'official-cases.zip': git_bytes('6389c68f4c5e7e3003ad79c09253076156b89b36', 'data/raw/a/official-cases.zip'),
        'p2-e2-manifest.json': git_bytes('c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f', 'results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json'),
        'README.md': (HERE / 'BUNDLE-README.md').read_bytes(),
        'MISSING.md': (HERE / 'MISSING.md').read_bytes(),
        'p1-entry-evidence.json': (HERE / 'p1-entry-evidence.json').read_bytes(),
        'data-verification.json': (HERE.parent / 'official-requirements-20260927/data-verification.json').read_bytes(),
    }
    assert sha(files['source-code-v10.zip']) == '1bd41bc1beaefb97b9b2cc9fac72c71103b9933cf497e1841eacf0c95bf219d1'
    assert sha(files['official-cases.zip']) == 'e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528'
    rows = ['sha256\tbytes\tpath']
    for name, raw in sorted(files.items()):
        rows.append(f'{sha(raw)}\t{len(raw)}\t{name}')
        if name.endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                assert z.testzip() is None
                for item in sorted(z.infolist(), key=lambda i: i.filename):
                    assert not Path(item.filename).is_absolute() and '..' not in Path(item.filename).parts
                    if not item.is_dir():
                        data = z.read(item)
                        rows.append(f'{sha(data)}\t{len(data)}\t{name}!/{item.filename}')
    files['FILE-SHA256.tsv'] = ('\n'.join(rows) + '\n').encode()
    (HERE / 'FILE-SHA256.tsv').write_bytes(files['FILE-SHA256.tsv'])
    files['SHA256SUMS'] = ''.join(f'{sha(raw)}  {name}\n' for name, raw in sorted(files.items())).encode()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / 'attachment-a-source-candidate.zip'
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 9, 27, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, raw)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
    digest = sha(target.read_bytes())
    (OUTPUT / 'SHA256SUMS.txt').write_text(f'{digest}  {target.name}\n')
    print(json.dumps({'path': str(target.relative_to(ROOT)), 'bytes': target.stat().st_size, 'sha256': digest}))


if __name__ == '__main__':
    main()
