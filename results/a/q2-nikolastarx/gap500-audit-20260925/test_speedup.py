import importlib.util
import unittest
from pathlib import Path

p = Path(__file__).with_name('audit.py')
spec = importlib.util.spec_from_file_location('gap500_audit', p)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class SharedBaselineTest(unittest.TestCase):
    def test_same_official_singlecore_denominator_but_paired_old_core_makespan(self):
        B = 100
        old_k1_makespan, old_k2_makespan, new_k2_makespan = 100, 60, 50
        self.assertEqual(audit.paired_baseline(
            {'baseline_m': old_k1_makespan}, {'baseline_m': old_k1_makespan},
            {'metrics': {'makespan_cycles': old_k1_makespan}}, B, old_k1_makespan)['old_B_over_M'], 1)
        pair = audit.paired_baseline(
            {'baseline_m': old_k2_makespan}, {'baseline_m': old_k2_makespan},
            {'metrics': {'makespan_cycles': old_k2_makespan}}, B, new_k2_makespan)
        self.assertEqual((pair['B_i'], pair['old_M'], pair['new_M']), (100, 60, 50))
        self.assertAlmostEqual(pair['old_B_over_M'], 100 / 60)
        self.assertEqual(pair['new_B_over_M'], 2)
        with self.assertRaises(ValueError):
            audit.paired_baseline({'baseline_m': B}, {'baseline_m': B},
                                  {'metrics': {'makespan_cycles': 60}}, B, 50)

if __name__ == '__main__':
    unittest.main()
