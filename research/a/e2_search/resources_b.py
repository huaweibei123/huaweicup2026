"""Clean-process, fixed-worker P2/P3 resource comparison against matching E0.

Measures case005's same 16 distinct plans, workers=1/2, E0/native separately.
Exactly 32 additional formal E0 calls per problem on successful completion.
"""
import argparse
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from src.eval_exact._official import REPO_ROOT as ROOT
from src.eval_exact.batch_benchmark import equal
from . import E2BatchEvaluator,read_config


def save(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def child(args):
    start,cpu=time.perf_counter(),time.process_time()
    graph=json.loads((ROOT/'data/raw/a/official/data/case_005.json').read_text())
    plans=json.loads((args.source/'005.plans.json').read_text())
    config=read_config(ROOT/'data/raw/a/official/data/config.txt',problem=args.problem)
    pool=E2BatchEvaluator(graph,problem=args.problem,workers=args.workers,native_enabled=args.mode=='native')
    stop=threading.Event(); peaks=[]
    def sample():
        while not stop.is_set():
            pids=[os.getpid()]
            for slot in pool._slots:
                try:
                    if slot is not None and slot[0].pid: pids.append(slot[0].pid)
                except ValueError: pass
            proc=subprocess.run(['ps','-o','rss=','-p',','.join(map(str,pids))],capture_output=True,text=True,timeout=3)
            if proc.returncode==0:
                peaks.append(sum(int(x)*1024 for x in proc.stdout.split()))
            stop.wait(.05)
    monitor=threading.Thread(target=sample,daemon=True);monitor.start()
    rows=[]
    try:
        with pool:
            with Path(str(args.output)+'.rows.jsonl').open('x') as f:
                for row in pool.evaluate_batch(plans,**config):
                    rows.append(row);f.write(json.dumps(row)+'\n');f.flush()
    finally:
        stop.set();monitor.join(timeout=4)
    save(args.output,dict(problem=args.problem,mode=args.mode,workers=args.workers,
        inner_wall_seconds=time.perf_counter()-start,parent_cpu_seconds=time.process_time()-cpu,
        worker_candidate_cpu_seconds=sum(r.get('cpu_seconds',0) for r in rows),
        parent_plus_workers_sampled_rss_bytes=max(peaks,default=None),samples=len(peaks),
        maximum_worker_peak_rss_bytes=max((r.get('worker_peak_rss_bytes') or 0 for r in rows),default=0),
        rss_method='sum ps RSS every50ms; shared pages double counted, resource tracker excluded, not PSS/hard cap',
        completed=len(rows),formal_e0_calls=sum(r.get('route')=='e0_fallback' for r in rows),
        closed=all(x is None for x in pool._slots)))


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    summaries=[];ledger=[]
    for problem,source in ((2,'e2-p2-localopt-20260924'),(3,'e2-p3-20260924')):
        source=ROOT/'results/a/proxy'/source
        expected=[]
        with gzip.open(source/'005.e0.jsonl.gz','rt') as f:
            for line in f: expected.append(json.loads(line)['result'])
        for workers in (1,2):
            paired={}
            # Order reversal reduces systematic first/second bias, not a statistical guarantee.
            for mode in (('e0','native') if workers==1 else ('native','e0')):
                name=f'p{problem}-{workers}worker-{mode}'
                output=out/(name+'.json')
                command=[sys.executable,'-m','research.a.e2_search.resources_b','--child','--problem',str(problem),
                         '--source',str(source),'--workers',str(workers),'--mode',mode,'--output',str(output)]
                row=dict(name=name,formal_e0_reserved=16 if mode=='e0' else 0,status='started')
                ledger.append(row);save(out/'ledger.json',ledger)
                start=time.perf_counter()
                run=subprocess.run(command,capture_output=True,text=True,cwd=ROOT,timeout=120)
                elapsed=time.perf_counter()-start
                row.update(returncode=run.returncode,status='finished',outer_wall_seconds=elapsed)
                save(out/'ledger.json',ledger)
                if run.returncode: raise RuntimeError(run.stderr)
                result=json.loads(output.read_text())
                rows=[json.loads(line) for line in Path(str(output)+'.rows.jsonl').read_text().splitlines()]
                assert len(rows)==16
                fields=('makespan','data_movement_bytes','cross_task_traffic')+(('cache_stats',) if problem==3 else ())
                for actual,truth in zip(rows,expected):
                    assert actual['status']=='ok' and actual['route']==('native' if mode=='native' else 'e0_fallback')
                    assert all(equal(actual[k],truth[k]) for k in fields)
                row['actual_formal_e0_calls']=result['formal_e0_calls'];save(out/'ledger.json',ledger)
                result.update(outer_wall_seconds=elapsed,all_scores_equal=True)
                paired[mode]=result
            summaries.append(dict(problem=problem,workers=workers,case='005',candidates=16,
                outer_speedup=paired['e0']['outer_wall_seconds']/paired['native']['outer_wall_seconds'],
                measurements=paired))
            save(out/'summary.json',summaries)
            print(json.dumps(summaries[-1]),flush=True)
    save(out/'completion.json',dict(completed=True,formal_e0_calls_by_problem={'2':32,'3':32},
        timing='outer subprocess launch -> exit: includes Python startup/imports, graph/config/plan IO, worker start, IPC, scoring, JSONL writes, sampler and teardown; native build excluded; both routes same search fields',
        note='E0 internal full diagnostics still constructed; no equivalent optimized E1. All candidates previously truth-labelled, no new unique plans; one run per cell.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--child',action='store_true')
    p.add_argument('--problem',type=int);p.add_argument('--source',type=Path)
    p.add_argument('--workers',type=int);p.add_argument('--mode')
    args=p.parse_args()
    child(args) if args.child else main(args.output)
