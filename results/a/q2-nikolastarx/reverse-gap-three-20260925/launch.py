"""Inside the verified extracted capsule: restore real Git commit, run frozen probe."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
COMMIT = '6836516874ce9e65d85ab2deed206e22d77b1562'


def main():
    freeze = json.loads((ROOT / 'freeze.json').read_bytes())
    assert freeze['source_commit'] == COMMIT
    commit_raw = (ROOT / 'commit.object').read_bytes()
    digest = subprocess.check_output(['git', 'hash-object', '-t', 'commit', '--stdin'],
                                     input=commit_raw, cwd=ROOT).decode().strip()
    if digest != COMMIT:
        raise ValueError('transported Git commit object mismatch')
    subprocess.run(['git', 'init', '-q'], cwd=ROOT, check=True)
    written = subprocess.check_output(['git', 'hash-object', '-w', '-t', 'commit', '--stdin'],
                                      input=commit_raw, cwd=ROOT).decode().strip()
    if written != COMMIT:
        raise ValueError('Git object write mismatch')
    subprocess.run(['git', 'update-ref', 'HEAD', COMMIT], cwd=ROOT, check=True)
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() != COMMIT:
        raise ValueError('Git HEAD verification failed')
    sys.path.insert(0, str(ROOT))
    from scripts.q2_reverse_gap_pilot import run
    run(ROOT / 'freeze.json', ROOT / 'data/raw/a/official/data',
        Path('/content/reverse-gap-results/pilot'), sys.executable)


if __name__ == '__main__':
    main()
