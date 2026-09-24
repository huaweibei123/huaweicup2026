"""Check structural invariants and independent compute timing, without E0."""
import random
import unittest

from src.q3.construct import Index, topo
from src.q3.fragment_tree import construct as fragment
from src.q3.release_tree import construct


def ownership(plan):
    core_of = {g: c for c, seq in enumerate(plan["core_schedules"]) for g in seq}
    return {int(u): core_of[g] for u, g in plan["node_to_subgraph"].items()}


class ReleaseTreeTests(unittest.TestCase):
    def test_random_trees_preserve_owner_and_independent_timing(self):
        rng = random.Random(24092403)
        for n in (5, 11, 37):
            for _ in range(6):
                edges = [{"source": u, "target": rng.randrange(u + 1, n)} for u in range(n - 1)]
                # Last two non-root vertices ensure a join.
                edges[-2]["target"] = n - 1
                g = {"ops": [{"id": u, "op": "COMPUTE", "cycles": rng.randrange(1, 100),
                              "pipe": rng.choice(["PIPE_M", "PIPE_V"])} for u in range(n)],
                     "tensors": [], "edges": edges}
                index = Index(g)
                for k in (2, 5):
                    old, _ = fragment(index, k)
                    for place in (False, True):
                        p, m = construct(index, k, place=place)
                        owner = ownership(p)
                        self.assertEqual(set(owner), set(index.ops))
                        if not place:
                            self.assertEqual(owner, ownership(old))
                        succ = {u: set(index.succ[u]) for u in index.ops}
                        edge_delay = {(u, v): 500 if owner[u] != owner[v] else 0
                                      for u in index.ops for v in index.succ[u]}
                        reverse = {v: int(u) for u, v in p["node_to_subgraph"].items()}
                        for seq in p["core_schedules"]:
                            prev = {}
                            for subgraph in seq:
                                u = reverse[subgraph]
                                pipe = index.ops[u]["pipe"]
                                if pipe in prev:
                                    a = prev[pipe]
                                    succ[a].add(u)
                                    edge_delay.setdefault((a, u), 0)
                                prev[pipe] = u
                        order = topo(succ, succ)
                        release = dict.fromkeys(succ, 0)
                        completion = {}
                        for u in order:
                            completion[u] = release[u] + index.duration(u)
                            for v in succ[u]:
                                release[v] = max(release[v], completion[u] + edge_delay[u, v])
                        self.assertEqual(max(completion.values()), m["proxy_makespan_cycles"])

    def test_determinism_and_forest_coverage(self):
        g = {"ops": [{"id": u, "op": "COMPUTE", "cycles": 1000, "pipe": "PIPE_M"}
                      for u in range(8)], "tensors": [],
             "edges": [{"source": u, "target": v} for u, v in [(0, 2), (1, 2), (3, 5), (4, 5), (6, 7)]]}
        index = Index(g)
        for place in (False, True):
            a = construct(index, 3, place=place)
            self.assertEqual(a, construct(index, 3, place=place))
            self.assertEqual(sum(a[1]["core_work_cycles"]), 8000)


if __name__ == "__main__":
    unittest.main()
