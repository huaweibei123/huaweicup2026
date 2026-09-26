"""Synthetic stopped-prefix checks; no official cases or executables."""
import copy
import unittest

from src.q2.feedback.audit_stopped_batch import stopped_prefix


def fixture():
    method = {'variant': 'gap_packet', 'args': []}
    spec = {'run_id': 'fixed', 'output': 'batch', 'cores': 4,
            'cases': [f'{i:03}' for i in range(1, 13)] + ['014']
                     + [f'{i:03}' for i in range(15, 35)], 'methods': [method]}
    runs, attempts = [], []
    for case in spec['cases'][:13]:
        failed = case == '014'
        attempts.append(f'batch/{case}-gap_packet/run.json')
        runs.append({'case_id': case, 'status': 'timeout' if failed else 'ok',
                     'attempt_id': f'fixed-gap_packet-p2-{case}-k4-seed0-repeat0',
                     'method': method, 'cores': 4,
                     'calls': {'solver': 1, 'E0': 0 if failed else 1, 'E1': 0, 'E2': 0},
                     'stages': {'solver': {'status': 'timeout'}} if failed else {'solver': {}, 'E0': {}},
                     'compression': {}, 'artifacts': {},
                     'identity': {'plan_sha256': None},
                     'failure': {'stage': 'solver', 'reason': 'fixed wall-clock timeout; process killed; no retry'} if failed else None,
                     'stop_reason': 'first unexpected failure; batch stopped without retry' if failed else None})
    ledger = {'state': 'stopped', 'stop_reason': 'first unexpected failure; batch stopped without retry',
              'charged_calls': {'solver': 13, 'E0': 12, 'E1': 0, 'E2': 0}, 'attempts': attempts}
    return spec, ledger, runs


class StoppedPrefixTests(unittest.TestCase):
    def test_exact_prefix_one_timeout_and_zero_failed_e0(self):
        spec, ledger, runs = fixture()
        failed = stopped_prefix(spec, ledger, runs)
        self.assertEqual(failed['case_id'], '014')
        self.assertEqual(failed['calls']['E0'], 0)
        self.assertEqual(len(spec['cases'][13:]), 20)

    def test_tampered_counts_failure_or_prefix_rejected(self):
        spec, ledger, runs = fixture()
        for mutation in ('e0', 'status', 'attempts', 'prefix', 'retry'):
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                s, l, r = copy.deepcopy((spec, ledger, runs))
                if mutation == 'e0':
                    r[-1]['calls']['E0'] = 1
                elif mutation == 'status':
                    r[-1]['status'] = 'failed'
                elif mutation == 'attempts':
                    l['charged_calls']['solver'] = 12
                elif mutation == 'prefix':
                    r[0]['case_id'] = '099'
                else:
                    l['attempts'].append(l['attempts'][-1])
                stopped_prefix(s, l, r)


if __name__ == '__main__':
    unittest.main()
