"""P2/P3 differential development tests; every expected score comes from E0."""
import copy
import random
import sys
import types
import json
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from research.a.e2_search import SceneBEvaluator, E2BatchEvaluator, read_config
from research.a.e2_search._official_b import load_bundle
from research.a.e2_search import _native_b
from research.a.e2_search.tests.test_search import simple_graph, PLAN, tensor_graph
from src.eval_exact._official import REPO_ROOT
from src.eval_exact.batch_benchmark import equal


def micro(seed):
    rng = random.Random(923500 + seed)
    n = rng.randrange(2, 15)
    ids = rng.sample(range(10, 90), n)
    graph = dict(ops=[], tensors=[], edges=[])
    for j, oid in enumerate(ids):
        graph['ops'].append(dict(id=oid, op='RELU', pipe=rng.choice(['PIPE_M', 'PIPE_V']),
                                  cycles=rng.choice([0, 1, 3, 17, 100])))
        tid = 100+j
        graph['tensors'].append(dict(id=tid, pos='UB', size=rng.choice([0, 1, 16, 60, 128])))
        graph['edges'].append(dict(source=tid, target=oid))
        if j and rng.random() < .8:
            graph['edges'].append(dict(source=ids[rng.randrange(j)], target=tid))
        if j+1 < n and rng.random() < .5:
            graph['edges'].append(dict(source=tid, target=ids[rng.randrange(j+1, n)]))
        if j and rng.random() < .3:
            graph['edges'].append(dict(source=ids[j-1], target=oid, data_size=rng.choice([0, 17, 61])))
    orders = [[] for _ in range(1+seed % 5)]
    for j in range(n):
        orders[rng.randrange(len(orders))].append(j)
    return graph, dict(node_to_subgraph={str(oid): j for j, oid in enumerate(ids)}, core_schedules=orders)


