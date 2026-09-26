"""Independent tiny-graph audit, without official scoring or full-corpus plans."""
from __future__ import annotations

from collections import defaultdict
import heapq
import itertools
import math
import random
import unittest

from src.q2.feedback.tensor_packet import TensorIndex


def node(i, cycles=1000, pipe="PIPE_M", kind="COMPUTE"):
    return {"id": i, "cycles": cycles, "pipe": pipe, "op": kind}


def fixture(ops, tensors=(), edges=()):
    return {"ops": list(ops),
            "tensors": [{"id": i, "size": size, "pos": pos} for i, size, pos in tensors],
            "edges": [{"source": e[0], "target": e[1], **({"data_size": e[2]} if len(e) == 3 else {})}
                      for e in edges]}


def boundary_copies(g, sequences):
    """Enumerate the frozen P2 no-spill COPY identities, not timing estimates.

    Every tensor/source-core/destination-core connection has its own pair;
    direct edges each have their own pair even between the same two cores.
    """
    original = {o["id"]: o for o in g["ops"]}
    owner = {u: c for c, seq in enumerate(sequences) for u in seq}
    tensors = {t["id"]: t for t in g["tensors"]}
    producers, consumers = defaultdict(set), defaultdict(set)
    transfers = []
    for edge in g["edges"]:
        u, v = edge["source"], edge["target"]
        if u in original and v in tensors:
            producers[v].add(u)
        if u in tensors and v in original:
            consumers[u].add(v)
    for tid, tensor in tensors.items():
        source_cores = {owner[u] for u in producers[tid] if u in owner}
        target_cores = {owner[u] for u in consumers[tid] if u in owner}
        if not source_cores:
            transfers.extend((("input", tid, c), tensor["size"]) for c in sorted(target_cores))
        elif not target_cores or any(original[u]["op"] == "COPY_OUT" for u in consumers[tid]):
            transfers.extend((("output", tid, c), tensor["size"]) for c in sorted(source_cores))
        for src in sorted(source_cores):
            for dst in sorted(target_cores):
                if src != dst:
                    transfers.extend([(("cross_out", tid, src, dst), tensor["size"]),
                                      (("cross_in", tid, src, dst), tensor["size"])])
    for i, edge in enumerate(g["edges"]):
        u, v = edge["source"], edge["target"]
        if u in owner and v in owner and owner[u] != owner[v]:
            size = max(0, int(edge.get("data_size", 0)))
            transfers.extend([(("direct_out", i), size), (("direct_in", i), size)])
    return transfers


def sequences_for(plan):
    inverse = {sg: int(u) for u, sg in plan["node_to_subgraph"].items()}
    return [[inverse[sg] for sg in seq] for seq in plan["core_schedules"]]


