"""Package fixed research evidence and update gap arithmetic; no evaluation."""
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import subprocess
import zipfile

PAPER = '1e35e3994d4792dfa2bb406669b547cb8b7e8fb0'
SOLVER = '311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1'
FEEDS = '19bebf35205d23fdd832781540f8879da52eeb62'
AUDIT = 'cf4d77a018def540358c3b4667c2d2466390981a'
LATEST = '65d7355ee0856783ede81328915e8bd43227c842'
OFFICIAL = 'de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0'
CONFIG = 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    archive = Path(__file__).resolve().parent
    payload = {}
    sources = []

    def add(name, data, **origin):
        assert name not in payload
        payload[name] = data
        sources.append(dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), **origin))

    def git(commit, path, destination=None):
        raw = subprocess.run(['git', 'show', f'{commit}:{path}'], cwd=args.repo,
                             capture_output=True, check=True).stdout
        add(destination or path, raw, source_commit=commit, source_path=path)
        return raw

    def listing(commit, prefix):
        return subprocess.run(['git', 'ls-tree', '-r', '--name-only', commit, prefix],
                              cwd=args.repo, capture_output=True, check=True).stdout.decode('utf-8').splitlines()

    add('START_HERE.md', (archive/'r3-user-prepared.md').read_bytes(), source_path='r3-user-prepared.md')
    for path in ['data/raw/a/problem.pdf', 'data/raw/a/official-cases.zip',
                 'data/raw/a/official/README.md', 'data/raw/a/official/data/config.txt',
                 'docs/a/source-manifest.json', 'docs/a/OFFICIAL_OBJECTIVES.md']:
        git(PAPER, path)
    for path in listing(PAPER, 'data/raw/a/official/code'):
        if path.endswith('.py'):
            git(PAPER, path)
    for path in listing(SOLVER, 'src/q3'):
        if path.endswith('.py'):
            git(SOLVER, path, 'solver-311/'+path)
    for path in ['paper/sections/a-q3.md', 'paper/notes/a-q3-evidence.md',
                 'paper/drafts/p3-published-summary-audit.json',
                 'paper/drafts/p3-prefix-cache-audit.json',
                 'paper/drafts/p3-release-envelope-audit.json']:
        git(PAPER, path)

    base = 'results/a/q3-nikolastarx/'
    feed_dir = base+'forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft'
    rows = {}
    for shard in range(1, 11):
        data = json.loads(git(FEEDS, f'{feed_dir}/board-feed-s{shard:02}-revision2.json'))
        for r in data['records']:
            key = (r['case_id'], r['cores'])
            assert key not in rows
            assert r['solver_commit'] == SOLVER and r['status'] == 'ok'
            assert r['identity']['config_sha256'] == CONFIG
            assert r['identity']['official_sha256'] == OFFICIAL
            rows[key] = r
    assert len(rows) == 500
    for path in ['forest-full500-feedback-20260925/independent-audit.json',
                 'forest-cachepair-delta-20260925/independent-audit.json']:
        git(AUDIT, base+path)

    bound_prefix = base+'global-bounds-20260925/'
    bounds_raw = git(LATEST, bound_prefix+'bounds.csv')
    for path in ['REPORT.md', 'README.md', 'summary.json', 'ARCHIVE.json', 'audit-snapshot.zip']:
        git(LATEST, bound_prefix+path)
    bounds = list(csv.DictReader(io.StringIO(bounds_raw.decode('utf-8-sig'))))
    updated = []
    for b in bounds:
        key = (b['case_id'], int(b['cores']))
        r = rows[key]
        assert r['identity']['graph_sha256'] == b['graph_sha256']
        assert r['baseline']['graph_sha256'] == b['graph_sha256']
        assert r['baseline']['config_sha256'] == CONFIG
        assert r['baseline']['official_sha256'] == OFFICIAL
        B, L, U = int(b['official_baseline_cycles']), int(b['lower_bound_cycles']), int(r['metrics']['makespan_cycles'])
        assert 0 < L <= U
        updated.append(dict(case_id=key[0], cores=key[1], graph_sha256=b['graph_sha256'],
                            current_solver_commit=SOLVER, current_plan_sha256=r['identity']['plan_sha256'],
                            baseline_B=B, published_global_lower_L=L, current_official_M3_U=U,
                            current_B_over_U=B/U, relaxed_B_over_L=B/L,
                            max_cycle_reduction_U_minus_L=U-L,
                            max_fraction_of_U_reduction=1-L/U,
                            certified_ratio_if_L_valid=U/L,
                            max_mean_speedup_contribution=(B/L-B/U)/100,
                            old_bound_baseline_sha=b['baseline_result_sha256'],
                            current_feed_baseline_sha=r['baseline']['result']['sha256']))
    assert len(updated) == 500 and len({(r['case_id'],r['cores']) for r in updated}) == 500
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=list(updated[0]))
    writer.writeheader()
    writer.writerows(updated)
    csv_bytes = out.getvalue().encode('utf-8')
    (archive/'r3-current-gap.csv').write_bytes(csv_bytes)
    add('derived/current-gap.csv', csv_bytes, source_path='r3-current-gap.csv', scope='Arithmetic join; no new bound proof or E0.')
    summary = {'solver_commit':SOLVER, 'feed_commit':FEEDS, 'bound_source_commit':LATEST,
               'cells':500, 'new_solver_calls':0, 'new_official_calls':0,
               'baseline_sha_exact_matches':sum(x['old_bound_baseline_sha']==x['current_feed_baseline_sha'] for x in updated),
               'limitations':['Published lower bounds and baseline values reused, not re-proved by packaging.',
                              'Hash/identity fields joined; complete raw 500 P3/P2 records not rehashed.',
                              'Baseline gzip bytes can differ across receipts; equal denominator arithmetic cross-checked against fixed published means.',
                              'This is upper-bounded possible headroom, not an achievable improvement or convergence proof.'],
               'per_core':{}, 'top10_k5':sorted([x for x in updated if x['cores']==5], key=lambda x:-x['max_mean_speedup_contribution'])[:10]}
    known = json.loads(payload['paper/drafts/p3-published-summary-audit.json'])['per_core']
    for k in range(1,6):
        rr = [x for x in updated if x['cores']==k]
        current=statistics.fmean(x['current_B_over_U'] for x in rr)
        assert math.isclose(current, known[str(k)]['published_mean_B_over_M'], abs_tol=1e-10)
        ceiling=statistics.fmean(x['relaxed_B_over_L'] for x in rr)
        summary['per_core'][str(k)]={'current_mean_B_over_U':current, 'relaxed_mean_B_over_L':ceiling,
                                     'max_mean_speedup_gain':ceiling-current}
    raw = (json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    (archive/'r3-current-gap-summary.json').write_bytes(raw)
    add('derived/current-gap-summary.json',raw,source_path='r3-current-gap-summary.json')

    for path in ['partial-preload-linux-20260925T0603Z/receipt-public/REPORT.md',
                 'partial-preload-linux-20260925T0603Z/receipt-public/SHA256SUMS.json',
                 'partial-preload-linux-20260925T0603Z/INDEPENDENT_AUDIT.json',
                 'pro-r08-independent-20260925/REVIEW.md',
                 'query-flow-static-repair-20260925/REPORT.md',
                 'query-flow-static-repair-20260925/run/summary.json',
                 'query-flow-one-shot-20260925/README.md',
                 'pro-r08-bottleneck-20260925/README.md']:
        git(LATEST,base+path)
    for path in listing(LATEST,base+'partial-preload-linux-20260925T0603Z/receipt-public/artifacts'):
        git(LATEST,path)
    for name in ['query_flow.py','pipe_bound.py','partial_preload_prepare.py','partial_preload_probe.py',
                 'release_envelope.py','partial_preload.py']:
        path='src/q3/'+name
        if path in listing(LATEST,'src/q3'):
            git(LATEST,path,'research-65/'+path)
    # Retain the model response as external evidence, not as a theorem or new result.
    all_paths=subprocess.run(['git','-c','core.quotepath=false','ls-tree','-r','--name-only',LATEST,'AI chats'],
                             cwd=args.repo,capture_output=True,check=True).stdout.decode('utf-8').splitlines()
    for path in all_paths:
        if path.endswith(('FINAL-r08-bc5e4db8.rendered.txt','manifest-r08-bc5e4db8.json')):
            git(LATEST,path)
    add('r3-build-input.py',Path(__file__).read_bytes(),source_path='r3-build-input.py')
    manifest={'schema':'p3-pro-r3-input-v1','files':sources,'file_count_without_manifest':len(sources),
              'official_sha256':OFFICIAL,'config_sha256':CONFIG,
              'limitations':summary['limitations']}
    manifest_bytes=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    payload['MANIFEST.json']=manifest_bytes
    (archive/'input-manifest-r3.json').write_bytes(manifest_bytes)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,data in payload.items():
            assert not name.startswith('/') and '..' not in Path(name).parts
            z.writestr(name,data)
    with zipfile.ZipFile(args.output) as z:
        assert z.testzip() is None
        for source in sources:
            assert hashlib.sha256(z.read(source['path'])).hexdigest()==source['sha256']
    raw=args.output.read_bytes()
    record={'filename':args.output.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
            'entries':len(payload),'per_core':summary['per_core']}
    (archive/'input-package-r3.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':
    main()
