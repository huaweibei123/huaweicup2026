from itertools import permutations, product
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/q1_yuanzhifang"))
from barrier_bound import comparable_barriers, gate_capacity_inverse, lower_bound
from test_construct import graph_from_edges


def partitions(n, prefix=()):
    if len(prefix) == n:
        yield prefix
    else:
        for x in range(max(prefix, default=-1) + 2):
            yield from partitions(n, prefix + (x,))


class BarrierBoundTests(unittest.TestCase):
    def test_inverse_matches_capacity_definition(self):
        for k, lag, ends, work in product(range(1, 6), range(6), range(3), range(31)):
            expected = next(d for d in range(31) if work <= d + (k - 1) * max(d - ends * lag, 0))
            self.assertEqual(gate_capacity_inverse(work, k, lag, ends), expected)

    def test_prefix_suffix_matches_transitive_closure(self):
        possible = [(u, v) for u in range(4) for v in range(u + 1, 4)]
        for mask in range(64):
            edges = {e for j, e in enumerate(possible) if mask & (1 << j)}
            reach = set(edges)
            for via in range(4):
                for u, v in product(range(4), repeat=2):
                    if (u, via) in reach and (via, v) in reach:
                        reach.add((u, v))
            pred = {v: {u for u, w in edges if w == v} for v in range(4)}
            succ = {u: {v for w, v in edges if w == u} for u in range(4)}
            want = [u for u in range(4) if all(v == u or (u, v) in reach or (v, u) in reach for v in range(4))]
            self.assertEqual(comparable_barriers(list(range(4)), pred, succ), want)

    def test_bound_under_every_small_relaxed_plan(self):
        # Offline proof falsification, NOT the submitted construction. For any
        # acyclic joint Task order there exists a global topological order, so
        # projection of all total orders covers all core-order choices here.
        possible = [(u, v) for u in range(4) for v in range(u + 1, 4)]
        weights, examined = [1, 3, 2, 4], 0
        for mask in range(64):
            edges = [e for j, e in enumerate(possible) if mask & (1 << j)]
            g = graph_from_edges(4, edges)
            for u, op in enumerate(g["ops"]):
                op["cycles"], op["pipe"] = weights[u], "PIPE_V"
            bound = lower_bound(g, 2, 2)["lower_bound_cycles"]
            for mapping in partitions(4):
                m = max(mapping) + 1
                task_edges = {(mapping[u], mapping[v]) for u, v in edges if mapping[u] != mapping[v]}
                duration = [sum(weights[u] for u in range(4) if mapping[u] == t) for t in range(m)]
                for order in permutations(range(m)):
                    pos = {t: i for i, t in enumerate(order)}
                    if any(pos[u] >= pos[v] for u, v in task_edges):
                        continue
                    for owner in product(range(2), repeat=m):
                        end, prev = {}, [None, None]
                        for t in order:
                            core = owner[t]
                            release = 0 if prev[core] is None else end[prev[core]] + 1
                            release = max([release, *(end[u] + (2 if owner[u] != core else 0) for u, v in task_edges if v == t)])
                            end[t] = release + duration[t]
                            prev[core] = t
                        self.assertLessEqual(bound, max(end.values()), (mask, mapping, order, owner))
                        examined += 1
        self.assertGreater(examined, 10000)

    def test_invalid_capacity_arguments(self):
        for args in ((-1, 2, 1, 2), (2, 0, 1, 1), (2, 2, -1, 1), (2, 2, 1, 3), (True, 2, 1, 1)):
            with self.assertRaises(ValueError):
                gate_capacity_inverse(*args)


if __name__ == "__main__":
    unittest.main()
