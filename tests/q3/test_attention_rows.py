"""Synthetic original tensor graphs and independent scheduling checks; 0 E0."""
import heapq
import hashlib
import json
import random
import unittest
from functools import lru_cache
from unittest.mock import patch

from src.q3 import attention_rows
from src.q3.attention_rows import _ready_word, construct, recognize
from src.q3.construct import Index, UnsupportedStructure, derive_multicore_plan


class GraphBuilder:
    def __init__(self):
        self.graph = {"ops": [], "tensors": [], "edges": []}
        self.next_op, self.next_tensor = 7, 10000

    def tensor(self, size=64, pos="UB"):
        u = self.next_tensor
        self.next_tensor += 11
        self.graph["tensors"].append({"id": u, "pos": pos, "size": size})
        return u

    def op(self, kind, pipe, cycles, inputs, size=64, pos="UB"):
        u = self.next_op
        self.next_op += 7
        t = self.tensor(size, pos)
        self.graph["ops"].append({"id": u, "op": kind, "pipe": pipe, "cycles": cycles})
        self.graph["edges"].extend({"source": x, "target": u} for x in inputs)
        self.graph["edges"].append({"source": u, "target": t})
        return u, t

    def source(self, size=64, pos="L1"):
        ddr = self.tensor(size, "DDR")
        return self.op("COPY_IN", "PIPE_MTE2", 0, [ddr], size, pos)[1]


def attention_graph():
    """Two score/value lanes, original max/sum trees, and one closed query row."""
    b = GraphBuilder()
    vector, weight, scalar = b.source(), b.source(), b.source(2, "UB")
    front = [b.op("MATMUL", "PIPE_M", w, [vector, weight], pos="L1")
             for w in (7, 3, 29, 5, 37)]
    q, k0, k1, v0, v1 = front
    row = []

    def operation(kind, cycles, inputs, size=64, pipe="PIPE_V", pos="UB"):
        result = b.op(kind, pipe, cycles, inputs, size, pos)
        row.append(result[0])
        return result

    scores = []
    for k, cycles in ((k0, 9), (k1, 11)):
        m = operation("MATMUL", cycles, [q[1], k[1]], pipe="PIPE_M", pos="L1")
        scores.append(operation("DIV", 3, [m[1], scalar]))
    maxima = [operation("REDUCE", 2, [s[1]], 16) for s in scores]
    difference = operation("SUB", 1, [maxima[0][1], maxima[1][1]], 16)
    relu = operation("RELU", 1, [difference[1]], 16)
    maximum = operation("ADD", 1, [maxima[1][1], relu[1]], 16)
    exps = []
    for score in scores:
        shift = operation("SUB", 2, [score[1], maximum[1]])
        exps.append(operation("EXP", 4, [shift[1]]))
    reductions = [operation("REDUCE", 2, [e[1]], 16) for e in exps]
    denominator = operation("ADD", 1, [r[1] for r in reductions], 16)
    weighted = [operation("MATMUL", w, [e[1], v[1]], pipe="PIPE_M", pos="L1")
                for e, v, w in zip(exps, (v0, v1), (7, 13))]
    numerator = operation("ADD", 2, [w[1] for w in weighted])
    sink = operation("DIV", 3, [numerator[1], denominator[1]])
    b.op("COPY_OUT", "PIPE_MTE3", 0, [sink[1]], pos="DDR")
    return b, {"nodes": tuple(sorted(row)), "sink": sink[0], "q": q[0],
               "k": (k0[0], k1[0]), "v": (v0[0], v1[0]),
               "exp": exps[0], "front": front, "output": sink[1],
               "inputs": tuple(sorted([p[1] for p in front] + [scalar]))}


def plan_words(plan):
    inverse = {sg: int(u) for u, sg in plan["node_to_subgraph"].items()}
    return [[inverse[sg] for sg in seq] for seq in plan["core_schedules"]]


def attention_ffn_graph(count=2):
    """Original tensor-port FFN diamonds after a valid attention row."""
    builder, row = attention_graph()
    weight = builder.source()
    diamonds = []
    for _ in range(count):
        a = builder.op("MATMUL", "PIPE_M", 1, [row["output"], weight])
        b = builder.op("SIGMOID", "PIPE_V", 10, [a[1]])
        c = builder.op("MUL", "PIPE_V", 1, [a[1], b[1]])
        d = builder.op("MATMUL", "PIPE_M", 1, [c[1], weight])
        builder.op("COPY_OUT", "PIPE_MTE3", 0, [d[1]], pos="DDR")
        diamonds.append((a, b, c, d))
    return builder, row, diamonds


