"""Pure necessary-job fixtures: no contest graph, solver or evaluator calls."""

import copy
import itertools
import random
import unittest

from src.q1.resource_windows import resource_window_bound, verify_resource_window


def enumerate_windows(jobs, capacity):
    """Independent small-object oracle: explicitly visit every threshold pair."""
    bounds = [0]
    for release, tail in itertools.product(
        {job[0] for job in jobs}, {job[2] for job in jobs},
    ):
        selected = [job for job in jobs if job[0] >= release and job[2] >= tail]
        if selected:
            quotient, remainder = divmod(sum(job[1] for job in selected), capacity)
            bounds.append(release + tail + quotient + int(remainder != 0))
    return max(bounds)


class ResourceWindowTests(unittest.TestCase):
    def test_empty_jobs(self):
        certificate = resource_window_bound([], 3)
        self.assertEqual(certificate["bound"], 0)
        self.assertTrue(certificate["empty"])
        self.assertTrue(verify_resource_window([], 3, certificate))

    def test_empty_rectangle_cannot_manufacture_a_bound(self):
        # At r=1000, the q=1000 leaf exists but has no activated job.
        jobs = [(1000, 1, 0), (0, 1, 1000)]
        certificate = resource_window_bound(jobs, 1)
        self.assertEqual(certificate["bound"], 1001)
        self.assertTrue(verify_resource_window(jobs, 1, certificate))

    def test_zero_service_still_has_a_required_event(self):
        for jobs, expected in [
            ([(8, 0, 9)], 17),
            ([(1000, 0, 0), (0, 0, 1000)], 1000),
            ([(0, 0, 0)] * 3, 0),
        ]:
            with self.subTest(jobs=jobs):
                certificate = resource_window_bound(jobs, 5)
                self.assertEqual(certificate["bound"], expected)
                self.assertFalse(certificate["empty"])
                self.assertTrue(verify_resource_window(jobs, 5, certificate))

    def test_double_threshold_strengthens_total_work(self):
        jobs = [(0, 1, 0), (100, 100, 100), (100, 100, 100)]
        certificate = resource_window_bound(jobs, 1)
        self.assertEqual(certificate["bound"], 400)
        self.assertEqual(certificate["selected_count"], 2)
        self.assertEqual(certificate["selected_work"], 200)
        self.assertTrue(verify_resource_window(jobs, 1, certificate))

    def test_duplicate_jobs_and_nondivisible_capacity(self):
        jobs = [(2, 3, 4)] * 3
        self.assertEqual(resource_window_bound(jobs, 2)["bound"], 11)

    def test_large_integers_never_pass_through_float(self):
        huge = 10**120 + 7
        jobs = [(huge, huge + 1, huge + 2), (huge + 3, huge + 4, 0)]
        for capacity in (1, 3, huge):
            certificate = resource_window_bound(jobs, capacity)
            self.assertEqual(certificate["bound"], enumerate_windows(jobs, capacity))
            self.assertTrue(verify_resource_window(jobs, capacity, certificate))

    def test_fixed_seed_small_objects_against_exhaustive_thresholds(self):
        rng = random.Random(660724)
        for sample in range(350):
            jobs = [tuple(rng.randrange(12) for _ in range(3))
                    for _ in range(rng.randrange(14))]
            capacity = rng.randrange(1, 8)
            with self.subTest(sample=sample):
                original = copy.deepcopy(jobs)
                certificate = resource_window_bound(jobs, capacity)
                self.assertEqual(certificate["bound"], enumerate_windows(jobs, capacity))
                self.assertTrue(verify_resource_window(jobs, capacity, certificate))
                self.assertEqual(jobs, original)
                rng.shuffle(jobs)
                self.assertEqual(resource_window_bound(iter(jobs), capacity), certificate)

    def test_rejects_invalid_capacity_and_job_domains(self):
        for capacity in (True, False, 0, -1, 1.0, "1", None):
            with self.subTest(capacity=capacity), self.assertRaises(ValueError):
                resource_window_bound([], capacity)
        invalid = [None, [1], [(1, 2)], [(1, 2, 3, 4)],
                   [{0: 1, 1: 2, 2: 3}], ["123"]]
        for index in range(3):
            for value in (-1, True, False, 1.0, "1", None):
                row = [1, 2, 3]
                row[index] = value
                invalid.append([row])
        for jobs in invalid:
            with self.subTest(jobs=jobs), self.assertRaises(ValueError):
                resource_window_bound(jobs, 1)

    def test_tampered_witness_is_rejected(self):
        jobs = [(0, 1, 0), (100, 100, 100), (100, 100, 100)]
        certificate = resource_window_bound(jobs, 1)
        mutations = {
            "kind": "wrong", "capacity": 2, "job_count": 4, "empty": True,
            "r_threshold": 101, "q_threshold": 101, "selected_count": 3,
            "selected_work": 201, "bound": 401,
        }
        for field, value in mutations.items():
            modified = dict(certificate, **{field: value})
            with self.subTest(field=field):
                self.assertFalse(verify_resource_window(jobs, 1, modified))
        for field in ("capacity", "job_count", "r_threshold", "q_threshold",
                      "selected_count", "selected_work", "bound"):
            with self.subTest(field=field, type="bool"):
                self.assertFalse(verify_resource_window(jobs, 1, dict(certificate, **{field: True})))
        for malformed in (None, [], {}, dict(certificate, extra=1)):
            self.assertFalse(verify_resource_window(jobs, 1, malformed))
        empty = resource_window_bound([], 1)
        self.assertFalse(verify_resource_window([], 1, dict(empty, r_threshold=0)))
        self.assertFalse(verify_resource_window([], 1, dict(empty, bound=1)))

    def test_verifier_checks_a_witness_not_global_maximality(self):
        jobs = [(0, 1, 0), (100, 100, 100), (100, 100, 100)]
        certificate = resource_window_bound(jobs, 1)
        certificate.update(r_threshold=0, q_threshold=0,
                           selected_count=3, selected_work=201, bound=201)
        self.assertTrue(verify_resource_window(jobs, 1, certificate))


if __name__ == "__main__":
    unittest.main()
