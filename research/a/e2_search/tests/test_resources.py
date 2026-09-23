"""Platform regression probes: real host + injected ABI; not Windows acceptance."""
import ctypes as ct
import os
import unittest
from unittest.mock import patch
from research.a.e2_search import _resources
from research.a.e2_search import E2BatchEvaluator
from research.a.e2_search.tests.test_search import simple_graph, PLAN
from research.a.e2_search import pool as pool_module


def _no_telemetry_worker(connection, *unused):
    """Explicit control-plane fault injection; does not evaluate a graph."""
    connection.send(dict(ready=True,pid=os.getpid()))
    try:
        while True:
            request=connection.recv()
            if request is None:
                return
            connection.send(dict(index=request[0],status='ok',worker_pid=os.getpid(),worker_peak_rss_bytes=None))
    except EOFError:
        pass
    finally:
        connection.close()


class ResourceTest(unittest.TestCase):
    def test_windows_counter_field_widths_and_peak_not_current(self):
        def query(handle,pointer,size):
            self.assertEqual(handle,123)
            self.assertEqual(size,ct.sizeof(_resources._ProcessMemoryCounters))
            counters=ct.cast(pointer,ct.POINTER(_resources._ProcessMemoryCounters)).contents
            self.assertEqual(counters.cb,size)
            counters.PeakWorkingSetSize=12345678
            counters.WorkingSetSize=543
            return 1
        self.assertEqual(_resources._ProcessMemoryCounters.PeakWorkingSetSize.offset,8)
        with patch.object(_resources,'_windows_functions',return_value=(lambda:123,query)):
            self.assertEqual(_resources._windows_peak_rss_bytes(),12345678)
        with patch.object(_resources,'_windows_functions',return_value=(lambda:123,lambda *args:0)):
            with self.assertRaises(OSError):
                _resources._windows_peak_rss_bytes()
        with patch.object(_resources.sys,'platform','win32'),patch.object(_resources,'_windows_peak_rss_bytes',side_effect=OSError('probe')):
            self.assertIsNone(_resources.peak_rss_bytes())

    def test_actual_host_peak_and_high_resolution_timeout(self):
        self.assertGreater(_resources.peak_rss_bytes(),0)
        config=dict(bandwidth=60,capacity={'UB':131072,'L1':524288},same_core_wait=100,cross_core_wait=1000)
        with E2BatchEvaluator(simple_graph(),timeout_seconds=1e-12) as pool:
            rows=list(pool.evaluate_batch([PLAN]*8,**config))
            self.assertEqual([r['status'] for r in rows],['timeout']*8)
        with E2BatchEvaluator(simple_graph(),recycle_peak_rss_bytes=1) as pool:
            rows=list(pool.evaluate_batch([PLAN,PLAN],**config))
            self.assertEqual([r['recycle_reason'] for r in rows],['peak_rss_threshold']*2)
            self.assertNotEqual(rows[0]['worker_pid'],rows[1]['worker_pid'])

    def test_requested_rss_limit_never_silently_ignores_missing_telemetry(self):
        with patch.object(pool_module,'_worker',_no_telemetry_worker):
            with E2BatchEvaluator(simple_graph(),recycle_peak_rss_bytes=100000000) as pool:
                rows=list(pool.evaluate_batch([PLAN,PLAN]))
        self.assertEqual([r['recycle_reason'] for r in rows],['rss_telemetry_unavailable']*2)
        self.assertNotEqual(rows[0]['worker_pid'],rows[1]['worker_pid'])


if __name__=='__main__':
    unittest.main()
