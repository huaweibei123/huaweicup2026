"""Static envelope/ordering checks; no official scoring or timing simulation."""
from collections import Counter, defaultdict
import copy
import unittest
import tempfile
import json
import hashlib
import io
import sys
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch

from src.q2_nikolastarx import component_envelope

from src.q2_nikolastarx.component_envelope import build
from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan


def jobs(count=6):
    graph = {'ops': [], 'tensors': [{'id': 1000, 'size': 64, 'pos': 'DDR'}], 'edges': []}
    for j in range(count):
        a, b, t, out = 2*j+1, 2*j+2, 1001+2*j, 1002+2*j
        graph['ops'] += [{'id': a, 'op': 'M', 'pipe': 'PIPE_M', 'cycles': 10},
                         {'id': b, 'op': 'V', 'pipe': 'PIPE_V', 'cycles': 10}]
        graph['tensors'] += [{'id': t, 'size': 32, 'pos': 'UB'}, {'id': out, 'size': 16, 'pos': 'UB'}]
        graph['edges'] += [{'source': u, 'target': v} for u,v in
                          [(1000,a),(a,t),(t,b),(b,out)]]
    return graph


def config(ub=160):
    return {'capacity': {'L1': 524288, 'UB': ub}, 'bandwidth': 60, 'cross_core_copy_delay_cycles': 500}


def ownership(plan):
    sgcore = {sg:c for c,seq in enumerate(plan['core_schedules']) for sg in seq}
    return {int(u):sgcore[sg] for u,sg in plan['node_to_subgraph'].items()}


class ComponentEnvelopeTests(unittest.TestCase):
    def test_whole_ownership_internal_order_and_memory_bound(self):
        graph = jobs(); index = DAGIndex(graph)
        plan, detail = build(graph, 2, config())
        derive_multicore_plan(graph, plan)
        owner = ownership(plan)
        inverse = {sg:int(u) for u,sg in plan['node_to_subgraph'].items()}
        for job in index.components:
            self.assertEqual(len({owner[u] for u in job}), 1)
            sequence = [inverse[s] for s in plan['core_schedules'][owner[job[0]]]]
            self.assertEqual([u for u in sequence if u in set(job)], job)
        self.assertFalse(detail['zero_spill_claim'])
        for core in detail['per_core']:
            self.assertTrue(core['all_raw_envelopes_fit'])
            self.assertEqual(core['max_open_components_bound'], 2)
            self.assertEqual([len(r['components']) for r in core['cohorts']], [2,1])
            # Original DDR graph input must consume UB capacity.
            self.assertEqual(core['cohorts'][0]['shared_reserve_bytes']['UB'], 64)
            self.assertEqual(core['cohorts'][0]['raw_priority_envelope_bytes']['UB'], 160)

    def test_shared_input_retained_across_middle_component_without_use(self):
        graph = {'ops': [], 'tensors': [{'id':101,'size':50,'pos':'UB'},
                                       {'id':102,'size':40,'pos':'UB'},
                                       {'id':103,'size':30,'pos':'UB'}], 'edges': []}
        touches = [[101],[101,103],[102],[102],[103]]
        for j, inputs in enumerate(touches,1):
            graph['ops'].append({'id':j,'op':'M','pipe':'PIPE_M','cycles':1})
            graph['tensors'].append({'id':200+j,'size':60,'pos':'UB'})
            graph['edges'].extend({'source':t,'target':j} for t in inputs)
            graph['edges'].append({'source':j,'target':200+j})
        _, detail = build(graph, 1, config(120))
        middle = next(r for r in detail['per_core'][0]['cohorts'] if 2 in r['components'])
        self.assertEqual(middle['components'], [2])
        # Job 2 uses 40B input 102, but 30B input 103 is still live across it.
        self.assertEqual(middle['shared_reserve_bytes']['UB'], 70)
        self.assertEqual(middle['raw_priority_envelope_bytes']['UB'], 130)
        self.assertFalse(middle['within_capacity'])

    def test_oversized_singleton_is_not_falsely_certified_or_merged(self):
        graph = jobs(3)
        _, detail = build(graph, 1, config(32))
        core = detail['per_core'][0]
        self.assertFalse(core['all_raw_envelopes_fit'])
        self.assertEqual(core['max_open_components_bound'], 1)
        self.assertTrue(all(len(r['components']) == 1 for r in core['cohorts']))
        self.assertTrue(all(not r['within_capacity'] for r in core['cohorts']))

    def test_too_few_components_has_no_silent_one_core_fallback(self):
        with self.assertRaises(UnsupportedStructure):
            build(jobs(1), 2, config())

    def test_input_permutation_determinism_without_mutation(self):
        graph = jobs(); original = copy.deepcopy(graph); shuffled = copy.deepcopy(graph)
        for values in shuffled.values(): values.reverse()
        self.assertEqual(build(graph, 2, config()), build(shuffled, 2, config()))
        self.assertEqual(graph, original)

    def test_cli_no_evaluator_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); graph = root/'graph.json'; output = root/'plan.json'
            graph.write_text(json.dumps(jobs()))
            argv = ['component_envelope', str(graph), '--cores', '2',
                    '--output', str(output), '--evidence', str(root/'evidence')]
            with patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()), \
                    patch('subprocess.Popen', side_effect=AssertionError('No evaluator process')), \
                    patch('multicore_cut_evaluate_problem_2.evaluate_scene_b', side_effect=AssertionError('No E0')):
                component_envelope.main()
            ledger = json.loads((root/'evidence/solver.json').read_text())
            original = output.read_bytes()
            self.assertEqual(ledger['status'], 'ok')
            self.assertEqual(ledger['calls'], {'E0':0, 'E1':0, 'E2':0})
            self.assertEqual(ledger['selected'], 'component_envelope')
            self.assertEqual(ledger['plan_sha256'], hashlib.sha256(original).hexdigest())
            self.assertFalse(ledger['attempts'][0]['detail']['zero_spill_claim'])
            argv[-1] = str(root/'second-evidence')
            with patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    component_envelope.main()
            self.assertEqual(error.exception.code, 1)
            self.assertEqual(output.read_bytes(), original)
            failed = json.loads((root/'second-evidence/solver.json').read_text())
            self.assertEqual(failed['status'], 'failed')
            self.assertIn('FileExistsError', failed['error'])

    def test_reported_envelope_bounds_actual_raw_prefixes(self):
        graph = jobs(13); index = DAGIndex(graph)
        plan, detail = build(graph, 3, config(208))
        inverse = {sg:int(u) for u,sg in plan['node_to_subgraph'].items()}
        jobof = {u:j for j,job in enumerate(index.components) for u in job}
        for c, core in enumerate(detail['per_core']):
            sequence = [inverse[s] for s in plan['core_schedules'][c]]
            where = defaultdict(list)
            for i,u in enumerate(sequence):
                for t in set(index.inputs[u]) | set(index.outputs[u]): where[t].append(i)
            for i,u in enumerate(sequence):
                cohort = next(r for r in core['cohorts'] if jobof[u] in r['components'])
                used = Counter()
                for t,places in where.items():
                    if places[0] <= i <= places[-1]:
                        tensor = index.tensors[t]
                        used['UB' if tensor['pos']=='DDR' else tensor['pos']] += tensor['size']
                for pool in ('L1','UB'):
                    self.assertLessEqual(used[pool], cohort['raw_priority_envelope_bytes'][pool])


if __name__ == '__main__': unittest.main()
