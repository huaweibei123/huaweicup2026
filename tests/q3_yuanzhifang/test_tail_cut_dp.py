import itertools
import random
import unittest

from src.q3_yuanzhifang.tail_cut_dp import decide, optimize


def exhaustive(length, cores, table):
    options = []
    for inside in itertools.combinations(range(1, length), cores - 1):
        cuts = (0, *inside, length)
        arrival, peak = 0, 0
        for c, (left, right) in enumerate(zip(cuts, cuts[1:])):
            item = table.get((c, left, right))
            if item is None:
                break
            peak = max(peak, item["A"], arrival + item["B"])
            arrival = max(item["C"], arrival + item["D"])
        else:
            options.append((peak, cuts))
    return min(options) if options else None


class TailCutDPTest(unittest.TestCase):
    def test_minimax_matches_independent_all_cuts_enumeration(self):
        rng = random.Random(8673)
        for _ in range(70):
            length = rng.randint(2, 6)
            cores = rng.randint(1, min(4, length))
            table = {(c, l, r): {name: rng.randint(0, 7) for name in "ABCD"}
                     for c in range(cores) for l in range(length)
                     for r in range(l + 1, length + 1)}
            oracle = exhaustive(length, cores, table)
            result = optimize(length, cores, table)
            self.assertEqual(result["optimum"], oracle[0])
            self.assertEqual(result["makespan"], oracle[0])
            self.assertEqual((result["cuts"][0], result["cuts"][-1]), (0, length))
            self.assertEqual(len(result["cuts"]), cores + 1)
            self.assertTrue(all(a < b for a, b in zip(result["cuts"], result["cuts"][1:])))
            self.assertEqual(len(result["arrival"]), cores)
            self.assertTrue(result["transition_count"] > 0)

    def test_threshold_must_keep_minimal_arrival_not_minimal_prefix_peak(self):
        # All responses also obey physical local-DAG inequalities A>=B,C;
        # B,C>=D>0. At the merge, prefixes have (R,M)=(2,11) and (5,9).
        table = {(0, 0, 1): dict(A=11, B=1, C=1, D=1),
                 (0, 0, 2): dict(A=4, B=1, C=4, D=1),
                 (1, 1, 3): dict(A=1, B=1, C=1, D=1),
                 (1, 2, 3): dict(A=9, B=1, C=1, D=1),
                 (2, 3, 4): dict(A=7, B=7, C=1, D=1)}
        route, _ = decide(4, 3, table, 11)
        self.assertEqual(route["cuts"], [0, 1, 3, 4])
        self.assertEqual(route["arrival"], [0, 1, 2])
        self.assertEqual(optimize(4, 3, table)["optimum"], 11)
        self.assertIsNone(decide(4, 3, table, 10)[0])

    def test_sparse_no_path_and_zero_boundary(self):
        with self.assertRaisesRegex(ValueError, "no connected"):
            optimize(3, 2, {(0, 0, 1): dict(A=1, B=1, C=1, D=1)})
        zero = optimize(2, 2, {(0, 0, 1): dict(A=0, B=0, C=0, D=0),
                               (1, 1, 2): dict(A=0, B=0, C=0, D=0)})
        self.assertEqual((zero["cuts"], zero["optimum"]), ([0, 1, 2], 0))

    def test_invalid_domains_and_coefficients_rejected(self):
        valid = {(0, 0, 1): dict(A=1, B=1, C=1, D=1)}
        for length, cores in ((0, 1), (2, 0), (2, 3)):
            with self.assertRaises(ValueError):
                optimize(length, cores, valid)
        for key, value in [((0, 0, 0), dict(A=1, B=1, C=1, D=1)),
                           ((1, 0, 1), dict(A=1, B=1, C=1, D=1)),
                           ((0, 0, 1), dict(A=-1, B=1, C=1, D=1)),
                           ((0, 0, 1), dict(A=1.0, B=1, C=1, D=1))]:
            with self.assertRaises(ValueError):
                optimize(1, 1, {key: value})
        with self.assertRaises(ValueError):
            decide(1, 1, valid, -1)


if __name__ == "__main__":
    unittest.main()
