"""Structural shared-input waves; no official evaluator calls."""
import copy
import unittest

from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan
from src.q2_nikolastarx import component_envelope, shared_input_wave, active_core_wave, adaptive_budget


CONFIG = {'capacity': {'L1': 300, 'UB': 300}}


def graph(count=3):
    result = {'ops': [], 'tensors': [], 'edges': []}
    for k in range(3):
        result['tensors'].append({'id': 1000+k, 'size': 100, 'pos': 'L1'})
    for j in range(count):
        previous = None
        for k in range(3):
            conv, relu = 100*j + 10*k + 1, 100*j + 10*k + 2
            a, b = 2000+100*j+10*k, 2001+100*j+10*k
            result['ops'].extend([{'id': conv, 'op': 'CONV', 'pipe': 'PIPE_M', 'cycles': 10},
                                  {'id': relu, 'op': 'RELU', 'pipe': 'PIPE_V', 'cycles': 2}])
            result['tensors'].extend([{'id': a, 'size': 20, 'pos': 'L1'},
                                      {'id': b, 'size': 20, 'pos': 'L1'}])
            result['edges'].extend({'source': x, 'target': y} for x,y in
                                   [(1000+k,conv),(conv,a),(a,relu),(relu,b)])
            if previous is not None:
                add, out = 100*j + 10*k + 3, 3000+100*j+10*k
                result['ops'].append({'id': add, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 1})
                result['tensors'].append({'id': out, 'size': 20, 'pos': 'L1'})
                result['edges'].extend({'source': x, 'target': y} for x,y in
                                       [(previous,add),(b,add),(add,out)])
                previous = out
            else:
                previous = b
    return result


def ops_on_core(plan, core=0):
    inverse = {v:int(k) for k,v in plan['node_to_subgraph'].items()}
    return [inverse[sg] for sg in plan['core_schedules'][core]]


class SharedInputWaveTests(unittest.TestCase):
    def test_active_core_reduction_preserves_requested_plan_shape(self):
        g = graph(3)
        config = {'capacity': {'L1': 1000, 'UB': 1000}, 'bandwidth': 1}
        plan, detail = active_core_wave.build_from_index(DAGIndex(g), 3, config)
        self.assertEqual(detail['active_cores'], 1)
        self.assertEqual(len(plan['core_schedules']), 3)
        self.assertEqual(plan['core_schedules'][1:], [[], []])
        derive_multicore_plan(g, plan)
        self.assertFalse(detail['official_optimality_claim'])

    def test_capacity_prevents_unsafe_core_reduction(self):
        g = graph(3)
        config = {'capacity': {'L1': 150, 'UB': 150}, 'bandwidth': 1}
        _, detail = active_core_wave.build_from_index(DAGIndex(g), 3, config)
        self.assertEqual(detail['active_cores'], 3)

    def test_new_guard_preserves_existing_wave_fallback(self):
        g = graph(3)
        config = {'capacity': {'L1': 1000, 'UB': 1000}, 'bandwidth': 1.5}
        expected, _ = shared_input_wave.build(g, 3, config)
        actual, detail = adaptive_budget.wave_route(DAGIndex(g), 3, config)
        self.assertEqual(actual, expected)
        self.assertIn('active_core_guard_rejected', detail)

    def test_coverage_dependency_and_shared_use_wave(self):
        g = graph(); ix = DAGIndex(g)
        plan, detail = shared_input_wave.build_from_index(ix, 1, CONFIG)
        self.assertEqual(set(plan), {'node_to_subgraph','core_schedules'})
        derive_multicore_plan(g, plan)
        seq = ops_on_core(plan)
        self.assertEqual(len(seq), len(ix.ops))
        self.assertEqual(set(seq), set(ix.ops))
        pos = {u:i for i,u in enumerate(seq)}
        for u in ix.ops:
            self.assertTrue(all(pos[v] < pos[u] for v in ix.pred[u]))
        for t in range(1000, 1003):
            users = [u for u in seq if t in ix.inputs[u]]
            self.assertEqual(len(users), 3)
            self.assertEqual([pos[u] for u in users], list(range(pos[users[0]], pos[users[0]]+3)))
        self.assertEqual(detail['shared_external_inputs'], 3)
        self.assertFalse(detail['zero_spill_claim'])

    def test_raw_lifetime_reduction(self):
        g = graph(); ix = DAGIndex(g)
        wave, detail = shared_input_wave.build(g, 1, CONFIG)
        old, _ = component_envelope.build(g, 1, CONFIG)
        old_peak = shared_input_wave._raw_peak(ix, ops_on_core(old))['L1']
        new_peak = detail['raw_priority_peak_bytes'][0]['L1']
        self.assertLess(new_peak, old_peak)
        self.assertGreater(old_peak, CONFIG['capacity']['L1'])
        self.assertTrue(detail['raw_peaks_fit_capacity'])

    def test_renamed_ids_and_record_permutation(self):
        g = graph(); changed = copy.deepcopy(g)
        op_map = {op['id']: 10000+7*i for i,op in enumerate(reversed(g['ops']))}
        private = {t['id']: 30000+11*i for i,t in enumerate(reversed(g['tensors'])) if t['id'] < 1000 or t['id'] >= 2000}
        remap = {**op_map, **private}
        for op in changed['ops']: op['id'] = remap[op['id']]
        for tensor in changed['tensors']: tensor['id'] = remap.get(tensor['id'],tensor['id'])
        for edge in changed['edges']:
            edge['source'] = remap.get(edge['source'],edge['source'])
            edge['target'] = remap.get(edge['target'],edge['target'])
        for records in changed.values(): records.reverse()
        original, _ = shared_input_wave.build(g,1,CONFIG)
        renamed, _ = shared_input_wave.build(changed,1,CONFIG)
        self.assertEqual(len(original['node_to_subgraph']), len(renamed['node_to_subgraph']))
        self.assertEqual(shared_input_wave._raw_peak(DAGIndex(g),ops_on_core(original)),
                         shared_input_wave._raw_peak(DAGIndex(changed),ops_on_core(renamed)))
        ix = DAGIndex(changed); seq = ops_on_core(renamed)
        self.assertEqual({t:[u for u in seq if t in ix.inputs[u]] for t in range(1000,1003)}.keys(),
                         {1000,1001,1002})

    def test_heterogeneous_template_rejected(self):
        g = graph()
        g['ops'][-1]['cycles'] += 1
        with self.assertRaises(UnsupportedStructure):
            shared_input_wave.build(g,1,CONFIG)


if __name__ == '__main__': unittest.main()