def topological_packet_order(pred, succ):
    degrees = [len(p) for p in pred]
    ready = [i for i, d in enumerate(degrees) if d == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in succ[u]:
            degrees[v] -= 1
            if degrees[v] == 0:
                heapq.heappush(ready, v)
    return order


def slow_pipeline_reference(index, packets, groups):
    """Direct definition with predecessor scans; independent of incremental cache."""
    pipes = ("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3")
    clocks = [{p: 0 for p in pipes} for _ in groups]
    schedules = [[] for _ in groups]
    active = [[] for _ in groups]
    cursors = [0 for _ in groups]
    states, finish, windows = {}, {}, []

    def admit(core, release):
        j = groups[core][cursors[core]]
        cursors[core] += 1
        active[core].append(j)
        states[j] = [0, sum(index.duration(u) for u in packets[j]), release]

    for c, group in enumerate(groups):
        loads = [sum(index.duration(u) for j in group for u in packets[j]
                     if index.ops[u]["pipe"] == p) for p in pipes]
        window = min(len(group), 8, 1 + math.ceil(sum(loads) / max(loads))) if group else 0
        windows.append(window)
        for _ in range(window):
            admit(c, 0)
    while any(active):
        candidates = []
        for c, jobs in enumerate(active):
            for j in jobs:
                position, remaining, release = states[j]
                u = packets[j][position]
                if not all(v in finish for v in index.pred[u]):
                    continue
                time = max(release, clocks[c][index.ops[u]["pipe"]],
                           max((finish[v] for v in index.pred[u]), default=0))
                candidates.append((time, remaining, u, c, j))
        if not candidates:
            raise AssertionError("reference has no ready packet")
        time, _, u, c, j = min(candidates)
        finish[u] = time + index.duration(u)
        schedules[c].append(u)
        clocks[c][index.ops[u]["pipe"]] = finish[u]
        states[j] = [states[j][0] + 1, states[j][1] - index.duration(u), finish[u]]
        if states[j][0] == len(packets[j]):
            active[c].remove(j)
            if cursors[c] < len(groups[c]):
                admit(c, finish[u])
    return schedules, {"method": "bounded_packet_pipeline", "windows": windows,
                       "ideal_compute_coordinate_end": max(finish.values(), default=0)}


class TensorPacketAuditTests(unittest.TestCase):
    def assert_copy_model(self, g, cores=2, delay=0):
        index = TensorIndex(g)
        sequences, meta = index.packet_eft(cores, 60, delay)
        transfers = boundary_copies(g, sequences)
        self.assertEqual(len({key for key, _ in transfers}), len(transfers))
        self.assertEqual(meta["no_spill_ddr_bytes"], sum(size for _, size in transfers))
        self.assertEqual(meta["no_spill_ddr_service"], sum(max(1, math.ceil(size / 60)) for _, size in transfers))
        return sequences, meta, transfers

    def test_repeated_remote_consumers_deduplicate_pair_but_keep_final_copy(self):
        g = fixture([node(i) for i in range(1, 6)] + [node(6, 999, "PIPE_MTE3", "COPY_OUT")],
                    [(100, 60, "L1"), (101, 61, "UB")],
                    [(100, 1), (1, 101), (101, 2), (101, 3), (101, 4), (101, 5), (101, 6)])
        sequences, meta, transfers = self.assert_copy_model(g)
        owner = {u: c for c, seq in enumerate(sequences) for u in seq}
        self.assertEqual(sum(owner[u] != owner[1] for u in range(2, 6)), 2)
        kinds = [key[0] for key, _ in transfers]
        self.assertEqual(kinds.count("cross_in"), 1)
        self.assertEqual(kinds.count("cross_out"), 1)
        self.assertEqual(kinds.count("output"), 1)
        self.assertEqual(meta["no_spill_ddr_service"], 7)

    def test_direct_zero_byte_edges_each_get_a_copy_pair(self):
        g = fixture([node(i) for i in range(1, 6)], edges=[(1, i, 0) for i in range(2, 6)])
        sequences, meta, transfers = self.assert_copy_model(g)
        self.assertGreater(len(transfers), 0)
        self.assertTrue(all(key[0].startswith("direct_") for key, _ in transfers))
        self.assertEqual(meta["no_spill_ddr_bytes"], 0)
        self.assertEqual(meta["no_spill_ddr_service"], len(transfers))

    def test_copy_bridge_has_rebuilt_endpoints_not_a_fictitious_core_pair(self):
        g = fixture([node(1), node(2, 999, "PIPE_MTE3", "COPY_OUT"),
                     node(3, 999, "PIPE_MTE2", "COPY_IN"), node(4, 1000, "PIPE_V")],
                    [(100, 60, "UB"), (101, 60, "DDR"), (102, 60, "UB")],
                    [(1, 100), (100, 2), (2, 101), (101, 3), (3, 102), (102, 4)])
        _, meta, transfers = self.assert_copy_model(g)
        self.assertEqual(meta["no_spill_ddr_service"], 2)
        self.assertEqual(sorted(key[0] for key, _ in transfers), ["input", "output"])

    def test_random_tiny_tensor_dags_match_boundary_copy_accounting(self):
        rng = random.Random(271828)
        for repeat in range(60):
            n = rng.randrange(2, 10)
            ops = [node(i, rng.randrange(1, 3000), rng.choice(("PIPE_M", "PIPE_V"))) for i in range(1, n + 1)]
            tensors, edges = [], []
            for u in range(1, n + 1):
                tid = 100 + u
                tensors.append((tid, rng.choice((0, 1, 60, 61, 120)), "UB"))
                edges.append((u, tid))
                edges.extend((tid, v) for v in range(u + 1, n + 1) if rng.random() < .25)
            tensors.append((200, 61, "L1"))
            edges.extend((200, u) for u in range(1, n + 1) if rng.random() < .4)
            g = fixture(ops, tensors, edges)
            for k in (1, 2, 4):
                with self.subTest(repeat=repeat, cores=k):
                    self.assert_copy_model(g, k, delay=500)

    def test_shortcut_difference_is_chain_order_compatible_not_strict_isomorphism(self):
        g = fixture([node(i, 10) for i in range(1, 7)], [(100, 60, "UB")],
                    [(100, 1), (100, 4), (1, 2), (2, 3), (1, 3), (4, 5), (5, 6)])
        index = TensorIndex(g)
        self.assertEqual(index.shared_signature(), {100})
        self.assertEqual(len(index.pred[3]), 2)
        self.assertEqual(len(index.pred[6]), 1)
        plan, meta = index.build_tensor_plan(2, 60, 0)
        self.assertEqual(meta["selected"], "shared_stages")
        rank = {u: i for seq in sequences_for(plan) for i, u in enumerate(seq)}
        for u in index.ops:
            for v in index.succ[u]:
                self.assertLess(rank[u], rank[v])

    def test_cohort_signature_separates_distinct_ordered_dags(self):
        edges = [(100, u) for u in (1, 4, 7)]
        edges += [(1, 2), (1, 3), (4, 5), (5, 6), (7, 8), (7, 9)]
        g = fixture([node(i, 10) for i in range(1, 10)], [(100, 61, "L1")], edges)
        index = TensorIndex(g)
        self.assertIsNone(index.shared_signature())
        plan, meta = index.build_tensor_plan(3, 60, 500)
        self.assertEqual(meta["selected"], "shared_cohorts")
        self.assertEqual(sorted(c["jobs"] for c in meta["cohorts"]), [1, 2])
        transfers = boundary_copies(g, sequences_for(plan))
        self.assertEqual(meta["no_spill_ddr_service"], sum(max(1, math.ceil(s / 60)) for _, s in transfers))
        self.assertTrue(all(key[0] == "input" for key, _ in transfers))

    def test_every_five_node_dag_contracts_to_a_dag_without_losing_nodes(self):
        possible = list(itertools.combinations(range(1, 6), 2))
        for mask in range(1 << len(possible)):
            edges = [e for i, e in enumerate(possible) if mask & (1 << i)]
            index = TensorIndex(fixture([node(i, 1) for i in range(1, 6)], edges=edges))
            packets, pred, succ, _, _ = index.packets(3)
            self.assertEqual(sorted(u for p in packets for u in p), list(range(1, 6)))
            self.assertEqual(len(topological_packet_order(pred, succ)), len(packets))
            owner = {u: j for j, packet in enumerate(packets) for u in packet}
            observed = {(owner[u], owner[v]) for u, v in edges if owner[u] != owner[v]}
            self.assertEqual({(u, v) for u, ss in enumerate(succ) for v in ss}, observed)

    def test_incremental_pipeline_matches_scan_definition_on_random_tiny_dags(self):
        rng = random.Random(314159)
        for repeat in range(100):
            n = rng.randrange(2, 16)
            edges = [(u, v) for u, v in itertools.combinations(range(1, n + 1), 2) if rng.random() < .2]
            ops = [node(i, rng.randrange(1, 40), rng.choice(("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3"))) for i in range(1, n + 1)]
            index = TensorIndex(fixture(ops, edges=edges))
            k = rng.randrange(1, 6)
            packets, pred, succ, _, _ = index.packets(k)
            dispatch = topological_packet_order(pred, succ)
            groups = [[] for _ in range(k)]
            for j in dispatch:
                groups[rng.randrange(k)].append(j)
            self.assertEqual(index.pipeline_packets(packets, groups), slow_pipeline_reference(index, packets, groups), repeat)

    def test_high_indegree_waiting_head_uses_one_successor_update_per_edge(self):
        n = 65
        edges = [(u, n) for u in range(1, n)]
        index = TensorIndex(fixture([node(i, 1) for i in range(1, n + 1)], edges=edges))
        packets = [[i] for i in range(1, n + 1)]
        # The join is admitted immediately on core0 while its 64 predecessors
        # occupy a bounded prefix on core1; this is a legal global dispatch.
        groups = [[n - 1], list(range(n - 1)), []]
        expected = slow_pipeline_reference(index, packets, groups)
        touches = defaultdict(int)

        class CountedSet(set):
            def __init__(self, values, label):
                super().__init__(values)
                self.label = label

            def __iter__(self):
                for value in super().__iter__():
                    touches[self.label] += 1
                    yield value

        index.pred = {u: CountedSet(ps, "predecessor_iteration") for u, ps in index.pred.items()}
        index.succ = {u: CountedSet(ss, "successor_iteration") for u, ss in index.succ.items()}
        self.assertEqual(index.pipeline_packets(packets, groups), expected)
        self.assertEqual(touches["predecessor_iteration"], 0)
        self.assertEqual(touches["successor_iteration"], len(edges))


if __name__ == "__main__":
    unittest.main()
