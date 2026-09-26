import unittest

from src.q3_yuanzhifang.construct import SharingIndex
from src.q3_yuanzhifang.tail_phase_model import analyze


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


class TailPhaseModelTest(unittest.TestCase):
    def test_staggered_phase_covers_each_compute_and_respects_wave_width(self):
        sequences, meta = analyze(SharingIndex(synthetic(7)), 3, {"L1": 70, "UB": 0})
        self.assertEqual(sorted(u for seq in sequences for u in seq), list(range(1, 22)))
        self.assertEqual(meta["q"], 2)
        self.assertEqual(meta["bmax"], 2)
        self.assertEqual([p["tail_wave_index"] for p in meta["phase"]], [0, 1, 1])
        self.assertEqual([p["full_job_wave_sizes"] for p in meta["phase"]],
                         [[1, 1], [1, 1], [2, 0]])
        self.assertTrue(all(max(p["full_job_wave_sizes"]) <= meta["bmax"] for p in meta["phase"]))
        self.assertTrue(all(p["tail_wave_full_jobs"] + 1 <= meta["bmax"] for p in meta["phase"]))
        self.assertEqual(meta["workload_peak_cycles"], 50)
        self.assertGreaterEqual(meta["lower_bound_cycles"], meta["workload_peak_cycles"])
        self.assertTrue(meta["no_plan"] and meta["no_derive"])

    def test_q_smaller_than_phase_prefix_guard(self):
        with self.assertRaisesRegex(ValueError, "q >= cores-1"):
            analyze(SharingIndex(synthetic(4)), 3, {"L1": 70, "UB": 0})


if __name__ == "__main__":
    unittest.main()
