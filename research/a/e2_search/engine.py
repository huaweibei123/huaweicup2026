"""Resident E2 scorer. Search records are deliberately separate from official JSON.

Fast success runs the full event replay, including DDR clock cuts; no learned
correction, sample-dependent calibration, or stored candidate scores are used.
Unsupported native inputs are evaluated in full by E1, never declared invalid
by the native adapter. This is a P1 development candidate, not sealed acceptance.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, fields, is_dataclass
import pickle
import sys
import threading
import time

import numpy as np

from src.eval_exact import P1Evaluator
from src.eval_exact._official import OFFICIAL_CODE_HASH
from . import _native

ENGINE_VERSION = "p1-e2-native-search-v1"


def _owned_bytes(value, seen=None):
    """Account retained Python objects/owned array buffers, not allocator/RSS.

    Called only on insertion. NumPy owns these packed arrays; getsizeof includes
    their buffer, so do not add nbytes again. The bound excludes transient local
    compilation, the resident graph/runtime, and per-call replay allocations.
    """
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = sys.getsizeof(value)
    if isinstance(value, np.ndarray):
        return max(size, value.nbytes)
    if isinstance(value, dict):
        return size + sum(_owned_bytes(k, seen) + _owned_bytes(v, seen) for k, v in value.items())
    if isinstance(value, (list, tuple, set, frozenset)):
        return size + sum(_owned_bytes(v, seen) for v in value)
    if is_dataclass(value):
        return size + _owned_bytes(vars(value), seen)
    return size


@dataclass
class _Partition:
    compiled: _native.Compiled
    movement: dict
    cross_traffic: int


class E2Evaluator:
    """Snapshot one graph, reuse validated partitions under an explicit budget.

    Calls on one instance are serialized. Choose E2BatchEvaluator for processes;
    the native kernel has no internal thread pool. Changing any raw mapping,
    capacity, or bandwidth rebuilds the complete partition. New core orders and
    waits always revalidate/replay; they never retrieve old scores.
    """

    def __init__(self, graph, *, cache_bytes=16 << 20, max_cache_entries=32,
                 native_enabled=True, max_native_ops=2_000_000):
        for name, value, minimum in (("cache_bytes", cache_bytes, 0),
                                     ("max_cache_entries", max_cache_entries, 1),
                                     ("max_native_ops", max_native_ops, 1)):
            if type(value) is not int or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
        if type(native_enabled) is not bool:
            raise ValueError("native_enabled must be boolean")
        # Disable E1's separate Task cache: keep a single budget for E2 entries.
        self._e1 = P1Evaluator(graph, cache_bytes=0)
        self._lock = threading.RLock()
        self._entries = OrderedDict()
        self._limit, self._max_entries = cache_bytes, max_cache_entries
        self._native_enabled, self._max_ops = native_enabled, max_native_ops
        self._bytes = 0
        self._counts = dict(hits=0, misses=0, evictions=0, bypasses=0,
                            native_calls=0, fallback_calls=0, full_calls=0)

    def cache_stats(self):
        with self._lock:
            return dict(self._counts, accounted_bytes=self._bytes,
                        limit_bytes=self._limit, entries=len(self._entries),
                        max_entries=self._max_entries)

    def clear_cache(self):
        with self._lock:
            self._entries.clear()
            self._bytes = 0

    def _native_score(self, plan, config):
        if not self._native_enabled:
            raise _native.Unsupported("native_disabled")
        runtime = self._e1._runtime
        capacity = dict(config["capacity"])
        runtime.validate_parameters(config["bandwidth"], capacity, config["max_iter"],
                                    cross_core_wait=config["cross_core_wait"],
                                    same_core_wait=config["same_core_wait"])
        # Only plain, official-shaped input is fast-pathed. Other Python API
        # containers/numeric subclasses retain official behavior via fallback.
        if (type(plan) is not dict or set(plan) != {"node_to_subgraph", "core_schedules"}
                or type(plan["node_to_subgraph"]) is not dict
                or type(plan["core_schedules"]) is not list
                or any(type(row) is not list for row in plan["core_schedules"])):
            raise _native.Unsupported("plan_container_domain")
        if any(type(k) not in (str, int) or type(v) is not int
               for k, v in plan["node_to_subgraph"].items()):
            raise _native.Unsupported("mapping_type_domain")
        # Preserve insertion order and numeric types: global COPY IDs depend
        # on the entire partition, and raw-key distinctions are not normalized.
        key = pickle.dumps((plan["node_to_subgraph"], config["bandwidth"], capacity), protocol=5)
        cached = self._entries.get(key)
        cold = cached is None
        if cold:
            self._counts["misses"] += 1
            tasks, cross, movement, _ = self._e1._build_tasks(
                self._e1._graph, plan, config["bandwidth"], capacity)
            if sum(len(t["seq"]) for t in tasks.values()) > self._max_ops:
                raise _native.Unsupported("max_native_ops")
            compiled = _native.pack_tasks(tasks, runtime, config["bandwidth"])
            # Search never returns per-op IDs/timestamps; keep only O(tasks)
            # Python metadata and the numeric program. No prepared Task graphs.
            compiled.op_keys = range(len(compiled.op_keys))
            compiled.index = {}
            entry = _Partition(compiled, movement, cross)
            del tasks
        else:
            self._counts["hits"] += 1
            self._entries.move_to_end(key)
            entry = cached[0]
        result = _native.score(entry.compiled, plan["core_schedules"],
                               same_wait=config["same_core_wait"],
                               cross_wait=config["cross_core_wait"],
                               max_iter=config["max_iter"], project_once=True)
        # Do not admit a partition on failed global replay.
        if cold:
            size = _owned_bytes((key, entry))
            if size <= self._limit:
                while self._entries and (self._bytes + size > self._limit
                                         or len(self._entries) >= self._max_entries):
                    _, (_, old_size) = self._entries.popitem(last=False)
                    self._bytes -= old_size
                    self._counts["evictions"] += 1
                self._entries[key] = (entry, size)
                self._bytes += size
            else:
                self._counts["bypasses"] += 1
        self._counts["native_calls"] += 1
        return dict(status="ok", makespan=result["makespan"],
                    data_movement_bytes=deepcopy(entry.movement),
                    cross_task_traffic=entry.cross_traffic, route="native",
                    execution="native_replayed", numeric_kind="computed",
                    replay_iterations=int(result["stats"][1]))

    def evaluate_record(self, plan, *, bandwidth, capacity, cross_core_wait,
                        same_core_wait, max_iter=1_000_000, full=False):
        """Return a compact search record; full=True transparently runs full E1.

        Records expose routing and actual elapsed time, including fallback. An
        E1 validation exception alone may classify input as invalid. Native
        load failure/limits, unexpected errors, timeouts and crashes differ.
        """
        with self._lock:
            start, cpu = time.perf_counter(), time.process_time()
            config = dict(bandwidth=bandwidth, capacity=capacity,
                          cross_core_wait=cross_core_wait, same_core_wait=same_core_wait,
                          max_iter=max_iter)
            reason = None
            if not full:
                try:
                    record = self._native_score(plan, config)
                except Exception as error:
                    # Replay adapter is not an authority on official invalidity.
                    reason = dict(error_type=type(error).__name__, message=str(error))
            if full or reason is not None:
                self._counts["full_calls" if full else "fallback_calls"] += 1
                record = self._e1.evaluate_record(plan, full=full, **config)
                # Outer timing/cache always describes ALL work in this request.
                record.update(route="e1_full" if full else "e1_fallback",
                              execution="e1_replayed" if record["status"] == "ok" else "failed",
                              numeric_kind="computed" if record["status"] == "ok" else None)
                if reason is not None:
                    record["fallback_reason"] = reason
            record.update(engine=ENGINE_VERSION, official_code_hash=OFFICIAL_CODE_HASH,
                          wall_seconds=time.perf_counter() - start,
                          cpu_seconds=time.process_time() - cpu, cache=self.cache_stats())
            return record

    def evaluate_batch(self, plans, *, full=False, **config):
        """One-at-a-time streaming; no batch-sized score/result storage."""
        for index, plan in enumerate(plans):
            yield dict(self.evaluate_record(plan, full=full, **config), index=index)
