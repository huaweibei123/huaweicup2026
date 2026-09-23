"""Timing audit detects residuals and retains tied critical predecessors."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/q1'))
from trace_explain import gates
from trace_priority import critical_tasks


def tied_result():
    return {'makespan':1015,'task_same_core_wait_cycles':100,'task_cross_core_wait_cycles':1000,
            'per_core_timeline':[
                {'core_id':0,'tasks':[{'task_id':0,'start':0,'end':10,'duration':10}]},
                {'core_id':1,'tasks':[{'task_id':1,'start':0,'end':10,'duration':10}]},
                {'core_id':2,'tasks':[{'task_id':2,'start':1010,'end':1015,'duration':5}]}],
            'task_dependencies':[{'source':0,'target':2},{'source':1,'target':2}]}


class TraceAudit(unittest.TestCase):
    def test_tied_predecessors_belong_to_critical_dag(self):
        annotation = gates(tied_result())
        self.assertEqual(annotation['start_mismatches'], [])
        self.assertEqual(critical_tasks(annotation), {0,1,2})
        self.assertEqual(annotation['chain_busy']+annotation['chain_wait'],1015)

    def test_unexplained_start_delay_is_reported_not_forced_away(self):
        result = copy.deepcopy(tied_result())
        task=result['per_core_timeline'][2]['tasks'][0]
        task['start']+=7;task['end']+=7;result['makespan']+=7
        annotation=gates(result)
        self.assertEqual(annotation['start_mismatches'],[2])
        self.assertEqual(annotation['chain_residual'],7)
        self.assertEqual(annotation['chain_busy']+annotation['chain_wait']+annotation['chain_residual'],1022)


if __name__ == '__main__':
    unittest.main()
