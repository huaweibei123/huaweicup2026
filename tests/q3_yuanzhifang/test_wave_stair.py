import unittest

from src.q3_yuanzhifang.construct import SharingIndex
from src.q3_yuanzhifang.wave_stair import build


def synthetic(count):
    ops, tensors, edges = [], [{"id": 1000, "pos": "L1", "size": 50}], []
    for j in range(count):
        a = 1 + 3*j
        ops.extend(({"id": a, "op": "MUL", "pipe": "PIPE_M", "cycles": 10},
                    {"id": a+1, "op": "ADD", "pipe": "PIPE_V", "cycles": 10},
                    {"id": a+2, "op": "MUL", "pipe": "PIPE_M", "cycles": 10}))
        edges.extend(({"source": a, "target": a+1},
                      {"source": a+1, "target": a+2},
                      {"source": 1000, "target": a+2}))
        tid = 2000+j
        tensors.append({"id": tid, "pos": "L1", "size": 10})
        edges.extend(({"source": a, "target": tid}, {"source": tid, "target": a+2}))
    return {"ops": ops, "tensors": tensors, "edges": edges}


class WaveStairTest(unittest.TestCase):
    def test_real_derive_of_two_field_singleton_plan_and_tail_first_order(self):
        index = SharingIndex(synthetic(10))
        plan, meta = build(index, 3, 60, {"L1": 90, "UB": 0})
        self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
        mapping = plan["node_to_subgraph"]
        self.assertEqual(set(map(int, mapping)), set(index.ops))
        self.assertEqual(len(set(mapping.values())), len(index.ops))
        self.assertEqual(sorted(s for seq in plan["core_schedules"] for s in seq),
                         sorted(mapping.values()))
        self.assertEqual((meta["guard"], meta["selected"], meta["active_cores"]),
                         (True, "wave_stair", 3))
        self.assertEqual(meta["first_wave_sizes"], [1, 2, 3])
        self.assertEqual(meta["full_jobs_per_core"], 3)
        self.assertEqual(meta["tail_job_id"], 9)
        inverse = {s: int(u) for u, s in mapping.items()}
        for c, seq in enumerate(plan["core_schedules"]):
            ids = [inverse[s] for s in seq]
            tail = index.components[-1][meta["cuts"][c]]
            first_full = index.components[c][meta["cuts"][c]]
            self.assertLess(ids.index(tail), ids.index(first_full))
        self.assertTrue(meta["derive_checked"] and meta["plan_built"])
        self.assertEqual(meta["internal_E0_calls"], 0)

    def test_stair_capacity_guard_rejects_without_fallback(self):
        with self.assertRaisesRegex(ValueError, "h < 1"):
            build(SharingIndex(synthetic(7)), 3, 60, {"L1": 90, "UB": 0})

    def test_structure_guard_rejects_without_fallback(self):
        graph = synthetic(10)
        graph["tensors"][-1]["size"] = 11
        with self.assertRaisesRegex(ValueError, "private_tensor_template_mismatch"):
            build(SharingIndex(graph), 3, 60, {"L1": 90, "UB": 0})


if __name__ == "__main__":
    unittest.main()
