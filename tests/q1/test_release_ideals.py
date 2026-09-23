"""Bounded mathematical checks only: no E0/E1/E2 imports or calls."""
import itertools
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/q1'))
from release_ideals import (Net, closure, cut_bytes, is_ideal, partial_ideal,
                           release_labels, split_nets, threshold_buckets,
                           threshold_costs, topological)


def subsets(nodes):
    values = sorted(nodes)
    for bits in itertools.product([False, True], repeat=len(values)):
        yield frozenset(v for v, include in zip(values, bits) if include)


class ReleaseIdealTests(unittest.TestCase):
    def test_augmented_task_split_cycles(self):
        # Every forward graph on four internal nodes; external Task chain
        # before -> T -> after is unchanged. Test all proper bisections.
        pairs = [(u,v) for u in range(4) for v in range(u+1,4)]
        for mask in range(1 << len(pairs)):
            pred = {v:set() for v in range(4)}
            for i, (u,v) in enumerate(pairs):
                if mask & (1 << i): pred[v].add(u)
            for chosen in subsets(pred):
                if not chosen or len(chosen)==4: continue
                task_pred={10:set(),11:{10},12:{11},13:{12}}
                owner={v:11 if v in chosen else 12 for v in pred}
                for v, before in pred.items():
                    for u in before:
                        if owner[u]!=owner[v]: task_pred[owner[v]].add(owner[u])
                try:
                    topological(task_pred); valid=True
                except ValueError:
                    valid=False
                self.assertEqual(valid,is_ideal(chosen,pred))

    def test_release_thresholds_are_maximal(self):
        pred={0:set(),1:set(),2:{0},3:{1,2},4:{2}}
        labels=release_labels(pred,{0:7,1:20},core_floor=3)
        self.assertEqual(labels,{0:7,1:20,2:7,3:20,4:7})
        accumulated=set()
        for gate,bucket in threshold_buckets(labels):
            accumulated.update(bucket)
            self.assertTrue(is_ideal(accumulated,pred))
            for candidate in subsets(pred):
                if is_ideal(candidate,pred) and max([3]+[labels[v] for v in candidate])<=gate:
                    self.assertTrue(candidate<=accumulated)
        self.assertEqual(closure({3,4},pred),frozenset(pred))

    @staticmethod
    def graph(external):
        # Internal96-byte output fans out to two local consumers; shared
        # COPY_IN120-byte input goes to those same consumers. Two further
        # raw tensors deliberately share logical_tid but stay distinct nets.
        graph={'ops':[{'id':v,'op':'MATMUL'} for v in range(4)]+
                     [{'id':10,'op':'COPY_IN'},{'id':11,'op':'COPY_OUT'}],
               'tensors':[{'id':100,'size':96},{'id':101,'size':120},
                          {'id':102,'size':5},{'id':103,'size':9,'logical_tid':999},
                          {'id':104,'size':13,'logical_tid':999}], 'edges':[]}
        pairs=[(0,100),(100,1),(100,2),(10,101),(101,1),(101,2),(2,102),(102,11),
               (103,0),(103,1),(104,0),(104,2)]
        if external:pairs.append((100,3))
        graph['edges']=[{'source':u,'target':v} for u,v in pairs]
        return graph

    @staticmethod
    def direct_builder_bytes(graph, members):
        # Independent direct official boundary predicates, not net weights.
        value=0
        eligible={0,1,2,3}
        for tensor in graph['tensors']:
            tid=tensor['id']
            producers={e['source'] for e in graph['edges'] if e['target']==tid}
            consumers={e['target'] for e in graph['edges'] if e['source']==tid}
            if consumers & members and not producers & members:value+=tensor['size']
            if producers & members and (11 in consumers or not consumers & eligible or (consumers & eligible)-members):
                value+=tensor['size']
        return value

    def test_exact_boundary_bytes_from_raw_tensors(self):
        members={0,1,2}
        for external in [False,True]:
            graph=self.graph(external)
            nets=split_nets(graph,{0,1,2,3},members)
            self.assertEqual({n.tensor for n in nets},{100,101,103,104})
            self.assertEqual(next(n.weight for n in nets if n.tensor==100),96 if external else 192)
            for chosen in subsets(members):
                observed=(self.direct_builder_bytes(graph,set(chosen))+
                          self.direct_builder_bytes(graph,members-set(chosen))-
                          self.direct_builder_bytes(graph,members))
                self.assertEqual(observed,cut_bytes(nets,chosen))

    def test_threshold_sweep_matches_materialized_cost(self):
        labels={0:1,1:2,2:3}
        nets=split_nets(self.graph(False),{0,1,2,3},{0,1,2})
        for gate,cost in threshold_costs(nets,labels):
            self.assertEqual(cost,cut_bytes(nets,{v for v,g in labels.items() if g<=gate}))

    def test_min_cut_against_exhaustive_ideals(self):
        rng=random.Random(20260924)
        for _ in range(40):
            pred={v:{u for u in range(v) if rng.random()<.25} for v in range(6)}
            labels=release_labels(pred,{v:rng.randrange(4) for v in pred})
            gate=rng.randrange(4)
            upper={v for v in pred if labels[v]<=gate}
            forced=closure({min(upper)},pred) if upper and rng.random()<.5 else frozenset()
            nets=[Net(i,frozenset(rng.sample(range(6),rng.randint(2,6))),rng.randint(1,50)) for i in range(4)]
            work={v:rng.randint(1,10) for v in pred}
            previous=frozenset()
            for price in [0,1,3,11]:
                result=partial_ideal(pred,nets,work,upper=upper,forced=forced,price_numerator=price,price_denominator=3)
                best=min(3*cut_bytes(nets,p)-price*sum(work[v] for v in p)
                         for p in subsets(pred) if is_ideal(p,pred) and forced<=p<=upper)
                selected=frozenset(result['members'])
                self.assertEqual(result['scaled_objective'],best)
                self.assertTrue(previous<=selected)
                previous=selected

    def test_nonprefix_partial_ideal_and_complete_exit_closure(self):
        # Pro's coverage mechanism, only algebraic here: no timing numbers.
        pred={0:set(),1:set(),2:set()}; labels=release_labels(pred,{1:4002})
        upper={v for v,g in labels.items() if g==0}
        result=partial_ideal(pred,[Net(99,frozenset({0,1}),262144)],{0:1,1:1,2:3000},upper=upper)
        self.assertEqual(result['members'],[2])
        self.assertNotIn(set(result['members']),[{0},{0,1}])
        self.assertEqual(closure({2,3},{0:set(),1:set(),2:{0},3:{1}}),frozenset({0,1,2,3}))

    def test_guards_are_explicit(self):
        with self.assertRaises(ValueError):topological({0:{1},1:{0}})
        with self.assertRaises(ValueError):topological({0:{9}})
        with self.assertRaises(ValueError):partial_ideal({0:set(),1:{0}},[],{0:1,1:1},upper={1})
        with self.assertRaises(ValueError):partial_ideal({0:set()},[],{0:0})
        with self.assertRaises(ValueError):partial_ideal({0:set()},[],{0:2**30})
        graph=self.graph(False);graph['edges'].append({'source':3,'target':100})
        with self.assertRaises(ValueError):split_nets(graph,{0,1,2,3},{0,1,2})


if __name__=='__main__':unittest.main()
