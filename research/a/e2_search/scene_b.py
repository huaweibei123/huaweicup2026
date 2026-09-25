"""P2 search adapter: official compilation/validation, native event replay.

The full ordered plan is compilation identity in Scene B. A changed core order
or assignment rebuilds Step1--3; P1 partition-only reuse would be incorrect.
"""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
import pickle
import threading
import time

from src.eval_exact._official import OFFICIAL_CODE_HASH
from .engine import E2Evaluator, _owned_bytes
from ._native import Unsupported
from . import _native_b
from ._official_b import load_bundle


@dataclass
class _Entry:
    compiled: _native_b.CompiledB
    movement: dict
    cross: int


class SceneBEvaluator(E2Evaluator):
    """Graph snapshot, bounded instance LRU, no stored candidate scores.

    Full results and unsupported inputs use this problem's frozen E0. In-process
    calls have no wall timeout; use E2BatchEvaluator for cancellable workers.
    """
    def __init__(self, graph, *, problem=2, cache_bytes=16 << 20,
                 max_cache_entries=32, native_enabled=True, max_native_ops=2_000_000):
        if type(problem) is not int or problem not in (2,3):
            raise ValueError('problem must be 2 or 3')
        for name, value, minimum in (('cache_bytes', cache_bytes, 0), ('max_cache_entries', max_cache_entries, 1),
                                     ('max_native_ops', max_native_ops, 1)):
            if type(value) is not int or value < minimum:
                raise ValueError(f'{name} must be an integer >= {minimum}')
        if type(native_enabled) is not bool:
            raise ValueError('native_enabled must be boolean')
        self.problem = problem
        self.version = f'p{problem}-e2-native-search-v1-rank-index'
        self._runtime, self._support = load_bundle(problem)
        self._fast_runtime, self._fast_support = load_bundle(problem)
        from ._local_b import install
        from ._rank_b import install as install_rank
        self._local_error = None
        try:
            self.local_optimization = install(self._fast_support)
            self.rank_optimization = install_rank(self._fast_runtime)
        except Exception as error:
            self._local_error = str(error)
            self.local_optimization = None
            self.rank_optimization = None
        self._graph = deepcopy(graph)
        self._lock, self._entries = threading.RLock(), OrderedDict()
        self._limit, self._max_entries = cache_bytes, max_cache_entries
        self._native_enabled, self._max_ops, self._bytes = native_enabled, max_native_ops, 0
        self._counts = dict(hits=0, misses=0, evictions=0, bypasses=0,
                            native_calls=0, fallback_calls=0, full_calls=0)

    def _native_score(self, plan, config, *, debug=False):
        if not self._native_enabled:
            raise Unsupported('native_disabled')
        if self._local_error is not None:
            raise Unsupported('local optimization unavailable: '+self._local_error)
        _native_b.get_lib()  # Missing DLL should not incur duplicate local compilation.
        r = self._fast_runtime
        if self.problem == 3:
            r.require_integer(config['cache_capacity_bytes'],'cache_capacity_bytes')
            r.require_number(config['cache_bandwidth_bytes_per_cycle'],'cache_bandwidth_bytes_per_cycle',positive=True)
        capacity = dict(config['capacity'])
        r.validate_parameters(config['bandwidth'], capacity, config['max_iter'],
                              cross_core_copy_delay=config['cross_core_copy_delay'])
        if (type(plan) is not dict or set(plan) != {'node_to_subgraph', 'core_schedules'}
                or type(plan['node_to_subgraph']) is not dict or type(plan['core_schedules']) is not list
                or any(type(row) is not list for row in plan['core_schedules'])
                or any(type(k) not in (str, int) or type(v) is not int for k, v in plan['node_to_subgraph'].items())
                or any(type(t) is not int for row in plan['core_schedules'] for t in row)):
            raise Unsupported('plan container/numeric domain')
        key = pickle.dumps((plan, config['bandwidth'], capacity, config.get('cache_bandwidth_bytes_per_cycle')), protocol=5)
        start = time.perf_counter()
        cached = None if debug else self._entries.get(key)
        if cached is None:
            self._counts['misses'] += 1
            tasks, cross, traffic, movement, _ = r._build_scene_b_tasks(self._graph, plan, config['bandwidth'], capacity)
            r.validate_execution(tasks, cross)
            if sum(len(t['seq']) for t in tasks.values()) > self._max_ops:
                raise Unsupported('max_native_ops')
            compiled = _native_b.pack(tasks, cross, r, config['bandwidth'], cache_bandwidth=config.get('cache_bandwidth_bytes_per_cycle'))
            entry = _Entry(compiled, movement, traffic)
            del tasks
        else:
            self._counts['hits'] += 1
            self._entries.move_to_end(key)
            entry = cached[0]
        prepared = time.perf_counter() - start
        replay_start = time.perf_counter()
        result = _native_b.score(entry.compiled, cross_core_copy_delay=config['cross_core_copy_delay'],
                                 max_iter=config['max_iter'], cache_capacity=config.get('cache_capacity_bytes',0), debug=debug)
        replay = time.perf_counter() - replay_start
        if cached is None and not debug:
            entry.compiled.op_keys = range(len(entry.compiled.op_keys))
            size = _owned_bytes((key, entry))
            if size <= self._limit:
                while self._entries and (self._bytes+size > self._limit or len(self._entries) >= self._max_entries):
                    _, (_, old_size) = self._entries.popitem(last=False)
                    self._bytes -= old_size
                    self._counts['evictions'] += 1
                self._entries[key] = (entry, size)
                self._bytes += size
            else:
                self._counts['bypasses'] += 1
        self._counts['native_calls'] += 1
        record = dict(status='ok', makespan=result['makespan'], data_movement_bytes=deepcopy(entry.movement),
                      cross_task_traffic=entry.cross, route='native', execution='native_replayed', numeric_kind='computed',
                      replay_iterations=int(result['stats'][1]), preparation_seconds=prepared,
                      replay_seconds=replay, compilation_cache_hit=cached is not None)
        if self.problem == 3:
            record['cache_stats'] = result['cache_stats']
        if debug:
            record['debug'] = dict(op_keys=entry.compiled.op_keys, **result)
        return record

    def evaluate_record(self, plan, *, full=False, **config):
        with self._lock:
            start, cpu = time.perf_counter(), time.process_time()
            config = dict(config)
            config.setdefault('max_iter', 1_000_000)
            reason = None
            if not full:
                try:
                    # Unexpected config keys must not silently pass the native path.
                    required = {'bandwidth', 'capacity', 'max_iter', 'cross_core_copy_delay'}
                    if self.problem == 3:
                        required.update(('cache_capacity_bytes','cache_bandwidth_bytes_per_cycle'))
                    if set(config) != required:
                        raise Unsupported('config keys')
                    record = self._native_score(plan, config)
                except Exception as error:
                    reason = dict(error_type=type(error).__name__, message=str(error))
            if full or reason is not None:
                self._counts['full_calls' if full else 'fallback_calls'] += 1
                try:
                    fn = self._runtime.evaluate_scene_b if self.problem == 2 else self._runtime.evaluate_problem_3
                    value = fn(self._graph, plan, **config)
                    fields = ('makespan','data_movement_bytes','cross_task_traffic') + (('cache_stats',) if self.problem == 3 else ())
                    record = {k: value[k] for k in fields}
                    record.update(status='ok', execution='e0_replayed', numeric_kind='computed')
                    if full:
                        record['result'] = value
                except Exception as error:
                    invalid = isinstance(error, (self._support['evaluation_validation'].EvaluationValidationError,
                                                 self._support['stub_multicore_cut_and_schedule'].MulticoreCutError))
                    # Official priority-order rejection is explicit input validation.
                    invalid |= isinstance(error, self._runtime.SceneBEvaluationError) and str(error) == 'subgraph priority order violates an intra-core dependency'
                    record = dict(status='invalid' if invalid else 'error', error_type=type(error).__name__,
                                  message=str(error), execution='failed', numeric_kind=None)
                record['route'] = 'e0_full' if full else 'e0_fallback'
                if reason is not None:
                    record['fallback_reason'] = reason
            record.update(engine=self.version, problem=self.problem, official_code_hash=OFFICIAL_CODE_HASH,
                          wall_seconds=time.perf_counter()-start, cpu_seconds=time.process_time()-cpu,
                          cache=self.cache_stats())
            return record
