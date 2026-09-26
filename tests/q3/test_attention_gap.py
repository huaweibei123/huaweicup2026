"""Bounded attention placement gap checks; no E0 calls."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from src.q3.attention_rows import _gap_trial, construct
from src.q3.construct import Index, derive_multicore_plan
from src.q3.gap_calendar import earliest, empty, reserve
from test_attention_rows import attention_graph, plan_words, dag_timing


class AttentionGapTests(unittest.TestCase):
    def test_two_pipe_gap_trial_is_private_and_respects_dependencies(self):
        # Existing reservations end late on both pipes, but leave an early slot
        # for the M -> V capsule. A rejected trial must not change either core.
        ops = {1: {"pipe": "PIPE_M"}, 2: {"pipe": "PIPE_V"}}
        index = SimpleNamespace(ops=ops, pred={1: set(), 2: {1}})
        core0 = {"PIPE_M": reserve(empty(), 20, 20),
                 "PIPE_V": reserve(empty(), 30, 20)}
        core1 = {"PIPE_M": reserve(empty(), 10, 20),
                 "PIPE_V": reserve(empty(), 10, 20)}
        roots = [core0, core1]
        before = [(earliest(r["PIPE_M"], 0, 5), earliest(r["PIPE_V"], 0, 5)) for r in roots]
        local0, trial0, starts0, count0 = _gap_trial(
            index, (1, 2), 0, {1: 0, 2: 0}, 0, roots[0],
            {"PIPE_M": 40, "PIPE_V": 50}, {}, {}, {1: 5, 2: 5}, 5)
        local1, trial1, starts1, count1 = _gap_trial(
            index, (1, 2), 0, {1: 0, 2: 0}, 1, roots[1],
            {"PIPE_M": 30, "PIPE_V": 30}, {}, {}, {1: 5, 2: 5}, 5)
        assert (starts0, local0, count0) == ({1: 0, 2: 5}, {1: 5, 2: 10}, 2)
        assert starts1[2] >= local1[1]
        assert count1 == 2
        assert [(earliest(r["PIPE_M"], 0, 5), earliest(r["PIPE_V"], 0, 5)) for r in roots] == before
        assert earliest(trial0["PIPE_M"], 0, 5) == 5
        assert earliest(trial0["PIPE_V"], 5, 5) == 10
        assert earliest(trial1["PIPE_M"], 0, 5) == 5


    def test_gap_construct_is_deterministic_and_officially_derived(self):
        for pack_ffn in (False, True):
            builder, _ = attention_graph()
            original = deepcopy(builder.graph)
            index = Index(builder.graph)
            plan, meta = construct(index, 2, cross_delay=5, pack_ffn=pack_ffn,
                                   placement_mode="gap")
            assert (plan, meta) == construct(index, 2, cross_delay=5, pack_ffn=pack_ffn,
                                             placement_mode="gap")
            assert builder.graph == original
            assert meta["placement_mode"] == "gap"
            assert meta["strategy"] == ("attention_rows_ffn_gap" if pack_ffn else "attention_rows_gap")
            assert meta["operations_inserted_before_tail"] >= 0
            assert set(plan) == {"node_to_subgraph", "core_schedules"}
            assert sorted(s for word in plan["core_schedules"] for s in word) == list(range(len(index.ops)))
            derive_multicore_plan(builder.graph, plan)
            words = plan_words(plan)
            dag_timing(index, words, 5, whole_core_order=True)
            starts, finishes = dag_timing(index, words, 5)
            assert all(starts[v] >= finishes[u] for u in index.ops for v in index.succ[u]
                       if any(u in word and v in word for word in words))


    def test_bad_mode_rejected(self):
        builder, _ = attention_graph()
        with self.assertRaisesRegex(ValueError, "placement_mode"):
            construct(Index(builder.graph), 2, placement_mode="invalid")
