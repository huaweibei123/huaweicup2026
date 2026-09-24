import unittest
from src.q1.bounded_tasks import split_large_tasks
from tests.q1.test_component_pack import graph


class BoundedTaskTests(unittest.TestCase):
    def test_independent_nodes_split_in_place(self):
        g = graph([(v, "V", 1) for v in range(12)], [])
        original = {"node_to_subgraph": {v: 0 for v in range(12)}, "core_schedules": [[0], []]}
        p, d = split_large_tasks(g, original, 8, 4)
        self.assertEqual(p["core_schedules"], [[0, 1, 2], []])
        self.assertEqual(d["split_tasks"][0]["chunk_compute_ops"], [4, 4, 4])
        self.assertEqual(original["core_schedules"], [[0], []])

    def test_indivisible_chain_is_not_silently_cut(self):
        g = graph([(v, "V", 1) for v in range(10)], [(v, v+1) for v in range(9)])
        original = {"node_to_subgraph": {v: 0 for v in range(10)}, "core_schedules": [[0]]}
        p, d = split_large_tasks(g, original, 8, 4)
        self.assertEqual(p, original)
        self.assertEqual(d["oversize_indivisible_components"], [{"task": 0, "ops": 10}])

    def test_tail_dependencies_survive_refinement(self):
        g = graph([(v, "V", 1) for v in range(3)], [(0, 2), (1, 2)])
        original = {"node_to_subgraph": {0: 0, 1: 0, 2: 1}, "core_schedules": [[0], [1]]}
        p, d = split_large_tasks(g, original, 1, 1)
        self.assertEqual(p["core_schedules"], [[0, 2], [1]])
        self.assertEqual(p["node_to_subgraph"], {0: 0, 1: 2, 2: 1})

    def test_small_plans_remain_byte_structure_equal(self):
        g = graph([(1, "V", 1)], [])
        original = {"node_to_subgraph": {1: 4}, "core_schedules": [[4]]}
        p, _ = split_large_tasks(g, original)
        self.assertIs(p, original)


if __name__ == "__main__":
    unittest.main()
