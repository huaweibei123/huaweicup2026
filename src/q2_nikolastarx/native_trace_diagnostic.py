"""One owned-worker E2 native replay with a retrospective prepared trace audit.

Private E2 API: version-pin the E2 bundle before use. The caller owns this worker
and must not score concurrently while its runtime build function is wrapped.
"""
from __future__ import annotations

import hashlib
import json
from operator import index

from .direct import derive_multicore_plan
from .prepared_trace_contract import audit, capture


REQUIRED_CONFIG = {'bandwidth', 'capacity', 'max_iter', 'cross_core_copy_delay'}


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def _native_int(value, label):
    if isinstance(value, bool):
        raise ValueError(label + ' is boolean')
    result = index(value)  # accepts np.int64; rejects lossy float conversion
    if result < 0:
        raise ValueError(label + ' is negative')
    return result


def _trace_result(contract, record, config):
    debug = record['debug']
    keys = list(debug['op_keys'])
    starts, ends = debug['op_start'], debug['op_end']
    if len(keys) != len(starts) or len(keys) != len(ends):
        raise ValueError('native debug vector lengths differ')
    expected = {(o['core'], o['id']): o for o in contract['operations']}
    if len(expected) != len(contract['operations']) or len(keys) != len(expected):
        raise ValueError('native operation coverage differs from prepared graph')
    timelines = {row['core']: {'core_id': row['core'], 'ops': []}
                 for row in contract['prepared_by_core']}
    seen = set()
    for pos, key in enumerate(keys):
        if not isinstance(key, (tuple, list)) or len(key) != 2:
            raise ValueError('native op_keys lost (core,op_id) identity')
        pair = tuple(_native_int(v, 'native op key') for v in key)
        if pair in seen or pair not in expected:
            raise ValueError('native duplicate or unknown op key')
        seen.add(pair)
        start, end = (_native_int(value, label) for value, label in
                      ((starts[pos], 'native start'), (ends[pos], 'native end')))
        if end <= start:
            raise ValueError('native operation has nonpositive duration')
        op = expected[pair]
        timelines[pair[0]]['ops'].append({
            'task_id': pair[0], 'op_id': pair[1], 'op': op['kind'],
            'pipe': op['pipe'], 'start': start, 'end': end,
            'duration': end - start,
        })
    if seen != set(expected):
        raise ValueError('native trace omits prepared operation')
    makespan = _native_int(record['makespan'], 'native makespan')
    if _native_int(debug['makespan'], 'debug makespan') != makespan:
        raise ValueError('native/debug makespan differs')
    if _native_int(debug['stats'][0], 'native stats makespan') != makespan:
        raise ValueError('native stats makespan differs')
    links = [dict(source_core=l['source'][0], source_copy_out_id=l['source'][1],
                  target_core=l['target'][0], target_copy_in_id=l['target'][1],
                  tensor_id=l['tensor_id'], size=l['size'])
             for l in contract['cross_links']]
    return {
        'scene': 'B', 'num_cores': len(timelines), 'makespan': makespan,
        'bandwidth_bytes_per_cycle': config['bandwidth'],
        'cross_core_copy_delay_cycles': config['cross_core_copy_delay'],
        'task_dependencies': links,
        'step3_by_core': {row['core']: {
            'memory_dependency_count': row['memory_dependency_count'],
            'pipe_op_counts': row['pipe_op_counts'],
        } for row in contract['prepared_by_core']},
        'per_core_timeline': [timelines[core] for core in sorted(timelines)],
    }


