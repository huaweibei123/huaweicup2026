"""Static independent guard/arithmetic audit; no plan construction or evaluator.

The mathematical proof is in paper/notes/a-theory-coherence-final.md.
Finite arithmetic fixtures are regression checks, not proofs over all inputs.
"""
from pathlib import Path
from fractions import Fraction
import argparse
import hashlib
import importlib.util
import io
import json
import zipfile


def digest(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args()
    raw = args.input.read_bytes()
    assert digest(raw) == '2613eb486f625747dc4e4cd23fd37e37bbdbdc3f2c6923b1b88d134f6a2c0c81'
    z = zipfile.ZipFile(io.BytesIO(raw))
    assert z.testzip() is None
    manifest = json.loads(z.read('MANIFEST.json'))
    for f in manifest['files']:
        b = z.read(f['path'])
        assert len(b) == f['bytes'] and digest(b) == f['sha256']

    # Reuse only our previously reviewed graph parser, not any Pro/official module.
    helper_path = Path(__file__).with_name('verify_pro_r3_certificates.py')
    spec = importlib.util.spec_from_file_location('local_graph_guard', helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    graphs = zipfile.ZipFile(io.BytesIO(z.read('official/official-cases.zip')))
    rows = json.loads(z.read('DATA_IDENTITY_JOIN.json'))['cells']
    identity = {(r['case'], r['cores']): r for r in rows}
    graph_checks = []
    for i in range(1, 101):
        case = f'{i:03}'
        b = graphs.read(f'data/case_{case}.json')
        g = json.loads(b)
        compute, succ, duration, work, heads, tails = helper.graph_view(g)
        assert len({t['id'] for t in g['tensors']}) == len(g['tensors'])
        assert all(t.get('logical_tid', t['id']) == t['id'] for t in g['tensors'])
        assert all(identity[case, k]['graph_sha256'] == digest(b) for k in range(1, 6))
        graph_checks.append(dict(case=case, graph_sha256=digest(b),
            compute_ops=len(compute), compute_edges=sum(map(len, succ.values())),
            unique_ids_and_producers=True, no_original_logical_alias=True,
            positive_integer_compute_duration=True, DAG=True))
    assert sum(r['compute_ops'] for r in graph_checks) == 634506
    assert sum(r['compute_edges'] for r in graph_checks) == 740641

    # Check the closed inverse at and before its reported integer threshold.
    inverse_checks = 0
    for k in range(1, 6):
        for c in (0, 1, 2, 499, 500, 501, 999, 1000, 1001, 1999, 2000):
            for w in sorted(set(range(201)) | {c, c+1, c+2, k*c, k*c+1}):
                x = min(w, (w+(k-1)*c+k-1)//k)
                cap = lambda y: y+(k-1)*max(y-c, 0)
                assert cap(x) >= w and (x == 0 or cap(x-1) < w)
                inverse_checks += 1
    capacity_checks = 0
    for A in (0, 1, 499, 500, 999, 1000):
        for B in (0, 1, 499, 500, 999, 1000):
            points = {Fraction(v)+d for v in (0, min(A,B), max(A,B), A+B)
                      for d in (Fraction(-1,2), Fraction(0), Fraction(1,2))}
            for x in points:
                if x < 0:
                    continue
                assert max(x-A,0)+max(x-B,0) <= x+max(x-A-B,0)
                capacity_checks += 1
    atomic_checks = []
    for values in ((10,8,7), (10,10), (1,), (9,8,8,7,6,4,2)):
        for k in range(1,6):
            ds = sorted(values, reverse=True)
            atom = max(sum(ds[m-r:m]) for r in range(1,len(ds)+1)
                       if (m := (r-1)*k+1) <= len(ds))
            weak = max(((j+k-1)//k)*v for j,v in enumerate(ds,1))
            assert atom >= weak
            atomic_checks.append(dict(durations=ds,k=k,strong=atom,weak=weak))
    assert atomic_checks[1]['strong'] == 15 and atomic_checks[1]['weak'] == 14

    summaries = {}
    for q in ('P1','P2','P3'):
        groups = []
        for k in range(1,6):
            rr = [r for r in rows if r['cores'] == k]
            assert len(rr) == 100 and all(0 < r[q+'_L'] < r[q+'_U'] for r in rr)
            a = sum((Fraction(r['B'],r[q+'_U']) for r in rr),Fraction())/100
            c = sum((Fraction(r['B'],r[q+'_L']) for r in rr),Fraction())/100
            groups.append(dict(k=k,current_mean=float(a),ceiling_mean=float(c),
                gap=float(c-a),relative_mean_gain_cap=float(c/a-1),
                within_1pct=sum(100*r[q+'_U'] <= 101*r[q+'_L'] for r in rr),
                within_5pct=sum(100*r[q+'_U'] <= 105*r[q+'_L'] for r in rr)))
        summaries[q] = groups
    assert [summaries[q][-1]['within_1pct'] for q in summaries] == [3,6,7]
    assert [summaries[q][-1]['within_5pct'] for q in summaries] == [18,23,31]
    result = dict(status='pass', input_sha256=digest(raw),
        verifier_sha256=digest(Path(__file__).read_bytes()),
        graph_helper_sha256=digest(helper_path.read_bytes()),
        manifest_entries=len(manifest['files']), graphs=graph_checks,
        compute_ops=634506,compute_edges=740641,
        arithmetic_fixtures=dict(inverse_checks=inverse_checks,
            endpoint_capacity_checks=capacity_checks, atomic=atomic_checks),
        saved_table_summary=summaries,
        calls={k:0 for k in ['solver','Task','Step','E0','E1','E2','response_simulator']},
        limits=['No new combined 500-cell certificate construction or threshold search.',
                'No execution of Pro attachments or official source.',
                'Published B/U are not replayed. Source proofs require the companion review.',
                'Graph guards are sufficient, not a full characterization of official validity.',
                'Arithmetic fixtures alone are not universal mathematical proofs.'])
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='pass',graphs=100,compute_ops=634506,compute_edges=740641,
        inverse_checks=inverse_checks,capacity_checks=capacity_checks,calls=result['calls'])))


if __name__ == '__main__':
    main()
