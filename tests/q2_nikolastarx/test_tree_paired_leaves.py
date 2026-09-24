"""Guard, ideal two-pipe formula and raw-memory counterexample; zero scores."""
from contextlib import ExitStack, redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.q2_nikolastarx import tree_paired_leaves as paired
from src.q2_nikolastarx import tree_packets_first, tree_frontier
from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.direct import derive_multicore_plan
from evaluation_validation import check_acyclic
from tests.q2_nikolastarx.test_tree_frontier import CONFIG, per_core_ops


def chains(leaves=8, rounds=2, a=3, b=1, join_cycles=1, large=False):
    ops=[];tensors=[];edges=[];leaf_words=[]
    def add(pipe, cycles, size):
        u=len(ops)+1
        ops.append({'id':u,'op':'MATMUL' if pipe=='PIPE_M' else 'RELU','pipe':pipe,'cycles':cycles})
        tensors.append({'id':1000+u,'size':size,'pos':'UB'})
        edges.append({'source':u,'target':1000+u})
        return u
    for _ in range(leaves):
        word=[]
        for i in range(2*rounds):
            u=add('PIPE_M' if i%2==0 else 'PIPE_V', a if i%2==0 else b,
                  8 if large and i<2*rounds-1 else 1)
            if word:edges.append({'source':1000+word[-1],'target':u})
            word.append(u)
        leaf_words.append(word)
    roots=[word[-1] for word in leaf_words]
    while len(roots)>1:
        assert len(roots)%2==0
        next_roots=[]
        for left,right in zip(roots[::2],roots[1::2]):
            u=add('PIPE_V',join_cycles,1)
            edges.extend([{'source':1000+left,'target':u},{'source':1000+right,'target':u}])
            next_roots.append(u)
        roots=next_roots
    return {'ops':ops,'tensors':tensors,'edges':edges},leaf_words,roots[0]


def owner(plan):return {u:c for c,seq in enumerate(per_core_ops(plan)) for u in seq}