def dag_timing(index, words, delay, whole_core_order=False):
    """Independent enhanced-DAG longest path, optionally serializing whole cores."""
    owner = {u: c for c, word in enumerate(words) for u in word}
    edges = {u: {v: delay if owner[u] != owner[v] else 0 for v in index.succ[u]}
             for u in index.ops}
    for word in words:
        last = {}
        for u in word:
            pipe = "whole" if whole_core_order else index.ops[u]["pipe"]
            if pipe in last:
                p = last[pipe]
                edges[p][u] = max(edges[p].get(u, 0), 0)
            last[pipe] = u
    indegree = dict.fromkeys(index.ops, 0)
    for vs in edges.values():
        for v in vs:
            indegree[v] += 1
    ready = [u for u in index.ops if not indegree[u]]
    heapq.heapify(ready)
    starts, finishes = dict.fromkeys(index.ops, 0), {}
    while ready:
        u = heapq.heappop(ready)
        finishes[u] = starts[u] + index.duration(u)
        for v, lag in edges[u].items():
            starts[v] = max(starts[v], finishes[u] + lag)
            indegree[v] -= 1
            if not indegree[v]:
                heapq.heappush(ready, v)
    if len(finishes) != len(index.ops):
        raise AssertionError("enhanced graph is cyclic")
    return starts, finishes


def ready_scan_oracle(index, owner, cores, delay):
    """Freshly scan every ready op at every step; no heaps or cached ready keys."""
    @lru_cache(None)
    def bottom(u):
        return index.duration(u) + max((bottom(v) for v in index.succ[u]), default=0)

    free = {(c, p): 0 for c in range(cores) for p in ("PIPE_M", "PIPE_V")}
    finish, starts, word = {}, {}, []
    while len(finish) < len(index.ops):
        candidates = []
        for u in index.ops:
            if u in finish or not index.pred[u] <= finish.keys():
                continue
            release = max((finish[p] + (delay if owner[p] != owner[u] else 0)
                           for p in index.pred[u]), default=0)
            start = max(release, free[owner[u], index.ops[u]["pipe"]])
            candidates.append((start, -bottom(u), u))
        start, _, u = min(candidates)
        starts[u], finish[u] = start, start + index.duration(u)
        free[owner[u], index.ops[u]["pipe"]] = finish[u]
        word.append(u)
    schedules = [[u for u in word if owner[u] == c] for c in range(cores)]
    return schedules, finish, starts, word


