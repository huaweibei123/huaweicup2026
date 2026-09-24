import copy
import itertools
import unittest

from tests.q1.test_component_pack import graph
from src.q1.component_overload import construct, _place
from src.q1.heavy_suffix import construct as previous
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


class OverloadListTests(unittest.TestCase):
    def test_non_dominant_pipe_overload_is_detected(self):
        g = graph([(1,'V',10000),(2,'V',40000),(3,'V',40000),
                   (10,'M',200000),(11,'M',1),(12,'M',1)], [(1,2),(1,3)])
        old, d0 = previous(g,4)
        new, d = construct(g,4)
        self.assertNotEqual(d0['selected'],'heavy-suffix')
        self.assertEqual(old['node_to_subgraph'][2],old['node_to_subgraph'][3])
        self.assertEqual(d['selected'],'overload-list')
        self.assertNotEqual(new['node_to_subgraph'][2],new['node_to_subgraph'][3])
        self.assertEqual(d['split_components'][0]['overloaded_pipes'],['PIPE_V'])

    def test_independent_other_pipe_bundle_can_start_at_zero(self):
        g=graph([(1,'V',10000),(2,'V',40000),(3,'V',40000),
                 (10,'M',89000),(11,'M',1),(12,'M',1)],[(1,2),(1,3)])
        p,d=construct(g,4)
        t=p['node_to_subgraph'][10]
        self.assertEqual(d['placement']['task_start_proxy'][t],0)
        v=derive_multicore_plan(g,p)
        self.assertTrue(all(t not in edge for edge in v['dependency_pairs']))
        # This is a proxy/topology assertion, not a claim about official time.
        self.assertLess(d['placement']['compute_gate_proxy_finish'],99100)

    def test_all_64_ordered_four_node_dags_keep_augmented_graph_acyclic(self):
        edges=list(itertools.combinations(range(1,5),2))
        for mask in range(64):
            links=[edge for i,edge in enumerate(edges) if mask & (1<<i)]
            g=graph([(i,'V' if i%2 else 'M',10000) for i in range(1,5)]
                    +[(10,'M',1),(11,'V',1),(12,'M',1)],links)
            old=copy.deepcopy(g)
            p,d=construct(g,3)
            validate_task_order(derive_multicore_plan(g,p))
            self.assertEqual(g,old)
            self.assertEqual(list(p['node_to_subgraph']),[o['id'] for o in g['ops']])
            self.assertEqual(len(p['core_schedules']),3)
            self.assertEqual((p,d),construct(g,3))

    def test_single_sink_budget_and_single_core_keep_complete_fallback(self):
        g=graph([(1,'V',10000),(2,'V',20000),(3,'V',20000),
                 (10,'M',1),(11,'M',1)],[(1,2),(1,3)])
        for kwargs in [{'max_rounds':1},{'max_sinks':1}]:
            self.assertEqual(construct(g,3,**kwargs)[0],previous(g,3,**kwargs)[0])
        self.assertEqual(construct(g,1)[0],previous(g,1)[0])
        single=graph([(1,'V',10000),(2,'V',20000),(3,'V',20000),
                      (10,'M',1),(11,'M',1)],[(1,3),(2,3)])
        self.assertEqual(construct(single,3)[0],previous(single,3)[0])

    def test_bad_contraction_is_rejected_before_placement(self):
        g=graph([(1,'V',1),(2,'M',1),(3,'V',1)],[(1,2),(2,3)])
        ops={o['id']:o for o in g['ops']}
        with self.assertRaisesRegex(AssertionError,'cyclic'):
            _place([[1,3],[2]],{1:{2},2:{3},3:set()},ops,2,100,1000)

    def test_copy_bridge_and_invalid_core_domains(self):
        g=graph([(1,'V',10000),(2,'M',1),(3,'V',40000),(4,'V',40000),
                 (10,'M',1),(11,'M',1)],[(1,2),(2,3),(1,4)])
        g['ops'][1]['op']='COPY_IN'
        p,d=construct(g,3)
        self.assertEqual(d['selected'],'overload-list')
        self.assertNotIn(2,p['node_to_subgraph'])
        for k in [0,6,True]:
            with self.assertRaises(ValueError):construct(g,k)


if __name__=='__main__':
    unittest.main()
