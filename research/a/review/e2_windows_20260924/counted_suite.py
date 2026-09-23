"""Count direct truth calls and completed routes without editing the tested core."""
from collections import Counter
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from research.a.e2_search.tests.test_search import SearchTest
from research.a.e2_search import E2Evaluator, E2BatchEvaluator


def main():
    counts = Counter()
    setup = SearchTest.setUpClass
    direct = E2Evaluator.evaluate_record
    batch = E2BatchEvaluator.evaluate_batch

    def setup_counted(cls):
        setup()
        oracle = cls.oracle.evaluate_scene_a
        def truth(*args, **kwargs):
            counts["direct_e0_started"] += 1
            try:
                result = oracle(*args, **kwargs)
            except Exception as exc:
                counts["direct_e0_exception_" + type(exc).__name__] += 1
                raise
            counts["direct_e0_success"] += 1
            return result
        cls.oracle.evaluate_scene_a = truth

    def evaluate(self, *args, **kwargs):
        counts["parent_e2_requests"] += 1
        record = direct(self, *args, **kwargs)
        counts["parent_e2_route_" + record.get("route", "unspecified")] += 1
        counts["parent_e2_status_" + record["status"]] += 1
        return record

    def evaluate_batch(self, *args, **kwargs):
        for record in batch(self, *args, **kwargs):
            counts["pool_completed_records"] += 1
            counts["pool_route_" + record.get("route", "unspecified")] += 1
            counts["pool_status_" + record["status"]] += 1
            yield record

    SearchTest.setUpClass = classmethod(setup_counted)
    E2Evaluator.evaluate_record = evaluate
    E2BatchEvaluator.evaluate_batch = evaluate_batch
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SearchTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("CALL_COUNTS " + json.dumps(dict(counts), sort_keys=True))
    print("Counts distinguish direct unmodified E0 from E1 fallback; killed/timeout in-flight internals are unknown. No performance claims from instrumented tests.")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
