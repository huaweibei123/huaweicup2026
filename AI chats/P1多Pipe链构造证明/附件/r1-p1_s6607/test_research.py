#!/usr/bin/env python3
"""Finite mathematical/model tests, no official graphs or E0 invocations."""
import itertools,json,random,unittest
from fractions import Fraction
from pathlib import Path
from p1_phase_cut import *
from make_micrographs import chains
from lower_bounds_extensions import *

class ResearchTests(unittest.TestCase):
    def test_energy_against_naive(self):
        rng=random.Random(6607)
        for _ in range(240):
            jobs=[Job(str(i),rng.randrange(31),rng.randrange(1,20),rng.randrange(31)) for i in range(rng.randrange(1,16))]
            for c in range(1,6):
                result=energetic_bound(jobs,c)
                self.assertEqual(result['bound'],brute_energetic(jobs,c))
                self.assertTrue(verify_energetic(jobs,result))
    def test_energy_not_empty_set(self):
        jobs=[Job('late',100,1,0),Job('tail',0,1,100)]
        self.assertEqual(energetic_bound(jobs,1)['bound'],101)
    def test_energy_strength(self):
        jobs=[Job('loose',0,1,0),Job('middle1',100,100,100),Job('middle2',100,100,100)]
        self.assertEqual(energetic_bound(jobs,1)['bound'],400)
        self.assertLess(max(sum(j.d for j in jobs),max(j.r+j.d+j.q for j in jobs)),400)
    def test_cut_crossing_vs_naive(self):
        rng=random.Random(708)
        for _ in range(400):
            n=rng.randrange(1,110);k=rng.randrange(1,6);ell=rng.randrange(2,6000);mw=rng.randrange(1,ell+1)
            delta=rng.randrange(0,4000);d0=rng.randrange(0,10000)
            result=homogeneous_cut_or_serialize(n,ell,delta,d0,k,mw)
            naive=min(max(ell*ceildiv(n-s,k),ceildiv(n*mw+(n-s)*(ell-mw),k),d0+delta*s) for s in range(n+1))
            self.assertEqual(result['bound'],naive)
    def test_hetero_dual(self):
        rng=random.Random(6608)
        for _ in range(100):
            b=[rng.randrange(1,100) for i in range(rng.randrange(1,10))];d=[rng.randrange(100) for _ in b]
            k=rng.randrange(1,6);d0=rng.randrange(100);wm=rng.randrange(100)
            result=heterogeneous_dual(b,d,d0,k,wm)
            def value(a):return a*wm/k+(1-a)*d0+sum(min(a*bb/k,(1-a)*dd) for bb,dd in zip(b,d))
            points=[Fraction(0),Fraction(1)]+[Fraction(k*dd,bb+k*dd) for bb,dd in zip(b,d)]
            self.assertEqual(Fraction(result['rational_bound']),max(map(value,points)))
            self.assertEqual(Fraction(result['rational_bound']),value(Fraction(result['alpha'])))
    def test_closed_form(self):
        for a,b,c in [(3,2,4),(2,7,2),(8,3,5),(5,5,5)]:
            for q in range(1,9):
                g=chains(2*q,a,b,c);v,cs,_,_,_=recognize(g)
                p=encode(cs,g['ops'],1,q,len(cs),100)
                local=local_model(g,p,60);middle=p['core_schedules'][0][1]
                response=task_profile(local[middle],60,copy_factor=0)['cycles']
                expected=max(q*(a+c),a+b+(q-1)*max(a,b))
                self.assertEqual(response,expected)
    def test_unequal_packets(self):
        for a,b,c in [(3,2,4),(2,7,2),(8,3,5)]:
            for u in range(1,6):
                for vcount in range(1,6):
                    g=chains(u+vcount,a,b,c);_,cs,_,_,_=recognize(g)
                    mapping={}
                    for i,comp in enumerate(cs):
                        for j,node in enumerate(comp):
                            mapping[node]=(0 if j<2 else 1) if i<vcount else (1 if j<2 else 2)
                    p={'node_to_subgraph':mapping,'core_schedules':[[0,1,2]]}
                    response=task_profile(local_model(g,p,60)[1],60,copy_factor=0)['cycles']
                    self.assertEqual(response,max(u*a+vcount*c,a+b+(u-1)*max(a,b)))
    def test_micro_plan_validity(self):
        for n in range(1,12):
            g=chains(n);_,cs,_,_,_=recognize(g)
            for k in range(1,6):
                for q in range(1,4):
                    for cut in {0,1,n//2,n}:
                        p=encode(cs,g['ops'],k,q,cut,3)
                        validate_plan_structure(g,p)
    def test_orientation_and_large_interface(self):
        for size,expected in [(60,6207),(30000,7704)]:
            g=chains(cut_bytes=size);_,cs,_,_,_=recognize(g)
            p=encode(cs,g['ops'],1,1,2,2)
            m=model_plan(g,p,60,{'UB':131072,'L1':524288},100)
            self.assertEqual(m['cycles'],expected);self.assertTrue(m['conditional_exact_model'])
            self.assertEqual(m['M_V_overlap_cycles_sum_over_cores'],1000)
    def test_capacity_guard(self):
        g=chains(n=2,cut_bytes=70000);_,cs,_,_,_=recognize(g)
        p=encode(cs,g['ops'],1,1,2,2)
        self.assertFalse(model_plan(g,p,60,{'UB':131072,'L1':524288},100)['virgin_capacity_certificate'])
    def test_skip_not_scalar(self):
        g=chains(n=1,cut_bytes=30000,skip=True);_,cs,_,_,_=recognize(g)
        row=cut_table(g,cs[0],60)[1]
        self.assertEqual(row['internal_cut_bytes'],30060)
        self.assertEqual(row['universal_extra_service_min'],1002)
    def test_reverse_task_quotient_cycle(self):
        g=chains();_,cs,_,_,_=recognize(g)
        p={'node_to_subgraph':{u:(0 if (i==0 and j==0) or (i==1 and j>0) else 1) for i,c in enumerate(cs) for j,u in enumerate(c)},
           'core_schedules':[[0],[1]]}
        with self.assertRaises(ValueError):validate_plan_structure(g,p)
    def test_no_COPY_bridge_contraction_in_LB(self):
        # The frozen P1 source removes the middle COPY inside a Task.
        g={'ops':[{'id':1,'op':'M','pipe':'PIPE_M','cycles':100},
                  {'id':2,'op':'COPY_IN','pipe':'PIPE_MTE2','cycles':1},
                  {'id':3,'op':'V','pipe':'PIPE_V','cycles':100}],
           'tensors':[{'id':10001,'pos':'UB','size':60},{'id':10002,'pos':'UB','size':60}],
           'edges':[{'source':1,'target':10001},{'source':10001,'target':2},
                    {'source':2,'target':10002},{'source':10002,'target':3}]}
        res,cp=universal_jobs(g,60);self.assertEqual(cp,101)
        with self.assertRaises(Unsupported):recognize(g)
    def test_general_certificates(self):
        for g in [chains(),chains(cut_bytes=30000),chains(n=1,cut_bytes=30000,skip=True)]:
            for k in range(1,6):self.assertTrue(verify_general(g,general_certificate(g,k,60)))
    def test_safety_wrapper_rejects_proxy_failure(self):
        called=[]
        def fallback(g,k):
            called.append(1);_,cs,_,_,_=recognize(g)
            return encode(cs,g['ops'],k,1,0,999),{'fixed_stub':'test_only_not_official'}
        p,info=integrate_construct(chains(cut_bytes=30000),1,60,{'UB':131072,'L1':524288},fallback)
        self.assertEqual(info['selected'],'frozen_fixed_fallback');self.assertEqual(called,[1])
        p,info=integrate_construct(chains(),1,60,{'UB':131072,'L1':524288},fallback)
        self.assertTrue(info['conservative_dominance_certificate']);self.assertEqual(called,[1])

if __name__=='__main__':unittest.main(verbosity=2)
