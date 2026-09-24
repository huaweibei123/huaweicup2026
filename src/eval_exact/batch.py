"""Exact, graph-resident P1 evaluation with bounded local-compilation reuse.

The batch records are a SEARCH adapter, not a replacement official JSON schema.
``evaluate`` returns the complete official result and preserves oracle exceptions.
For cancellable/time-limited work use ``P1BatchEvaluator`` in ``pool``.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import pickle
import threading
import time

from ._official import OFFICIAL_CODE_HASH, load_problem1_bundle
from ._scene_a import evaluate_scene_a
from .problem1 import _build_scene_a_tasks_indexed, _copy_step3_extended_graph

ENGINE_VERSION = "p1-exact-batch-v1"
DEFAULT_CACHE_BYTES = 16 * 1024 * 1024


def read_config(path):
    """Read the unchanged official config into keyword arguments for evaluate."""
    runtime, support = load_problem1_bundle("_p1_batch_config")
    settings = support["evaluation_validation"].read_evaluation_config(str(path))
    scene = runtime.read_scene_a_config(str(path))
    return dict(bandwidth=settings["bandwidth"], capacity=settings["capacity"],
                cross_core_wait=scene["task_cross_core_wait_cycles"],
                same_core_wait=scene["task_same_core_wait_cycles"])


class P1Evaluator:
    """Own a snapshot of one official graph and an instance-local LRU cache.

    Recreate the evaluator to change the graph. Plan/config changes are checked on
    every call. No global result is cached. Stored bytes are private and decoded
    for each candidate, preventing aliases across calls or into returned results.
    cache_bytes bounds serialized keys + values, NOT the Python process RSS.
    A lock serializes calls on an instance; use processes for parallel evaluation.
    """

    def __init__(self, graph, *, cache_bytes=DEFAULT_CACHE_BYTES, max_cache_entries=128):
        if type(cache_bytes) is not int or cache_bytes < 0:
            raise ValueError("cache_bytes must be a non-negative integer")
        if type(max_cache_entries) is not int or max_cache_entries < 1:
            raise ValueError("max_cache_entries must be a positive integer")
        self._graph = deepcopy(graph)
        self._runtime, self._support = load_problem1_bundle("_p1_batch_runtime")
        self._lock = threading.RLock()
        self._entries = OrderedDict()
        self._limit = cache_bytes
        self._max_entries = max_cache_entries
        self._bytes = 0
        self._counts = dict(hits=0, misses=0, evictions=0, bypasses=0)
        self._pending = None
        step3_globals = self._runtime.prepare_step3_execution.__globals__
        step3_globals["deepcopy"] = _copy_step3_extended_graph
        original_step3 = step3_globals["step3_simulation"]

        def compact_step3(*args, **kwargs):
            result = original_step3(*args, **kwargs)
            # These are all fields consumed by frozen prepare_step3 + P1.
            return {key: result[key] for key in (
                "execution_graph", "pipe_orders", "makespan", "memory_peak",
                "memory_dependencies")}

        step3_globals["step3_simulation"] = compact_step3
        self._runtime._build_scene_a_tasks = self._build_tasks

    def _build_tasks(self, graph, plan, bandwidth, capacity):
        runtime = self._runtime
        # Always validate order, including on a hit and when waits change.
        view = runtime.derive_multicore_plan(graph, plan)
        runtime.validate_task_order(view)
        key = None
        if self._limit:
            # Graph and engine are fixed per instance. Preserve ordered raw
            # mapping and capacity, numeric types and float representations.
            key = pickle.dumps((plan["node_to_subgraph"], bandwidth, capacity), protocol=5)
            value = self._entries.get(key)
            if value is not None:
                self._counts["hits"] += 1
                self._entries.move_to_end(key)
                tasks, cross_traffic, traffic = pickle.loads(value)
                for tid, task in tasks.items():
                    task["core_id"] = view["core_by_subgraph"][tid]
                    task["pred_tasks"] = view["subgraph_preds"][tid]
                    graph = task["graph"]
                    inputs, outputs, preds, succs = runtime._build_graph_views(
                        graph["ops"], graph["edges"])
                    # Unpickling a set need not preserve its iteration layout.
                    task.update(in_tids=inputs, out_tids=outputs,
                                op_preds=preds, op_succs=succs)
                return tasks, cross_traffic, traffic, view
            self._counts["misses"] += 1
        else:
            self._counts["bypasses"] += 1
        tasks, cross_traffic, traffic, view = _build_scene_a_tasks_indexed(
            graph, plan, bandwidth, capacity, runtime=runtime)
        if key is not None:
            value = pickle.dumps((tasks, cross_traffic, traffic), protocol=5)
            if len(key) + len(value) <= self._limit:
                # Commit only after the GLOBAL simulation succeeds. A deadlock,
                # max_iter or any unexpected error cannot add a cache entry.
                self._pending = (key, value)
            else:
                self._counts["bypasses"] += 1
        return tasks, cross_traffic, traffic, view

    def evaluate(self, plan, bandwidth, capacity, cross_core_wait, same_core_wait,
                 max_iter=1_000_000):
        """Return full official P1 results; propagate exact exception type/message."""
        with self._lock:
            self._pending = None
            try:
                result = evaluate_scene_a(
                    self._runtime, self._graph, plan, bandwidth, capacity,
                    cross_core_wait, same_core_wait, max_iter=max_iter)
                if self._pending is not None:
                    key, value = self._pending
                    size = len(key) + len(value)
                    while (self._bytes + size > self._limit or
                           len(self._entries) >= self._max_entries):
                        old_key, old_value = self._entries.popitem(last=False)
                        self._bytes -= len(old_key) + len(old_value)
                        self._counts["evictions"] += 1
                    self._entries[key] = value
                    self._bytes += size
                return result
            finally:
                self._pending = None

    def clear_cache(self):
        """Release stored payload; keep cumulative counters for diagnostics."""
        with self._lock:
            self._entries.clear()
            self._bytes = 0

    def cache_stats(self):
        with self._lock:
            return dict(self._counts, payload_bytes=self._bytes,
                        limit_bytes=self._limit, entries=len(self._entries),
                        max_entries=self._max_entries)

    def _is_invalid(self, error):
        # Only explicit input/plan validation is an invalid candidate. Runtime
        # deadlocks and resource/iteration limits remain errors, never invalid.
        return isinstance(error, (
            self._support["evaluation_validation"].EvaluationValidationError,
            self._support["stub_multicore_cut_and_schedule"].MulticoreCutError,
        ))

    def evaluate_record(self, plan, *, full=False, **config):
        """Search record with status; full=False still computes the full result."""
        with self._lock:
            start = time.perf_counter()
            try:
                result = self.evaluate(plan, **config)
                record = dict(status="ok", makespan=result["makespan"],
                              data_movement_bytes=result["data_movement_bytes"],
                              cross_task_traffic=result["cross_task_traffic"])
                if full:
                    record["result"] = result
            except Exception as error:
                record = dict(status="invalid" if self._is_invalid(error) else "error",
                              error_type=type(error).__name__, message=str(error))
            record.update(wall_seconds=time.perf_counter() - start,
                          engine=ENGINE_VERSION, official_code_hash=OFFICIAL_CODE_HASH,
                          cache=self.cache_stats())
            return record

    def evaluate_batch(self, plans, *, full=False, **config):
        """Yield in input order in-process; no wall-clock timeout in this method."""
        for index, plan in enumerate(plans):
            yield dict(self.evaluate_record(plan, full=full, **config), index=index)