def _original_compute_identity(graph, plan, contract):
    """Require every eligible original op at exactly its validated owner."""
    view = derive_multicore_plan(graph, plan)  # structural only; no Task/Step3
    original = [op for op in graph['ops'] if op['op'] not in ('COPY_IN', 'COPY_OUT')]
    by_id = {op['id']: op for op in original}
    if len(by_id) != len(original) or set(by_id) != set(view['mapping']):
        raise ValueError('eligible original operation identity differs from plan')
    seen = {}
    for op in contract['operations']:
        oid = op['id']
        if oid not in by_id:
            continue
        if oid in seen:
            raise ValueError('original operation ID repeats in prepared tasks')
        expected_core = view['core_by_subgraph'][view['mapping'][oid]]
        source = by_id[oid]
        if (op['core'] != expected_core or op['kind'] != source['op']
                or op['pipe'] != source['pipe'] or not op['is_compute']):
            raise ValueError('original operation owner/kind/Pipe differs from plan')
        seen[oid] = (op['core'], oid)
    if set(seen) != set(by_id):
        raise ValueError('prepared tasks omit an eligible original operation')
    return set(seen.values())


def diagnose(scene_b_module, graph, plan, config, evidence_tags, *, include_trace=False):
    """Return native score plus proven tight links, or an explicit no-diagnostic result.

    `scene_b_module` is the caller's already-imported, pinned E2 scene_b module.
    This does not call E0 or a second preparer and never falls back.
    """
    counts = {'native_attempted': 0, 'native_returned': 0, 'prepare_observed': 0}
    result = {'diagnostic_status': 'unavailable', 'critical_links': [],
              'critical_original_ids': {'op_ids': [], 'tensor_ids': []},
              'score': None, 'counts': counts, 'evidence_tags': evidence_tags}
    try:
        if not isinstance(evidence_tags, dict) or not evidence_tags or any(
            not isinstance(k, str) or not k or not isinstance(v, str) or not v
            for k, v in evidence_tags.items()
        ):
            raise ValueError('explicit nonempty string evidence tags required')
        if type(config) is not dict or set(config) != REQUIRED_CONFIG:
            raise ValueError('P2 config must have exactly the native required keys')
        result['input_identity'] = {'graph_canonical_sha256': _fingerprint(graph),
                                    'plan_canonical_sha256': _fingerprint(plan),
                                    'config_canonical_sha256': _fingerprint(config)}
        evaluator = scene_b_module.SceneBEvaluator(graph, problem=2)
        runtime = evaluator._fast_runtime
        original = runtime._build_scene_b_tasks
        observed = []

        def intercept(*args, **kwargs):
            built = original(*args, **kwargs)
            observed.append(built)
            counts['prepare_observed'] += 1
            return built

        runtime._build_scene_b_tasks = intercept
        try:
            counts['native_attempted'] = 1
            record = evaluator._native_score(plan, config, debug=True)
            counts['native_returned'] = 1
        finally:
            runtime._build_scene_b_tasks = original
        if (record.get('status') != 'ok' or record.get('route') != 'native'
                or record.get('compilation_cache_hit') is not False
                or len(observed) != 1):
            raise ValueError('native score or one-preparation identity failed')
        tasks, cross, traffic, movement, _ = observed[0]
        if (record.get('cross_task_traffic') != traffic
                or record.get('data_movement_bytes') != movement):
            raise ValueError('native score differs from captured prepared movement')
        result['score'] = {k: record[k] for k in ('status', 'route', 'makespan',
                           'data_movement_bytes', 'cross_task_traffic',
                           'replay_iterations', 'preparation_seconds', 'replay_seconds')}
        contract = capture(tasks, cross)
        original_compute_keys = _original_compute_identity(graph, plan, contract)
        trace = _trace_result(contract, record, config)
        checked = audit(contract, trace)
        if not checked['consistent']:
            raise ValueError('prepared/native trace mismatch: ' + str(checked['errors'] or checked['residuals'][:2]))
        original_tensors = {tensor['id'] for tensor in graph['tensors']}
        if include_trace:
            result['trace_result'] = trace
        result.update(diagnostic_status='consistent',
                      critical_links=checked['critical_cross_links'],
                      critical_original_ids={
                          'op_ids': sorted(u for c, u in checked['critical_operations']
                                           if (c, u) in original_compute_keys),
                          'tensor_ids': sorted({l['tensor_id'] for l in checked['critical_cross_links']
                                                if l['tensor_id'] in original_tensors}),
                      })
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)}
    return result
