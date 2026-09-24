"""Normalize only profiles produced locally by profile_once.py.

No construction/evaluation runs here. Python profile files are not safe to
load from untrusted sources. Raw originals are retained outside the worktree.
"""
import hashlib
import json
import marshal
from pathlib import Path
import pstats
import shutil
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
RAW = Path('/tmp/p2-constructor-profile-20260924-s8ee')
RAW.mkdir(exist_ok=True)


def canonical_name(path):
    return path.replace(str(ROOT), '${REPO_ROOT}').replace(
        str(Path(sys.base_prefix)), '${PYTHON_BASE}')


def canonical_key(key):
    return canonical_name(key[0]), key[1], key[2]


receipt = []
for case in ('008', '014', '025'):
    path = OUT / (case + '-k4') / 'profile.pstats'
    raw = RAW / (case + '-k4.pstats')
    if raw.exists():
        raise FileExistsError('No automatic overwrite of preserved raw profile')
    shutil.move(path, raw)
    stats = pstats.Stats(str(raw))
    normalized = {
        canonical_key(key): (*values[:4],
                             {canonical_key(k): v for k, v in values[4].items()})
        for key, values in stats.stats.items()
    }
    with path.open('wb') as stream:
        marshal.dump(normalized, stream)
    check = pstats.Stats(str(path))
    assert check.total_tt == stats.total_tt
    assert check.total_calls == stats.total_calls
    assert check.prim_calls == stats.prim_calls
    for kind, sort_by in [('cumulative', 'cumulative'), ('self', 'tottime')]:
        text_path = path.parent / ('profile-' + kind + '.txt')
        with text_path.open('w') as stream:
            pstats.Stats(str(path), stream=stream).strip_dirs().sort_stats(sort_by).print_stats(100)
        text_path.write_text(canonical_name(text_path.read_text()))
    receipt.append({'case': case, 'raw_local_path': str(raw),
                    'raw_sha256': hashlib.sha256(raw.read_bytes()).hexdigest(),
                    'normalized_path': str(path.relative_to(ROOT)),
                    'normalized_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'total_seconds': stats.total_tt, 'total_calls': stats.total_calls,
                    'primitive_calls': stats.prim_calls,
                    'transformation': 'Filename and caller-filename prefix substitution only; all counts/timings/caller edges preserved.'})
(OUT/'normalization-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
