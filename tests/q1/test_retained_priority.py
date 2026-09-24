"""Synthetic graph checks only; no Task compilation or evaluator calls."""
import copy
import unittest
from unittest.mock import patch

from tests.q1.test_component_pack import graph
from src.q1.component_overload import _place, construct
from src.q1.bounded_tasks import split_large_tasks
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


def bundle_graph():
    g = graph([(1, "V", 100), (2, "V", 300), (3, "V", 300)]
              + [(u, "M", 300) for u in range(10, 19)], [(1, 2), (1, 3)])
    g["ops"].append({"id": 90, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 1})
    g["tensors"].append({"id": 9000, "size": 64, "pos": "UB"})
    g["edges"].append({"source": 90, "target": 9000})
    g["edges"].extend({"source": 9000, "target": o["id"]} for o in g["ops"] if o["id"] != 90)
    return g


class RetainedPriorityTests(unittest.TestCase):
    def test_priority_reorders_ready_but_duration_keeps_whole_bundle(self):
        g = graph([(1, "V", 10), (2, "V", 100)]
                  + [(u, "M", 50) for u in [10, 11, 12, 20, 21, 22]], [(1, 2)])
        ops = {o["id"]: o for o in g["ops"]}
        succ = {u: ({2} if u == 1 else set()) for u in ops}
        tasks = [[1], [2], [10, 11, 12], [20, 21, 22]]
        old, before = _place(tasks, succ, ops, 2, 100, 1000)
        new, after = _place(tasks, succ, ops, 2, 100, 1000,
                            ready_priority_overrides={2: 50, 3: 50})
        self.assertEqual(before["placement_order"][:2], [2, 3])
        self.assertEqual(after["placement_order"][:2], [0, 1])
        self.assertEqual(old["node_to_subgraph"], new["node_to_subgraph"])
        self.assertEqual(after["task_compute_weight"], [10, 100, 150, 150])
        self.assertEqual(after["task_ready_priority"], [110, 100, 50, 50])
        for t in [2, 3]:
            self.assertEqual(after["task_finish_proxy"][t] - after["task_start_proxy"][t], 150)
        for order in new["core_schedules"]:
            for a, b in zip(order, order[1:]):
                self.assertGreaterEqual(after["task_start_proxy"][b], after["task_finish_proxy"][a] + 100)
        validate_task_order(derive_multicore_plan(g, new))

    def test_synthetic_construction_preserves_mapping_shared_inputs_and_split_tails(self):
        g = bundle_graph()
        original = copy.deepcopy(g)
        old, d0 = construct(g, 3)
        new, d = construct(g, 3, retained_component_priority=True)
        self.assertEqual(d["selected"], "overload-list")
        self.assertEqual(d["algorithm_id"], "q1-component-overload-retained-priority")
        self.assertEqual(new["node_to_subgraph"], old["node_to_subgraph"])
        self.assertEqual(set(new), {"node_to_subgraph", "core_schedules"})
        self.assertEqual(d["split_components"], d0["split_components"])
        self.assertEqual(d["placement"]["task_compute_weight"], d0["placement"]["task_compute_weight"])
        self.assertEqual(g, original)
        self.assertNotIn(90, new["node_to_subgraph"])
        placement = d["placement"]
        retained = placement["retained_priority_overrides"]
        self.assertEqual(sorted(retained.values()), [300, 300, 300])
        self.assertTrue(all(placement["task_compute_weight"][t] == 900 for t in retained))
        self.assertIn(d0["placement"]["placement_order"][0], retained)
        self.assertNotIn(placement["placement_order"][0], retained)
        for t, priority in enumerate(placement["task_ready_priority"]):
            if t not in retained:
                self.assertEqual(priority, placement["task_data_tail"][t])
        self.assertEqual((new, d), construct(g, 3, retained_component_priority=True))
        validate_task_order(derive_multicore_plan(g, new))

    def test_soft_chunks_keep_the_same_partition_for_both_priority_policies(self):
        g = bundle_graph()
        def small_chunks(graph_json, plan):
            return split_large_tasks(graph_json, plan, trigger_ops=2, chunk_ops=1)
        with patch("src.q1.component_overload.split_large_tasks", side_effect=small_chunks):
            old, d0 = construct(g, 3)
            new, d = construct(g, 3, retained_component_priority=True)
        self.assertTrue(d["chunks"]["split_tasks"])
        self.assertEqual(d["chunks"], d0["chunks"])
        self.assertEqual(new["node_to_subgraph"], old["node_to_subgraph"])
        validate_task_order(derive_multicore_plan(g, new))

    def test_zero_cycle_retained_components_still_have_positive_priority(self):
        g = graph([(1, "V", 0), (2, "V", 10), (3, "V", 10)]
                  + [(u, "M", 0) for u in range(10, 16)], [(1, 2), (1, 3)])
        p, d = construct(g, 3, retained_component_priority=True)
        self.assertEqual(d["selected"], "overload-list")
        for t, priority in d["placement"]["retained_priority_overrides"].items():
            self.assertEqual(priority, 1)
            self.assertEqual(d["placement"]["task_compute_weight"][t], 2)
        validate_task_order(derive_multicore_plan(g, p))

    def test_internal_copy_bridge_does_not_create_retained_component(self):
        g = graph([(1, "V", 100), (2, "M", 1), (3, "V", 300), (4, "V", 300)]
                  + [(u, "M", 300) for u in range(10, 19)], [(1, 2), (2, 3), (1, 4)])
        g["ops"][1]["op"] = "COPY_IN"
        old, _ = construct(g, 3)
        new, d = construct(g, 3, retained_component_priority=True)
        self.assertEqual(new["node_to_subgraph"], old["node_to_subgraph"])
        self.assertNotIn(2, new["node_to_subgraph"])
        self.assertEqual(d["split_components"][0]["ops"], 3)
        validate_task_order(derive_multicore_plan(g, new))

    def test_fallbacks_are_unchanged_and_flag_requires_boolean(self):
        g = bundle_graph()
        for cores, options in [(1, {}), (3, {"max_rounds": 1}), (3, {"max_sinks": 1})]:
            old, d0 = construct(g, cores, **options)
            new, d = construct(g, cores, retained_component_priority=True, **options)
            self.assertEqual(new, old)
            self.assertEqual(d["selected"], d0["selected"])
            self.assertNotIn("placement", d)
        for value in [1, "true", None]:
            with self.assertRaises(ValueError):
                construct(g, 3, retained_component_priority=value)

    def test_priority_overrides_cannot_replace_dependent_tail_or_invent_work(self):
        g = graph([(1, "V", 10), (2, "V", 20), (3, "M", 40)], [(1, 2)])
        ops = {o["id"]: o for o in g["ops"]}
        for overrides in [{0: 1}, {1: 1}, {2: 0}, {2: True}, {2: 41}, {3: 1}, {False: 1}]:
            with self.assertRaises(ValueError):
                _place([[1], [2], [3]], {1: {2}, 2: set(), 3: set()}, ops, 2, 100, 1000,
                       ready_priority_overrides=overrides)


if __name__ == "__main__":
    unittest.main()
