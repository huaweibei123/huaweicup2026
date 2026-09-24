"""Hand-verifiable relaxations and small exhaustive load checks; zero E0 calls."""
import itertools
import unittest

from src.q2_nikolastarx.global_bounds import certify, indivisible_work_bound


def operation(ident, pipe, cycles, kind="COMPUTE"):
    return {"id": ident, "pipe": pipe, "cycles": cycles, "op": kind}


class GlobalBoundsTests(unittest.TestCase):
    def test_indivisible_jobs_stronger_than_average(self):
        bound = indivisible_work_bound([100] * 5, 4)
        self.assertEqual(bound["cycles"], 200)
        self.assertEqual(bound["largest_jobs"], 5)
        self.assertEqual(bound["jobs_on_one_core"], 2)

    def test_pigeonhole_is_below_exhaustive_relaxed_optimum(self):
        # Exhaustive assignment is a tiny independent test oracle, never a solver.
        for jobs in ([8, 7, 6, 5, 4], [9, 1, 1], [5] * 6, [3, 2, 2, 1]):
            for cores in (1, 2, 3):
                optimum = sum(jobs)
                for assignment in itertools.product(range(cores), repeat=len(jobs)):
                    loads = [0] * cores
                    for duration, core in zip(jobs, assignment):
                        loads[core] += duration
                    optimum = min(optimum, max(loads))
                self.assertLessEqual(indivisible_work_bound(jobs, cores)["cycles"], optimum)

    def test_dependency_window_combines_release_work_and_tail(self):
        ops = [operation(0, "PIPE_M", 10), operation(9, "PIPE_M", 20)]
        ops.extend(operation(i, "PIPE_V", 10) for i in range(1, 9))
        edges = [{"source": 0, "target": i} for i in range(1, 9)]
        edges.extend({"source": i, "target": 9} for i in range(1, 9))
        result = certify({"ops": ops, "tensors": [], "edges": edges}, (2,))
        self.assertEqual(result["retained_compute_critical_path_cycles"], 40)
        self.assertEqual(result["by_core_count"][0]["makespan_lower_bound_cycles"], 70)

    def test_removed_original_copy_is_not_a_timing_edge(self):
        graph = {"ops": [operation(0, "PIPE_M", 10),
                         operation(1, "PIPE_MTE3", 1, "COPY_OUT"),
                         operation(2, "PIPE_V", 10)], "tensors": [],
                 "edges": [{"source": 0, "target": 1}, {"source": 1, "target": 2}]}
        result = certify(graph, (1,))
        self.assertEqual(result["removed_copy_only_contracted_edge_count"], 1)
        self.assertEqual(result["retained_compute_critical_path_cycles"], 10)
        self.assertEqual(result["by_core_count"][0]["makespan_lower_bound_cycles"], 10)

    def test_boundary_bytes_are_not_original_copy_cycles(self):
        graph = {"ops": [operation(0, "PIPE_MTE2", 999, "COPY_IN"),
                         operation(1, "PIPE_V", 5),
                         operation(2, "PIPE_MTE3", 999, "COPY_OUT")],
                 "tensors": [{"id": 10, "pos": "UB", "size": 70},
                             {"id": 11, "pos": "UB", "size": 20}],
                 "edges": [{"source": a, "target": b} for a, b in
                           ((0, 10), (10, 1), (1, 11), (11, 2))]}
        result = certify(graph, (1,))
        self.assertEqual(result["by_core_count"][0]["makespan_lower_bound_cycles"], 5)
        io = result["mandatory_boundary_io"]
        self.assertEqual(io["scheduled_copy_bytes_lower_bound"], 90)
        self.assertEqual(io["added_copy_bytes_lower_bound"], 0)
        self.assertFalse(io["ddr_time_bound_certified"])

    def test_multiple_producers_disable_precedence_but_keep_work(self):
        graph = {"ops": [operation(0, "PIPE_M", 3), operation(1, "PIPE_V", 4),
                         operation(2, "PIPE_M", 5)],
                 "tensors": [{"id": 10, "pos": "UB", "size": 1}],
                 "edges": [{"source": a, "target": b} for a, b in
                           ((0, 10), (1, 10), (10, 2))]}
        result = certify(graph, (1,))
        self.assertFalse(result["precedence_supported"])
        self.assertIsNone(result["retained_compute_critical_path_cycles"])
        self.assertEqual(result["by_core_count"][0]["makespan_lower_bound_cycles"], 8)

    def test_invalid_input_abstains_and_zero_cycle_uses_one(self):
        graph = {"ops": [operation(0, "PIPE_V", 0.5)], "tensors": [], "edges": []}
        self.assertFalse(certify(graph)["supported"])
        graph["ops"][0]["cycles"] = 0
        self.assertEqual(certify(graph, (1,))["by_core_count"][0]
                         ["makespan_lower_bound_cycles"], 1)


if __name__ == "__main__":
    unittest.main()
