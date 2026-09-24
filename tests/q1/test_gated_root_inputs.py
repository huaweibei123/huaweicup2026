"""Generator-only checks; never invoke a solver or evaluator."""
import hashlib
import json
import unittest

from src.q1_benchmarks.gated_root_synthetic_inputs import fixtures, FAMILIES, SIZES


def digest(graph):
    payload = (json.dumps(graph, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(payload).hexdigest()


class SyntheticInputsTests(unittest.TestCase):
    def test_shape_ids_edges_and_repeat_hashes(self):
        first = list(fixtures())
        second = list(fixtures())
        self.assertEqual(len(first), 9)
        self.assertEqual(len({name for name, *_ in first}), 9)
        self.assertEqual([(name, digest(graph)) for name, graph, *_ in first],
                         [(name, digest(graph)) for name, graph, *_ in second])
        for (name, graph, cores, meta), (family, specs, shapes, expected_cores) in zip(
                first, [(family, specs, shapes, cores) for family, specs, shapes, cores in FAMILIES
                        for _ in SIZES]):
            with self.subTest(name=name):
                self.assertEqual(cores, expected_cores)
                self.assertEqual(meta["family"], family)
                self.assertEqual(meta["rounds"], [list(s) for s in specs])
                self.assertEqual(meta["reduction_shapes"], list(shapes))
                self.assertIn(meta["tensor_size_bytes"], SIZES)
                self.assertTrue(meta["synthetic_only"])
                compute = sum(width * depth + width - 1 for width, depth, *_ in specs)
                self.assertEqual(len(graph["ops"]), compute + 2)
                self.assertEqual(len(graph["tensors"]), compute + 3)
                self.assertEqual(len(graph["edges"]),
                                 len(graph["ops"]) + 2 +
                                 sum(width*depth + 2*(width-1) for width, depth, *_ in specs))
                op_ids = {o["id"] for o in graph["ops"]}
                tensor_ids = {t["id"] for t in graph["tensors"]}
                self.assertEqual(len(op_ids), len(graph["ops"]))
                self.assertEqual(len(tensor_ids), len(graph["tensors"]))
                self.assertFalse(op_ids & tensor_ids)
                self.assertEqual({t["size"] for t in graph["tensors"]},
                                 {meta["tensor_size_bytes"]})
                self.assertEqual(sum(o["op"] == "COPY_IN" for o in graph["ops"]), 1)
                self.assertEqual(sum(o["op"] == "COPY_OUT" for o in graph["ops"]), 1)
                self.assertEqual(sum(t["pos"] == "DDR" for t in graph["tensors"]), 2)
                produced = {e["target"] for e in graph["edges"]
                            if e["source"] in op_ids and e["target"] in tensor_ids}
                self.assertEqual(len(produced), len(graph["ops"]))
                self.assertEqual(len(set((e["source"], e["target"]) for e in graph["edges"])),
                                 len(graph["edges"]))


if __name__ == "__main__":
    unittest.main()
