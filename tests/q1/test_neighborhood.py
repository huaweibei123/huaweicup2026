import itertools
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/q1'))
from neighborhood import TaskOrderIndex
from test_structure import graph
from stub_multicore_cut_and_schedule import derive_multicore_plan, MulticoreCutError
from evaluation_validation import validate_task_order, EvaluationValidationError


class InsertionIntervals(unittest.TestCase):
    def test_all_four_node_dags_assignments_tasks_and_slots(self):
        pairs = list(itertools.combinations(range(4), 2))
        checked = 0
        for mask in range(1 << len(pairs)):
            g = graph(4, [edge for i, edge in enumerate(pairs) if mask & (1 << i)])
            for assignment in itertools.product(range(2), repeat=4):
                plan = {'node_to_subgraph': {str(v): v for v in range(4)},
                        'core_schedules': [[v for v in range(4) if assignment[v] == k] for k in range(2)]}
                index = TaskOrderIndex(g, plan)
                for task in range(4):
                    for target in range(2):
                        actual = set()
                        slots = len([t for t in plan['core_schedules'][target] if t != task]) + 1
                        for position in range(slots):
                            candidate = index.move(task, target, position)
                            try:
                                validate_task_order(derive_multicore_plan(g, candidate))
                                actual.add(position)
                            except (MulticoreCutError, EvaluationValidationError):
                                pass
                            checked += 1
                        self.assertEqual(set(index.positions(task, target)), actual)
        self.assertEqual(checked, 20480)


if __name__ == '__main__':
    unittest.main()
