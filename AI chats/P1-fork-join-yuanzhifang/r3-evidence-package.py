"""Package fixed repository research evidence; no solver/evaluator execution."""
import argparse, gzip, hashlib, io, json, subprocess, zipfile
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--repo', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
a.output.parent.mkdir(parents=True, exist_ok=True)
def git_bytes(commit, path):
    return subprocess.check_output(['git', 'show', commit + ':' + path], cwd=a.repo)
entries, origins = {}, []
def add(commit, path, dest=None, decompress=False):
    raw = git_bytes(commit, path)
    data = gzip.decompress(raw) if decompress else raw
    dest = dest or path
    if dest in entries:
        raise ValueError(dest)
    entries[dest] = data
    origins.append(dict(path=dest, source_commit=commit, source_path=path,
                        source_sha256=hashlib.sha256(raw).hexdigest(),
                        sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data)))
base = '48faef6f1386c3dc7d037674a38af29d533ba774'
hsource = '4f1b9f8be4bbcc98759a19451c108e62e80abb17'
hdata = '1c9b654223b663f6e624fc413913c076c843ed56'
proof = '0b47d802cdd0bfe7011017c8098c1c0917b2c959'
for name in ['contest_io.py', 'evaluation_validation.py', 'multicore_cut_evaluate_problem_1.py',
             'schedule_step1.py', 'schedule_step2.py', 'schedule_step3.py',
             'singlecore_evaluate.py', 'stub_multicore_cut_and_schedule.py']:
    add(base, 'data/raw/a/official/code/' + name, 'official/code/' + name)
add(base, 'data/raw/a/official/data/config.txt', 'official/data/config.txt')
add(base, 'docs/a/source-manifest.json')
archive = git_bytes(base, 'data/raw/a/official-cases.zip')
with zipfile.ZipFile(io.BytesIO(archive)) as z:
    matches = [n for n in z.namelist() if n.endswith('/case_051.json') or n == 'case_051.json']
    if len(matches) != 1:
        raise ValueError(matches)
    graph = z.read(matches[0])
assert hashlib.sha256(graph).hexdigest() == '884e8b12ac1f7a9b569958909680e8c2f6055966a59c9f929ffd5cee48aae43b'
entries['official/data/case_051.json'] = graph
origins.append(dict(path='official/data/case_051.json', source_commit=base,
                    source_path='data/raw/a/official-cases.zip::' + matches[0],
                    sha256=hashlib.sha256(graph).hexdigest(), size_bytes=len(graph)))
for name in ['prefetch_frontier.py', 'star_frontier.py', 'construct.py', 'fork_frontier.py', 'diagnose.py']:
    add(hsource, 'src/q1_yuanzhifang/' + name, 'H-source/' + name)
prefix = 'results/a/q1-yuanzhifang/stage-h-20260925/'
add(hdata, prefix + 'README.md', 'H-evidence/README.md')
for name in ['case_051_multicore_res.json', 'diagnostics.json', 'result.json.gz', 'trace.json.gz']:
    add(hdata, prefix + 'run/051-k5-four-core-start-subtrees-v1/' + name,
        'H-evidence/' + name.removesuffix('.gz'), name.endswith('.gz'))
add(proof, 'docs/a/q1-yuanzhifang/DDR_BARRIER_BOUND.md', 'proof/DDR_BARRIER_BOUND.md')
add(proof, 'src/q1_yuanzhifang/ddr_barrier_bound.py', 'proof/ddr_barrier_bound.py')
add(proof, 'results/a/q1-yuanzhifang/ddr-proof-20260925/REVIEW.md', 'proof/independent-review.md')
audit = 'eb5a05cd39fabbbcca4a6e4cd13e1885104fcff4'
for name in ['README.md', 'rows.json', 'summary.json']:
    add(audit, 'results/a/q1-unified-independent-audit-20260925/' + name, 'captain-audit/' + name)
entries['MANIFEST.json'] = (json.dumps(origins, ensure_ascii=False, indent=2) + '\n').encode()
entries['README.md'] = b'''# P1 round 3 fixed evidence packet\n\nSources are identified by full Git commit and SHA-256 in MANIFEST.json.\nThe 051 graph, official code and config are unchanged original bytes.\nH-evidence contains an actual successful 231551-cycle E0 plan/result/trace.\nGzip results were decompressed without changing their JSON bytes.\nH-source is a research algorithm, not official evaluator code.\nThe independent captain audit is not a substitute for its full raw evidence.\nProof files are candidates/reviews, not a global optimality claim.\nNo code was executed while building this packet.\nAll uploaded files already have repository sources; this package is an index/copy for reading.\n'''
with zipfile.ZipFile(a.output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for path, data in entries.items():
        z.writestr(path, data)
print(json.dumps(dict(output=str(a.output), files=len(entries), bytes=a.output.stat().st_size,
                     sha256=hashlib.sha256(a.output.read_bytes()).hexdigest())))