class AttentionRowsTests(unittest.TestCase):
    def test_default_plan_and_metadata_bytes_match_frozen_80fabde1(self):
        # Captured from the unmodified 80fabde1 implementation before this
        # optional packing change. Hash the full insertion-ordered plan/meta,
        # including diagnostic order, not merely Makespan or node coverage.
        golden = {
            "attention": ("0e9d7855b46f53b34cfa4b7fbae507a885cbfa1d286e0321db2d5b7d6c77fc67",
                          "a76c88c07fda0f9d931c22967af687876fd8a76ddc2f5640f22b314f41a0a358",
                          "4107a2cba4dbb32e562b3d28d23fc13c0a5da33f9f41d995334dd1e8c17fb2f8"),
            "ffn": ("b5e8fdef9f166104497b03e0966a8e2539e8519431d45ff544f3bf82e5aba4dd",
                    "6f9115c5f688535b0bb6de5144d2ecc479d194d501fce3e5844053baaef1f4a8",
                    "777af80c7441c01d8d5285811d5af61b783d04539c0c2f9c0cae2a3b2ad9797e"),
        }
        for name, fixture in (("attention", attention_graph), ("ffn", attention_ffn_graph)):
            for cores, digest in zip((1, 2, 5), golden[name]):
                with self.subTest(fixture=name, cores=cores):
                    index = Index(fixture()[0].graph)
                    default = construct(index, cores, cross_delay=5)
                    explicit = construct(index, cores, cross_delay=5, pack_ffn=False)
                    self.assertEqual(default, explicit)
                    encoded = json.dumps(default, ensure_ascii=False, separators=(",", ":")).encode()
                    self.assertEqual(hashlib.sha256(encoded).hexdigest(), digest)
                    self.assertNotIn("packed_ffn_count", default[1])

    def test_closed_ffn_is_one_owner_but_keeps_four_original_ops(self):
        builder, row, diamonds = attention_ffn_graph()
        original = json.dumps(builder.graph, sort_keys=True)
        index = Index(builder.graph)
        for cores in (1, 2, 5):
            with self.subTest(cores=cores):
                plan, meta = construct(index, cores, cross_delay=5, pack_ffn=True)
                self.assertEqual(meta["strategy"], "attention_rows_ffn")
                self.assertEqual(meta["packed_ffn_count"], 2)
                words = plan_words(plan)
                owner = {u: c for c, word in enumerate(words) for u in word}
                self.assertEqual(len(owner), sum(map(len, words)))
                self.assertEqual(set(owner), set(index.ops))
                self.assertEqual(len(set(plan["node_to_subgraph"].values())), len(index.ops))
                units = [r for r in meta["capsule_dispatch"] if r["kind"] == "ffn_diamond"]
                self.assertEqual(len(units), 2)
                self.assertEqual({tuple(u["nodes"]) for u in units},
                                 {tuple(o[0] for o in diamond) for diamond in diamonds})
                for diamond in diamonds:
                    nodes = [o[0] for o in diamond]
                    self.assertEqual(len({owner[u] for u in nodes}), 1)
                    self.assertFalse(set(nodes).intersection(row["nodes"]))
                    # The a->MUL edge remains in addition to the sigmoid chain.
                    self.assertEqual(index.pred[nodes[2]], {nodes[0], nodes[1]})
                self.assertTrue(all(not d["split"] for d in meta["ffn_diamonds"]))
                self.assertTrue(all(d["remote_internal_tensor_bytes_proxy"] == 0 for d in meta["ffn_diamonds"]))
                derive_multicore_plan(builder.graph, plan)
                dag_timing(index, words, 5, whole_core_order=True)
                _, finish = dag_timing(index, words, 5)
                self.assertEqual(meta["proxy_makespan_cycles"], max(finish.values()))
        self.assertEqual(json.dumps(builder.graph, sort_keys=True), original)

    def test_ffn_nonterminal_raw_compute_or_copy_consumer_prevents_packing(self):
        for position in (0, 1, 2):
            for copy in (False, True):
                with self.subTest(position=position, copy=copy):
                    b, _, diamonds = attention_ffn_graph(count=1)
                    tensor = diamonds[0][position][1]
                    if copy:
                        b.op("COPY_OUT", "PIPE_MTE3", 0, [tensor], pos="DDR")
                    else:
                        b.op("RELU", "PIPE_V", 1, [tensor])
                    _, meta = construct(Index(b.graph), 2, pack_ffn=True)
                    self.assertEqual(meta["packed_ffn_count"], 0)
                    self.assertFalse(any(x["kind"] == "ffn_diamond" for x in meta["capsule_dispatch"]))

    def test_ffn_terminal_external_consumer_is_allowed(self):
        b, _, diamonds = attention_ffn_graph(count=1)
        b.op("RELU", "PIPE_V", 1, [diamonds[0][-1][1]])
        _, meta = construct(Index(b.graph), 2, pack_ffn=True)
        self.assertEqual(meta["packed_ffn_count"], 1)

    def test_near_motif_missing_skip_edge_wrong_op_or_pipe_is_not_packed(self):
        for change in ("missing_skip", "wrong_op", "wrong_pipe"):
            with self.subTest(change=change):
                b, _, diamonds = attention_ffn_graph(count=1)
                a, sigmoid, mul, _ = diamonds[0]
                if change == "missing_skip":
                    b.graph["edges"].remove({"source": a[1], "target": mul[0]})
                else:
                    op = next(o for o in b.graph["ops"] if o["id"] == sigmoid[0])
                    op["op" if change == "wrong_op" else "pipe"] = "RELU" if change == "wrong_op" else "PIPE_M"
                _, meta = construct(Index(b.graph), 2, pack_ffn=True)
                self.assertEqual(meta["packed_ffn_count"], 0)

    def test_overlapping_ffn_diamonds_have_a_deterministic_disjoint_selection(self):
        b, row = attention_graph()
        weight = b.source()
        a = b.op("MATMUL", "PIPE_M", 1, [row["output"], weight])
        sigmoid = b.op("SIGMOID", "PIPE_V", 10, [a[1]])
        mul = b.op("MUL", "PIPE_V", 1, [a[1], sigmoid[1]])
        shared = b.op("MATMUL", "PIPE_M", 1, [mul[1], weight])
        sigmoid2 = b.op("SIGMOID", "PIPE_V", 10, [shared[1]])
        mul2 = b.op("MUL", "PIPE_V", 1, [shared[1], sigmoid2[1]])
        end = b.op("MATMUL", "PIPE_M", 1, [mul2[1], weight])
        b.op("COPY_OUT", "PIPE_MTE3", 0, [end[1]], pos="DDR")
        index = Index(b.graph)
        plan, meta = construct(index, 2, cross_delay=5, pack_ffn=True)
        self.assertEqual(len(meta["ffn_diamonds"]), 2)
        self.assertEqual(meta["packed_ffn_count"], 1)
        packed = [x for x in meta["capsule_dispatch"] if x["kind"] == "ffn_diamond"]
        self.assertEqual(packed[0]["nodes"], [a[0], sigmoid[0], mul[0], shared[0]])
        flat = [u for word in plan_words(plan) for u in word]
        self.assertEqual(len(flat), len(set(flat)))
        self.assertEqual(set(flat), set(index.ops))
        self.assertEqual((plan, meta), construct(index, 2, cross_delay=5, pack_ffn=True))

    def test_packed_ffn_final_ready_pass_can_interleave_M_and_V(self):
        builder, _, diamonds = attention_ffn_graph()
        index = Index(builder.graph)
        plan, meta = construct(index, 1, cross_delay=5, pack_ffn=True)
        words = plan_words(plan)
        owner = dict.fromkeys(index.ops, 0)
        expected_words, expected_finish, starts, _ = ready_scan_oracle(index, owner, 1, 5)
        self.assertEqual(words, expected_words)
        self.assertEqual(meta["proxy_makespan_cycles"], max(expected_finish.values()))
        first, second = diamonds
        self.assertLess(starts[second[0][0]], expected_finish[first[1][0]])
        _, contiguous = dag_timing(index, [[u for d in meta["capsule_dispatch"] for u in d["nodes"]]], 5)
        self.assertLess(max(expected_finish.values()), max(contiguous.values()))

    def test_packed_quotient_is_checked_and_invalid_switch_is_rejected(self):
        builder, _, _ = attention_ffn_graph()
        index = Index(builder.graph)
        with patch.object(attention_rows, "topo", side_effect=ValueError("synthetic quotient cycle")):
            with self.assertRaisesRegex(UnsupportedStructure, "attention/FFN/chain quotient"):
                construct(index, 2, pack_ffn=True)
        for bad in (0, 1, None, "yes"):
            with self.subTest(pack_ffn=bad), self.assertRaises(ValueError):
                construct(index, 2, pack_ffn=bad)

    def test_exact_row_cover_immutability_and_independent_final_timing(self):
        b, expected = attention_graph()
        graph = b.graph
        original = json.dumps(graph, sort_keys=True)
        index = Index(graph)
        rows = recognize(index)
        self.assertEqual(len(rows), 1)
        for key in ("nodes", "sink", "q", "k", "v"):
            self.assertEqual(rows[0][key], expected[key])
        self.assertEqual(len(rows[0]["nodes"]), 20)
        self.assertEqual(rows[0]["work"], {"PIPE_M": 40, "PIPE_V": 35})
        self.assertEqual(rows[0]["boundary_inputs"], expected["inputs"])
        self.assertEqual(rows[0]["boundary_outputs"], (expected["output"],))
        self.assertNotIn(expected["q"], rows[0]["nodes"])
        for cores in (1, 2, 5):
            with self.subTest(cores=cores):
                plan, meta = construct(index, cores, cross_delay=5)
                self.assertEqual((plan, meta), construct(index, cores, cross_delay=5))
                self.assertEqual(set(plan), {"node_to_subgraph", "core_schedules"})
                words = plan_words(plan)
                flat = [u for word in words for u in word]
                self.assertEqual(len(words), cores)
                self.assertEqual(len(flat), len(index.ops))
                self.assertEqual(set(flat), set(index.ops))
                self.assertEqual(len(set(plan["node_to_subgraph"].values())), len(index.ops))
                owner = {u: c for c, word in enumerate(words) for u in word}
                self.assertEqual(len({owner[u] for u in expected["nodes"]}), 1)
                derive_multicore_plan(graph, plan)  # Static check, never E0.
                dag_timing(index, words, 5, whole_core_order=True)
                _, finish = dag_timing(index, words, 5)
                self.assertEqual(meta["proxy_makespan_cycles"], max(finish.values()))
                self.assertIn("placement_proxy_makespan_cycles", meta)
        self.assertEqual(json.dumps(graph, sort_keys=True), original)

    def test_internal_tensor_external_compute_and_copy_consumers_rejected(self):
        for copy_consumer in (False, True):
            with self.subTest(copy_consumer=copy_consumer):
                b, row = attention_graph()
                if copy_consumer:
                    b.op("COPY_OUT", "PIPE_MTE3", 0, [row["exp"][1]], pos="DDR")
                else:
                    b.op("RELU", "PIPE_V", 1, [row["exp"][1]])
                with self.assertRaises(UnsupportedStructure):
                    construct(Index(b.graph), 2)

    def test_direct_edge_and_duplicate_producer_fail_raw_guard(self):
        for duplicate in (False, True):
            with self.subTest(duplicate_producer=duplicate):
                b, row = attention_graph()
                index = Index(b.graph)
                # Mutate raw data after creating Index so this specifically tests
                # the constructor's own guard, not an earlier Index exception.
                edge = ({"source": row["q"], "target": row["exp"][1]} if duplicate
                        else {"source": row["q"], "target": row["k"][0]})
                b.graph["edges"].append(edge)
                with self.assertRaisesRegex(UnsupportedStructure, "multiple original producers|direct edges"):
                    construct(index, 2)

    def test_invalid_parameters_and_non_attention_graph(self):
        b, _ = attention_graph()
        index = Index(b.graph)
        for cores in (True, False, 0, -1, 1.5):
            with self.subTest(cores=cores), self.assertRaises(ValueError):
                construct(index, cores)
        for delay in (True, False, -1, 0.5):
            with self.subTest(delay=delay), self.assertRaises(ValueError):
                construct(index, 2, delay)
        tiny = GraphBuilder()
        tiny.op("RELU", "PIPE_V", 1, [tiny.source()])
        with self.assertRaises(UnsupportedStructure):
            recognize(Index(tiny.graph))

    def test_ready_pass_has_no_row_barrier_and_promotes_future_releases(self):
        b = GraphBuilder()
        source = b.source()
        chains = []
        for _ in range(2):
            a = b.op("MATMUL", "PIPE_M", 1, [source])
            middle = b.op("RELU", "PIPE_V", 10, [a[1]])
            end = b.op("MATMUL", "PIPE_M", 1, [middle[1]])
            chains.append((a[0], middle[0], end[0]))
        index = Index(b.graph)
        owner = dict.fromkeys(index.ops, 0)
        result = _ready_word(index, owner, 1, 0)
        self.assertEqual(result, ready_scan_oracle(index, owner, 1, 0))
        words, finish, starts, global_word = result
        a, b = chains
        # Initial equal-release/equal-bottom tie is broken by ID. After A's V
        # op advances V time to 11, B's release=2 must move to available and win
        # the start=11 tie over A's short final M operation by bottom priority.
        self.assertEqual(global_word, [a[0], b[0], a[1], b[1], a[2], b[2]])
        self.assertEqual(starts[b[0]], 1)
        self.assertEqual(starts[a[1]], 1)
        self.assertLess(starts[b[0]], finish[a[1]])
        self.assertEqual(max(finish.values()), 22)
        _, contiguous = dag_timing(index, [list(a) + list(b)], 0)
        self.assertEqual(max(contiguous.values()), 24)
        self.assertEqual(dag_timing(index, words, 0), (starts, finish))

    def test_ready_heaps_match_fresh_scan_on_fixed_small_dags(self):
        for seed, n, cores, delay in ((17, 5, 2, 3), (19, 9, 3, 7), (23, 9, 1, 0)):
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                b = GraphBuilder()
                source, nodes, owner = b.source(), [], {}
                for j in range(n):
                    incoming = [t for _, t in nodes if rng.random() < 0.3]
                    pipe = rng.choice(("PIPE_M", "PIPE_V"))
                    node = b.op("MATMUL" if pipe == "PIPE_M" else "ADD", pipe,
                                rng.randrange(1, 12), incoming or [source])
                    nodes.append(node)
                    owner[node[0]] = rng.randrange(cores)
                index = Index(b.graph)
                actual = _ready_word(index, owner, cores, delay)
                self.assertEqual(actual, ready_scan_oracle(index, owner, cores, delay))
                words, finish, starts, _ = actual
                self.assertEqual(dag_timing(index, words, delay), (starts, finish))


if __name__ == "__main__":
    unittest.main()
