"""Synthetic construction equivalence; no evaluator or real case input."""
import copy
import hashlib
import unittest
from unittest.mock import patch

from src.q1 import unified
from src.q1.bounded_tasks import construct as bounded
from src.q1.sink_peel import construct as sink
from src.q1.heavy_suffix import construct as heavy
from src.q1.component_overload import construct as overload
from tests.q1.test_capacity_return import chains
from tests.q1.test_component_pack import graph


class FallbackCacheTests(unittest.TestCase):
    def test_one_successful_construction_per_level(self):
        g = graph([(1, 'V', 10), (2, 'V', 10)], [])
        with (patch.object(unified, 'bounded', wraps=bounded) as b,
              patch.object(unified, 'sink', wraps=sink) as s,
              patch.object(unified, 'heavy', wraps=heavy) as h):
            items, _ = unified.generate_candidates(g, 2)
        self.assertTrue(items)
        self.assertEqual((b.call_count, s.call_count, h.call_count), (1, 1, 1))

    def test_bytes_equal_uncached_constructor_results(self):
        samples = [(chains(5), 2),
                   (graph([(1, 'V', 10), (2, 'V', 20)], []), 2),
                   (graph([(1, 'V', 10), (2, 'V', 20), (3, 'V', 5)], [(1, 2), (1, 3)]), 3)]
        dominant = graph([(1,'V',5),(2,'V',400),(3,'V',400),
                          (10,'M',1),(11,'M',1),(12,'M',1)], [(1,2),(1,3)])
        non_dominant = graph([(1,'V',10000),(2,'V',40000),(3,'V',40000),
                              (10,'M',200000),(11,'M',1),(12,'M',1)], [(1,2),(1,3)])
        bridge = graph([(1,'V',100),(2,'M',1),(3,'V',100),(4,'V',100),
                        (10,'M',1),(11,'M',1)], [(1,2),(2,3),(1,4)])
        bridge['ops'][1]['op'] = 'COPY_IN'
        self.assertEqual(heavy(dominant,3)[1]['selected'], 'heavy-suffix')
        self.assertEqual(overload(non_dominant,4)[1]['selected'], 'overload-list')
        samples.extend([(dominant,3),(non_dominant,4),(bridge,3)])
        for g, cores in samples:
            with self.subTest(cores=cores, ops=len(g['ops'])):
                items, diagnostics = unified.generate_candidates(g, cores)
                self.assertEqual(diagnostics['construction_failures'], [])
                by_name = {item['name']: item for item in items}
                for name, constructor in [('bounded', bounded),
                                          ('heavy-or-sink', heavy), ('overload', overload)]:
                    direct_plan, direct_info = constructor(g, cores)
                    if name in by_name:
                        self.assertEqual(unified.plan_bytes(by_name[name]['plan']),
                                         unified.plan_bytes(direct_plan))
                        self.assertEqual(by_name[name]['details'], direct_info)
                    else:
                        # A byte-identical earlier candidate is recorded as a duplicate.
                        duplicate = next(d for d in diagnostics['duplicates'] if d['name'] == name)
                        self.assertEqual(duplicate['details'], direct_info)
                        self.assertEqual(duplicate['plan_sha256'],
                                         hashlib.sha256(unified.plan_bytes(direct_plan)).hexdigest())

    def test_injected_fallback_is_not_mutated(self):
        g = chains(5)
        b = bounded(g, 2)
        original_b = copy.deepcopy(b)
        s = sink(g, 2, fallback_candidate=b)
        self.assertEqual(b, original_b)
        original_s = copy.deepcopy(s)
        h = heavy(g, 2, fallback_candidate=s)
        self.assertEqual(s, original_s)
        original_h = copy.deepcopy(h)
        overload(g, 2, fallback_candidate=h)
        self.assertEqual(h, original_h)

    def test_heavy_failure_is_retried_inside_overload(self):
        g = graph([(1, 'V', 10), (2, 'V', 10)], [])
        calls = 0
        def once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError('synthetic first candidate failure')
            return heavy(*args, **kwargs)
        with patch.object(unified, 'heavy', side_effect=once):
            items, diagnostics = unified.generate_candidates(g, 2)
        self.assertEqual(calls, 2)
        self.assertEqual(diagnostics['construction_failures'][0]['name'], 'heavy-or-sink')
        self.assertFalse(any(f['name'] == 'overload' for f in diagnostics['construction_failures']))
        self.assertTrue(items)


if __name__ == '__main__':
    unittest.main()
