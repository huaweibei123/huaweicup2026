import unittest

from src.q3_yuanzhifang.construct import SharingIndex
from src.q3_yuanzhifang.wave_capacity import build, model, structure
from test_pipeline_setup import synthetic_jobs


def residual_jobs():
    graph = synthetic_jobs()
    for j in range(6):
        tid = 200 + j
        graph["tensors"].append({"id": tid, "pos": "L1", "size": 100})
        graph["edges"].extend(({"source": 1+6*j, "target": tid},
                               {"source": tid, "target": 6+6*j}))
    return graph


class WaveCapacityTest(unittest.TestCase):
    def test_difference_frontier_and_active_hand_calculation(self):
        data = dict(length=4, weights=[[0, 0, 0, 0], [0, 0, 0, 0]],
                    lifetimes=[("L1", 7, 0, 3), ("L1", 5, 1, 2), ("UB", 3, 2, 3)])
        bmax, footprint = model(data, {"L1": 31, "UB": 6}, 4)
        self.assertEqual(footprint["active"], [[7, 12, 12, 7], [0, 0, 3, 3]])
        self.assertEqual(footprint["frontier"], [[0, 7, 12, 7, 0], [0, 0, 0, 3, 0]])
        self.assertEqual(bmax, 2)
        self.assertEqual(model(data, {"L1": 30, "UB": 6}, 4)[0], 2)

    def test_shared_original_copy_in_with_single_ddr_backing(self):
        graph = residual_jobs()
        graph["ops"].append({"id": 900, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 4})
        graph["tensors"].append({"id": 901, "pos": "DDR", "size": 6000})
        graph["edges"].extend(({"source": 901, "target": 900}, {"source": 900, "target": 100}))
        plan, meta = build(SharingIndex(graph), 2, 60, {"L1": 6300, "UB": 0})
        self.assertTrue(meta["guard"])
        self.assertEqual(len(plan["node_to_subgraph"]), 36)
        graph["edges"].append({"source": 901, "target": 1})
        _, reason = structure(SharingIndex(graph), 2)
        self.assertEqual(reason, "common_input_copy_semantics")

    def test_long_residual_frontier_boundary_and_balanced_waves(self):
        graph = residual_jobs()
        index = SharingIndex(graph)
        plan, meta = build(index, 2, 60, {"L1": 6299, "UB": 0})
        self.assertTrue(meta["guard"])
        self.assertEqual(meta["bmax"], 2)
        self.assertEqual(meta["F"]["L1"], [0, 100, 100, 100, 100, 100, 0])
        self.assertEqual(meta["A"]["L1"], [100]*6)
        self.assertEqual(meta["W"]["L1"], [0, 0, 0, 0, 0, 6000])
        self.assertEqual(meta["wave_sizes"], [[2, 1], [2, 1]])
        self.assertEqual(meta["conditional_shared_read_bound_bytes"], 24000)
        self.assertEqual(len(set(plan["node_to_subgraph"].values())), 36)
        inverse = {s: int(u) for u, s in plan["node_to_subgraph"].items()}
        owners = {u: c for c, seq in enumerate(plan["core_schedules"]) for u in map(inverse.get, seq)}
        self.assertEqual(len(owners), 36)
        self.assertTrue(all(len({owners[u] for u in range(1+6*j, 7+6*j)}) == 1 for j in range(6)))
        self.assertEqual([inverse[s] for s in plan["core_schedules"][0]][:4], [1, 13, 2, 14])
        _, exact = build(index, 2, 60, {"L1": 6300, "UB": 0})
        self.assertEqual(exact["bmax"], 3)

    def test_full_mode_is_fixed_control_on_same_assignment(self):
        index = SharingIndex(residual_jobs())
        cap = {"L1": 6299, "UB": 0}
        capacity_plan, capacity = build(index, 2, 60, cap)
        full_plan, full = build(index, 2, 60, cap, mode="full")
        self.assertTrue(full["guard"])
        self.assertEqual(full["wave_sizes"], [[3], [3]])
        self.assertFalse(full["modeled_full_wave_fit"])
        self.assertEqual(capacity_plan["node_to_subgraph"], full_plan["node_to_subgraph"])
        self.assertNotEqual(capacity_plan["core_schedules"], full_plan["core_schedules"])
        self.assertEqual(full["conditional_shared_read_bound_bytes"], 12000)

    def test_private_signature_mismatch_falls_back(self):
        graph = residual_jobs()
        graph["tensors"][-1]["size"] = 101
        _, meta = build(SharingIndex(graph), 2, 60, {"L1": 7000, "UB": 0})
        self.assertFalse(meta["guard"])
        self.assertEqual(meta["reason"], "private_tensor_template_mismatch")
        graph = residual_jobs()
        next(edge for edge in graph["edges"] if edge == {"source": 205, "target": 36})["target"] = 35
        _, reason = structure(SharingIndex(graph), 2)
        self.assertEqual(reason, "compute_dependency_template_mismatch")
        graph = residual_jobs()
        graph["edges"].extend({"source": 2+6*j, "target": 200+j} for j in range(6))
        _, reason = structure(SharingIndex(graph), 2)
        self.assertEqual(reason, "multiple_private_compute_producers")

    def test_direct_compute_ddr_and_multi_position_weight_reject(self):
        graph = residual_jobs()
        graph["tensors"].append({"id": 999, "pos": "DDR", "size": 20})
        graph["edges"].append({"source": 999, "target": 1})
        _, reason = structure(SharingIndex(graph), 2)
        self.assertEqual(reason, "direct_compute_ddr")
        graph = residual_jobs()
        graph["edges"].extend({"source": 100, "target": 5+6*j} for j in range(6))
        _, reason = structure(SharingIndex(graph), 2)
        self.assertEqual(reason, "common_input_consumers")


if __name__ == "__main__":
    unittest.main()
