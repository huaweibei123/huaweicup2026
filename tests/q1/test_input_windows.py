import unittest

from src.q1.bounded_tasks import construct as bounded
from src.q1.input_windows import construct
from tests.q1.test_component_pack import graph
from stub_multicore_cut_and_schedule import derive_multicore_plan


def shared_inputs():
    g = graph([(u, "V", 10) for u in [1, 2, 3, 4, 11, 12, 13, 14]],
              [(u, u + 1) for u in [1, 2, 3, 11, 12, 13]])
    g["tensors"].extend({"id": t, "size": 8, "pos": "L1"} for t in [900, 901])
    g["edges"].extend({"source": t, "target": u}
                      for t, consumers in [(900, [1, 11]), (901, [3, 13])]
                      for u in consumers)
    return g


class InputWindowTests(unittest.TestCase):
    def test_complete_components_keep_core_while_windows_add_only_forward_edges(self):
        g = shared_inputs()
        p, d = construct(g, 2, input_budget_bytes=10, activation_bytes=10)
        self.assertEqual(d["phase_count"], 2)
        self.assertEqual([x["external_input_bytes"] for x in d["phases"]], [8, 8])
        self.assertEqual(p["core_schedules"], [[0, 2], [1, 3]])
        self.assertEqual(set(map(tuple, derive_multicore_plan(g, p)["dependency_pairs"])),
                         {(0, 2), (1, 3)})
        self.assertEqual(list(p["node_to_subgraph"]), [1, 2, 3, 4, 11, 12, 13, 14])

    def test_declines_do_not_leave_partial_plans(self):
        g = shared_inputs()
        for cores, kwargs in [(1, {}), (2, {}),
                              (2, {"input_budget_bytes": 10, "activation_bytes": 10, "max_phases": 1})]:
            p, d = construct(g, cores, **kwargs)
            self.assertEqual(p, bounded(g, cores)[0])
            self.assertEqual(d["selected"], "bounded04")

    def test_oversize_input_is_not_misrepresented_as_capacity_safe(self):
        g = shared_inputs()
        p, d = construct(g, 2, input_budget_bytes=4, activation_bytes=10)
        self.assertEqual(d["phase_count"], 2)
        self.assertTrue(all(x["external_input_bytes"] > d["input_budget_bytes"] for x in d["phases"]))
        self.assertEqual(len(derive_multicore_plan(g, p)["subgraph_ids"]), 4)

    def test_invalid_budgets_fail_before_construction(self):
        for kwargs in [{"input_budget_bytes": 0}, {"max_phases": True}]:
            with self.assertRaises(ValueError):
                construct(shared_inputs(), 2, **kwargs)


if __name__ == "__main__":
    unittest.main()
