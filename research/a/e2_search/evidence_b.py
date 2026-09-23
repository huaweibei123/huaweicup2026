"""Persist native event traces and fresh paired final E0 confirmations.

Native traces use _native_score directly: an unsupported input stops this probe,
never silently falls back. Eight explicit formal E0 calls, four per problem.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import time

import numpy as np
from src.eval_exact._official import REPO_ROOT as ROOT
from src.eval_exact.batch_benchmark import equal
from . import SceneBEvaluator,read_config


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def convert(value):
    if isinstance(value,np.ndarray): return value.tolist()
    if isinstance(value,np.integer): return int(value)
    raise TypeError(type(value).__name__)


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    ledger=[];summaries=[]
    sources=[p for p in (ROOT/'research/a/e2_search').rglob('*') if p.suffix in ('.py','.cpp')]
    save(out/'run.json',dict(git_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip(),
        source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        native_binary_sha256=hashlib.sha256((ROOT/'research/a/e2_search/native/libreplay_bc.so').read_bytes()).hexdigest(),
        note='new persisted trace readback; not retroactive raw evidence for older benchmarks',formal_e0_budget=8))
    for problem,source in ((2,'e2-p2-localopt-20260924'),(3,'e2-p3-20260924')):
        source=ROOT/'results/a/proxy'/source
        config=read_config(ROOT/'data/raw/a/official/data/config.txt',problem=problem)
        for case in ('004','005'):
            graph=json.loads((ROOT/f'data/raw/a/official/data/case_{case}.json').read_text())
            plans=json.loads((source/f'{case}.plans.json').read_text())
            expected=[]
            with gzip.open(source/f'{case}.e0.jsonl.gz','rt') as f:
                for line in f:expected.append(json.loads(line)['result'])
            engine=SceneBEvaluator(graph,problem=problem)
            with gzip.open(out/f'p{problem}-{case}.native-traces.jsonl.gz','wt') as f:
                for i,plan in enumerate(plans):
                    native=engine._native_score(plan,dict(config,max_iter=1000000),debug=True)
                    d=native['debug'];truth=expected[i]
                    fields=('makespan','data_movement_bytes','cross_task_traffic')+(('cache_stats',) if problem==3 else ())
                    assert all(equal(native[k],truth[k]) for k in fields)
                    wanted={(c['core_id'],o['op_id']):(o['start'],o['end']) for c in truth['per_core_timeline'] for o in c['ops']}
                    actual={key:(int(d['op_start'][j]),int(d['op_end'][j])) for j,key in enumerate(d['op_keys'])}
                    assert equal(actual,wanted)
                    if problem==3:
                        for field in ('cache_stats','cache_events','cache_final_entries','cache_used_bytes_final'):
                            assert equal(d[field],truth[field])
                    f.write(json.dumps(dict(index=i,record=native),default=convert,separators=(',',':'))+'\n')
            winner=min(range(16),key=lambda i:expected[i]['makespan'])
            repeats=[]
            for repeat in range(2):
                assert len(ledger)<8
                event=dict(problem=problem,case=case,index=winner,repeat=repeat,reserved_e0_calls=1,status='started')
                ledger.append(event);save(out/'e0-ledger.json',ledger)
                start=time.perf_counter()
                record=engine.evaluate_record(plans[winner],full=True,**config)
                event.update(wall_seconds=time.perf_counter()-start,status=record['status'],route=record['route'])
                save(out/'e0-ledger.json',ledger)
                assert record['status']=='ok' and record['route']=='e0_full'
                with gzip.open(out/f'p{problem}-{case}.winner-{repeat}.json.gz','wt') as f:json.dump(record['result'],f)
                # JSON round-trip normalizes integer dictionary keys consistently.
                repeats.append(json.loads(json.dumps(record['result'])))
            assert equal(repeats[0],repeats[1]) and equal(repeats[0],expected[winner])
            summaries.append(dict(problem=problem,case=case,persisted_native_traces=16,winner_index=winner,
                                  paired_full_e0_equal=True,all_op_times_equal=True,
                                  all_cache_events_equal=problem==3,formal_e0_calls=2))
            save(out/'summary.json',summaries)
    save(out/'completion.json',dict(completed=True,formal_e0_calls_by_problem={'2':4,'3':4},
                                    native_fallback_calls=0,new_unique_candidates=0))
    print(json.dumps(summaries),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
