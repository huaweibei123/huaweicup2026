"""Opt-in P1 score adapter; official full results always use existing E1.

Not exported from eval_exact.__init__: existing callers and CLI are unchanged.
The native API is experimental and is not a complete official result schema.
"""
from __future__ import annotations

from dataclasses import dataclass

from .batch import P1Evaluator
from .native_backend import BackendUnavailable, load_backend


@dataclass(frozen=True)
class ScoreResult:
    makespan: int
    backend: str
    fallback_reason: str | None = None


class NativeP1Evaluator(P1Evaluator):
    """Existing E1 with a separate, explicitly enabled experimental score API.

    native_manifest=None disables native discovery/import/loading. An explicit
    manifest opts into loading that reviewed artifact on the first score call.
    evaluate/evaluate_record/evaluate_batch/CLI remain on complete E1. No public
    prepared handle, persistent native cache, worker integration or native full
    JSON is claimed. Calls on one instance use its existing serial lock.
    """

    def __init__(self, graph, *, native_manifest=None, **cache_options):
        super().__init__(graph, **cache_options)
        self._native_manifest = native_manifest
        self._native_backend = None

    def _e1_score(self, plan, config, reason):
        result = self.evaluate(plan, **config)
        return ScoreResult(result["makespan"], "e1", reason)

    def score(self, plan, bandwidth, capacity, cross_core_wait, same_core_wait,
              max_iter=1_000_000):
        """Return a small score or raise; never turn internal errors into success.

        Missing backend/capability limits fall back once to full E1. Input and
        unexpected errors propagate. A fallback may repeat local preparation;
        reserve one complete E1 evaluation and its CPU/wall cost per call.
        There is no pre-fallback budget callback or hard process/time limit.
        """
        config = dict(bandwidth=bandwidth, capacity=capacity,
                      cross_core_wait=cross_core_wait, same_core_wait=same_core_wait,
                      max_iter=max_iter)
        with self._lock:
            if self._native_manifest is None:
                return self._e1_score(plan, config, "native-disabled")
            self._pending = None
            try:
                # Same order as _scene_a: capacity conversion, parameters, then
                # official graph/plan checks and local compilation. All errors
                # here propagate unchanged, before any native loading.
                capacity = dict(capacity)
                config["capacity"] = capacity
                self._runtime.validate_parameters(
                    bandwidth, capacity, max_iter,
                    cross_core_wait=cross_core_wait, same_core_wait=same_core_wait)
                tasks, _, _, view = self._build_tasks(self._graph, plan, bandwidth, capacity)
                orders = [view["core_orders"].get(core, []) for core in range(view["num_cores"])]
                try:
                    if self._runtime.PIPE_SLOTS != 1:
                        raise BackendUnavailable("pipe-slots-unsupported")
                    # The official typed API permits some int subclasses; the
                    # prototype's order validator accepts built-in ints only.
                    # Preserve official behavior by using E1 for that domain.
                    if (any(type(task_id) is not int for task_id in tasks)
                            or any(type(task_id) is not int for order in orders for task_id in order)):
                        raise BackendUnavailable("task-id-type-unsupported")
                    if self._native_backend is None:
                        self._native_backend = load_backend(self._native_manifest)
                except BackendUnavailable as error:
                    return self._e1_score(plan, config, error.reason)
                backend = self._native_backend
                try:
                    compiled = backend.bridge.pack_tasks(tasks, self._runtime, bandwidth)
                    result = backend.bridge.score(
                        compiled, orders, library=backend.library,
                        cross_wait=cross_core_wait, same_wait=same_core_wait,
                        max_iter=max_iter, audit=False, project_once=False)
                except backend.bridge.Unsupported as error:
                    return self._e1_score(plan, config, f"native-unsupported: {error}")
                # CandidateError/NativeExecutionError and unexpected errors are
                # deliberately not caught. This is not an official invalid API.
                return ScoreResult(result["makespan"], "native")
            finally:
                # Native-only preparation does not commit E1's pending cache.
                # Existing full-E1 fallback commits through evaluate as before.
                self._pending = None
