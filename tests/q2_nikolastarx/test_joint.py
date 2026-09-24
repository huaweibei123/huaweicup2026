import unittest

from src.q2_nikolastarx.joint import FixedAssignment, derive_multicore_plan


def graph(ops, edges=()):
    return {"ops": [{"id": i, "op": "COMPUTE", "pipe": pipe, "cycles": cycles}
                    for i, pipe, cycles in ops], "tensors": [],
            "edges": [{"source": a, "target": b} for a, b in edges]}


def parent(g):
    return {"node_to_subgraph": {str(op["id"]): 0 for op in g["ops"]},
            "core_schedules": [[0]]}


class JointTests(unittest.TestCase):
    def test_full_ready_sees_critical_job_outside_id_window(self):
        g = graph([(i, "PIPE_M", 100 if i == 40 else 1) for i in range(1, 41)])
        idx = FixedAssignment(g, parent(g))
        self.assertEqual(idx.order("critical32")[0], 1)
        self.assertEqual(idx.order("critical")[0], 40)

    def test_earliest_start_exposes_other_pipe(self):
        g = graph([(1, "PIPE_M", 100), (2, "PIPE_M", 99), (3, "PIPE_V", 1)])
        idx = FixedAssignment(g, parent(g))
        self.assertEqual(idx.order("critical"), [1, 2, 3])
        self.assertEqual(idx.order("earliest_start"), [1, 3, 2])

    def test_copy_contraction_preserved(self):
        g = graph([(1, "PIPE_M", 1), (2, "PIPE_MTE3", 1), (3, "PIPE_V", 100)], [(1, 2), (2, 3)])
        g["ops"][1]["op"] = "COPY_OUT"
        p = {"node_to_subgraph": {"3": 1, "1": 0}, "core_schedules": [[0, 1]]}
        idx = FixedAssignment(g, p)
        for policy in ("id", "critical32", "critical", "earliest_start"):
            self.assertEqual(idx.order(policy), [1, 3])

    def test_stable_mapping_and_owner_for_all_policies(self):
        g = graph([(5, "PIPE_M", 1), (3, "PIPE_V", 2), (2, "PIPE_M", 1)], [(5, 2)])
        p = {"node_to_subgraph": {"3": 1, "5": 0, "2": 2}, "core_schedules": [[0, 2], [1], []]}
        idx = FixedAssignment(g, p)
        mapping = None
        for policy in ("id", "critical32", "critical", "earliest_start"):
            plan = idx.build(policy)
            self.assertEqual(list(plan["node_to_subgraph"]), list(p["node_to_subgraph"]))
            if mapping is not None:
                self.assertEqual(list(plan["node_to_subgraph"].items()), mapping)
            mapping = list(plan["node_to_subgraph"].items())
            view = derive_multicore_plan(g, plan)
            self.assertEqual({op: view["core_by_subgraph"][sg] for op, sg in view["mapping"].items()}, idx.owner)
            self.assertEqual(plan["core_schedules"][2], [])


if __name__ == "__main__":
    unittest.main()
