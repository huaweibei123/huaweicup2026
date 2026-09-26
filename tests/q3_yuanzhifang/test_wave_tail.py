import itertools
import random
import unittest

from src.q3_yuanzhifang.construct import SharingIndex
from src.q3_yuanzhifang.wave_tail import build, partition_tail


def synthetic_jobs(count=5, length=6):
    ops, edges, tensors = [], [], [{"id": 10000, "pos": "L1", "size": 6000}]
    for j in range(count):
        first = 1 + j * length
        for p in range(length):
            u = first + p
            pipe = "PIPE_V" if p == 1 else "PIPE_M"
            ops.append({"id": u, "op": "ADD" if p == 1 else "MUL",
                        "pipe": pipe, "cycles": p + 2})
            if p:
                edges.append({"source": u - 1, "target": u})
        edges.append({"source": 10000, "target": first + length - 1})
        tid = 20000 + j
        tensors.append({"id": tid, "pos": "L1", "size": 100})
        edges.extend(({"source": first, "target": tid},
                      {"source": tid, "target": first + length - 1}))
    return {"ops": ops, "tensors": tensors, "edges": edges}


class WaveTailTest(unittest.TestCase):
    def test_secondary_objective_after_peak_is_fixed(self):
        cuts, objective = partition_tail([1, 3, 1, 1, 10], [0]*5, 3, 1,
                                         [0, 0, 100, 100, 0, 0])
        self.assertEqual(objective, (26, 0))
        self.assertEqual(cuts, [0, 1, 4, 5])

    def test_dp_matches_independent_exhaustive_objective(self):
        rng = random.Random(2059)
        for _ in range(60):
            length = rng.randint(2, 7)
            cores = rng.randint(2, min(4, length))
            q = rng.randint(1, 4)
            m = [rng.randint(0, 9) for _ in range(length)]
            v = [rng.randint(0, 9) for _ in range(length)]
            boundary = [0] + [rng.randint(0, 30) for _ in range(length - 1)] + [0]
            choices = []
            for inside in itertools.combinations(range(1, length), cores - 1):
                cuts = (0, *inside, length)
                peak = max(max(q * sum(m) + sum(m[cuts[c]:cuts[c + 1]]),
                               q * sum(v) + sum(v[cuts[c]:cuts[c + 1]]))
                           for c in range(cores))
                choices.append((peak, sum(boundary[h] for h in inside)))
            cuts, objective = partition_tail(m, v, cores, q, boundary)
            self.assertEqual(objective, min(choices))
            self.assertEqual((cuts[0], cuts[-1]), (0, length))
            self.assertTrue(all(a < b for a, b in zip(cuts, cuts[1:])))

    def test_one_tail_only_and_all_eligible_once(self):
        graph = synthetic_jobs()
        plan, meta = build(SharingIndex(graph), 2, 60, {"L1": 6299, "UB": 0})
        self.assertTrue(meta["guard"])
        self.assertEqual(meta["selected"], "wave_tail")
        self.assertEqual(meta["full_jobs_per_core"], 2)
        self.assertEqual(meta["full_job_wave_sizes"], [1, 1])
        self.assertEqual(meta["final_wave_tail_occupancy"], 2)
        self.assertEqual(meta["internal_e0_calls"], 0)
        self.assertEqual(len(set(plan["node_to_subgraph"].values())), 30)
        inverse = {sg: int(u) for u, sg in plan["node_to_subgraph"].items()}
        sequences = [[inverse[sg] for sg in seq] for seq in plan["core_schedules"]]
        self.assertEqual(sorted(u for seq in sequences for u in seq), list(range(1, 31)))
        owners = {u: c for c, seq in enumerate(sequences) for u in seq}
        for j in range(4):
            self.assertEqual(len({owners[u] for u in range(1 + 6*j, 7 + 6*j)}), 1)
        self.assertEqual([owners[u] for u in range(25, 31)],
                         [c for c in range(2) for _ in range(meta["cuts"][c + 1] - meta["cuts"][c])])
        for seq in sequences:
            for j in range(5):
                located = [seq.index(u) for u in range(1 + 6*j, 7 + 6*j) if u in seq]
                self.assertEqual(located, sorted(located))

    def test_workload_and_fallback_guards(self):
        graph = synthetic_jobs()
        _, meta = build(SharingIndex(graph), 2, 60, {"L1": 6299, "UB": 0})
        m_total = sum(p + 2 for p in range(6) if p != 1)
        v_total = 3
        for c, (a, b) in enumerate(zip(meta["cuts"], meta["cuts"][1:])):
            self.assertEqual(meta["per_core_compute_work_cycles"][c], {
                "M": 2*m_total + sum(p + 2 for p in range(a, b) if p != 1),
                "V": 2*v_total + (3 if a <= 1 < b else 0)})
        _, bad = build(SharingIndex(synthetic_jobs(4)), 2, 60, {"L1": 6299, "UB": 0})
        self.assertFalse(bad["guard"])
        self.assertEqual(bad["reason"], "single_tail_shape")
        _, bad = build(SharingIndex(graph), 2, 60, {"L1": 6100, "UB": 0})
        self.assertFalse(bad["guard"])
        self.assertEqual(bad["reason"], "insufficient_wave_width")

    def test_three_core_single_full_job_and_signature_rejection(self):
        graph = synthetic_jobs(4)
        plan, meta = build(SharingIndex(graph), 3, 60, {"L1": 6299, "UB": 0})
        self.assertTrue(meta["guard"])
        self.assertEqual(meta["full_job_wave_sizes"], [1])
        self.assertEqual(len(meta["tail_owner_intervals"]), 3)
        self.assertEqual(sum(map(len, plan["core_schedules"])), 24)
        graph["tensors"][-1]["size"] = 101
        _, bad = build(SharingIndex(graph), 3, 60, {"L1": 6299, "UB": 0})
        self.assertFalse(bad["guard"])
        self.assertEqual(bad["reason"], "private_tensor_template_mismatch")


if __name__ == "__main__":
    unittest.main()
