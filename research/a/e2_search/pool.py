"""E2 pool adapted from E1 5bfe53a pool.py; no global/default process pool.

Use a context manager and the normal __main__ guard for spawn. One candidate per
worker is in flight. A timed-out/crashed worker is terminated and restarted only
for a later candidate; its partial output and cache are discarded.
"""
from __future__ import annotations

import contextlib
import io
import math
import multiprocessing as mp
from multiprocessing.connection import wait
import os
import sys
import time

from .engine import ENGINE_VERSION, E2Evaluator
DEFAULT_CACHE_BYTES = 16 << 20
from src.eval_exact._official import OFFICIAL_CODE_HASH
from ._resources import peak_rss_bytes as _peak_rss_bytes


class _BoundedLog(io.StringIO):
    def write(self, text):
        remaining = max(0, 16384 - self.tell())
        super().write(text[:remaining])
        return len(text)


def _worker(connection, graph, cache_bytes, max_cache_entries, problem, native_enabled):
    try:
        if problem == 1:
            evaluator = E2Evaluator(graph, cache_bytes=cache_bytes, max_cache_entries=max_cache_entries,
                                    native_enabled=native_enabled)
        else:
            from .scene_b import SceneBEvaluator
            evaluator = SceneBEvaluator(graph, problem=problem, cache_bytes=cache_bytes,
                                         max_cache_entries=max_cache_entries, native_enabled=native_enabled)
        connection.send({"ready": True, "pid": os.getpid()})
        while True:
            request = connection.recv()
            if request is None:
                return
            index, plan, config, full = request
            log = _BoundedLog()
            cpu_start = time.process_time()
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                record = evaluator.evaluate_record(plan, full=full, **config)
            record.update(index=index, worker_pid=os.getpid(),
                          cpu_seconds=time.process_time() - cpu_start,
                          worker_peak_rss_bytes=_peak_rss_bytes())
            if log.getvalue():
                record["diagnostic_log"] = log.getvalue()
                record["diagnostic_log_limit_chars"] = 16384
            connection.send(record)
    except (EOFError, BrokenPipeError):
        pass
    except Exception as error:
        try:
            connection.send({"ready": False, "error_type": type(error).__name__,
                             "message": str(error)})
        except (EOFError, BrokenPipeError, OSError):
            pass
    finally:
        connection.close()


