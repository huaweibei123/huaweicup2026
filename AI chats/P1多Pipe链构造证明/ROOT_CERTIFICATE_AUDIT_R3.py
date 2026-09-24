"""Check saved R3 arithmetic certificates; no author code or evaluator runs."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import zipfile


def audit(package):
    with zipfile.ZipFile(package) as archive:
        def read(name):
            raw = archive.read('p1_r3_s6607/results/' + name)
            return json.loads(raw), hashlib.sha256(raw).hexdigest()
        d, dhash = read('variable_q/diagnostics.json')
        bellman, _ = read('bellman_certificate.json')
        potentials, _ = read('cycle_certificate.json')
    assert bellman['input_sha256'] == potentials['input_sha256'] == dhash
    B, R, Q, gate = (d[k] for k in ('B', 'Rmax', 'Qmax', 'gate'))
    edges = {(e['r'], e['q'], e['s']): e['cost'] for e in d['edges']}
    drains = {(e['r'], 0, 0): e['cost'] for e in d['drains']}
    assert len(edges) == len(d['edges']) and len(drains) == R
    f, capacity = d['footprints'], d['capacity']
    expected = {
        (r, q, s) for r in range(R + 1)
        for q in range(1, min(Q, B-r) + 1) for s in range(min(q, R) + 1)
        if all(r*f['returning'][p] + (q-s)*f['whole'][p] + s*f['prefix'][p]
               <= capacity[p] for p in capacity)
    }
    assert set(edges) == expected
    all_edges = edges | drains
    tails = {(t['r'], t['policy']): t['cost'] for t in d['terminals']}
    H = bellman['labels']
    checks = 0
    for n in range(B + 1):
        for r in range(min(n, R) + 1):
            assert type(H[n][r]) is int
            if n == B:
                assert H[n][r] <= min(v[0] for (rr, _), v in tails.items() if rr == r)
                checks += 1
            for (rr, q, s), cost in all_edges.items():
                if rr == r and n+q <= B:
                    assert H[n][r] <= cost[0] + H[n+q][s]
                    checks += 1
    n = r = 0
    path = [0, 0, 0]
    for nn, rr, q, s in d['actions']:
        assert (nn, rr) == (n, r)
        cost = all_edges[r, q, s]
        path = [a+b for a, b in zip(path, cost)]
        n, r = n+q, s
    assert (n, r) == (B, d['terminal_pending'])
    path = [a+b for a, b in zip(path, tails[r, d['terminal_policy']])]
    assert path[0] == H[0][0] == d['model_makespan'] + gate
    assert path[1] == d['traffic']['scheduled_copy_bytes']
    assert path[2] == d['tasks']
    assert checks == bellman['edge_inequalities_checked']
    cycle_results = {}
    for name in ('variable', 'fixed_capacity_packet'):
        c = potentials[name]
        rate = Fraction(c['lambda_fraction'])
        h = list(map(Fraction, c['potentials']))
        subset = {k: v for k, v in all_edges.items()
                  if max(k[0], k[2]) < len(h) and (k[1] == 0 or c['fixed_q'] in (None, k[1]))}
        slack = [Fraction(v[0])-rate*q-h[s]+h[r] for (r, q, s), v in subset.items()]
        assert len(slack) == c['constraints_checked'] and min(slack) >= 0
        terminal = min(h[r]+v[0] for (r, _), v in tails.items() if r < len(h))
        lower = rate*B + terminal - h[0] - gate
        ceiling = -(-lower.numerator // lower.denominator)
        assert ceiling == c['finite_lower_bound_ceil']
        cycle_results[name] = {'inequalities': len(slack), 'min_slack': str(min(slack)), 'lower_bound': ceiling}
    return {'package_sha256': hashlib.sha256(Path(package).read_bytes()).hexdigest(),
            'diagnostics_sha256': dhash, 'capacity_feasible_normal_types': len(edges),
            'bellman_inequalities': checks, 'selected_path_cost': path,
            'model_makespan': path[0]-gate, 'potentials': cycle_results,
            'scope': 'Arithmetic and declared finite transition coverage only; no recompilation, physical-model equivalence, E0 result or global P1 optimum proved.',
            'calls': {'solver': 0, 'static_task_compile': 0, 'E0': 0, 'E1': 0, 'E2': 0}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('package', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = audit(args.package)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