class PairedLeavesTests(unittest.TestCase):
    def forbidden(self):
        context=ExitStack()
        for name in ['subprocess.Popen','multicore_cut_evaluate_problem_2.evaluate_scene_b',
                     'multicore_cut_evaluate_problem_2._build_scene_b_tasks']:
            context.enter_context(patch(name,side_effect=AssertionError('No scoring/compilation')))
        return context

    def test_one_local_rule_preserves_owner_packets_skeleton_and_coverage(self):
        graph,_,_=chains()
        old,old_detail=tree_packets_first.build(graph,2,CONFIG)
        with self.forbidden(), patch.object(paired,'DAGIndex',wraps=DAGIndex) as ix:
            plan,detail=paired.build(graph,2,CONFIG)
        self.assertEqual(ix.call_count,1)
        self.assertEqual(len(detail['pairs']),4)
        self.assertEqual(detail['covered_compute_ops'],32)
        self.assertEqual(owner(plan),owner(old))
        self.assertEqual(plan['node_to_subgraph'],old['node_to_subgraph'])
        for key in ['packets','compute_load_by_core','cut_edges','tensor_copy_bytes_without_spill']:
            self.assertEqual(detail[key],old_detail[key])
        changed={u for p in detail['pairs'] for u in p['left']+p['right']}
        for before,after in zip(per_core_ops(old),per_core_ops(plan)):
            self.assertEqual([u for u in before if u not in changed],[u for u in after if u not in changed])
        view=derive_multicore_plan(graph,plan)
        edges=[(a,b,'original') for a,b in view['dependency_pairs']]
        for seq in plan['core_schedules']:edges.extend((a,b,'core order') for a,b in zip(seq,seq[1:]))
        check_acyclic(view['subgraph_ids'],edges,'original plus full core order')
        self.assertFalse(detail['zero_spill_claim'])

    def test_ideal_formula_and_closed_word_cost_for_twelve_small_parameter_points(self):
        # This is formula verification, not candidate or score search.
        for r in [2,3,4]:
            for a,b in [(1,1),(3,1),(3,3),(300,36)]:
                graph,words,join=chains(2,r,a,b,join_cycles=2)
                ix=DAGIndex(graph);left,right=words
                woven=[u for pair in zip(left,right) for u in pair]+[join]
                with self.subTest(r=r,a=a,b=b):
                    self.assertEqual(tree_packets_first._fifo_bound(ix,[woven]),2*r*a+b+2)
                    self.assertEqual(tree_packets_first._fifo_bound(ix,[left+right+[join]]),2*r*a+(2*r-1)*b+2)

    def test_raw_capacity_counterexample_limits_the_ideal_claim(self):
        graph,words,join=chains(2,2,3,1,large=True)
        ix=DAGIndex(graph);left,right=words
        old=tree_frontier._priority_peaks(ix,[left+right+[join]])[0]['raw_priority_peak_bytes']['UB']
        woven=[u for pair in zip(left,right) for u in pair]+[join]
        new=tree_frontier._priority_peaks(ix,[woven])[0]['raw_priority_peak_bytes']['UB']
        self.assertEqual((old,new),(17,24))
        self.assertLessEqual(old,17);self.assertGreater(new,17)

    def test_nonisomorphic_or_vector_heavy_pairs_stay_unwoven(self):
        graph,_,_=chains();graph['ops'][1]['cycles']=2
        _,detail=paired.build(graph,1,CONFIG)
        self.assertEqual(len(detail['pairs']),3)
        self.assertEqual(detail['rejected_binary_joins']['different_chain_signatures'],1)
        graph,_,_=chains(a=1,b=2)
        base,_=tree_packets_first.build(graph,1,CONFIG)
        plan,detail=paired.build(graph,1,CONFIG)
        self.assertEqual(plan,base)
        self.assertEqual(len(detail['pairs']),0)
        self.assertEqual(detail['rejected_binary_joins']['not_constant_durations_with_b_le_a'],4)

    def test_matching_but_nonconstant_layer_durations_do_not_use_constant_formula(self):
        graph,words,_=chains(a=2,b=2)
        for word in words:
            graph['ops'][word[2]-1]['cycles']=1
            graph['ops'][word[3]-1]['cycles']=1
        base,_=tree_packets_first.build(graph,1,CONFIG)
        plan,detail=paired.build(graph,1,CONFIG)
        self.assertEqual(plan,base)
        self.assertEqual(len(detail['pairs']),0)
        self.assertEqual(detail['rejected_binary_joins']['not_constant_durations_with_b_le_a'],4)
        small,words,join=chains(2,2,2,2,join_cycles=1)
        for word in words:
            small['ops'][word[2]-1]['cycles']=1
            small['ops'][word[3]-1]['cycles']=1
        woven=[u for pair in zip(*words) for u in pair]+[join]
        self.assertEqual(tree_packets_first._fifo_bound(DAGIndex(small),[woven]),9)
        self.assertNotEqual(9,2*(2+1)+1+1)

    def test_pair_crossing_packet_boundary_is_left_alone_and_no_case_table(self):
        graph,_,_=chains()
        base,_=tree_packets_first.build(graph,3,CONFIG)
        plan,detail=paired.build(graph,3,CONFIG)
        self.assertEqual(plan,base)
        self.assertEqual(len(detail['pairs']),0)
        self.assertTrue(detail['rejected_binary_joins'])
        graph['ops'].reverse();graph['tensors'].reverse();graph['edges'].reverse()
        self.assertEqual(paired.build(graph,3,CONFIG),(plan,detail))

    def test_cli_one_attempt_hash_zero_calls_and_no_overwrite(self):
        graph,_,_=chains()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'graph.json';output=root/'plan.json'
            source.write_text(json.dumps(graph))
            argv=['tree_paired_leaves',str(source),'--cores','2','--output',str(output),'--evidence',str(root/'evidence')]
            with self.forbidden(),patch.object(sys,'argv',argv),redirect_stdout(io.StringIO()):paired.main()
            ledger=json.loads((root/'evidence/solver.json').read_bytes());raw=output.read_bytes()
            self.assertEqual(ledger['status'],'ok');self.assertEqual(ledger['selected'],'tree_paired_leaves')
            self.assertEqual(ledger['calls'],{'E0':0,'E1':0,'E2':0});self.assertEqual(len(ledger['attempts']),1)
            self.assertEqual(ledger['plan_sha256'],hashlib.sha256(raw).hexdigest())
            argv[-1]=str(root/'second')
            with self.forbidden(),patch.object(sys,'argv',argv),redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):paired.main()
            self.assertEqual(output.read_bytes(),raw)


if __name__=='__main__':unittest.main()