class E2BatchEvaluator:
    """Reusable graph-resident pool with ordered, streaming search records.

    Explicit worker count prevents nested automatic oversubscription. Cache cap
    is per worker. Periodic recycling bounds the number of calls per process,
    not an individual candidate's RSS; this is NOT a hard process-memory limit.
    """

    def __init__(self, graph, *, workers=1, cache_bytes=DEFAULT_CACHE_BYTES,
                 max_cache_entries=128, timeout_seconds=60.0,
                 startup_timeout_seconds=30.0, max_tasks_per_worker=256,
                 recycle_peak_rss_bytes=None, problem=1, native_enabled=True):
        if type(native_enabled) is not bool:
            raise ValueError('native_enabled must be boolean')
        if type(problem) is not int or problem not in (1, 2, 3):
            raise ValueError('problem must be 1, 2 or 3')
        self.problem = problem
        for name, value in (("workers", workers), ("max_cache_entries", max_cache_entries),
                            ("max_tasks_per_worker", max_tasks_per_worker)):
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if type(cache_bytes) is not int or cache_bytes < 0:
            raise ValueError("cache_bytes must be a non-negative integer")
        for name, value in (("timeout_seconds", timeout_seconds),
                            ("startup_timeout_seconds", startup_timeout_seconds)):
            if (value is None and name == "timeout_seconds"):
                continue
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive")
        if recycle_peak_rss_bytes is not None and (type(recycle_peak_rss_bytes) is not int or recycle_peak_rss_bytes < 1):
            raise ValueError("recycle_peak_rss_bytes must be a positive integer or None")
        self._recycle_rss = recycle_peak_rss_bytes
        from copy import deepcopy
        self._graph = deepcopy(graph)
        self._options = (cache_bytes, max_cache_entries, problem, native_enabled)
        self._workers = workers
        self._timeout = timeout_seconds
        self._startup_timeout = startup_timeout_seconds
        self._max_tasks = max_tasks_per_worker
        self._context = mp.get_context("spawn")
        self._slots = [None] * workers
        self._closed = False
        self._busy = False

    def __enter__(self):
        if self._closed:
            raise RuntimeError("pool is closed")
        return self

    def __exit__(self, *_):
        self.close()

    def _stop(self, index):
        slot = self._slots[index]
        if slot is None:
            return
        process, connection, _ = slot
        connection.close()
        if process.is_alive():
            process.terminate()
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)
        process.close()
        self._slots[index] = None

    def close(self):
        """Cancel outstanding work and release all workers (also on context exit)."""
        self._closed = True
        for index in range(self._workers):
            self._stop(index)

    def _start(self, index):
        if self._slots[index] is not None:
            if self._slots[index][2] < self._max_tasks:
                return
            self._stop(index)
        parent, child = self._context.Pipe()
        process = self._context.Process(target=_worker,
            args=(child, self._graph, *self._options), daemon=True)
        try:
            process.start()
        except BaseException:
            parent.close()
            child.close()
            raise
        child.close()
        self._slots[index] = [process, parent, 0]
        try:
            if not parent.poll(self._startup_timeout):
                raise TimeoutError("evaluator worker startup timeout")
            message = parent.recv()
            if message.get("ready") is not True:
                raise RuntimeError(f"evaluator worker startup failed: {message}")
        except BaseException:
            self._stop(index)
            raise

    def _failure(self, index, status, error_type, message, seconds, pid):
        return dict(index=index, status=status, error_type=error_type, message=message,
                    wall_seconds=seconds, worker_pid=pid, cache=None,
                    problem=self.problem, engine=f'p{self.problem}-e2-native-search-v1-rank-index', official_code_hash=OFFICIAL_CODE_HASH)

    def evaluate_batch(self, plans, *, full=False, **config):
        """Yield at most one worker-sized chunk in order; never retain all results.

        Timeouts cover dispatch through response; startup is separately bounded.
        Early exit: close the iterator or the pool/context to cancel active work.
        Chunking gives bounded input consumption and output buffering even when
        one candidate stalls. It can sacrifice throughput on skewed workloads.
        """
        if self._closed or self._busy:
            raise RuntimeError("pool is closed or already evaluating a batch")
        self._busy = True
        iterator = enumerate(plans)
        try:
            while not self._closed:
                chunk = []
                for _ in range(self._workers):
                    try:
                        chunk.append(next(iterator))
                    except StopIteration:
                        break
                if not chunk:
                    return
                active, completed = {}, {}
                # Start all slots before any candidate deadline begins.
                for slot_index in range(len(chunk)):
                    self._start(slot_index)
                for slot_index, (index, plan) in enumerate(chunk):
                    process, connection, _ = self._slots[slot_index]
                    start = time.perf_counter()
                    try:
                        connection.send((index, plan, config, full))
                        active[slot_index] = (index, start, process.pid)
                    except (OSError, EOFError) as error:
                        completed[index] = self._failure(index, "error", "WorkerError",
                            str(error), time.perf_counter() - start, process.pid)
                        self._stop(slot_index)
                while active and not self._closed:
                    connections = [self._slots[i][1] for i in active]
                    ready = wait(connections, timeout=0.02)
                    for slot_index, (index, start, pid) in list(active.items()):
                        process, connection, _ = self._slots[slot_index]
                        elapsed = time.perf_counter() - start
                        if self._timeout is not None and elapsed >= self._timeout:
                            completed[index] = self._failure(index, "timeout", "TimeoutError",
                                "candidate exceeded wall-clock budget", elapsed, pid)
                            self._stop(slot_index)
                            del active[slot_index]
                        elif connection in ready:
                            try:
                                record = connection.recv()
                                if record.get("index") != index or "status" not in record:
                                    raise RuntimeError(f"unexpected worker response: {record}")
                                record["dispatch_wall_seconds"] = elapsed
                                completed[index] = record
                                self._slots[slot_index][2] += 1
                                peak = record.get("worker_peak_rss_bytes")
                                if self._recycle_rss is not None and (peak is None or peak >= self._recycle_rss):
                                    self._slots[slot_index][2] = self._max_tasks
                                    record["recycle_after_response"] = True
                                    record['recycle_reason'] = 'rss_telemetry_unavailable' if peak is None else 'peak_rss_threshold'
                            except (OSError, EOFError, RuntimeError) as error:
                                completed[index] = self._failure(index, "error", "WorkerError",
                                    str(error), elapsed, pid)
                                self._stop(slot_index)
                            del active[slot_index]
                        elif not process.is_alive():
                            completed[index] = self._failure(index, "error", "WorkerError",
                                f"worker exited with code {process.exitcode}", elapsed, pid)
                            self._stop(slot_index)
                            del active[slot_index]
                for index, _ in chunk:
                    if self._closed:
                        return
                    yield completed[index]
        finally:
            self._busy = False
            # A cancelled iterator never leaves a worker evaluating in background.
            for i, slot in enumerate(self._slots):
                if slot is not None and "active" in locals() and i in active:
                    self._stop(i)
