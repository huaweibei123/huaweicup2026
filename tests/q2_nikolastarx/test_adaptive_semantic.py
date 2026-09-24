"""Structural repair boundaries and unchanged-plan guarantees; zero scoring."""
from contextlib import ExitStack,redirect_stdout
import copy,hashlib,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from src.q2_nikolastarx import adaptive_semantic as new,adaptive_direct as old,vector_lanes,vector_arrival,tree_paired_leaves
from src.q2_nikolastarx.dag_direct import DAGIndex
from tests.q2_nikolastarx.test_direct_solve import word_graph,CONFIG
from tests.q2_nikolastarx.test_component_envelope import jobs
from tests.q2_nikolastarx.test_tree_paired_leaves import chains
from tests.q2_nikolastarx.test_vector_lanes import template

class SemanticTests(unittest.TestCase):
 def forbidden(self):
  stack=ExitStack()
  for name in ['subprocess.Popen','multicore_cut_evaluate_problem_2.evaluate_scene_b','multicore_cut_evaluate_problem_2._build_scene_b_tasks']:stack.enter_context(patch(name,side_effect=AssertionError('No scoring')))
  return stack
 def test_word_and_component_plans_remain_exact_and_one_index(self):
  for graph,k in [(word_graph(4),2),(jobs(6),2)]:
   expected=old.build(graph,k,CONFIG)[0]
   with self.forbidden(),patch.object(new,'DAGIndex',wraps=DAGIndex) as index:
    plan,detail=new.build(graph,k,CONFIG)
   self.assertEqual(plan,expected);self.assertEqual(index.call_count,1)
   self.assertEqual(detail['repair_construct_calls'],0)
 def test_tree_uses_verified_pair_word_with_one_index(self):
  graph,_,_=chains()
  expected=tree_paired_leaves.build(graph,2,CONFIG)[0]
  with self.forbidden(),patch.object(new,'DAGIndex',wraps=DAGIndex) as index:
   plan,detail=new.build(graph,2,CONFIG)
  self.assertEqual(plan,expected);self.assertEqual(index.call_count,1)
  self.assertEqual(detail['adaptive_route'],'tree_paired_leaves');self.assertGreater(len(detail['pairs']),0)
 def base(self,split):
  graph=template(lanes=4,stages=2,length=3)
  plan,_=vector_lanes.build(graph,2,CONFIG);index=DAGIndex(graph)
  model=vector_lanes.recognize(index)
  owners={int(u):c for c,s in enumerate(plan['core_schedules']) for sg in s for u,v in plan['node_to_subgraph'].items() if v==sg}
  if split:
   chain=model['heads'][next(iter(model['stages'][0]['heads'].values()))]
   owners[chain[1]]=1-owners[chain[0]]
   plan['core_schedules']=[[plan['node_to_subgraph'][str(u)] for u in index.order if owners[u]==c] for c in range(2)]
  return graph,plan
 def test_large_vector_cut_triggers_exactly_one_repair_and_preserves_input(self):
  graph,base=self.base(True);saved=copy.deepcopy(graph)
  expected=vector_arrival.build(graph,2,CONFIG)[0]
  with self.forbidden(),patch.object(DAGIndex,'build',return_value=(base,{})),patch.object(vector_arrival,'build_from_index',wraps=vector_arrival.build_from_index) as repair:
   plan,detail=new.build(graph,2,CONFIG)
  self.assertEqual(plan,expected);self.assertEqual(graph,saved);self.assertEqual(repair.call_count,1)
  self.assertGreater(detail['repair_trigger']['large_crossings'],0);self.assertEqual(detail['base_construct_calls'],1)
 def test_scalar_crossing_alone_never_replaces_the_general_plan(self):
  graph,base=self.base(False)
  with self.forbidden(),patch.object(DAGIndex,'build',return_value=(base,{})),patch.object(vector_arrival,'build_from_index',side_effect=AssertionError('unnecessary repair')):
   plan,detail=new.build(graph,2,CONFIG)
  self.assertEqual(plan,base);self.assertTrue(detail['repair_trigger']['recognized']);self.assertEqual(detail['repair_construct_calls'],0)
 def test_repair_failure_is_not_swallowed_or_retried(self):
  graph,base=self.base(True)
  with self.forbidden(),patch.object(DAGIndex,'build',return_value=(base,{})),patch.object(vector_arrival,'build_from_index',side_effect=ValueError('repair defect')) as repair:
   with self.assertRaisesRegex(ValueError,'repair defect'):new.build(graph,2,CONFIG)
  self.assertEqual(repair.call_count,1)
 def test_cli_emits_one_attempt_zero_calls_and_refuses_existing_output(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory);source=path/'graph.json';source.write_text(json.dumps(jobs(6)));output=path/'plan.json';evidence=path/'evidence'
   args=['adaptive_semantic',str(source),'--cores','2','--output',str(output),'--evidence',str(evidence)]
   with self.forbidden(),patch.object(sys,'argv',args),redirect_stdout(io.StringIO()):new.main()
   raw=output.read_bytes();ledger=json.loads((evidence/'solver.json').read_text())
   self.assertEqual(ledger['calls'],{'E0':0,'E1':0,'E2':0});self.assertEqual(len(ledger['attempts']),1)
   self.assertEqual(ledger['plan_sha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(ledger['selected'],'adaptive_semantic')
   args[-1]=str(path/'second')
   with self.forbidden(),patch.object(sys,'argv',args),redirect_stdout(io.StringIO()):
    with self.assertRaises(SystemExit):new.main()
   self.assertEqual(output.read_bytes(),raw)

if __name__=='__main__':unittest.main()
