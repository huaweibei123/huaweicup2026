"""One fixed case084/k5 split-core mechanism experiment: one construction and one E0.

No candidate search, baseline rerun, E1, E2, or retry. Execution requires the
root's explicit --execute flag after resource coordination. Output is immutable.
"""
from __future__ import annotations
import argparse
import json
import platform
from pathlib import Path
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q1_benchmarks.pro_case008_e0 import process
from src.q1_benchmarks import pro_micro_e0 as h


def run(run_id):
    if Path(run_id).name != run_id:
        raise ValueError('Invalid run id')
    head = h.git('rev-parse', 'HEAD').decode().strip()
    if sys.version_info[:2] != (3, 12) or h.git('diff', '--name-only', head).strip():
        raise RuntimeError('Locked Python and clean frozen source required')
    for path in ('src/q1/capacity_split_cores.py', 'src/q1_benchmarks/split_core_probe.py'):
        if (ROOT/path).read_bytes() != h.git('show', f'{head}:{path}'):
            raise RuntimeError('Uncommitted implementation')
    manifest = h.read(ROOT/'docs/a/source-manifest.json')
    for record in manifest['files']:
        path = record['path']
        if path.startswith('code/') or path == 'data/config.txt':
            if h.digest((ROOT/'data/raw/a/official'/path).read_bytes()) != record['sha256']:
                raise RuntimeError('Official source/config identity mismatch')
    archive = ROOT/manifest['case_archive']['path']
    if h.digest(archive.read_bytes()) != manifest['case_archive']['sha256']:
        raise RuntimeError('Input archive mismatch')
    out = ROOT/'output/p1-split-core'/run_id
    out.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        entries = [n for n in z.namelist() if Path(n).name == 'case_084.json' and '__MACOSX' not in n]
        if len(entries) != 1:
            raise RuntimeError('Ambiguous input')
        raw = z.read(entries[0])
    graph = out/'graph.json'; graph.write_bytes(raw)
    record = dict(run_id=run_id, case_id='084', cores=5, source_commit=head,
                  started_at=h.utc(), status='running', calls=dict(solver=0,E0=0,E1=0,E2=0,retry=0),
                  graph_sha256=h.digest(raw), official_code_hash=manifest['official_code_hash'],
                  config_sha256=h.digest((ROOT/'data/raw/a/official/data/config.txt').read_bytes()),
                  environment=dict(platform=platform.platform(),python=sys.version,workers=1),
                  budget=dict(solver_seconds=15,E0_seconds=60,batch_seconds=90),
                  scope='One offline structural probe; not a unified full-batch algorithm result')
    began=time.perf_counter(); deadline=began+90
    rel=lambda p:p.relative_to(ROOT).as_posix()
    def launched(kind):
        record['calls'][kind]+=1; h.write(out/'run.json', record)
    h.write(out/'run.json', record)
    try:
        argv=[sys.executable,'-B','src/q1/capacity_split_cores.py',rel(graph),'--cores','5',
              '--output',rel(out/'plan.json'),'--diagnostics',rel(out/'diagnostics.json')]
        record['solver']=process(argv,out,'solver',15,deadline,lambda:launched('solver'))
        if record['solver']['status']!='ok':
            raise RuntimeError('Constructor failed')
        argv=[sys.executable,'-B','data/raw/a/official/code/multicore_cut_evaluate_problem_1.py',
              rel(graph),rel(out/'plan.json'),'--config','data/raw/a/official/data/config.txt',
              '--output',rel(out/'result.json'),'--trace-output',rel(out/'trace.json'),
              '--log-output',rel(out/'official.log')]
        record['evaluation']=process(argv,out,'e0',60,deadline,lambda:launched('E0'))
        if record['evaluation']['status']!='ok':
            raise RuntimeError('E0 failed')
        result=h.read(out/'result.json')
        assert result['scene']=='A' and result['num_cores']==5
        record.update(status='ok',makespan=result['makespan'],movement=result['data_movement_bytes'],
                      memory_dependencies=sum(x['memory_dependency_count'] for x in result['step3_by_task'].values()),
                      M_V_overlap_sum=h.overlap(result),diagnostics=h.read(out/'diagnostics.json'))
    except BaseException as error:
        record.update(status='failed',error=f'{type(error).__name__}: {error}')
    finally:
        receipts=[h.read(p) for p in out.glob('*-process.json')]
        record.update(finished_at=h.utc(),wall_seconds=time.perf_counter()-began,
                      cleanup_confirmed=all(x['cleanup_confirmed'] and h.group_gone(x['pid']) for x in receipts))
        record['artifacts']={p.name:h.artifact(p) for p in out.iterdir() if p.is_file() and p.name!='run.json'}
        h.write(out/'run.json',record)
    print(json.dumps({k:record[k] for k in ('status','calls','cleanup_confirmed','wall_seconds')},ensure_ascii=False))
    return 0 if record['status']=='ok' and record['cleanup_confirmed'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run_id');p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:p.error('--execute is required; no automatic scoring')
    raise SystemExit(run(a.run_id))
