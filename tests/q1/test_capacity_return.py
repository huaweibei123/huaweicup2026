import unittest

from src.q1.capacity_return import construct, author


def chains(count):
    graph = dict(ops=[], tensors=[], edges=[])
    for i in range(count):
        ops = [i * 3 + j for j in range(3)]
        ts = [1000 + i * 4 + j for j in range(4)]
        graph['ops'].extend(dict(id=u, op='COMPUTE', pipe=p, cycles=c)
                            for u, p, c in zip(ops, ['PIPE_M', 'PIPE_V', 'PIPE_M'], [10, 20, 10]))
        graph['tensors'].extend(dict(id=t, size=16, pos='UB') for t in ts)
        for j, u in enumerate(ops):
            graph['edges'].extend([dict(source=ts[j], target=u), dict(source=u, target=ts[j+1])])
    return graph


class CapacityReturnTests(unittest.TestCase):
    def test_capacity_boundary_and_last_partial_packet(self):
        graph = chains(5)
        plan, info = construct(graph, 2, {'L1': 1024, 'UB': 160})
        self.assertEqual(info['packet'], 2)
        self.assertEqual(info['mixed_packet_bytes']['UB'], 160)
        self.assertEqual(sorted(map(len, plan['core_schedules'])), [2, 3])
        self.assertEqual(set(map(int, plan['node_to_subgraph'])), set(range(15)))
        self.assertEqual(len(author.validate_plan_structure(graph, plan)), 5)
        _, smaller = construct(graph, 2, {'L1': 1024, 'UB': 159})
        self.assertEqual(smaller['packet'], 1)
        with self.assertRaises(author.Unsupported):
            construct(graph, 2, {'L1': 1024, 'UB': 79})

    def test_shared_external_input_rejected(self):
        graph = chains(2)
        graph['tensors'] = [t for t in graph['tensors'] if t['id'] != 1004]
        for edge in graph['edges']:
            if edge['source'] == 1004:
                edge['source'] = 1000
        with self.assertRaises(author.Unsupported):
            construct(graph, 2)

    def test_metadata_does_not_select_parameters(self):
        graph = chains(7)
        first = construct(graph, 3)
        graph['case_id'] = 'arbitrary-unseen-case'
        self.assertEqual(first, construct(graph, 3))


if __name__ == '__main__':
    unittest.main()
