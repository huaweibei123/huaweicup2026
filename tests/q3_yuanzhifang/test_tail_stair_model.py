import itertools
import unittest

from src.q3_yuanzhifang.construct import SharingIndex
from src.q3_yuanzhifang.tail_stair_model import analyze


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


def independent_single_pipe(durations):
    """Tiny event oracle: each core has one FIFO pipe; tail has a cross-core chain."""
    sequences = []
    for c, count in enumerate((1, 2, 3)):
        sequence = []
        for p in range(3):
            if p == c:
                sequence.append(("tail", p))
            sequence.extend(((c, j), p) for j in range(count))
        sequences.append(sequence)
    cursor, free = [0]*3, [0]*3
    finished, started = {}, {}
    while sum(cursor) < sum(map(len, sequences)):
        progress = False
        for c, seq in enumerate(sequences):
            if cursor[c] == len(seq):
                continue
            job, p = seq[cursor[c]]
            predecessor = (job, p-1) if p else None
            if predecessor is not None and predecessor not in finished:
                continue
            start = max(free[c], finished.get(predecessor, 0))
            started[(job, p)] = start
            free[c] = start + durations[p]
            finished[(job, p)] = free[c]
            cursor[c] += 1
            progress = True
        if not progress:
            raise AssertionError("oracle deadlock")
    return started, finished


class TailStairModelTest(unittest.TestCase):
    def test_beta_stair_coverage_topology_and_width(self):
        index = SharingIndex(synthetic(10))
        schedules, meta = analyze(index, 3, {"L1": 90, "UB": 0})
        self.assertEqual(meta["beta"], [4, 4, 4])
        self.assertEqual(meta["U"], [3, 3, 3])
        self.assertEqual(meta["h"], 1)
        self.assertEqual(meta["first_wave_sizes"], [1, 2, 3])
        self.assertEqual([p["full_job_wave_sizes"] for p in meta["phase"]],
                         [[1, 2], [2, 1], [3]])
        self.assertEqual(sorted(u for seq in schedules for u in seq), list(range(1, 31)))
        owner = {u: c for c, seq in enumerate(schedules) for u in seq}
        rank = {u: i for seq in schedules for i, u in enumerate(seq)}
        self.assertTrue(all((owner[u] < owner[v] if owner[u] != owner[v]
                             else rank[u] < rank[v])
                            for u in index.succ for v in index.succ[u]))
        self.assertTrue(all(seq.index(index.components[-1][meta["cuts"][c]]) <
                            seq.index(index.components[c][meta["cuts"][c]])
                            for c, seq in enumerate(schedules)))
        self.assertTrue(meta["no_plan"] and meta["no_derive"])

    def test_stair_guard_rejects_insufficient_first_wave_room(self):
        with self.assertRaisesRegex(ValueError, "h < 1"):
            analyze(SharingIndex(synthetic(7)), 3, {"L1": 90, "UB": 0})

    def test_single_pipe_formula_against_independent_event_oracle(self):
        for durations in itertools.product((1, 2, 3), repeat=3):
            starts, ends = independent_single_pipe(durations)
            prefix = [0]
            for d in durations:
                prefix.append(prefix[-1] + d)
            for c, n in enumerate((1, 2, 3)):
                a, b = c, c+1
                predicted_end = (n+1)*prefix[b] - prefix[a] - n*durations[b-1]
                self.assertEqual(ends[("tail", c)], predicted_end)
                self.assertEqual(starts[("tail", c)], n*prefix[a])


if __name__ == "__main__":
    unittest.main()
