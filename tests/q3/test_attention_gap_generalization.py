"""Small deterministic structural checks for gap placement; no E0 or solver."""
from copy import deepcopy
import random
import unittest

from src.q3.attention_rows import construct
from src.q3.construct import Index, derive_multicore_plan
from test_attention_rows import attention_ffn_graph, attention_graph, dag_timing, plan_words


def varied_graph(seed, panel_count, ffn_count):
    rng = random.Random(seed)
    graph = {"ops": [], "tensors": [], "edges": []}
    for panel in range(panel_count):
        builder, *_ = (attention_ffn_graph(ffn_count) if ffn_count else attention_graph())
        source = builder.graph
        op_ids = [op["id"] for op in source["ops"]]
        tensor_ids = [tensor["id"] for tensor in source["tensors"]]
        shuffled_ops, shuffled_tensors = op_ids[:], tensor_ids[:]
        rng.shuffle(shuffled_ops)
        rng.shuffle(shuffled_tensors)
        offset = seed * 100000 + panel * 10000
        remap = {old: offset + 17 * (i + 1) for i, old in enumerate(shuffled_ops)}
        remap.update({old: 50000000 + offset + 19 * (i + 1)
                      for i, old in enumerate(shuffled_tensors)})
        m_scale, v_scale = ((1, 15), (15, 1), (1, 1))[seed % 3]
        for original in source["ops"]:
            op = dict(original, id=remap[original["id"]])
            if op["pipe"] in {"PIPE_M", "PIPE_V"}:
                op["cycles"] *= m_scale if op["pipe"] == "PIPE_M" else v_scale
            graph["ops"].append(op)
        graph["tensors"].extend(dict(tensor, id=remap[tensor["id"]])
                                for tensor in source["tensors"])
        graph["edges"].extend({"source": remap[edge["source"]],
                               "target": remap[edge["target"]]}
                              for edge in source["edges"])
    for key in ("ops", "tensors", "edges"):
        rng.shuffle(graph[key])
    return graph


class AttentionGapGeneralizationTests(unittest.TestCase):
    def test_sixty_fixed_small_structural_cases(self):
        checked = 0
        for seed in range(10):
            for panels in (1, 2):
                for ffn_count in (0, 1, 2):
                    graph = varied_graph(seed, panels, ffn_count)
                    original = deepcopy(graph)
                    index = Index(graph)
                    cores = 1 + (seed + panels + ffn_count) % 5
                    plan, metadata = construct(index, cores, cross_delay=5,
                                               pack_ffn=bool(ffn_count), placement_mode="gap")
                    self.assertEqual(graph, original)
                    self.assertEqual(metadata["row_count"], panels)
                    if ffn_count:
                        self.assertEqual(metadata["packed_ffn_count"], panels * ffn_count)
                    self.assertEqual(metadata["placement_mode"], "gap")
                    self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
                    words = plan_words(plan)
                    self.assertEqual(len(words), cores)
                    self.assertEqual({u for word in words for u in word}, set(index.ops))
                    self.assertEqual(sum(map(len, words)), len(index.ops))
                    derive_multicore_plan(graph, plan)
                    # The whole-core enhanced DAG is stricter than two-pipe
                    # overlap and detects dependency/order cycles.
                    dag_timing(index, words, 5, whole_core_order=True)
                    starts, finishes = dag_timing(index, words, 5)
                    owner = {u: c for c, word in enumerate(words) for u in word}
                    self.assertTrue(all(starts[v] >= finishes[u] +
                                        (5 if owner[u] != owner[v] else 0)
                                        for u in index.ops for v in index.succ[u]))
                    checked += 1
        self.assertEqual(checked, 60)
