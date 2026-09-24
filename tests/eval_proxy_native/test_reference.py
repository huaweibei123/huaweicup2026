from __future__ import annotations

import unittest
from pathlib import Path

from src.eval_proxy.native.reference import ProtocolError, evaluate_bytes
from src.eval_proxy.native.run_experiment import generate_input


class NativeProxyReferenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = Path(__file__).with_name("fixtures")

    def test_fixed_vector_matches_canonical_bytes(self):
        raw = (self.fixtures / "smoke.input.tsv").read_bytes()
        expected = (self.fixtures / "smoke.expected.tsv").read_bytes()
        self.assertEqual(evaluate_bytes(raw), expected)

    def test_generator_is_deterministic(self):
        first = generate_input(32, 20260923)
        self.assertEqual(first, generate_input(32, 20260923))
        self.assertNotEqual(first, generate_input(32, 20260924))
        self.assertEqual(len(evaluate_bytes(first).splitlines()), 33)

    def test_duplicate_id_is_rejected(self):
        raw = b"NATIVE_PROXY_V1\nsame\t1\t1\t0\t1\t0\t0\t1000000\nsame\t1\t1\t0\t1\t0\t0\t1000000\n"
        with self.assertRaisesRegex(ProtocolError, "duplicate candidate_id"):
            evaluate_bytes(raw)

    def test_invalid_relation_is_rejected(self):
        raw = b"NATIVE_PROXY_V1\nbad\t1\t1\t0\t1\t1\t2\t1000000\n"
        with self.assertRaisesRegex(ProtocolError, "cross_core_count exceeds"):
            evaluate_bytes(raw)

    def test_u64_overflow_is_rejected(self):
        raw = b"NATIVE_PROXY_V1\nbig\t1\t1\t18446744073709551615\t1\t0\t0\t1000000\n"
        with self.assertRaisesRegex(ProtocolError, "overflow while computing transfer"):
            evaluate_bytes(raw)


if __name__ == "__main__":
    unittest.main()
