import unittest

from src.q1_yuanzhifang.intact_pacing import assemble


def synthetic_rounds():
    return [{"chains": [[f"c{s}_{i}_{j}" for j in range(4)] for i in range(12)],
             "tail": [f"t{s}_{j}" for j in range(11)]} for s in range(24)]


def core_of(plan):
    task_core = {task: core for core, order in enumerate(plan["core_schedules"]) for task in order}
    return {node: task_core[task] for node, task in plan["node_to_subgraph"].items()}


class PacingStructureTest(unittest.TestCase):
    def test_fixed_task_counts_and_unchanged_chain_cores(self):
        rounds = synthetic_rounds()
        k3_control, _ = assemble(rounds, 3, "control")
        k3_paced, _ = assemble(rounds, 3, "paced")
        k4_paced, _ = assemble(rounds, 4, "paced")
        self.assertEqual([sum(map(len, p["core_schedules"])) for p in
                          (k3_control, k3_paced, k4_paced)], [96, 119, 143])
        self.assertEqual(core_of(k3_control), core_of(k3_paced))
        for plan in (k3_control, k3_paced, k4_paced):
            self.assertEqual(len(plan["node_to_subgraph"]), 24 * (12 * 4 + 11))
            for entry in rounds:
                for chain in entry["chains"]:
                    self.assertEqual(len({plan["node_to_subgraph"][u] for u in chain}), 1)

    def test_only_later_source_bin_split_and_phase_order(self):
        rounds = synthetic_rounds()
        _, tasks = assemble(rounds, 3, "paced")
        self.assertEqual([(t["phase"], t["chain_indices"]) for t in tasks if t["stage"] == 0 and t["core"] == 0],
                         [(0, [0, 1, 2, 3]), (2, [])])
        self.assertEqual([(t["phase"], t["chain_indices"]) for t in tasks if t["stage"] == 1 and t["core"] == 0],
                         [(0, [0]), (1, [1, 2, 3]), (2, [])])


if __name__ == "__main__":
    unittest.main()
