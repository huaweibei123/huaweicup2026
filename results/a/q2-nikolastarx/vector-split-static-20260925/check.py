"""One original-case static construction; 15-second alarm, zero E0/E1/E2."""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx import vector_split
from evaluation_validation import read_evaluation_config, read_required_settings


def main():
    home = Path(__file__).resolve().parent
    output = home/'report.json'
    if output.exists():
        raise FileExistsError('never overwrite or retry this static run')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    files = ['src/q2_nikolastarx/'+name+'.py' for name in
             ('vector_split', 'vector_arrival', 'vector_lanes', 'direct', 'baseline')]
    for name in files:
        assert (ROOT/name).read_bytes() == subprocess.check_output(['git', 'show', source+':'+name], cwd=ROOT)
    graph_path = ROOT/'data/raw/a/official/data/case_016.json'
    config_path = ROOT/'data/raw/a/official/data/config.txt'

    def limit(signum, frame):
        raise TimeoutError('static construction exceeded 15 seconds')

    report = {'source_commit': source, 'started_at': datetime.now(timezone.utc).isoformat(),
              'case': '016', 'cores': 5, 'alarm_seconds': 15, 'calls': {'E0': 0, 'E1': 0, 'E2': 0},
              'input_sha256': hashlib.sha256(graph_path.read_bytes()).hexdigest(),
              'config_sha256': hashlib.sha256(config_path.read_bytes()).hexdigest(),
              'source_sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files}}
    signal.signal(signal.SIGALRM, limit)
    signal.alarm(15)
    started = time.perf_counter()
    try:
        config = read_evaluation_config(str(config_path))
        config.update(read_required_settings(str(config_path), 'multicore_scene_b', ('cross_core_copy_delay_cycles',)))
        with ExitStack() as stack:
            for name in ('subprocess.Popen', 'multicore_cut_evaluate_problem_2.evaluate_scene_b',
                         'multicore_cut_evaluate_problem_2._build_scene_b_tasks'):
                stack.enter_context(patch(name, side_effect=AssertionError('No evaluator/subprocess')))
            plan, detail = vector_split.build(json.loads(graph_path.read_text()), 5, config)
        data = (json.dumps(plan, ensure_ascii=False, indent=2)+'\n').encode()
        report.update(status='ok', detail=detail, plan_sha256=hashlib.sha256(data).hexdigest(), plan_bytes=len(data))
    except Exception as error:
        report.update(status='failed', error=repr(error))
    finally:
        report['static_wall_seconds'] = time.perf_counter()-started
        signal.alarm(0)
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key: report.get(key) for key in ('status', 'error', 'static_wall_seconds', 'plan_sha256')}))
    if report['status'] != 'ok':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
