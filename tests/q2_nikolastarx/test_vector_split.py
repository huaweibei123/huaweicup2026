"""Small falsifiable split-lane invariants, negative domains, no E0."""
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import vector_split
from src.q2_nikolastarx.direct import Index, UnsupportedStructure
from src.q2_nikolastarx.vector_lanes import recognize
from tests.q2_nikolastarx.test_vector_lanes import template, owners
from tests.q2_nikolastarx.test_vector_arrival import per_core, CONFIG


def homogeneous(lanes=12, stages=2, length=4):
    graph = template(lanes=lanes, stages=stages, length=length, sizes=[32768]*lanes, scalar=2)
    model = recognize(Index(graph))
    chain_ops = {u for seq in model['heads'].values() for u in seq}
    for op in graph['ops']:
        if op['id'] in model['index'].ops:
            op['cycles'] = 524 if op['id'] in chain_ops else 13
    return graph


class VectorSplitTests(unittest.TestCase):
    def test_copy_lower_bound_rejects_float_rounding_counterexample(self):
        # Official ceil((2**53 + 1) / 2**53) is 1; integer ceil is 2.
        # Reject instead of publishing a lower bound with too much COPY lag.
        with self.assertRaisesRegex(UnsupportedStructure, 'rounding differs'):
            vector_split._transfer(2**53 + 1, 2**53, 500)
        self.assertEqual(vector_split._transfer(32768, 60, 500), 1594)

    def forbidden(self):
        context = ExitStack()
        for name in ('subprocess.Popen', 'multicore_cut_evaluate_problem_2.evaluate_scene_b',
                     'multicore_cut_evaluate_problem_2._build_scene_b_tasks'):
            context.enter_context(patch(name, side_effect=AssertionError('No evaluator/subprocess')))
        return context

    def test_only_two_large_cuts_per_stage_with_persistent_input_ownership(self):
        graph = homogeneous(stages=3)
        with self.forbidden():
            plan, detail = vector_split.build(graph, 5, CONFIG)
        model, own = recognize(Index(graph)), owners(graph, plan)
        input_cores = {a: {own[s['heads'][a]] for s in model['stages']} for a in model['anchors']}
        self.assertTrue(all(len(cs) == 1 for cs in input_cores.values()))
        cuts = [t for t in model['tensors'] if model['tensors'][t]['size'] == 32768
                and model['ep'][t] and model['ec'][t]
                and own[next(iter(model['ep'][t]))] != own[next(iter(model['ec'][t]))]]
        self.assertEqual(len(cuts), 6)
        self.assertEqual(detail['planned_large_vector_added_copy_bytes_without_spill'], 393216)
        seqs = per_core(plan)
        for s in model['stages']:
            for spec in detail['split_pairs']:
                chain = model['heads'][s['heads'][spec['anchor']]]
                self.assertEqual([own[u] for u in chain], [spec['sender']]*2+[spec['receiver']]*2)
                # Sender prefix precedes all its whole chains; receiver suffix follows all its whole chains.
                for a in detail['whole_lanes'][spec['sender']]:
                    self.assertLess(seqs[spec['sender']].index(chain[1]),
                                    seqs[spec['sender']].index(s['heads'][a]))
                for a in detail['whole_lanes'][spec['receiver']]:
                    whole = model['heads'][s['heads'][a]]
                    self.assertLess(seqs[spec['receiver']].index(whole[-1]),
                                    seqs[spec['receiver']].index(chain[2]))
        self.assertEqual(set(plan), {'node_to_subgraph', 'core_schedules'})

    def test_12_by_5_reaches_chain_work_bound_in_independent_lag_relaxation(self):
        with self.forbidden():
            _, detail = vector_split.build(homogeneous(stages=1), 5, CONFIG)
        self.assertEqual(detail['stage_detail'][0]['independent_lag_chain_end_by_core'],
                         (5240, 5240, 5240, 5240, 4192))
        self.assertEqual(detail['chain_only_work_lower_bound_cycles'], 5240)
        self.assertEqual(detail['vector_copy_minimum_lag_cycles'], 1594)
        self.assertEqual(detail['ideal_equal_release_communication_window_cycles'], 3144)
        self.assertFalse(detail['zero_spill_claim'])
        self.assertFalse(detail['official_score_available'])
        self.assertFalse(detail['fixed_plan_bound']['global_optimum_bound'])

    def test_equal_half_scheme_is_not_generally_chain_optimal_even_without_communication(self):
        # n=16,k=7,L=8 -> max20 operations, whereas ceil(128/7)=19.
        # This directly refutes a tempting unqualified work-bound attainment claim.
        with self.forbidden():
            _, detail = vector_split.build(homogeneous(lanes=16, stages=1, length=8), 7, CONFIG)
        self.assertEqual(detail['assigned_chain_work_maximum_cycles'], 20*524)
        self.assertEqual(detail['chain_only_work_lower_bound_cycles'], 19*524)
        self.assertGreater(detail['assigned_chain_work_maximum_cycles'], detail['chain_only_work_lower_bound_cycles'])

    def test_fixed_bound_and_capacity_scope_remain_honest_under_bad_resources(self):
        with self.forbidden():
            _, detail = vector_split.build(homogeneous(stages=2), 5,
                {**CONFIG, 'cross_core_copy_delay_cycles': 9000, 'capacity': {'L1': 1, 'UB': 1}})
        self.assertGreater(detail['vector_copy_minimum_lag_cycles'],
                           detail['ideal_equal_release_communication_window_cycles'])
        self.assertTrue(all(not c['original_peak_within_capacity'] for c in detail['per_core']))
        self.assertLessEqual(detail['fixed_plan_bound']['makespan_lower_bound_cycles'],
                             detail['listed_independent_lag_proxy_cycles'])
        self.assertFalse(detail['zero_spill_claim'])

    def test_deterministic_and_refuses_unsupported_domains(self):
        graph = homogeneous()
        before, shuffled = copy.deepcopy(graph), copy.deepcopy(graph)
        for items in shuffled.values():
            items.reverse()
        with self.forbidden():
            self.assertEqual(vector_split.build(graph, 5, CONFIG), vector_split.build(shuffled, 5, CONFIG))
        self.assertEqual(graph, before)
        for graph, k in [(homogeneous(), 4), (homogeneous(lanes=14), 5),
                         (homogeneous(length=3), 5), (template(lanes=12, length=4), 5)]:
            with self.subTest(cores=k), self.forbidden(), self.assertRaises(UnsupportedStructure):
                vector_split.build(graph, k, CONFIG)
        graph = homogeneous()
        ix = Index(graph)
        graph['edges'].append({'source': ix.order[0], 'target': ix.order[-1]})
        with self.forbidden(), self.assertRaises(UnsupportedStructure):
            vector_split.build(graph, 5, CONFIG)

    def test_cli_zero_calls_and_existing_output_is_not_replaced(self):
        with tempfile.TemporaryDirectory(prefix='vector-split-synthetic-') as tmp:
            root = Path(tmp)
            source, output, evidence = root/'graph.json', root/'plan.json', root/'evidence'
            source.write_text(json.dumps(homogeneous(stages=1)))
            argv = ['vector_split', str(source), '--cores', '5', '--output', str(output), '--evidence', str(evidence)]
            with self.forbidden(), patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
                vector_split.main()
            ledger = json.loads((evidence/'solver.json').read_text())
            self.assertEqual(ledger['status'], 'ok')
            self.assertEqual(ledger['calls'], {'E0': 0, 'E1': 0, 'E2': 0})
            self.assertEqual(len(ledger['attempts']), 1)
            saved = output.read_bytes()
            argv[-1] = str(root/'second-evidence')
            with self.forbidden(), patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                vector_split.main()
            self.assertEqual(output.read_bytes(), saved)


if __name__ == '__main__':
    unittest.main()
