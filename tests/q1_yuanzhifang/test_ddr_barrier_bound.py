"""Independent arithmetic and theorem-guard tests; no official scoring."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/q1_yuanzhifang"))
from ddr_barrier_bound import certificate, plan_terms
from star_frontier import guarded_stages, construct as split_construct
from prefetch_frontier import construct as intact_construct
from test_star_frontier import model_graph, WAITS


def tensor_graph(rounds, shape):
    graph = model_graph(rounds, shape)
    stages, _ = guarded_stages(graph)
    originals = []
    for b in range(12):
        copy = len(graph["ops"])
        graph["ops"].append({"id": copy, "op": "COPY_IN", "pipe": "PIPE_MTE2", "cycles": 547})
        tensor = 100000 + b
        originals.append(tensor)
        graph["tensors"].append({"id": tensor, "size": 32768, "pos": "UB"})
        graph["edges"].append({"source": copy, "target": tensor})
    for entry in stages["rounds"]:
        for b, chain in enumerate(entry["chains"]):
            graph["edges"].append({"source": originals[b], "target": chain[0]})
            for u, v in zip(chain, chain[1:]):
                tensor = 200000 + u
                graph["tensors"].append({"id": tensor, "size": 32768, "pos": "UB"})
                graph["edges"].extend(({"source": u, "target": tensor}, {"source": tensor, "target": v}))
    return graph


class BarrierTests(unittest.TestCase):
    def test_reduction_depth_tightens_bound(self):
        for shape, d in (("comb", 13), ("balanced", 39)):
            for rounds in (1, 2, 24):
                with self.subTest(shape=shape, rounds=rounds):
                    cert = certificate(tensor_graph(rounds, shape), 60, WAITS)
                    self.assertTrue(cert["supported"], cert)
                    first = 12 * 547 + 4 * 524 + d
                    self.assertEqual(cert["universal_makespan_lower_bound_cycles"], rounds * first + (rounds - 1) * 100)
                    self.assertEqual([s["minimum_reduction_path_cycles"] for s in cert["stages"]], [d] * rounds)
                    self.assertEqual(len(cert["private_internal_links"]), 36 * rounds)
        self.assertEqual(certificate(tensor_graph(24, "balanced"), 60, WAITS)["universal_makespan_lower_bound_cycles"], 211076)

    def test_pairs_and_cuts_are_plan_specific(self):
        graph = tensor_graph(2, "balanced")
        cert = certificate(graph, 60, WAITS)
        for fused in (False, True):
            plan, _ = intact_construct(graph, 5, WAITS, startup_cores=4, fuse_reductions=fused)
            terms = plan_terms(cert, plan)
            self.assertEqual((terms["M"], terms["B"]), (24, 0))
            self.assertEqual(terms["joint_lower_bound_cycles"], 17498)
            self.assertFalse(terms["plan_legality_checked"])
        plan, _ = split_construct(graph, 5, WAITS)
        self.assertEqual((plan_terms(cert, plan)["M"], plan_terms(cert, plan)["B"]), (24, 6))
        one = {"node_to_subgraph": {o["id"]: 0 for o in graph["ops"] if o["op"] != "COPY_IN"}, "core_schedules": [[0]]}
        terms = plan_terms(cert, one)
        self.assertEqual((terms["M"], terms["B"]), (12, 0))
        self.assertEqual(terms["blocking_lower_bound_cycles"], 17498 + 12 * 524)

    def test_rejects_missing_tensor_hypotheses(self):
        original = tensor_graph(2, "balanced")
        shared = deepcopy(original)
        for edge in shared["edges"]:
            if edge["source"] == 100001:
                edge["source"] = 100000
        self.assertFalse(certificate(shared, 60, WAITS)["supported"])
        mismatched = deepcopy(original)
        next(t for t in mismatched["tensors"] if t["id"] == 200000)["size"] = 32767
        self.assertFalse(certificate(mismatched, 60, WAITS)["supported"])
        incomplete = deepcopy(original)
        incomplete["edges"] = [e for e in incomplete["edges"] if e != {"source": 100000, "target": 59}]
        self.assertFalse(certificate(incomplete, 60, WAITS)["supported"])

    def test_rejects_unsupported_numerical_regimes(self):
        graph = tensor_graph(1, "balanced")
        for bandwidth in (30, 100):
            self.assertFalse(certificate(graph, bandwidth, WAITS)["supported"])
        self.assertFalse(certificate(graph, 60, {"task_same_core_wait_cycles": 1000, "task_cross_core_wait_cycles": 100})["supported"])
        self.assertFalse(certificate(graph, 60, {"task_same_core_wait_cycles": 30000, "task_cross_core_wait_cycles": 40000})["supported"])


if __name__ == "__main__":
    unittest.main()
