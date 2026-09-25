"""Synthetic fixed-assignment retiming tests; no official evaluator."""
import copy
import unittest

from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import UnsupportedStructure, derive_multicore_plan
from src.q2_nikolastarx.gap_candidate import _chain_dag
from src.q2_nikolastarx.gap_retime import retime
from tests.q2_nikolastarx.test_gap_candidate import CONFIG, diamond


def plan(rows):
    nodes = [u for row in rows for u in row]
    return {'node_to_subgraph': {str(u): u for u in nodes}, 'core_schedules': rows}


def owners(candidate):
    return {int(u): core for core, row in enumerate(candidate['core_schedules'])
            for u, sg in candidate['node_to_subgraph'].items() if sg in row}


class GapRetimeTests(unittest.TestCase):
    def test_fixed_cores_pipe_disjoint_and_cross_lag(self):
        graph = diamond()
        original = plan([[1, 4, 5], [2, 3]])
        graph_copy, plan_copy = copy.deepcopy(graph), copy.deepcopy(original)
        output, meta = retime(graph, original, CONFIG)
        derive_multicore_plan(graph, output)
        self.assertEqual(owners(output), owners(original))
        self.assertEqual(graph, graph_copy)
        self.assertEqual(original, plan_copy)
        self.assertEqual(output['node_to_subgraph'], original['node_to_subgraph'])
        starts = {int(u): at for u, at in meta['op_starts'].items()}
        index = DAGIndex(graph)
        chains, pred, _, delays, _ = _chain_dag(index, 60, 500)
        chaincore = {j: owners(original)[chain[0]] for j, chain in enumerate(chains)}
        for j, previous in enumerate(pred):
            for p in previous:
                end = starts[chains[p][-1]] + index.duration(chains[p][-1])
                self.assertGreaterEqual(starts[chains[j][0]],
                                        end + (delays[p, j] if chaincore[p] != chaincore[j] else 0))
        for core in range(2):
            for pipe in {op['pipe'] for op in index.ops.values()}:
                intervals = sorted((starts[u], starts[u] + index.duration(u))
                                   for u, op in index.ops.items()
                                   if owners(output)[u] == core and op['pipe'] == pipe)
                self.assertTrue(all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:])))

    def test_independent_pipes_overlap(self):
        graph = diamond()
        output, meta = retime(graph, plan([[1, 2, 3, 4, 5]]), CONFIG)
        self.assertEqual(meta['op_starts']['1'], 0)
        self.assertEqual(meta['op_starts']['2'], 0)
        derive_multicore_plan(graph, output)

    def test_reject_split_maximal_chain(self):
        graph = diamond()
        graph['ops'].append({'id': 6, 'op': 'COMPUTE', 'pipe': 'PIPE_M', 'cycles': 1})
        graph['edges'] = [e for e in graph['edges']
                          if (e['source'], e['target']) != (3, 4)]
        graph['edges'] += [{'source': 3, 'target': 6, 'data_size': 8},
                           {'source': 6, 'target': 4, 'data_size': 8}]
        with self.assertRaisesRegex(UnsupportedStructure, 'chain'):
            retime(graph, plan([[1, 3, 6], [2, 4, 5]]), CONFIG)
        valid, meta = retime(graph, plan([[1, 3, 6, 4], [2, 5]]), CONFIG)
        self.assertGreaterEqual(meta['op_starts']['4'], meta['op_starts']['6'] + 1)
        derive_multicore_plan(graph, valid)


if __name__ == '__main__':
    unittest.main()
