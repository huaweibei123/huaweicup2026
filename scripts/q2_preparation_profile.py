"""One preparation-only profile of fixed E2 P2 code; no native/E0 scoring.

This intentionally does not call evaluate_record (which may fall back to E0).
Run in a fresh capsule through a separate wall/RSS supervisor.
"""
import cProfile
import hashlib
import json
import os
from pathlib import Path
import platform
import pstats
import resource
import signal
import sys
import time


def main():
    root = Path(os.environ['P2_PROFILE_ROOT']).resolve()
    out = Path(os.environ['P2_PROFILE_OUTPUT']).resolve()
    out.mkdir(exist_ok=False)
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 << 20, 64 << 20))
    manifest = json.loads((root / 'manifest.json').read_bytes())
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    for rel, expected in manifest['files'].items():
        if sha(root / rel) != expected:
            raise ValueError('capsule drift: ' + rel)
    if manifest['limits'] != dict(preparations=1, E0=0, native=0, workers=1,
                                 seconds=180, rss_bytes=4 << 30, retries=0):
        raise ValueError('wrong limits')
    sys.path.insert(0, str(root / 'e2-src'))
    from research.a.e2_search._official_b import load_bundle, read_config
    from research.a.e2_search._local_b import install
    from research.a.e2_search import _native_b
    # Preparation must never silently invoke replay or fallback, even if a
    # future source change alters a helper. These are instance-local guards.
    def forbidden(*args, **kwargs):
        raise RuntimeError('scoring is forbidden in this preparation-only probe')
    _native_b.score = _native_b.get_lib = forbidden
    graph = json.loads((root / 'graph.json').read_bytes())
    plan = json.loads((root / 'plan.json').read_bytes())
    config = read_config(root / 'config.txt', problem=2)
    begin = time.perf_counter()
    runtime, support = load_bundle(2)
    runtime.evaluate_scene_b = forbidden
    optimization = install(support)
    report = dict(scope='single fixed-plan preparation diagnosis; no score',
                  status='preparing', started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  python=sys.version, platform=platform.platform(),
                  E0=0, native=0, preparations=1, source=manifest['source'],
                  plan_sha256=sha(root / 'plan.json'), graph_sha256=sha(root / 'graph.json'),
                  local_optimization=optimization, setup_seconds=time.perf_counter()-begin)
    def save():
        (out / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    save()
    profiler = cProfile.Profile()
    begin = time.perf_counter()
    def alarm(signum, frame):
        raise TimeoutError('150-second profiling limit; preserving partial profile')
    signal.signal(signal.SIGALRM, alarm)
    try:
        signal.setitimer(signal.ITIMER_REAL, 150)
        profiler.enable()
        tasks, cross, traffic, movement, view = runtime._build_scene_b_tasks(
            graph, plan, config['bandwidth'], config['capacity'])
        built = time.perf_counter()
        runtime.validate_execution(tasks, cross)
        validated = time.perf_counter()
        compiled = _native_b.pack(tasks, cross, runtime, config['bandwidth'])
        packed = time.perf_counter()
        profiler.disable()
        # Keep full prepared object for a subsequent independent equality check.
        import pickle
        raw = pickle.dumps((tasks, cross, traffic, movement, view), protocol=5)
        if len(raw) > 32 << 20:
            raise ValueError('prepared object exceeds artifact cap')
        (out / 'prepared.pickle').write_bytes(raw)
        report.update(status='completed', build_seconds=built-begin,
                      validation_seconds=validated-built, pack_seconds=packed-validated,
                      total_profiled_seconds=packed-begin,
                      task_operations=sum(len(t['seq']) for t in tasks.values()),
                      cross_traffic=traffic, movement=movement,
                      prepared_sha256=hashlib.sha256(raw).hexdigest(),
                      prepared_bytes=len(raw), packed_ops=len(compiled.op_keys))
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        profiler.disable()
        profiler.dump_stats(str(out / 'preparation.prof'))
        rows=[]
        for (filename, line, name), (primitive, calls, own, cumulative, callers) in pstats.Stats(profiler).stats.items():
            try: filename = str(Path(filename).relative_to(root))
            except ValueError: pass
            rows.append(dict(file=filename, line=line, function=name, calls=calls,
                             primitive_calls=primitive, self_seconds=own, cumulative_seconds=cumulative))
        (out / 'functions.json').write_text(json.dumps(sorted(rows,key=lambda r:-r['cumulative_seconds']),indent=2)+'\n')
        save()
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
