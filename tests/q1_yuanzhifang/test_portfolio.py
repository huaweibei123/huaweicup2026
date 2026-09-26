"""Mandatory boundary-copy semantics and pinned implementation integrity."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/q1_yuanzhifang"))
from portfolio import boundary_cost, construct
from test_construct import graph_from_edges


class PortfolioTests(unittest.TestCase):
    def test_private_tasks_repeat_inputs_even_on_same_core(self):
        # A shared 120-byte source, two 60-byte intermediate tensors and a
        # zero-byte output (still one cycle per COPY in the frozen evaluator).
        graph = {"ops": [
            {"id": 0, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 2},
            *({"id": i, "op": "COMPUTE", "pipe": "PIPE_V", "cycles": 4} for i in (1, 2, 3)),
            {"id": 4, "op": "COPY_OUT", "pipe": "PIPE_MTE3", "cycles": 1}],
            "tensors": [{"id": 100 + i, "pos": "UB", "size": b} for i, b in enumerate((120, 60, 60, 0))],
            "edges": [{"source": a, "target": b} for a, b in (
                (0, 100), (100, 1), (100, 2), (1, 101), (101, 3),
                (2, 102), (102, 3), (3, 103), (103, 4))]}
        for mapping, schedules, count, nbytes, service in (
            ({1: 0, 2: 0, 3: 0}, [[0]], 2, 120, 3),
            ({1: 0, 2: 0, 3: 1}, [[0, 1]], 6, 360, 7),
            ({1: 0, 2: 1, 3: 2}, [[0, 1, 2]], 7, 480, 9),
            ({1: 0, 2: 1, 3: 2}, [[0, 2], [1]], 7, 480, 9)):
            actual = boundary_cost(graph, {"node_to_subgraph": mapping, "core_schedules": schedules}, 60)
            self.assertEqual(actual["boundary_copy_count"], count)
            self.assertEqual(actual["boundary_copy_bytes"], nbytes)
            self.assertEqual(actual["boundary_ddr_service_cycles"], service)
            self.assertEqual(actual["partition_added_copy_bytes"], nbytes - 120)

    def test_direct_edges_do_not_invent_copy_traffic(self):
        graph = graph_from_edges(3, [])
        graph["edges"] = [{"source": 0, "target": 1}, {"source": 1, "target": 2}]
        plan = {"node_to_subgraph": {0: 0, 1: 1, 2: 2}, "core_schedules": [[0, 1, 2]]}
        self.assertEqual(boundary_cost(graph, plan, 60)["boundary_copy_count"], 0)

    def test_pin_is_only_path_and_import_adaptation(self):
        folder = ROOT / "src/q1_yuanzhifang/upstream_bounded"
        manifest = json.loads((folder / "provenance.json").read_bytes())
        for file in manifest["files"]:
            raw = (ROOT / file["destination_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), file["adapted_sha256"])
            upstream = raw.decode().replace("Path(__file__).resolve().parents[3]", "Path(__file__).resolve().parents[2]")
            upstream = upstream.replace("from .component_pack import", "from src.q1.component_pack import")
            upstream = upstream.replace("from .tree_frontier import", "from src.q1.tree_frontier import")
            self.assertEqual(hashlib.sha256(upstream.encode()).hexdigest(), file["upstream_sha256"])

    def test_empty_candidate_switch_does_not_change_coverage(self):
        waits = {"task_same_core_wait_cycles": 100, "task_cross_core_wait_cycles": 1000}
        for edges in ([], [(0, 1), (1, 2), (2, 3)], [(0, 1), (0, 2), (1, 3), (2, 3)]):
            graph = graph_from_edges(4, edges)
            for cores in range(1, 6):
                plan, info = construct(graph, cores, waits, 60)
                self.assertEqual(set(plan["node_to_subgraph"]), {0, 1, 2, 3})
                self.assertEqual(len(plan["core_schedules"]), cores)
                self.assertEqual(info["candidate_count"], 1 if cores == 1 else 2)


if __name__ == "__main__":
    unittest.main()
