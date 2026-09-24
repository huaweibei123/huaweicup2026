import copy
import unittest
from tests.q1.test_component_pack import graph
from src.q1.heavy_suffix import construct
from src.q1.sink_peel import construct as previous


class HeavySuffixTests(unittest.TestCase):
    def test_many_components_do_not_hide_a_dominant_fork(self):
        g = graph([(1, 'V', 5), (2, 'V', 400), (3, 'V', 400),
                   (10, 'M', 1), (11, 'M', 1), (12, 'M', 1)], [(1, 2), (1, 3)])
        old = copy.deepcopy(g)
        baseline, _ = previous(g, 3)
        plan, d = construct(g, 3)
        self.assertEqual(d['selected'], 'heavy-suffix')
        self.assertEqual(d['wave_count'], 2)
        self.assertEqual(set(plan['node_to_subgraph']), {o['id'] for o in g['ops']})
        self.assertEqual(baseline['node_to_subgraph'][2], baseline['node_to_subgraph'][3])
        self.assertNotEqual(plan['node_to_subgraph'][2], plan['node_to_subgraph'][3])
        self.assertEqual(g, old)
        self.assertEqual((plan, d), construct(g, 3))

    def test_minor_diamond_stays_whole(self):
        links = [(1,2),(1,3),(10,11),(10,12),(11,13),(12,13)]
        g = graph([(i,'M',1000 if i < 4 else 1) for i in [1,2,3,10,11,12,13,20]], links)
        plan,d = construct(g,3)
        self.assertEqual(d['selected'],'heavy-suffix')
        self.assertEqual(len({plan['node_to_subgraph'][i] for i in [10,11,12,13]}),1)

    def test_fallback_preserves_the_previous_plan_byte_structure(self):
        g = graph([(1,'V',100),(2,'V',100),(3,'V',100),(10,'V',1),(11,'V',1)],[(1,2),(1,3)])
        for kw in [{'max_rounds':1},{'max_sinks':1}]:
            self.assertEqual(construct(g,3,**kw)[0],previous(g,3,**kw)[0])
        self.assertEqual(construct(g,1)[0],previous(g,1)[0])
        balanced = graph([(u,'M',10) for u in range(6)], [])
        self.assertEqual(construct(balanced,3)[0],previous(balanced,3)[0])
        single_sink = graph([(1,'V',100),(2,'V',100),(3,'V',100),(10,'V',1),(11,'V',1)],[(1,3),(2,3)])
        self.assertEqual(construct(single_sink,3)[0],previous(single_sink,3)[0])

    def test_copy_bridge_is_in_the_heavy_component(self):
        g=graph([(1,'V',100),(2,'M',1),(3,'V',100),(4,'V',100),(10,'M',1),(11,'M',1)],
                [(1,2),(2,3),(1,4)])
        g['ops'][1]['op']='COPY_IN'
        plan,d=construct(g,3)
        self.assertEqual(d['selected'],'heavy-suffix')
        self.assertNotIn(2,plan['node_to_subgraph'])
        self.assertNotEqual(plan['node_to_subgraph'][1],plan['node_to_subgraph'][3])

    def test_reject_bad_threshold(self):
        g=graph([(1,'V',1)],[])
        for bad in [0,101,True,80.0]:
            with self.assertRaises(ValueError): construct(g,2,dominant_percent=bad)


if __name__=='__main__':
    unittest.main()
