"""Controller integration with fake workers only: zero evaluator invocations."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.q2 import stage_b
from src.q2.budget_search import ROOT, save


class ControllerBoundary(unittest.TestCase):
    def exercise(self, first_receipt, first_summary, units):
        parent=ROOT/'results/a/q2-yuanzhifang'
        with tempfile.TemporaryDirectory(prefix='controller-test-',dir=parent) as temp:
            folder=Path(temp)
            launched=[]
            def fake_job(command, **kwargs):
                name=kwargs['folder'].name
                launched.append(name)
                save(kwargs['folder']/'calls.json', {'charged':2, 'calls':[
                    {'phase':'dummy-reservation','launched':False},
                    {'phase':'dummy-reservation','launched':False}]})
                summary=first_summary if len(launched)==1 else {'status':'confirmed','calls_charged':2}
                if summary is not None:
                    save(kwargs['folder']/'summary.json',summary)
                return first_receipt if len(launched)==1 else {'status':'completed','returncode':0,'remaining_job_pids':[]}
            with patch.object(stage_b,'RUN',folder), patch.object(stage_b,'run_job',side_effect=fake_job), \
                    patch('sys.argv',['stage_b','--units',*units]):
                stage_b.main()
            return launched,json.loads((folder/'stage.json').read_text(encoding='utf-8'))

    def test_crash_with_missing_summary_recovers_calls_and_stops(self):
        launched,stage=self.exercise({'status':'worker_error','returncode':3,'remaining_job_pids':[]},
                                    None,['002-D','002-M1'])
        self.assertEqual(launched,['002-D'])
        self.assertEqual(stage['units']['002-D']['calls_charged'],2)
        self.assertEqual(stage['units']['002-D']['result_status'],'incomplete')
        self.assertNotIn('002-M1',stage['units'])

    def test_confirmed_summary_cannot_mask_controller_fault(self):
        launched,_=self.exercise({'status':'worker_error','returncode':0,
                                 'worker_exit_with_descendants':True,'remaining_job_pids':[]},
                                {'status':'confirmed','calls_charged':2},['002-D','002-M1'])
        self.assertEqual(launched,['002-D'])

    def test_known_baseline_rejection_blocks_case_only(self):
        launched,stage=self.exercise({'status':'worker_error','returncode':1,'remaining_job_pids':[]},
            {'status':'baseline_failed','failure_kind':'baseline_rejected','calls_charged':2},
            ['002-D','002-M1','008-D'])
        self.assertEqual(launched,['002-D','008-D'])
        self.assertNotIn('002-M1',stage['units'])

    def test_worker_timeout_or_unknown_error_halts(self):
        for kind in ('proposal_timeout_or_error','evaluation_timeout_or_error'):
            with self.subTest(kind=kind):
                self.assertTrue(stage_b.stop_after_unit(
                    {'status':'worker_error','returncode':1},
                    {'status':'confirmation_missing_or_failed','halt_stage':True,'failure_kind':kind}))


if __name__ == '__main__':
    unittest.main()
