"""Synthetic structure, placement counterexamples and CLI guards; no E0."""
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import vector_arrival as arrival
from src.q2_nikolastarx import vector_lanes
from src.q2_nikolastarx.direct import Index, UnsupportedStructure
from tests.q2_nikolastarx.test_vector_lanes import template, owners, CONFIG as BASE_CONFIG

CONFIG = {**BASE_CONFIG, 'cross_core_copy_delay_cycles': 500}


def per_core(plan):
    inverse = {sg: int(u) for u, sg in plan['node_to_subgraph'].items()}
    return [[inverse[sg] for sg in seq] for seq in plan['core_schedules']]


class VectorArrivalTests(unittest.TestCase):
    def forbidden(self):
        context = ExitStack()
        for name in ('subprocess.Popen', 'multicore_cut_evaluate_problem_2.evaluate_scene_b',
                     'multicore_cut_evaluate_problem_2._build_scene_b_tasks'):
            context.enter_context(patch(name, side_effect=AssertionError('No evaluator or subprocess')))
        return context

    def test_whole_chains_and_persistent_input_owner_match_original_partition(self):
        graph = template(lanes=5, stages=4, length=3)
        with self.forbidden():
            old, _ = vector_lanes.build(graph, 3, CONFIG)
            plan, detail = arrival.build(graph, 3, CONFIG)
        model = vector_lanes.recognize(Index(graph))
        a, b = owners(graph, old), owners(graph, plan)
        seqs = per_core(plan)
        for stage in model['stages']:
            for h in stage['heads'].values():
                chain = model['heads'][h]
                self.assertEqual({b[u] for u in chain}, {a[h]})
                positions = [seqs[b[h]].index(u) for u in chain]
                self.assertEqual(positions, list(range(positions[0], positions[0]+len(chain))))
            for c, seq in enumerate(seqs):
                lane_ops = [u for h in stage['heads'].values() for u in model['heads'][h] if b[u] == c]
                reducers = [u for u in stage['reducers'] if b[u] == c]
                if lane_ops and reducers:
                    self.assertLess(max(seq.index(u) for u in lane_ops), min(seq.index(u) for u in reducers))
        self.assertEqual(set(plan), {'node_to_subgraph', 'core_schedules'})
        self.assertFalse(detail['zero_spill_claim'])
        self.assertFalse(detail['official_score_available'])

    def test_root_conditioned_dp_avoids_the_greedy_return_counterexample(self):
        # A(1000),C(600) on core 0; B(1) on core 1; R=A+B; P=R+C.
        # EFT alone prefers R@1 ending1515 but P then ends2030. R@0,P@0 ends1626.
        children, order = {4: (1, 2), 5: (4, 3)}, [4, 5]
        leaves = {1: (0, 1000), 2: (1, 1), 3: (0, 1600)}
        free, durations = [1600, 1], {4: 13, 5: 13}
        assigned, detail = arrival._place_tree(children, order, durations, leaves, tuple(free), 502, [])
        self.assertEqual(assigned, {5: 0, 4: 0})
        self.assertEqual(detail['optimistic_root_end'], 1626)
        seq, done, _ = arrival._list_tree(children, order, durations, leaves, assigned, free, 502)
        self.assertEqual(seq, [4, 5])
        self.assertEqual(done[5], (0, 1626))

    def test_dp_optimism_is_corrected_for_sibling_V_competition(self):
        leaves = {u: (0, 100) for u in range(1, 5)}
        children, order = {5: (1, 2), 6: (3, 4), 7: (5, 6)}, [5, 6, 7]
        durations = {u: 13 for u in order}
        assigned, detail = arrival._place_tree(children, order, durations, leaves, (100,), 502, [])
        self.assertEqual(detail['optimistic_root_end'], 126)
        seq, done, _ = arrival._list_tree(children, order, durations, leaves, assigned, [100], 502)
        self.assertEqual(seq, [5, 6, 7])
        self.assertEqual(done[7][1], 139)

    def test_next_stage_broadcast_horizon_changes_tied_root_location(self):
        args = ({3: (1, 2)}, [3], {3: 13}, {1: (0, 100), 2: (1, 100)}, (100, 100), 502)
        final, a = arrival._place_tree(*args, [])
        next_stage, b = arrival._place_tree(*args, [1, 1000])
        self.assertEqual(final[3], 0)
        self.assertEqual(next_stage[3], 1)
        self.assertEqual(a['optimistic_root_end'], b['optimistic_root_end'])
        self.assertEqual(b['root_choice_horizon'], 1615)

    def test_next_stage_uses_listed_root_and_not_optimistic_DP_time(self):
        graph = template(lanes=4, stages=3, length=2)
        with self.forbidden():
            _, detail = arrival.build(graph, 1, CONFIG)
        stages = detail['stage_detail']
        self.assertTrue(any(s['listed_root_end'] > s['optimistic_root_end'] for s in stages))
        for before, after in zip(stages, stages[1:]):
            self.assertEqual(after['first_lane_start_by_core'][0], before['listed_root_end'])

    def test_full_compute_fifo_graph_is_acyclic_and_bound_cannot_exceed_list_proxy(self):
        graph = template(lanes=5, stages=3, length=2)
        for k in (1, 2, 7):
            with self.subTest(cores=k), self.forbidden():
                plan, detail = arrival.build(graph, k, CONFIG)
                ix = Index(graph)
                succ = {u: set(vs) for u, vs in ix.succ.items()}
                for seq in per_core(plan):
                    for a, b in zip(seq, seq[1:]):
                        succ[a].add(b)
                degree = {u: 0 for u in succ}
                for vs in succ.values():
                    for v in vs:
                        degree[v] += 1
                ready, seen = [u for u in degree if degree[u] == 0], []
                while ready:
                    u = ready.pop()
                    seen.append(u)
                    for v in succ[u]:
                        degree[v] -= 1
                        if not degree[v]:
                            ready.append(v)
                self.assertEqual(set(seen), set(ix.ops))
                self.assertLessEqual(detail['fixed_plan_bound']['makespan_lower_bound_cycles'],
                                     detail['listed_proxy_makespan_cycles'])
                self.assertFalse(detail['fixed_plan_bound']['official_execution_validated'])

    def test_shuffle_deterministic_input_unchanged_and_tiny_capacity_not_promised(self):
        graph, shuffled = template(), template()
        original = copy.deepcopy(graph)
        for values in shuffled.values():
            values.reverse()
        with self.forbidden():
            self.assertEqual(arrival.build(graph, 3, CONFIG), arrival.build(shuffled, 3, CONFIG))
            _, detail = arrival.build(graph, 1, {**CONFIG, 'capacity': {'L1': 1, 'UB': 1}})
        self.assertEqual(graph, original)
        self.assertFalse(detail['per_core'][0]['raw_envelope_within_capacity'])
        self.assertFalse(detail['zero_spill_claim'])

    def test_guard_rejects_hidden_dependency_and_configuration_errors(self):
        graph = template()
        ix = Index(graph)
        graph['edges'].append({'source': ix.order[0], 'target': ix.order[-1]})
        with self.forbidden(), self.assertRaises(UnsupportedStructure):
            arrival.build(graph, 2, CONFIG)
        for change in ({'bandwidth': 0}, {'cross_core_copy_delay_cycles': -1},
                       {'cross_core_copy_delay_cycles': True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                arrival.build(template(), 2, {**CONFIG, **change})
        for k in (0, True, -1):
            with self.assertRaises(ValueError):
                arrival.build(template(), k, CONFIG)

    def test_cli_writes_submission_and_zero_call_ledger(self):
        with tempfile.TemporaryDirectory(prefix='vector-arrival-synthetic-') as tmp:
            root = Path(tmp)
            source, output, evidence = root/'graph.json', root/'plan.json', root/'evidence'
            source.write_text(json.dumps(template(lanes=3, stages=2, length=2)))
            argv = ['vector_arrival', str(source), '--cores', '2', '--output', str(output),
                    '--evidence', str(evidence), '--wall', '30']
            with self.forbidden(), patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
                arrival.main()
            ledger = json.loads((evidence/'solver.json').read_text())
            self.assertEqual(ledger['status'], 'ok')
            self.assertEqual(ledger['calls'], {'E0': 0, 'E1': 0, 'E2': 0})
            self.assertEqual(output.read_bytes(), (evidence/'vector_arrival/plan.json').read_bytes())
            self.assertEqual(len(ledger['attempts']), 1)


if __name__ == '__main__':
    unittest.main()
