"""Only abstract mathematical unit tests. No official code or real cases imported."""
import json
from sealed_tree_dp import Node, Model, construct, evaluate_abstract, local_signatures, step2_interval_peak


def perfect(height, weight=1):
    nodes, children = {}, {}
    def rec(h):
        ch = [] if h == 0 else [rec(h-1), rec(h-1)]
        v = len(nodes)
        nodes[v] = Node(v, weight, 'M')
        children[v] = ch
        return v
    rec(height)
    return Model(nodes, children)

results = []
for name, m, k, delta, expected in [
    ('two_unit_leaves_remote_500', perfect(1), 2, 500, 3),
    ('perfect_15_unit_k4_no_comm', perfect(3), 4, 0, 5),
    ('perfect_15_weight1000_k4_delay500', perfect(3, 1000), 4, 500, 6000),
]:
    _, meta = construct(m, k, delta)
    assert meta['abstract_fifo_makespan'] == expected, meta
    results.append({'test': name, **meta})

children = {0: [], 1: [], 2: [0, 1], 3: [], 4: [], 5: [3, 4],
            6: [2, 5], 7: [], 8: [], 9: [7, 8], 10: [6, 9]}
m = Model({v: Node(v, 1, 'M') for v in children}, children)
_, meta = construct(m, 2, 0)
alternative = evaluate_abstract(m, [[0, 3, 2, 5, 6, 10], [1, 4, 7, 8, 9]], 0)
assert meta['abstract_fifo_makespan'] == 7
assert alternative['makespan'] == 6
results.append({'test': 'restricted_family_failure_11_nodes', **meta,
                'explicit_alternative_makespan': alternative['makespan']})

m = perfect(3)
m = Model({v: Node(v, (v * 7 % 11) + 1, 'M' if v % 3 else 'V') for v in m.nodes},
          m.children)
root, order = m.validate()
pipes, R, f, local = local_signatures(m, order)
assert local[root] == evaluate_abstract(m, [order], 0)['makespan']
for k in range(1, 6):
    construct(m, k, 500)  # verifies emitted abstract longest path <= witness
# Test the matrix interface for unequal initial availability, not merely zero.
initial = {'M': 37, 'V': 3}
a = [0] + [initial[p] for p in pipes]
projected = [max(c + a[j] for j, c in enumerate(row) if c is not None) for row in R[root]]
avail, ends = dict(initial), {}
for v in order:
    n = m.nodes[v]
    start = max(avail[n.pipe], max((ends[u] for u in m.children[v]), default=0))
    ends[v] = start + n.cycles
    avail[n.pipe] = ends[v]
assert projected[1:] == [avail[p] for p in pipes]
results.append({'test': 'two_pipe_maxplus_signature', 'passed': True,
                'zero_input_local_span': local[root], 'unequal_input_availability': initial})

peak = step2_interval_peak(
    [{'id': 100, 'pos': 'UB', 'size': 6}, {'id': 101, 'pos': 'UB', 'size': 6},
     {'id': 102, 'pos': 'UB', 'size': 6}],
    [{'source': 0, 'target': 100}, {'source': 1, 'target': 101},
     {'source': 100, 'target': 2}, {'source': 101, 'target': 2}, {'source': 2, 'target': 102}],
    [0, 1, 2])
assert peak['UB'] == 18
results.append({'test': 'alloc_before_last_use_free', 'interval_peaks': peak})
print(json.dumps({'official_experiments_run': 0, 'results': results}, indent=2))
