"""One ordering intervention, synthetic guards and zero evaluator calls."""
from contextlib import ExitStack, redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import tree_packets_first as first
from src.q2_nikolastarx import tree_frontier
from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan
from evaluation_validation import check_acyclic
from tests.q2_nikolastarx.test_tree_frontier import make_tree, per_core_ops, CONFIG


def balanced():
    return make_tree({1: 9, 2: 9, 3: 10, 4: 10, 5: 11, 6: 11, 7: 12, 8: 12,
                      9: 13, 10: 13, 11: 14, 12: 14, 13: 15, 14: 15, 15: None},
                     {u: 1536 for u in range(1, 16)})


def ownership(plan):
    return {u: c for c, seq in enumerate(per_core_ops(plan)) for u in seq}


class TreePacketsFirstTests(unittest.TestCase):
    def forbidden(self):
        context = ExitStack()
        for name in ['subprocess.Popen', 'multicore_cut_evaluate_problem_2.evaluate_scene_b',
                     'multicore_cut_evaluate_problem_2._build_scene_b_tasks']:
            context.enter_context(patch(name, side_effect=AssertionError('No evaluation/compilation')))
        return context

    def test_only_priority_changes_and_every_packet_precedes_skeleton(self):
        graph = balanced()
        old, base = tree_frontier.build(graph, 2, CONFIG)
        with (self.forbidden(), patch.object(first, 'DAGIndex', wraps=DAGIndex) as index,
              patch.object(tree_frontier, 'DAGIndex', side_effect=AssertionError('duplicate index'))):
            plan, detail = first.build(graph, 2, CONFIG)
        self.assertEqual(index.call_count, 1)
        self.assertEqual(ownership(old), ownership(plan))
        self.assertEqual(old['node_to_subgraph'], plan['node_to_subgraph'])
        self.assertEqual(detail['cut_edges'], base['cut_edges'])
        self.assertEqual(detail['tensor_copy_bytes_without_spill'], base['tensor_copy_bytes_without_spill'])
        self.assertGreater(detail['changed_core_orders'], 0)
        ix = DAGIndex(graph)
        membership = first._closed_packet_members(ix, detail['packets'], ownership(plan))
        for before, after in zip(per_core_ops(old), per_core_ops(plan)):
            self.assertEqual([u for u in before if u in membership], [u for u in after if u in membership])
            self.assertEqual([u for u in before if u not in membership], [u for u in after if u not in membership])
            flags = [u in membership for u in after]
            self.assertEqual(flags, sorted(flags, reverse=True))
        self.assertEqual(detail['per_core'], [{**r,
            'packet_root_reserve_bytes': detail['per_core'][c]['packet_root_reserve_bytes'],
            'raw_peaks_fit_capacity': detail['per_core'][c]['raw_peaks_fit_capacity']}
            for c, r in enumerate(tree_frontier._priority_peaks(ix, per_core_ops(plan)))])
        self.assertFalse(detail['zero_spill_claim'])

    def test_original_plus_full_core_order_is_acyclic_including_one_and_three_cores(self):
        graph = balanced()
        for cores in [1, 2, 3, 4]:
            with self.subTest(cores=cores), self.forbidden():
                plan, detail = first.build(graph, cores, CONFIG)
                view = derive_multicore_plan(graph, plan)
                edges = [(a, b, 'original') for a, b in view['dependency_pairs']]
                for seq in plan['core_schedules']:
                    edges.extend((a, b, 'core priority') for a, b in zip(seq, seq[1:]))
                check_acyclic(view['subgraph_ids'], edges, 'all original and core-order edges')
                self.assertEqual(detail['fixed_compute_fifo_bound_after'],
                                 first._fifo_bound(DAGIndex(graph), per_core_ops(plan)))

    def test_no_packet_boundary_is_explicit_and_safe(self):
        graph = make_tree({1: 3, 2: 3, 3: None}, cycles=1)
        old, _ = tree_frontier.build(graph, 3, CONFIG)
        plan, detail = first.build(graph, 3, CONFIG)
        self.assertEqual(detail['packet_count'], 0)
        self.assertEqual(detail['skeleton_ops'], 3)
        self.assertEqual(plan, old)
        self.assertEqual(detail['changed_core_orders'], 0)

    def test_guard_rejects_fork_and_partial_packet_metadata(self):
        graph = balanced()
        graph['edges'].append({'source': 1001, 'target': 2})
        with self.assertRaises(UnsupportedStructure):
            first.build(graph, 2, CONFIG)
        graph = balanced(); ix = DAGIndex(graph)
        with self.assertRaisesRegex(UnsupportedStructure, 'complete subtree'):
            first._closed_packet_members(ix, [{'root': 9, 'ops': 1, 'core': 0, 'work_cycles': 100}],
                                         {u: 0 for u in ix.ops})
        with self.assertRaisesRegex(ValueError, 'cycle'):
            first._fifo_bound(ix, [list(reversed(ix.order))])

    def test_record_shuffle_does_not_change_plan_or_detail(self):
        graph = balanced(); before = copy.deepcopy(graph)
        expected = first.build(graph, 3, CONFIG)
        self.assertEqual(graph, before)
        for records in graph.values(): records.reverse()
        self.assertEqual(first.build(graph, 3, CONFIG), expected)

    def test_cli_one_attempt_zero_calls_hash_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'graph.json'; output=root/'plan.json'
            source.write_text(json.dumps(balanced()))
            argv=['tree_packets_first',str(source),'--cores','2','--output',str(output),
                  '--evidence',str(root/'evidence')]
            with self.forbidden(), patch.object(sys,'argv',argv), redirect_stdout(io.StringIO()):
                first.main()
            ledger=json.loads((root/'evidence/solver.json').read_bytes()); raw=output.read_bytes()
            self.assertEqual(ledger['status'],'ok')
            self.assertEqual(ledger['calls'],{'E0':0,'E1':0,'E2':0})
            self.assertEqual(ledger['selected'],'tree_packets_first')
            self.assertEqual(len(ledger['attempts']),1)
            self.assertEqual(ledger['plan_sha256'],hashlib.sha256(raw).hexdigest())
            argv[-1]=str(root/'second')
            with self.forbidden(), patch.object(sys,'argv',argv), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit): first.main()
            self.assertEqual(output.read_bytes(),raw)


if __name__ == '__main__': unittest.main()
