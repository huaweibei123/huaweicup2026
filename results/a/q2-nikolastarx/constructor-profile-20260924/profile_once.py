"""One cProfile run of the unchanged direct CLI; never execute an evaluator.

Run from the repository root, once each for 008, 014, and 025. The imported E0
entry points and subprocess creation are poisoned before the profiled CLI.
The separate importtime capture covers the actual cold CLI import graph.
"""
import cProfile
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pstats
import runpy
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'data/raw/a/official/code'))
import multicore_cut_evaluate_problem_2 as scene_b

blocked_calls = []


def prohibited(*args, **kwargs):
    blocked_calls.append('evaluation_or_subprocess')
    raise AssertionError('Profile scope forbids evaluation and subprocesses')


scene_b.evaluate_scene_b = prohibited
scene_b._build_scene_b_tasks = prohibited
subprocess.Popen = prohibited

case = sys.argv[1]
summarize_only = '--summarize-only' in sys.argv[2:]
assert case in {'008', '014', '025'}
folder = Path(__file__).resolve().parent / (case + '-k4')
if summarize_only:
    assert (folder / 'profile.pstats').is_file()
else:
    folder.mkdir(exist_ok=False)
source_files = ['src/q2_nikolastarx/direct_solve.py',
                'src/q2_nikolastarx/dag_direct.py', 'src/q2_nikolastarx/direct.py']
input_path = 'data/raw/a/official/data/case_' + case + '.json'
argv = ['src.q2_nikolastarx.direct_solve', input_path,
        '--config', 'data/raw/a/official/data/config.txt', '--cores', '4',
        '--output', str(folder / 'plan.json'),
        '--evidence', str(folder / 'online'), '--wall', '30']
sys.argv = argv
started_at = datetime.now(timezone.utc).isoformat()
if summarize_only:
    profiler = str(folder / 'profile.pstats')
    elapsed = None
else:
    profiler = cProfile.Profile()
    start = time.perf_counter()
    profiler.runcall(runpy.run_module, 'src.q2_nikolastarx.direct_solve', run_name='__main__')
    elapsed = time.perf_counter() - start
    profiler.dump_stats(str(folder / 'profile.pstats'))
with (folder / 'profile-cumulative.txt').open('w') as stream:
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(100)
with (folder / 'profile-self.txt').open('w') as stream:
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats('tottime').print_stats(100)
stats = pstats.Stats(profiler)


def filename(path):
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return path.replace(str(Path(sys.base_prefix)), '<python>')


records = [dict(file=filename(f), line=line, function=name,
                primitive_calls=values[0], calls=values[1],
                self_seconds=values[2], cumulative_seconds=values[3])
           for (f, line, name), values in stats.stats.items()]
records.sort(key=lambda r: (-r['cumulative_seconds'], r['file'], r['line']))
plan = (folder / 'plan.json').read_bytes()
prior = ROOT / 'results/a/q2-nikolastarx/direct-pilot-20260924/run' / (case + '-k4')
ledger = json.loads((folder / 'online/solver.json').read_text())
prior_run = json.loads((prior / 'run.json').read_text())
graph = json.loads((ROOT / input_path).read_text())
assert not blocked_calls
assert ledger['calls'] == {'E0': 0, 'E1': 0, 'E2': 0}
assert plan == (prior / 'plan.json').read_bytes()
summary = dict(case=case, cores=4, started_at=started_at,
               strategy=ledger['attempts'][0]['detail']['selected_strategy'],
               argv=[s.replace(str(ROOT) + '/', '') for s in argv],
               profile_elapsed_seconds=elapsed,
               profile_total_accounted_seconds=stats.total_tt,
               frozen_source_commit='dd9d89918f7a4e3d2cfab48d4d0246db3408310b',
               source_sha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_files},
               input_path=input_path, input_bytes=(ROOT/input_path).stat().st_size,
               input_sha256=hashlib.sha256((ROOT/input_path).read_bytes()).hexdigest(),
               config_sha256=hashlib.sha256((ROOT/'data/raw/a/official/data/config.txt').read_bytes()).hexdigest(),
               graph_counts={k: len(graph[k]) for k in ('ops', 'tensors', 'edges')},
               eligible_ops=ledger['attempts'][0]['detail']['eligible_ops'],
               plan_sha256=hashlib.sha256(plan).hexdigest(),
               identical_to_existing_pilot_plan=True, blocked_calls=blocked_calls,
               prior_unprofiled_solver_outer_seconds=prior_run['solver']['wall_seconds'],
               prior_unprofiled_solver_internal_seconds=prior_run['online']['internal_wall_seconds'],
               python=sys.version,
               platform={'system': os.uname().sysname, 'release': os.uname().release,
                         'version': os.uname().version, 'machine': os.uname().machine},
               machine=os.uname().machine,
               postprocess_recovery=summarize_only,
               timing_limitations=['one sample per graph; shared host, not an exclusive benchmark',
                                   'cProfile overhead changes timings; use hotspot attribution only',
                                   'E0 module pre-imported to poison entry points; importtime is separate'],
               calls=ledger['calls'], functions=records)
(folder / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({k: summary[k] for k in ('case', 'profile_elapsed_seconds',
                  'identical_to_existing_pilot_plan', 'calls')}))
