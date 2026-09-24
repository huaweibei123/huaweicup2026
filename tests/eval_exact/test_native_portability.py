"""Proposed native-portability checks; not executed in the source-only phase.

Routing/manifest/bridge classes use mocks or one explicitly synthetic prepared
task: no complete E0/E1 evaluations, subprocesses, workers, or real CDLL calls.
The separate TinyE1IntegrationTest spends four full E1 evaluations and one E0
evaluation on a three-operation graph, plus rejected-input validation/local
preparation. Imports still load the existing official Python support bundle.
Running any class requires the next phase's explicit execution budget; these
tests do not build or validate a real native artifact or prove native parity.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import ctypes
import hashlib
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


CONFIG = dict(bandwidth=32, capacity={"UB": 1048576, "L1": 1048576},
              cross_core_wait=1000, same_core_wait=100)
PLAN = dict(node_to_subgraph={"1": 0, "2": 1, "3": 2},
            core_schedules=[[0, 2], [1]])


def tiny_graph():
    return dict(ops=[dict(id=i, op="CONV", pipe="PIPE_M", cycles=i)
                     for i in (1, 2, 3)],
                tensors=[], edges=[dict(source=1, target=3)])


def fake_engine(native, *, manifest="reviewed-manifest.json"):
    """Bypass official construction only for isolated routing checks."""
    engine = object.__new__(native.NativeP1Evaluator)
    engine._native_manifest = manifest
    engine._native_backend = None
    engine._lock = threading.RLock()
    engine._graph = object()
    engine._runtime = SimpleNamespace(validate_parameters=Mock(), PIPE_SLOTS=1)
    engine._pending = None
    engine._entries = OrderedDict([(b"prior-key", b"prior-value")])
    engine._bytes = len(b"prior-keyprior-value")
    engine._limit = 4096
    engine._max_entries = 8
    engine._counts = dict(hits=0, misses=0, evictions=0, bypasses=0)

    def prepare(*_args):
        engine._pending = (b"prepared-but-not-e1", b"not-committed")
        return {}, {}, {}, dict(core_orders={0: [0]}, num_cores=1)

    engine._build_tasks = Mock(side_effect=prepare)
    return engine


class NativeRoutingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.eval_exact import native
        from src.eval_exact import _native_replay as bridge
        cls.native, cls.bridge = native, bridge

    def backend(self, *, error=None):
        bridge = SimpleNamespace(
            Unsupported=self.bridge.Unsupported,
            pack_tasks=Mock(return_value=object()),
            score=Mock(return_value={"makespan": 7}, side_effect=error))
        return SimpleNamespace(bridge=bridge, library=object())

    def test_disabled_score_calls_e1_once_without_prepare_or_loader(self):
        engine = fake_engine(self.native, manifest=None)
        with patch.object(engine, "evaluate", return_value={"makespan": 7}) as evaluate, \
                patch.object(self.native, "load_backend") as load:
            result = engine.score(PLAN, **CONFIG)
        self.assertEqual((result.makespan, result.backend, result.fallback_reason),
                         (7, "e1", "native-disabled"))
        evaluate.assert_called_once()
        engine._build_tasks.assert_not_called()
        load.assert_not_called()

    def test_full_apis_never_load_even_with_explicit_manifest(self):
        from src.eval_exact import batch
        engine = fake_engine(self.native)
        complete = dict(makespan=7, data_movement_bytes={}, cross_task_traffic={})
        with patch.object(batch, "evaluate_scene_a", return_value=complete) as full, \
                patch.object(self.native, "load_backend") as load:
            self.assertIs(engine.evaluate(PLAN, **CONFIG), complete)
            self.assertIs(engine.evaluate_record(PLAN, full=True, **CONFIG)["result"], complete)
            self.assertIs(list(engine.evaluate_batch([PLAN], full=True, **CONFIG))[0]["result"], complete)
        self.assertEqual(full.call_count, 3)  # All three are mocked, not E1 runs.
        load.assert_not_called()

    def test_missing_and_unsupported_fall_back_exactly_once(self):
        for mode in ("missing", "unsupported"):
            with self.subTest(mode=mode):
                engine = fake_engine(self.native)
                backend = self.backend(error=self.bridge.Unsupported("numeric domain"))
                unavailable = self.native.BackendUnavailable("manifest-missing")
                with patch.object(engine, "evaluate", return_value={"makespan": 7}) as evaluate, \
                        patch.object(self.native, "load_backend", return_value=backend,
                                     side_effect=unavailable if mode == "missing" else None) as load:
                    result = engine.score(PLAN, **CONFIG)
                self.assertEqual((result.makespan, result.backend), (7, "e1"))
                self.assertIn("missing" if mode == "missing" else "unsupported", result.fallback_reason)
                evaluate.assert_called_once()
                load.assert_called_once()
                self.assertIsNone(engine._pending)

    def test_validation_failure_precedes_loader_and_fallback(self):
        for stage in ("parameters", "plan"):
            with self.subTest(stage=stage):
                engine = fake_engine(self.native)
                rejection = ValueError("official validation sentinel")
                target = (engine._runtime.validate_parameters if stage == "parameters"
                          else engine._build_tasks)
                target.side_effect = rejection
                with patch.object(engine, "evaluate") as evaluate, \
                        patch.object(self.native, "load_backend") as load:
                    with self.assertRaises(ValueError) as caught:
                        engine.score(PLAN, **CONFIG)
                self.assertIs(caught.exception, rejection)
                load.assert_not_called()
                evaluate.assert_not_called()
                self.assertIsNone(engine._pending)

    def test_official_int_subclass_uses_e1_before_loading(self):
        class OfficialTaskId(int):
            pass

        for location in ("task-key", "normalized-order"):
            with self.subTest(location=location):
                engine = fake_engine(self.native)
                task_id = OfficialTaskId(0)
                tasks = {task_id if location == "task-key" else 0: {}}
                orders = [task_id if location == "normalized-order" else 0]
                engine._build_tasks.side_effect = None
                engine._build_tasks.return_value = (
                    tasks, {}, {}, dict(core_orders={0: orders}, num_cores=1))
                with patch.object(engine, "evaluate", return_value={"makespan": 7}) as evaluate, \
                        patch.object(self.native, "load_backend") as load:
                    result = engine.score(PLAN, **CONFIG)
                self.assertEqual((result.backend, result.fallback_reason),
                                 ("e1", "task-id-type-unsupported"))
                evaluate.assert_called_once()
                load.assert_not_called()

    def test_fallback_failure_is_not_retried_or_relabelled(self):
        engine = fake_engine(self.native)
        failure = RuntimeError("E1 iteration limit")
        with patch.object(engine, "evaluate", side_effect=failure) as evaluate, \
                patch.object(self.native, "load_backend",
                             side_effect=self.native.BackendUnavailable("manifest-missing")):
            with self.assertRaises(RuntimeError) as caught:
                engine.score(PLAN, **CONFIG)
        self.assertIs(caught.exception, failure)
        evaluate.assert_called_once()
        self.assertIsNone(engine._pending)

    def test_internal_and_candidate_errors_are_not_successful_fallbacks(self):
        failures = (self.bridge.NativeExecutionError(4),
                    self.bridge.CandidateError("duplicate task"),
                    RuntimeError("unexpected adapter failure"))
        for failure in failures:
            with self.subTest(error=type(failure).__name__):
                engine = fake_engine(self.native)
                engine._native_backend = self.backend(error=failure)
                before = deepcopy(engine._entries)
                with patch.object(engine, "evaluate") as evaluate:
                    with self.assertRaises(type(failure)) as caught:
                        engine.score(PLAN, **CONFIG)
                self.assertIs(caught.exception, failure)
                evaluate.assert_not_called()
                self.assertEqual(engine._entries, before)
                self.assertIsNone(engine._pending)

    def test_native_success_does_not_commit_prepared_e1_cache(self):
        engine = fake_engine(self.native)
        engine._native_backend = self.backend()
        before = deepcopy(engine._entries)
        before_bytes = engine._bytes
        with patch.object(engine, "evaluate") as evaluate, \
                patch.object(self.native, "load_backend") as load:
            result = engine.score(PLAN, **CONFIG)
        self.assertEqual((result.makespan, result.backend), (7, "native"))
        self.assertEqual(engine._entries, before)
        self.assertEqual(engine._bytes, before_bytes)
        self.assertIsNone(engine._pending)
        evaluate.assert_not_called()
        load.assert_not_called()


class BackendManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.eval_exact import native_backend
        cls.backend = native_backend

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.manifest = self.directory / "reviewed.json"
        self.binary = self.directory / "replay.dll"
        self.binary.write_bytes(b"not executable: manifest-only fixture")
        self.value = dict(
            version=1, abi="huaweicup-p1-replay-v0.1-cdecl-64le",
            source_commit="03f02e79de4b4bd6f55241385664b154f4332454",
            kernel_sha256="77b814a1fbf58bad0d07a630eab0ce5b4e5f357a74ab6dccc94f8ad6c7bb6ad6",
            target=dict(platform="win32", machine="amd64", pointer_bits=64, byteorder="little"),
            build=dict(compiler="clang", compiler_version="fixture-version",
                       flags=["-std=c++17", "-O3", "-fno-fast-math", "-ffp-contract=off", "-shared"]),
            binary="replay.dll", binary_sha256=hashlib.sha256(self.binary.read_bytes()).hexdigest())
        self.enterContext(patch.object(self.backend, "sys", SimpleNamespace(platform="win32", byteorder="little")))
        self.enterContext(patch.object(self.backend.platform, "machine", return_value="AMD64"))
        real_sizeof = ctypes.sizeof

        def declared_pointer_size(value):
            return 8 if value is ctypes.c_void_p else real_sizeof(value)

        self.enterContext(patch.object(self.backend.ctypes, "sizeof", side_effect=declared_pointer_size))
        self.cdll = self.enterContext(patch.object(self.backend.ctypes, "CDLL"))

    def write_manifest(self, value):
        self.manifest.write_text(json.dumps(value), encoding="utf-8")

    def test_discovery_checks_identity_without_loading(self):
        self.write_manifest(self.value)
        spec = self.backend.discover_backend(self.manifest)
        self.assertEqual(spec.binary, self.binary.resolve())
        self.assertEqual(spec.binary_sha256, self.value["binary_sha256"])
        self.assertEqual(spec.manifest_sha256, hashlib.sha256(self.manifest.read_bytes()).hexdigest())
        self.cdll.assert_not_called()

    def test_explicit_load_binds_cdecl_signature_and_preserves_identity(self):
        self.write_manifest(self.value)
        replay = Mock()
        library = SimpleNamespace(replay=replay)
        self.cdll.return_value = library
        loaded = self.backend.load_backend(self.manifest)
        self.cdll.assert_called_once_with(str(self.binary.resolve()))
        self.assertIs(loaded.library, library)
        self.assertEqual(loaded.spec.binary, self.binary.resolve())
        self.assertEqual(loaded.spec.binary_sha256, self.value["binary_sha256"])
        self.assertEqual(loaded.spec.manifest_sha256,
                         hashlib.sha256(self.manifest.read_bytes()).hexdigest())
        self.assertEqual(replay.argtypes, [ctypes.POINTER(loaded.bridge.Input),
                                          ctypes.POINTER(loaded.bridge.Output)])
        self.assertIs(replay.restype, ctypes.c_int)
        replay.assert_not_called()  # Python binding only; no real DLL or replay.

    def test_missing_replay_symbol_rejects_otherwise_valid_artifact(self):
        self.write_manifest(self.value)
        self.cdll.return_value = SimpleNamespace()
        with self.assertRaisesRegex(self.backend.BackendManifestError,
                                    "does not export the declared replay symbol"):
            self.backend.load_backend(self.manifest)
        self.cdll.assert_called_once_with(str(self.binary.resolve()))

    def test_identity_recipe_and_suffix_rejections_precede_cdll(self):
        changes = (
            ("binary_sha256", "0" * 64),
            ("abi", "unreviewed-abi"),
            ("source_commit", "0" * 40),
            ("kernel_sha256", "0" * 64),
            ("binary", "replay.so"),
            ("binary", "../replay.dll"),
            ("version", True),
        )
        for field, value in changes:
            with self.subTest(field=field, value=value):
                manifest = deepcopy(self.value)
                manifest[field] = value
                self.write_manifest(manifest)
                with self.assertRaises(self.backend.BackendManifestError):
                    self.backend.load_backend(self.manifest)
                self.cdll.assert_not_called()
        for flags in (("-ffast-math",), ("-ffp-contract=fast",), ("-march=native",)):
            with self.subTest(flags=flags):
                manifest = deepcopy(self.value)
                manifest["build"]["flags"].extend(flags)
                self.write_manifest(manifest)
                with self.assertRaises(self.backend.BackendManifestError):
                    self.backend.load_backend(self.manifest)
                self.cdll.assert_not_called()

    def test_missing_artifact_and_foreign_target_are_unavailable(self):
        for mode, reason in (("manifest", "manifest-missing"),
                             ("artifact", "artifact-missing"),
                             ("platform", "target-mismatch")):
            with self.subTest(mode=mode):
                manifest = deepcopy(self.value)
                if mode == "artifact":
                    manifest["binary"] = "absent.dll"
                if mode == "platform":
                    manifest["target"]["platform"] = "linux"
                self.write_manifest(manifest)
                path = self.directory / "absent.json" if mode == "manifest" else self.manifest
                with self.assertRaises(self.backend.BackendUnavailable) as caught:
                    self.backend.load_backend(path)
                self.assertEqual(caught.exception.reason, reason)
                self.cdll.assert_not_called()


class NativeBridgeBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.eval_exact import _native_replay
        cls.bridge = _native_replay

    def prepared(self):
        # Synthetic prepared input, intentionally not claimed as official Tasks.
        task = dict(seq=[10], pred_tasks=set(), pipe_ops={"PIPE_M": [10]},
                    op_by_id={10: {}}, in_tids=set(), out_tids=set(),
                    tensor_by_id={}, op_preds={10: set()}, op_succs={10: set()})
        runtime = SimpleNamespace(_op_duration=Mock(return_value=1),
                                  op_pipe=Mock(return_value="PIPE_M"),
                                  _uses_ddr_bandwidth=Mock(return_value=False))
        return self.bridge.pack_tasks({0: task}, runtime, 32)

    def test_integer_overflow_is_rejected_before_native_dispatch(self):
        for field in ("same_wait", "cross_wait", "max_iter"):
            with self.subTest(field=field):
                library = SimpleNamespace(replay=Mock())
                with self.assertRaises(self.bridge.Unsupported):
                    self.bridge.score(self.prepared(), [[0]], library=library, **{field: 2**63})
                library.replay.assert_not_called()

    def test_max_iter_int64_boundary_is_not_narrowed_or_wrapped(self):
        observed = []

        def replay(input_pointer, output_pointer):
            input_value = ctypes.cast(input_pointer, ctypes.POINTER(self.bridge.Input)).contents
            output_value = ctypes.cast(output_pointer, ctypes.POINTER(self.bridge.Output)).contents
            observed.append(input_value.max_iter)
            output_value.stats[0] = 7
            output_value.stats[5] = 0
            return 0

        result = self.bridge.score(self.prepared(), [[0]],
                                   library=SimpleNamespace(replay=replay), max_iter=2**63 - 1)
        self.assertEqual(observed, [2**63 - 1])
        self.assertEqual(result["makespan"], 7)

    def test_only_environment_status_is_unsupported(self):
        for status in (1, 2, 3, 4, 5, 6, 99):
            with self.subTest(status=status):
                library = SimpleNamespace(replay=Mock(return_value=status))
                expected = self.bridge.Unsupported if status == 6 else self.bridge.NativeExecutionError
                with self.assertRaises(expected) as caught:
                    self.bridge.score(self.prepared(), [[0]], library=library)
                library.replay.assert_called_once()
                if status != 6:
                    self.assertEqual(caught.exception.status, status)

    def test_duplicate_candidate_is_rejected_before_native_dispatch(self):
        library = SimpleNamespace(replay=Mock())
        with self.assertRaises(self.bridge.CandidateError):
            self.bridge.score(self.prepared(), [[0, 0]], library=library)
        library.replay.assert_not_called()


class TinyE1IntegrationTest(unittest.TestCase):
    """NEXT-PHASE budget: four complete E1 and one E0, no worker or CDLL.

    The second test checks two official rejection paths without full scoring.
    Successful native arithmetic, ABI execution and speed are not tested here.
    """

    @classmethod
    def setUpClass(cls):
        from src.eval_exact import native, _native_replay
        from src.eval_exact._official import REPO_ROOT, load_problem1_bundle
        from src.eval_exact.batch import read_config
        cls.native, cls.bridge = native, _native_replay
        cls.oracle, _ = load_problem1_bundle("_native_portability_tiny_oracle")
        cls.config = read_config(REPO_ROOT / "data/raw/a/official/data/config.txt")

    def test_full_result_and_three_fallback_routes(self):
        graph = tiny_graph()
        expected = self.oracle.evaluate_scene_a(graph, PLAN, **self.config)  # E0: 1
        disabled = self.native.NativeP1Evaluator(graph)
        with patch.object(self.native, "load_backend") as load:
            self.assertEqual(disabled.evaluate(PLAN, **self.config), expected)  # E1: 1
            self.assertEqual(disabled.score(PLAN, **self.config).makespan, expected["makespan"])  # E1: 2
        load.assert_not_called()
        missing = self.native.NativeP1Evaluator(graph, native_manifest="missing.json")
        with patch.object(self.native, "load_backend",
                          side_effect=self.native.BackendUnavailable("manifest-missing")) as load:
            result = missing.score(PLAN, **self.config)  # E1: 3
        load.assert_called_once()
        self.assertEqual((result.backend, result.makespan), ("e1", expected["makespan"]))
        self.assertEqual(missing.cache_stats()["entries"], 1)
        unsupported = self.native.NativeP1Evaluator(graph, native_manifest="reviewed.json")
        unsupported._native_backend = SimpleNamespace(
            bridge=SimpleNamespace(Unsupported=self.bridge.Unsupported,
                                   pack_tasks=Mock(side_effect=self.bridge.Unsupported("test domain"))),
            library=object())
        result = unsupported.score(PLAN, **self.config)  # E1: 4
        self.assertEqual((result.backend, result.makespan), ("e1", expected["makespan"]))
        self.assertEqual(unsupported.cache_stats()["entries"], 1)
        self.assertIsNone(unsupported._pending)

    def test_official_invalid_inputs_fail_before_loading(self):
        engine = self.native.NativeP1Evaluator(tiny_graph(), native_manifest="reviewed.json")
        cases = (
            ({}, self.config,
             lambda: engine._runtime.derive_multicore_plan(engine._graph, {})),
            (PLAN, dict(self.config, bandwidth=0),
             lambda: engine._runtime.validate_parameters(
                 0, dict(self.config["capacity"]), 1_000_000,
                 cross_core_wait=self.config["cross_core_wait"],
                 same_core_wait=self.config["same_core_wait"])),
        )
        for plan, config, official_check in cases:
            with self.subTest(plan=plan, bandwidth=config["bandwidth"]):
                try:
                    official_check()
                except Exception as error:
                    expected_type, expected_message = type(error), str(error)
                else:
                    self.fail("fixture did not trigger official validation")
                with patch.object(self.native, "load_backend") as load, \
                        patch.object(engine, "evaluate") as fallback:
                    with self.assertRaises(expected_type) as caught:
                        engine.score(plan, **config)
                self.assertEqual(str(caught.exception), expected_message)
                load.assert_not_called()
                fallback.assert_not_called()
                self.assertIsNone(engine._pending)


if __name__ == "__main__":
    unittest.main()
