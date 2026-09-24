"""Hand-built precedence/communication tests; no E0 calls."""
import copy
import unittest

from src.q2_nikolastarx.dag_direct import construct, build as configured_build
from src.q2_nikolastarx.direct import derive_multicore_plan


def op(i, pipe='PIPE_M', cycles=1000, kind='COMPUTE'):
    return {'id': i, 'op': kind, 'pipe': pipe, 'cycles': cycles}


def tensor(i, size, pos='L1'):
    return {'id': i, 'size': size, 'pos': pos}


def edge(a, b, **rest):
    return {'source': a, 'target': b, **rest}


def owners(graph, plan):
    view = derive_multicore_plan(graph, plan)
    return {u: view['core_by_subgraph'][sg] for u, sg in view['mapping'].items()}


def build(graph, cores=2):
    return construct(graph, cores, bandwidth=60, cross_core_delay=500)


def fork(size):
    # One connected DAG: producer -> two parallel heavy M ops -> join.
    return {'ops': [op(1, 'PIPE_V', 10), op(2, cycles=2000), op(3, cycles=2000),
                    op(4, 'PIPE_V', 10)],
            'tensors': [tensor(101, size), tensor(102, 60), tensor(103, 60)],
            'edges': [edge(1, 101), edge(101, 2), edge(101, 3),
                      edge(2, 102), edge(102, 4), edge(3, 103), edge(103, 4)]}


class DAGDirectTests(unittest.TestCase):
    def test_parallel_branches_of_one_component_use_multiple_cores(self):
        graph = fork(60)
        plan, meta = build(graph)
        own = owners(graph, plan)
        self.assertEqual(meta['components'], 1)
        self.assertNotEqual(own[2], own[3])
        self.assertEqual(set(plan), {'node_to_subgraph', 'core_schedules'})

    def test_large_real_tensor_changes_split_decision(self):
        cheap, bulky = fork(60), fork(360000)
        cheap_owner = owners(cheap, build(cheap)[0])
        bulky_owner = owners(bulky, build(bulky)[0])
        self.assertNotEqual(cheap_owner[2], cheap_owner[3])
        self.assertEqual(bulky_owner[1], bulky_owner[2])
        self.assertEqual(bulky_owner[2], bulky_owner[3])

    def test_graph_input_reused_per_core_and_final_output_accounted(self):
        graph = {'ops': [op(1), op(2, 'PIPE_V')],
                 'tensors': [tensor(101, 120), tensor(102, 60)],
                 'edges': [edge(101, 1), edge(101, 2), edge(1, 2), edge(2, 102)]}
        _, meta = build(graph, 1)
        self.assertEqual(meta['predicted_ddr_bytes_without_spill'],
                         {'external_input_bytes': 120, 'cross_core_bytes': 0, 'output_bytes': 60})

    def test_original_copy_nodes_excluded_but_order_preserved(self):
        graph = {'ops': [op(1, 'PIPE_MTE2', 999, 'COPY_IN'), op(2),
                         op(3, 'PIPE_V', 1), op(4, 'PIPE_MTE3', 999, 'COPY_OUT')],
                 'tensors': [tensor(101, 60, 'DDR'), tensor(102, 60), tensor(103, 60)],
                 'edges': [edge(101, 1), edge(1, 102), edge(102, 2), edge(2, 3),
                           edge(3, 103), edge(103, 4)]}
        plan, meta = build(graph, 5)
        self.assertEqual(set(plan['node_to_subgraph']), {'2', '3'})
        self.assertEqual(len(plan['core_schedules']), 5)
        self.assertEqual(meta['predicted_ddr_bytes_without_spill']['external_input_bytes'], 60)
        self.assertEqual(meta['predicted_ddr_bytes_without_spill']['output_bytes'], 60)

    def test_shuffle_input_records_does_not_change_plan_or_metadata(self):
        graph = fork(60)
        shuffled = copy.deepcopy(graph)
        for key in ('ops', 'edges', 'tensors'):
            shuffled[key].reverse()
        self.assertEqual(build(graph), build(shuffled))
        self.assertEqual(graph, fork(60))  # Construction does not mutate raw input.

    def test_direct_edge_byte_size_affects_placement(self):
        graph = {'ops': [op(1, 'PIPE_V', 10), op(2, cycles=2000), op(3, cycles=2000)],
                 'tensors': [], 'edges': [edge(1, 2), edge(1, 3)]}
        cheap = owners(graph, build(graph)[0])
        graph['edges'] = [edge(1, 2, data_size=360000), edge(1, 3, data_size=360000)]
        bulky = owners(graph, build(graph)[0])
        self.assertNotEqual(cheap[2], cheap[3])
        self.assertEqual(bulky[1], bulky[2])
        self.assertEqual(bulky[2], bulky[3])

    def test_multi_producer_output_counts_once_per_producing_core(self):
        graph = {'ops': [op(1), op(2)], 'tensors': [tensor(101, 60)],
                 'edges': [edge(1, 101), edge(2, 101)]}
        plan, meta = build(graph)
        own = owners(graph, plan)
        self.assertNotEqual(own[1], own[2])
        self.assertEqual(meta['predicted_ddr_bytes_without_spill']['output_bytes'], 120)

    def test_router_config_interface_is_explicit(self):
        graph = fork(60)
        config = {'bandwidth': 60, 'cross_core_copy_delay_cycles': 500,
                  'capacity': {'L1': 524288, 'UB': 131072}}
        self.assertEqual(configured_build(graph, 2, config), build(graph, 2))
        with self.assertRaises(KeyError):
            configured_build(graph, 2, {'bandwidth': 60})

    def test_zero_cycle_clamp_and_bad_parameter_rejection(self):
        graph = {'ops': [op(1, cycles=0)], 'tensors': [], 'edges': []}
        self.assertEqual(build(graph, 1)[1]['predicted_finish_cycles'], 1)
        for cores, bandwidth, delay in [(0, 60, 500), (True, 60, 500), (2, 0, 500),
                                         (2, float('inf'), 500), (2, 60, -1)]:
            with self.assertRaises(ValueError):
                construct(graph, cores, bandwidth=bandwidth, cross_core_delay=delay)


if __name__ == '__main__':
    unittest.main()
