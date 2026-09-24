"""Synthetic tree mechanisms and structural guards; zero evaluator calls."""
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

from src.q2_nikolastarx import tree_frontier as tree
from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan
from evaluation_validation import check_acyclic

CONFIG = {'capacity': {'L1': 524288, 'UB': 131072},
          'bandwidth': 60, 'cross_core_copy_delay_cycles': 500}


def make_tree(parents, sizes=None, cycles=100, external=None):
    """parents maps every op to its successor (None for the unique root)."""
    sizes = sizes or {}
    ops = [{'id': u, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': cycles} for u in parents]
    tensors = [{'id': 1000+u, 'size': sizes.get(u, 1), 'pos': 'UB'} for u in parents]
    edges = []
    for u, parent in parents.items():
        edges.append({'source': u, 'target': 1000+u})
        if parent is not None:
            edges.append({'source': 1000+u, 'target': parent})
    for tid, size, consumers in external or []:
        tensors.append({'id': tid, 'size': size, 'pos': 'UB'})
        edges.extend({'source': tid, 'target': u} for u in consumers)
    return {'ops': ops, 'tensors': tensors, 'edges': edges}


def per_core_ops(plan):
    reverse = {sg: int(u) for u, sg in plan['node_to_subgraph'].items()}
    return [[reverse[sg] for sg in seq] for seq in plan['core_schedules']]


class TreeFrontierTests(unittest.TestCase):
    def forbidden_evaluation(self):
        guard = ExitStack()
        for name in ['subprocess.Popen', 'multicore_cut_evaluate_problem_2.evaluate_scene_b',
                     'multicore_cut_evaluate_problem_2._build_scene_b_tasks']:
            guard.enter_context(patch(name, side_effect=AssertionError('No evaluator or compiler')))
        return guard

    def test_private_weighted_order_closes_high_peak_small_output_subtree_first(self):
        graph = make_tree({1: 2, 2: 4, 3: 4, 4: None}, {1: 10, 2: 1, 3: 10, 4: 1})
        with self.forbidden_evaluation():
            plan, detail = tree.build(graph, 1, CONFIG)
        self.assertEqual(per_core_ops(plan), [[1, 2, 3, 4]])
        self.assertEqual(detail['private_profile']['private_pool_peak_bytes']['UB'], 12)
        self.assertEqual(detail['per_core'][0]['raw_priority_peak_bytes']['UB'], 12)

    def test_parent_output_coexists_with_all_child_outputs(self):
        graph = make_tree({1: 3, 2: 3, 3: None}, {1: 6, 2: 6, 3: 5})
        _, detail = tree.build(graph, 1, CONFIG)
        self.assertEqual(detail['private_profile']['private_pool_peak_bytes']['UB'], 17)
        self.assertEqual(detail['per_core'][0]['raw_priority_peak_bytes']['UB'], 17)

    def test_shared_inputs_are_counted_and_private_optimum_is_not_total_optimum(self):
        graph = make_tree({1: 5, 2: 5, 3: 5, 4: 5, 5: None},
                          external=[(2001, 10, [1, 3]), (2002, 10, [2, 4])])
        config = {**CONFIG, 'capacity': {'L1': 16, 'UB': 16}}
        plan, detail = tree.build(graph, 1, config)
        self.assertEqual(per_core_ops(plan), [[1, 2, 3, 4, 5]])
        self.assertEqual(detail['private_profile']['private_pool_peak_bytes']['UB'], 5)
        self.assertEqual(detail['per_core'][0]['raw_priority_peak_bytes']['UB'], 23)
        alternate = tree._priority_peaks(DAGIndex(graph), [[1, 3, 2, 4, 5]])
        self.assertEqual(alternate[0]['raw_priority_peak_bytes']['UB'], 14)
        self.assertFalse(detail['zero_spill_claim'])
        self.assertEqual(detail['tensor_copy_bytes_without_spill']['external_input_bytes'], 20)

    def test_subtree_interleaving_can_beat_even_private_closed_order(self):
        graph = make_tree({1: 2, 2: 3, 3: 7, 4: 5, 5: 6, 6: 7, 7: None},
                          {1: 99, 2: 1, 3: 50, 4: 99, 5: 1, 6: 50, 7: 1})
        _, detail = tree.build(graph, 1, CONFIG)
        self.assertEqual(detail['private_profile']['private_pool_peak_bytes']['UB'], 150)
        alternate = tree._priority_peaks(DAGIndex(graph), [[1, 2, 4, 5, 3, 6, 7]])
        self.assertEqual(alternate[0]['raw_priority_peak_bytes']['UB'], 101)

    def test_packets_use_multiple_cores_and_global_projection_is_acyclic(self):
        graph = make_tree({1: 5, 2: 5, 3: 6, 4: 6, 5: 7, 6: 7, 7: None},
                          {u: 60 for u in range(1, 8)})
        with self.forbidden_evaluation():
            plan, detail = tree.build(graph, 2, CONFIG)
        self.assertEqual(detail['active_cores'], 2)
        self.assertGreater(detail['packet_count'], 2)
        view = derive_multicore_plan(graph, plan)
        edges = [(a, b, 'original') for a, b in view['dependency_pairs']]
        for seq in plan['core_schedules']:
            edges.extend((a, b, 'priority') for a, b in zip(seq, seq[1:]))
        check_acyclic(view['subgraph_ids'], edges, 'original plus priority')
        self.assertEqual(detail['tensor_copy_bytes_without_spill']['cross_core_bytes'],
                         120*len(detail['cut_edges']))
        for packet in detail['packets']:
            self.assertLessEqual(packet['work_cycles'] * 4, 700)

    def test_copy_latency_can_dominate_balanced_tiny_tree(self):
        graph = make_tree({1: 3, 2: 3, 3: None}, {u: 60 for u in range(1, 4)}, cycles=1)
        _, detail = tree.build(graph, 2, CONFIG)
        self.assertEqual(detail['active_cores'], 2)
        self.assertEqual(detail['compute_load_by_core'], [2, 1])
        self.assertEqual(len(detail['cut_edges']), 1)
        # A single required remote dependency has 500 delay cycles, greater
        # than the three original compute cycles. This is a mechanism fact,
        # not an official score or a proof of a particular serial E0 outcome.
        self.assertGreater(CONFIG['cross_core_copy_delay_cycles'], 3)
        self.assertNotIn('makespan', detail)

    def test_guards_reject_fanout_multiwriter_multiple_outputs_and_direct_edges(self):
        base = make_tree({1: 3, 2: 3, 3: None})
        examples = []
        extra = copy.deepcopy(base); extra['edges'].append({'source': 1001, 'target': 2}); examples.append(extra)
        extra = copy.deepcopy(base); extra['edges'].append({'source': 2, 'target': 1001}); examples.append(extra)
        extra = copy.deepcopy(base); extra['tensors'].append({'id': 2001, 'size': 1, 'pos': 'UB'})
        extra['edges'].append({'source': 1, 'target': 2001}); examples.append(extra)
        extra = copy.deepcopy(base); extra['edges'].append({'source': 1, 'target': 2}); examples.append(extra)
        for graph in examples:
            with self.subTest(graph=graph), self.assertRaises(UnsupportedStructure):
                tree.build(graph, 2, CONFIG)

    def test_copy_contracted_dependency_must_be_explained_by_internal_tensor(self):
        graph = make_tree({1: 2, 2: None})
        graph['ops'].append({'id': 99, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 1})
        graph['tensors'].append({'id': 2001, 'size': 1, 'pos': 'UB'})
        graph['edges'] = [e for e in graph['edges'] if e != {'source': 1001, 'target': 2}]
        graph['edges'].extend([{'source': 1001, 'target': 99}, {'source': 99, 'target': 2001},
                               {'source': 2001, 'target': 2}])
        with self.assertRaisesRegex(UnsupportedStructure, 'contracted COPY'):
            tree.build(graph, 2, CONFIG)

    def test_record_shuffle_is_deterministic_and_input_not_mutated(self):
        graph = make_tree({1: 3, 2: 3, 3: None})
        before = copy.deepcopy(graph)
        expected = tree.build(graph, 2, CONFIG)
        self.assertEqual(graph, before)
        for values in graph.values():
            values.reverse()
        self.assertEqual(tree.build(graph, 2, CONFIG), expected)
        for bad in [True, 0, -1, 1.5]:
            with self.assertRaises(ValueError): tree.build(graph, bad, CONFIG)
        with self.assertRaises(ValueError):
            tree.build(graph, 1, {**CONFIG, 'capacity': {'L1': 0, 'UB': 1}})

    def test_cli_zero_calls_hash_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root/'graph.json'; output = root/'plan.json'
            source.write_text(json.dumps(make_tree({1: 3, 2: 3, 3: None})))
            argv = ['tree_frontier', str(source), '--cores', '2', '--output', str(output),
                    '--evidence', str(root/'evidence')]
            with self.forbidden_evaluation(), patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
                tree.main()
            ledger = json.loads((root/'evidence/solver.json').read_text()); raw = output.read_bytes()
            self.assertEqual(ledger['status'], 'ok')
            self.assertEqual(ledger['calls'], {'E0': 0, 'E1': 0, 'E2': 0})
            self.assertEqual(ledger['selected'], 'tree_frontier')
            self.assertEqual(ledger['plan_sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(len(ledger['attempts']), 1)
            argv[-1] = str(root/'second')
            with self.forbidden_evaluation(), patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit): tree.main()
            self.assertEqual(output.read_bytes(), raw)


if __name__ == '__main__': unittest.main()