class SceneBTest(unittest.TestCase):
    problem = 2

    @classmethod
    def setUpClass(cls):
        cls.oracle, cls.support = load_bundle(cls.problem)
        cls.config = read_config(REPO_ROOT/'data/raw/a/official/data/config.txt', problem=cls.problem)
        cls.truth_calls = 0

    @classmethod
    def tearDownClass(cls):
        print(f'P{cls.problem} synthetic explicit E0 calls={cls.truth_calls}; fallback/full calls additionally visible in records')

    def make_engine(self, graph, **kwargs):
        return SceneBEvaluator(graph, problem=self.problem, **kwargs)

    def truth(self, graph, plan, config):
        type(self).truth_calls += 1
        fn = self.oracle.evaluate_scene_b if self.problem == 2 else self.oracle.evaluate_problem_3
        return fn(graph, plan, **config)

    def compare(self, graph, plan, engine=None, config=None, debug=False, native=True):
        config = self.config if config is None else config
        engine = self.make_engine(graph) if engine is None else engine
        try:
            truth = self.truth(graph, plan, config)
        except Exception as error:
            row = engine.evaluate_record(plan, **config)
            self.assertIn(row['status'], ('invalid', 'error'))
            self.assertEqual((row['error_type'], row['message']), (type(error).__name__, str(error)))
            return row
        row = engine.evaluate_record(plan, **config)
        self.assertEqual(row['status'], 'ok', row)
        if native:
            self.assertEqual(row['route'], 'native', row)
        fields = ('makespan', 'data_movement_bytes', 'cross_task_traffic') + (('cache_stats',) if self.problem == 3 else ())
        for name in fields:
            self.assertTrue(equal(truth[name], row[name]), (name, row, truth))
        if debug:
            check = engine._native_score(plan, dict(config, max_iter=config.get('max_iter', 1_000_000)), debug=True)['debug']
            expected = {(core['core_id'], op['op_id']): (op['start'], op['end'])
                        for core in truth['per_core_timeline'] for op in core['ops']}
            actual = {key: (int(check['op_start'][i]), int(check['op_end'][i]))
                      for i, key in enumerate(check['op_keys'])}
            self.assertTrue(equal(actual, expected), (actual, expected))
            if self.problem == 3:
                for field in ('cache_events','cache_final_entries','cache_used_bytes_final','cache_stats'):
                    self.assertTrue(equal(check[field],truth[field]), (field,check[field],truth[field]))
                paths = {(core['core_id'],op['op_id']):op['memory_path'] for core in truth['per_core_timeline']
                         for op in core['ops'] if 'memory_path' in op}
                for i,key in enumerate(check['op_keys']):
                    if key in paths:
                        self.assertEqual(('ON_CHIP','DDR','CACHE_READ')[int(check['memory_path'][i])],paths[key])
        return row

    def test_seeded_timelines_cold_hit_and_reassignment(self):
        native = 0
        for seed in range(80):
            graph, plan = micro(seed)
            engine = self.make_engine(graph)
            with self.subTest(seed=seed):
                row = self.compare(graph, plan, engine, debug=True)
                native += row['status'] == 'ok'
                self.compare(graph, plan, engine)
                self.compare(graph, dict(plan, core_schedules=list(reversed(plan['core_schedules']))), engine, debug=True)
        self.assertGreater(native, 50)

    def test_input_invalid_global_fifo_and_iteration_failure(self):
        engine = self.make_engine(simple_graph())
        self.compare(simple_graph(), PLAN, engine)
        for plan in ({}, dict(PLAN, core_schedules=[]), dict(PLAN, core_schedules=[[2, 0], [1]]),
                     dict(PLAN, core_schedules=[[True, 2], [1]]), dict(PLAN, core_schedules=[[0, 2], [0, 1]]),
                     dict(PLAN, node_to_subgraph={'1': 0, '2': 1}), dict(PLAN, extra=True)):
            row = self.compare(simple_graph(), plan, engine)
            self.assertEqual(row['status'], 'invalid', row)
        for changes in ({'bandwidth': 0}, {'capacity': {'UB': 1}}, {'cross_core_copy_delay': float('nan')}, {'max_iter': 0}):
            self.assertEqual(self.compare(simple_graph(), PLAN, engine, dict(self.config, **changes))['status'], 'invalid')
        row = self.compare(simple_graph(), PLAN, engine, dict(self.config, max_iter=1))
        self.assertEqual(row['status'], 'error')
        self.assertEqual(row['route'], 'e0_fallback')
        # Contradictory cross-core chains + local priority constraints create a global cycle.
        graph = dict(ops=[dict(id=i, op='CONV', pipe='PIPE_M', cycles=2) for i in range(4)],
                     tensors=[], edges=[dict(source=0, target=1), dict(source=2, target=3)])
        plan = dict(node_to_subgraph={str(i): i for i in range(4)}, core_schedules=[[3, 0], [1, 2]])
        row = self.compare(graph, plan)
        self.assertIn(row['status'], ('invalid', 'error'))

    def test_cache_identity_graph_config_orders_and_isolation(self):
        graph, plan = micro(9)
        engine = self.make_engine(graph, max_cache_entries=2)
        self.compare(graph, plan, engine)
        self.assertTrue(self.compare(graph, plan, engine)['compilation_cache_hit'])
        for config in (dict(self.config, bandwidth=7.25), dict(self.config, cross_core_copy_delay=0),
                       dict(self.config, capacity={'L1': 4096, 'UB': 4096})):
            self.compare(graph, plan, engine, config, debug=True)
        shifted = dict(plan, core_schedules=plan['core_schedules'][1:]+plan['core_schedules'][:1])
        self.compare(graph, shifted, engine, debug=True)
        self.assertLessEqual(engine.cache_stats()['entries'], 2)
        self.assertLessEqual(engine.cache_stats()['accounted_bytes'], engine.cache_stats()['limit_bytes'])
        snapshot = copy.deepcopy(graph)
        graph['ops'][0]['cycles'] += 400
        self.compare(snapshot, plan, engine)
        for limit in (0, 1):
            small = self.make_engine(snapshot, cache_bytes=limit)
            self.compare(snapshot, plan, small)
            self.assertEqual(small.cache_stats()['entries'], 0)
        engine.clear_cache()
        self.assertEqual(engine.cache_stats()['accounted_bytes'], 0)

    def test_spill_empty_core_full_and_fallback(self):
        graph, plan = tensor_graph()
        row = self.compare(graph, plan, debug=True)
        self.assertGreater(row['data_movement_bytes']['spill_added_copy_bytes'], 0)
        self.compare(graph, dict(plan, core_schedules=[[], [0]]), debug=True)
        graph, plan = micro(17)
        engine = self.make_engine(graph)
        for config in (dict(self.config, cross_core_copy_delay=.5), dict(self.config, max_iter=10**30)):
            self.compare(graph, plan, engine, config, native=False)
        with patch.object(_native_b, 'get_lib', side_effect=OSError('missing native library')):
            row = self.compare(graph, plan, engine, native=False)
            self.assertEqual(row['route'], 'e0_fallback')
        self.compare(graph, plan, self.make_engine(graph, max_native_ops=1), native=False)
        full = engine.evaluate_record(plan, full=True, **self.config)
        self.assertEqual(full['route'], 'e0_full')
        self.assertTrue(equal(full['result'], self.truth(graph, plan, self.config)))

    def test_pool_dispatch_recycle_timeout_and_closed(self):
        with E2BatchEvaluator(simple_graph(),problem=self.problem,native_enabled=False) as pool:
            row=list(pool.evaluate_batch([PLAN],**self.config))[0]
            self.assertEqual(row['route'],'e0_fallback')
            self.assertTrue(equal(row['makespan'],self.truth(simple_graph(),PLAN,self.config)['makespan']))
        with E2BatchEvaluator(simple_graph(), problem=self.problem, workers=2, max_tasks_per_worker=1) as pool:
            rows = list(pool.evaluate_batch([PLAN, {}, PLAN, PLAN], **self.config))
            self.assertEqual([r['status'] for r in rows], ['ok', 'invalid', 'ok', 'ok'])
            self.assertEqual([r['problem'] for r in rows], [self.problem]*4)
            self.assertNotEqual(rows[0]['worker_pid'], rows[2]['worker_pid'])
        self.assertTrue(all(x is None for x in pool._slots))
        with E2BatchEvaluator(simple_graph(), problem=self.problem, timeout_seconds=1e-12) as pool:
            self.assertEqual(list(pool.evaluate_batch([PLAN], **self.config))[0]['status'], 'timeout')
            pool._timeout = 30
            self.assertEqual(list(pool.evaluate_batch([PLAN], **self.config))[0]['route'], 'native')

    def test_private_official_imports(self):
        fake = types.ModuleType('schedule_step3')
        fake.PIPES = ('wrong',)
        with patch.dict(sys.modules, {'schedule_step3': fake}):
            self.compare(simple_graph(), PLAN, debug=True)
            self.assertIs(sys.modules['schedule_step3'], fake)

    def test_cli_problem_routing_and_local_contract(self):
        graph, plan = tensor_graph()
        engine = self.make_engine(graph)
        original = self.oracle._build_scene_b_tasks(graph, plan, self.config['bandwidth'], self.config['capacity'])
        fast = engine._fast_runtime._build_scene_b_tasks(graph, plan, self.config['bandwidth'], self.config['capacity'])
        self.assertTrue(equal(original[1:], fast[1:]))
        for core in original[0]:
            for field in ('graph','seq','pipe_ops','op_preds','op_succs','op_subgraph','subgraph_ids'):
                self.assertEqual(original[0][core][field], fast[0][core][field])
            for field in ('execution_graph','pipe_orders','makespan','memory_peak','memory_dependencies'):
                self.assertTrue(equal(original[0][core]['step3'][field], fast[0][core]['step3'][field]))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'graph.json').write_text(json.dumps(simple_graph()))
            (root/'plans.jsonl').write_text('\n'.join(json.dumps(p) for p in [PLAN,{},PLAN]))
            result = subprocess.run([sys.executable,'-m','research.a.e2_search.cli',str(root/'graph.json'),
                str(root/'plans.jsonl'),'--problem',str(self.problem),'--config',str(REPO_ROOT/'data/raw/a/official/data/config.txt'),
                '--output',str(root/'out.jsonl')],capture_output=True,text=True,timeout=30,cwd=REPO_ROOT)
            self.assertEqual(result.returncode,1,result.stderr)
            rows=[json.loads(line) for line in (root/'out.jsonl').read_text().splitlines()]
            self.assertEqual([r['status'] for r in rows],['ok','invalid','ok'])
            self.assertEqual([r['problem'] for r in rows],[self.problem]*3)

    def test_full_cli_result_trace_log_and_invalid_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph,plan=micro(17)
            (root/'graph.json').write_text(json.dumps(graph))
            (root/'plan.json').write_text(json.dumps(plan))
            (root/'bad.json').write_text('{}')
            commands = [[sys.executable,str(REPO_ROOT/f'data/raw/a/official/code/multicore_cut_evaluate_problem_{self.problem}.py')],
                        [sys.executable,'-m',f'research.a.e2_search.multicore_cut_evaluate_problem_{self.problem}']]
            for name in ('plan','bad'):
                exits=[]
                for i,command in enumerate(commands):
                    result=subprocess.run(command+[str(root/'graph.json'),str(root/f'{name}.json'),
                        '--config',str(REPO_ROOT/'data/raw/a/official/data/config.txt'),
                        '--output',str(root/f'{i}.json'),'--trace-output',str(root/f'{i}.trace.json'),
                        '--log-output',str(root/f'{i}.log')],capture_output=True,text=True,cwd=REPO_ROOT,timeout=30)
                    exits.append(result.returncode)
                self.assertEqual(exits,[0,0] if name=='plan' else [1,1])
                if name=='plan':
                    for suffix in ('.json','.trace.json','.log'):
                        self.assertEqual((root/f'0{suffix}').read_bytes(),(root/f'1{suffix}').read_bytes())


class SceneCTest(SceneBTest):
    problem = 3

    def test_cache_zero_oversize_concurrent_fifo_and_bandwidth(self):
        for seed in range(20):
            graph, plan = micro(seed+20)
            engine = self.make_engine(graph)
            for cap in (0, 1, 16, 60, 128, 4096):
                config = dict(self.config, cache_capacity_bytes=cap, cache_bandwidth_bytes_per_cycle=3.25,
                              cross_core_copy_delay=seed % 4)
                self.compare(graph,plan,engine,config,debug=True)
        for changes in ({'cache_capacity_bytes': -1}, {'cache_capacity_bytes': .5},
                        {'cache_bandwidth_bytes_per_cycle': 0}, {'cache_bandwidth_bytes_per_cycle': float('nan')}):
            self.assertEqual(self.compare(simple_graph(),PLAN,config=dict(self.config,**changes))['status'],'invalid')


if __name__ == '__main__':
    unittest.main()
