import itertools
import random
import unittest
from unittest.mock import patch

from src.q3_yuanzhifang.construct import SharingIndex
from src.q3_yuanzhifang.pipeline_capacity import build, partition
from src.q3_yuanzhifang.pipeline_stages import build as baseline
from test_pipeline_setup import recurrence, synthetic_jobs


class CapacityPartitionTest(unittest.TestCase):
    def test_original_ddr_copy_endpoints_do_not_consume_l1_ub_budget(self):
        graph = synthetic_jobs()
        for j in range(6):
            first, last = 6*j + 1, 6*j + 6
            ddr_in, copy_in, local_in = 1000+j, 1100+j, 1200+j
            local_out, copy_out, ddr_out = 1300+j, 1400+j, 1500+j
            graph["tensors"].extend([
                {"id": ddr_in, "pos": "DDR", "size": 64},
                {"id": local_in, "pos": "L1", "size": 64},
                {"id": local_out, "pos": "L1", "size": 64},
                {"id": ddr_out, "pos": "DDR", "size": 64}])
            graph["ops"].extend([
                {"id": copy_in, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 2},
                {"id": copy_out, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 2}])
            graph["edges"].extend([
                {"source": ddr_in, "target": copy_in},
                {"source": copy_in, "target": local_in},
                {"source": local_in, "target": first},
                {"source": last, "target": local_out},
                {"source": local_out, "target": copy_out},
                {"source": copy_out, "target": ddr_out}])
        plan, meta = build(SharingIndex(graph), 2, 60, {"L1": 7000, "UB": 0})
        self.assertTrue(meta["guard"])
        self.assertEqual(meta["selected"], "pipeline_capacity")
        self.assertEqual(len(plan["node_to_subgraph"]), 36)
        self.assertTrue(all(row["modeled_required_bytes"]["L1"] <= 7000
                            for row in meta["stage_memory"]))

    def test_direct_shared_ddr_input_explicitly_falls_back(self):
        graph = synthetic_jobs()
        graph["tensors"][0]["pos"] = "DDR"
        index = SharingIndex(graph)
        expected, _ = baseline(index, 2, 60)
        plan, meta = build(index, 2, 60, {"L1": 6000, "UB": 6000})
        self.assertEqual(plan, expected)
        self.assertFalse(meta["guard"])
        self.assertEqual(meta["reason"], "shared_ddr_input_requires_ub_materialization_model")

    def test_unknown_space_keeps_guarded_fallback(self):
        index = SharingIndex(synthetic_jobs())
        index.graph["tensors"][0]["pos"] = "UNKNOWN"
        with patch("src.q3_yuanzhifang.pipeline_capacity.pipeline_build", return_value=({"fallback": True}, {})):
            plan, meta = build(index, 2, 60, {"L1": 6000, "UB": 0})
        self.assertEqual(plan, {"fallback": True})
        self.assertFalse(meta["guard"])
        self.assertEqual(meta["reason"], "unsupported_tensor_memory_space")

    def test_exact_small_partition_and_flowshop_oracle(self):
        rng = random.Random(24533)
        feasible_count = infeasible_count = 0
        for _ in range(150):
            n = rng.randint(2, 7)
            k, jobs = rng.randint(1, min(4, n)), rng.randint(1, 6)
            weights, setup = [rng.randint(1, 20) for _ in range(n)], [rng.randint(0, 50) for _ in range(n)]
            shared = [[rng.randint(0, 8), rng.randint(0, 4)] for _ in range(n)]
            local = [[rng.randint(0, 6), rng.randint(0, 3)] for _ in range(n)]
            capacity = [rng.randint(6, 30), rng.randint(3, 15)]
            feasible = []
            for inside in itertools.combinations(range(1, n), k-1):
                cuts = [0, *inside, n]
                if all(sum(shared[p][r] for p in range(a, b)) +
                       max(local[p][r] for p in range(a, b)) <= capacity[r]
                       for a, b in zip(cuts, cuts[1:]) for r in range(2)):
                    feasible.append((recurrence(weights, setup, cuts, jobs), cuts))
            actual = partition(weights, setup, shared, local, capacity, k, jobs)
            if feasible:
                feasible_count += 1
                self.assertIsNotNone(actual)
                cuts, cost = actual
                self.assertEqual(cost, min(x[0] for x in feasible))
                self.assertIn((cost, cuts), feasible)
            else:
                infeasible_count += 1
                self.assertIsNone(actual)
        self.assertGreater(feasible_count, 10)
        self.assertGreater(infeasible_count, 10)

    def test_capacity_equality_and_single_byte_infeasibility(self):
        args = ([10, 20], [5, 6], [[8, 0], [0, 0]], [[2, 0], [1, 0]])
        self.assertIsNotNone(partition(*args, [10, 0], 1, 3))
        self.assertIsNone(partition(*args, [9, 0], 1, 3))

    def test_oversize_shared_input_falls_back_without_changing_baseline(self):
        graph = synthetic_jobs()
        expected, _ = baseline(SharingIndex(graph), 2, 60)
        actual, meta = build(SharingIndex(graph), 2, 60, {"L1": 5999, "UB": 0})
        self.assertEqual(actual, expected)
        self.assertFalse(meta["guard"])
        self.assertEqual(meta["reason"], "no_partition_fits_shared_residence_model")

    def test_singleton_coverage_and_memory_metadata(self):
        graph = synthetic_jobs()
        plan, meta = build(SharingIndex(graph), 2, 60, {"L1": 6000, "UB": 0})
        self.assertTrue(meta["guard"])
        self.assertEqual(meta["cuts"], [0, 4, 6])
        self.assertEqual(set(map(int, plan["node_to_subgraph"])), set(range(1, 37)))
        self.assertEqual(sorted(s for core in plan["core_schedules"] for s in core), list(range(36)))
        self.assertEqual(meta["stage_memory"][1]["modeled_required_bytes"], {"L1": 6000, "UB": 0})


if __name__ == "__main__":
    unittest.main()
