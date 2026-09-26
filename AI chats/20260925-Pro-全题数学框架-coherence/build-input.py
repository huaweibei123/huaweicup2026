"""Bundle fixed public theory evidence; only byte checks and saved-table arithmetic.

Never imports research/official modules or executes downloaded code.
"""
from pathlib import Path
import argparse
import csv
from fractions import Fraction
import hashlib
import io
import json
import subprocess
import zipfile

COMMITS = {
    'P1': '5c5789bc7985ee98086160f75770da0018f4898b',
    'P2': '4591699737ec4fd124f8dc3d3ce2116e0a2387a2',
    'P3': 'e789a780c0c828c632a5e81b17b190883b68eb33',
}
ROOTS = {
    'P1': 'AI chats/P1-fork-join-yuanzhifang/',
    'P2': 'AI chats/P2-capacity-ddr-6ab57979/',
    'P3': 'AI chats/20260925-Pro-P3-容量与COPY排队突破/',
}
CONFIG = 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'
INPUT_SHA = '9d50a4260ff72981ea902c115cd39aa109f6fc8f88ee69ae0c0e9f759295ea4f'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True, type=Path)
    ap.add_argument('--official-input', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    here = Path(__file__).resolve().parent
    payload, sources = {}, []
    git_reader = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=args.repo,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def add(name, data, **origin):
        assert name not in payload, name
        payload[name] = data
        sources.append(dict(path=name, bytes=len(data), sha256=sha(data), **origin))
        return data

    def show(commit, path):
        git_reader.stdin.write((commit + ':' + path + '\n').encode('utf-8'))
        git_reader.stdin.flush()
        header = git_reader.stdout.readline().decode().strip().split()
        assert len(header) == 3 and header[1] == 'blob', (path, header)
        data = git_reader.stdout.read(int(header[2]))
        assert git_reader.stdout.read(1) == b'\n'
        return data

    def listing(commit, path):
        return subprocess.check_output(['git', '-c', 'core.quotepath=false',
            'ls-tree', '-r', '--name-only', commit, '--', path], cwd=args.repo).decode().splitlines()

    def take(q, path, dest):
        return add(q + '/' + dest, show(COMMITS[q], path), source_commit=COMMITS[q], source_path=path)

    add('START_HERE.md', (here / 'START_HERE.md').read_bytes(), source_path='START_HERE.md')
    add('COMPARISON.md', (args.repo / 'paper/notes/a-theory-coherence-review.md').read_bytes(),
        source_path='paper/notes/a-theory-coherence-review.md')
    add('build-input.py', Path(__file__).read_bytes(), source_path='build-input.py')

    # Complete latest messages and complete owner-verified public history, not summaries.
    for q, prompt, answer, history in [
        ('P1', '20260925T072606Z-user-01aa5a21.md', '20260925T082658Z-assistant-f6ff2015.md', 'clip-20260925T082658Z.md'),
        ('P3', 'r3-user-original.md', 'r3-answer-original.md', 'web-clip-20260925T082802Z.md'),
    ]:
        for src, dest in [(prompt, 'latest-question.md'), (answer, 'latest-answer.md'), (history, 'full-public-history.md')]:
            take(q, ROOTS[q] + src, dest)
    msg_path = ROOTS['P2'] + 'public-messages-20260925T080420Z.json'
    public = json.loads(take('P2', msg_path, 'archive/public-messages.json'))
    items = public['turns'][-1]['items']
    user = next(i for i in items if i['type'] == 'userMessage')
    assistant = next(i for i in items if i['type'] == 'agentMessage')
    assert user['id'] == 'b5f87c11-2751-4995-9a1a-1bc7857015cc'
    assert assistant['id'] == 'c89717c6-c1c2-472f-8a84-cf7fe5c0119f'
    assert len(user['content']) == 1 and user['content'][0]['type'] == 'text'
    for dest, text, mid in [('latest-question.md', user['content'][0]['text'], user['id']),
                            ('latest-answer.md', assistant['text'], assistant['id'])]:
        add('P2/' + dest, (text + '\n').encode('utf-8'), source_commit=COMMITS['P2'],
            source_path=msg_path, message_id=mid, transformation='exact public text plus final LF')
    take('P2', ROOTS['P2'] + 'snapshot-20260925T080420Z.md', 'full-public-history.md')

    # Current-round original attachments; preserve owner README and archival coverage limits.
    prefixes = {'P1': 'r4-f6ff2015-', 'P2': 'r4-', 'P3': 'r3-'}
    attachment_checks = {}
    for q in COMMITS:
        take(q, ROOTS[q] + 'README.md', 'archive/README.md')
        for path in listing(COMMITS[q], ROOTS[q] + '附件'):
            if Path(path).name.startswith(prefixes[q]):
                take(q, path, 'attachments/' + Path(path).name)
        manifest_name = {'P1': 'r4-f6ff2015-OUTPUT_MANIFEST.json',
                         'P2': 'r4-R4-ARTIFACT-MANIFEST.json',
                         'P3': 'r3-OUTPUT_MANIFEST.json'}[q]
        m = json.loads(payload[q + '/attachments/' + manifest_name])
        entries = m if isinstance(m, list) else m['files']
        for f in entries:
            data = payload[q + '/attachments/' + prefixes[q] + f['path']]
            assert len(data) == f.get('bytes', f.get('size_bytes')) and sha(data) == f['sha256']
        zips = [n for n in payload if n.startswith(q + '/attachments/') and n.endswith('.zip')]
        for name in zips:
            with zipfile.ZipFile(io.BytesIO(payload[name])) as z:
                assert z.testzip() is None
                members = [n for n in z.namelist() if not n.endswith('/')]
                assert len({Path(n).name for n in members}) == len(members)
                for n in members:
                    assert payload[q + '/attachments/' + prefixes[q] + Path(n).name] == z.read(n)
        attachment_checks[q] = dict(manifest_entries=len(entries), original_zips=len(zips),
            obtained_files=sum(n.startswith(q + '/attachments/') for n in payload), checks='pass')

    records = {
        'P1': ['manifest-20260925T082658Z.json', 'attachment-manifest-20260925T082658Z.json',
               'r4-native-inventory-20260925T082658Z.json', 'r4-upload-sources-20260925T072606Z.json'],
        'P2': [],
        'P3': ['archive-manifest-r3.json'],
    }
    for q, files in records.items():
        for name in files:
            take(q, ROOTS[q] + name, 'archive/' + name)
    for q, path, dest in [
        ('P1', 'paper/sections/P1-R4-理论界与优化差距.md', 'independent-review.md'),
        ('P1', 'paper/notes/P1-R4-本地审计与交接.md', 'independent-handoff.md'),
        ('P2', 'paper/sections/a-q2-theory-r4.md', 'independent-review.md'),
        ('P3', 'paper/notes/a-q3-theory-r3.md', 'independent-review.md'),
        ('P3', 'paper/sections/a-q3.md', 'paper-draft.md'),
    ]:
        take(q, path, dest)
    checks = {
        'P1': ('results/a/q1-yuanzhifang/pro-r4-bound-pairing-20260925/local-audit-20260925T082007Z/',
               ['verification.json', 'paired-500.csv', 'summary.json']),
        'P2': ('results/a/q2-yuanzhifang/feedback-20260924/pro-upper-bound-r4-20260925/',
               ['independent-review.json', 'verify_pro_r4.py', 'input-manifest.json']),
        'P3': ('results/a/q3-yuanzhifang/pro-r3-independent-20260925/',
               ['independent-certificate-check.json', 'independent-cells.csv']),
    }
    for q, (root, files) in checks.items():
        for name in files:
            take(q, root + name, 'local-check/' + name)
    take('P1', 'scripts/p1_pro_r4_verify_static.py', 'local-check/verifier.py')
    take('P3', 'docs/a/q3-yuanzhifang/verify_pro_r3_certificates.py', 'local-check/verifier.py')

    # Read exact official input; validate all old manifest members before selecting materials.
    old_raw = args.official_input.read_bytes()
    assert sha(old_raw) == INPUT_SHA
    with zipfile.ZipFile(io.BytesIO(old_raw)) as old:
        assert old.testzip() is None
        old_m = json.loads(old.read('MANIFEST.json'))
        for f in old_m['files']:
            raw = old.read(f['path'])
            assert len(raw) == f['bytes'] and sha(raw) == f['sha256']
        for name in old.namelist():
            dest = None
            if name in ['data/raw/a/problem.pdf', 'data/raw/a/official-cases.zip']:
                dest = 'official/' + Path(name).name
            elif name.startswith('data/raw/a/official/'):
                dest = 'official/' + name.removeprefix('data/raw/a/official/')
            elif name in ['docs/a/source-manifest.json', 'docs/a/OFFICIAL_OBJECTIVES.md']:
                dest = 'official/' + Path(name).name
            elif name.startswith(('solver-311/', 'research-65/')):
                dest = 'P3/method-source/' + name
            elif name.endswith(('query-flow-static-repair-20260925/REPORT.md',
                                'pro-r08-independent-20260925/REVIEW.md',
                                'receipt-public/REPORT.md')):
                dest = 'P3/mechanism-source/' + name
            if dest:
                add(dest, old.read(name), source_archive_sha256=INPUT_SHA, source_path=name)
        add('P3/input-sources-r3.json', old.read('MANIFEST.json'), source_archive_sha256=INPUT_SHA)
    assert sha(payload['official/data/config.txt']) == CONFIG
    for q, commit, prefix in [
        ('P1', 'a0537aeb72dc702af86d67d3194587d581ac207c', 'src/q1'),
        ('P2', 'c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f', 'src/q2_nikolastarx'),
    ]:
        for name in listing(commit, prefix):
            if name.endswith(('.py', '.json')):
                add(q + '/method-source/' + name, show(commit, name), source_commit=commit, source_path=name)
    git_reader.stdin.close()
    assert git_reader.wait(timeout=30) == 0

    # Join saved facts only: no plan, compiler, event engine, or witness search.
    def csv_rows(name):
        return list(csv.DictReader(io.StringIO(payload[name].decode('utf-8-sig'))))

    rows = {'P1': csv_rows('P1/attachments/r4-f6ff2015-paired_500_audited.csv'),
            'P2': csv_rows('P2/attachments/r4-r4-cells.csv'),
            'P3': csv_rows('P3/attachments/r3-cells_500.csv')}
    indexed = {q: {(r.get('case_id', r.get('case')), int(r['cores'])): r for r in rr} for q, rr in rows.items()}
    expected = {(f'{i:03}', k) for i in range(1, 101) for k in range(1, 6)}
    for q in indexed:
        assert len(rows[q]) == 500 and set(indexed[q]) == expected
    p1_verify = json.loads(payload['P1/local-check/verification.json'])
    assert p1_verify['config_sha256'] == CONFIG
    assert p1_verify['official_P1_sha256'] == sha(payload['official/code/multicore_cut_evaluate_problem_1.py'])
    raw_graphs = zipfile.ZipFile(io.BytesIO(payload['official/official-cases.zip']))
    assert raw_graphs.testzip() is None
    differences, joined, means = [], [], {}
    for case, k in sorted(expected):
        p1, p2, p3 = [indexed[q][case, k] for q in ['P1', 'P2', 'P3']]
        graph_hash = sha(raw_graphs.read(f'data/case_{case}.json'))
        assert p1['graph_sha256'] == p2['graph_sha256'] == p3['graph_sha256'] == graph_hash
        assert p1['config_sha256'] == p2['config_sha256'] == p3['config_sha256'] == CONFIG
        b = int(p1['B'])
        assert b == int(p2['A']) == int(p3['B_published'])
        rec = dict(case=case, cores=k, B=b, graph_sha256=graph_hash,
                   P1_U=int(p1['U']), P1_L=int(p1['L_safe_global']),
                   P2_U=int(p2['U']), P2_L=int(p2['L']),
                   P3_U=int(p3['U_feed_M3']), P3_L=int(p3['L1_proved']))
        assert all(0 < rec[q+'_L'] < rec[q+'_U'] for q in COMMITS)
        if rec['P2_L'] != rec['P3_L']:
            differences.append({f: rec[f] for f in ['case', 'cores', 'P2_L', 'P3_L']})
        joined.append(rec)
    for q in COMMITS:
        means[q] = []
        for k in range(1, 6):
            rr = [r for r in joined if r['cores'] == k]
            a = sum((Fraction(r['B'], r[q+'_U']) for r in rr), Fraction()) / 100
            c = sum((Fraction(r['B'], r[q+'_L']) for r in rr), Fraction()) / 100
            means[q].append(dict(cores=k, current_candidate_mean=float(a), ceiling_mean=float(c),
                                 gap_points=float(c-a), relative_mean_gain_cap=float(c/a-1),
                                 current_exact=str(a), ceiling_exact=str(c)))
    join = dict(status='pass', source_commits=COMMITS, cells_each=500,
        graph_hashes_compared_to_original_zip=100, graph_and_fixed_B_equal_all_three=True,
        config_sha256=CONFIG, P1_config_source='per-cell CSV and owner receipt; official P1 file checked',
        P2_P3_config_equal_per_cell=True, P2_P3_same_L=500-len(differences),
        P3_L_stronger=sum(r['P3_L'] > r['P2_L'] for r in differences),
        differences=differences, per_core_means=means, cells=joined,
        new_solver_Task_Step_E0_E1_E2_calls=0,
        limits=['B and U remain saved published evidence, not independently replayed official results.',
                'No objective/mode embedding follows from input identity.',
                'P1 formal one-core reference is 1, separate from repartitioned candidate mean.',
                'New combined certificates not constructed; retain each original L table.',
                'All selected domain modules included; transitive E1/E2 equivalence is not supplied.'])
    add('DATA_IDENTITY_JOIN.json', encoded(join), derivation='static saved CSV joins and Fraction means')
    manifest = dict(scope='fourth Pro coherence input, fixed public evidence only',
        source_commits=COMMITS, files=sources, original_attachment_checks=attachment_checks,
        official_input_sha256=INPUT_SHA, new_solver_Task_Step_E0_E1_E2_calls=0,
        hidden_reasoning_exported=False)
    payload['MANIFEST.json'] = encoded(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    assert not args.output.exists(), 'Choose a new output path rather than overwrite a sent archive.'
    with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for name, data in payload.items():
            zi = zipfile.ZipInfo(name, date_time=(2026, 9, 25, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(zi, data)
    with zipfile.ZipFile(args.output) as out:
        assert out.testzip() is None and len(out.namelist()) == len(payload)
        for f in sources:
            data = out.read(f['path'])
            assert len(data) == f['bytes'] and sha(data) == f['sha256']
    receipt = dict(filename=args.output.name, bytes=args.output.stat().st_size,
        sha256=sha(args.output.read_bytes()), members=len(payload),
        verified_manifest_entries=len(sources), source_commits=COMMITS,
        original_attachment_checks=attachment_checks, status='prepared_not_sent')
    for filename, data in [('input-manifest.json', manifest), ('DATA_IDENTITY_JOIN.json', join),
                           ('input-receipt.json', receipt)]:
        (here / filename).write_bytes(encoded(data))
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
