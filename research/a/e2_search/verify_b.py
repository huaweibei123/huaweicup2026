"""Bounded P2/P3 developer verification; fresh output, complete E0 evidence.

32 distinct plans (16 on each of 004/005), at most 128 formal E0 invocations
including fallback, failures and retries. Synthetic tests are a separate ledger.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import platform
import random
import subprocess
import sys
import time

from src.eval_exact._official import REPO_ROOT as ROOT, OFFICIAL_CODE_HASH
from src.eval_exact.batch_benchmark import equal
from . import SceneBEvaluator, E2BatchEvaluator, read_config
from ._official_b import load_bundle
from .build_native import build


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(problem, out):
    out.mkdir(parents=True, exist_ok=False)
    started = time.time()
    runtime, support = load_bundle(problem)
    generate = support['stub_multicore_cut_and_schedule'].generate_multicore_plan
    config = read_config(ROOT/'data/raw/a/official/data/config.txt', problem=problem)
    here = Path(__file__).parent
    sources = [p for p in here.rglob('*') if p.suffix in ('.py', '.cpp')]
    save(out/'run.json', dict(problem=problem, started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)),
        python=sys.version, platform=platform.platform(), official_code_hash=OFFICIAL_CODE_HASH,
        config=config, git_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip(),
        source_sha256={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sources},
        build=build(problem=problem), formal_e0_budget=128, unique_candidates=32,
        scope='Developer test only; no sealed, independent or Windows acceptance; no corresponding optimized E1 speed gate',
        timing='Parsed graph/plan -> search record; E0 internally builds full output; cold includes full compilation, hot identical plans only; candidate generation/truth archive IO excluded'))
    ledger, summaries = [], []
    def truth(graph, plan, label):
        assert len(ledger) < 128 and time.time()-started < 1800
        entry = dict(index=len(ledger), label=label, start=time.time())
        ledger.append(entry)
        save(out/'e0-ledger.json', ledger)
        start = time.perf_counter()
        fn = runtime.evaluate_scene_b if problem == 2 else runtime.evaluate_problem_3
        try:
            value = fn(graph, plan, **config)
            entry.update(status='ok', makespan=value['makespan'])
        except Exception as error:
            entry.update(status='error', error_type=type(error).__name__, message=str(error))
            raise
        finally:
            entry['wall_seconds'] = time.perf_counter()-start
            save(out/'e0-ledger.json', ledger)
        return value, entry['wall_seconds']
    for case in ('004', '005'):
        graph_file = ROOT/f'data/raw/a/official/data/case_{case}.json'
        graph = json.loads(graph_file.read_text())
        plans = []
        for i in range(16):
            base = generate(graph, num_cores=4, seed=924200+int(case)*100+i//4,
                            min_subgraph_size=50, max_subgraph_size=100)
            rng = random.Random(9242000+int(case)*100+i)
            orders = [[] for _ in range(4)]
            for sg in sorted(set(base['node_to_subgraph'].values())):
                orders[rng.randrange(4)].append(sg)
            plans.append(dict(node_to_subgraph=base['node_to_subgraph'], core_schedules=orders))
        assert len({sha(json.dumps(p,sort_keys=True).encode()) for p in plans}) == 16
        save(out/f'{case}.plans.json', plans)
        expected, e0_times = [], []
        for i, plan in enumerate(plans):
            value, seconds = truth(graph, plan, f'{case}/{i}/full-reference')
            expected.append(value); e0_times.append(seconds)
            with gzip.open(out/f'{case}.e0.jsonl.gz', 'at') as f:
                f.write(json.dumps(dict(index=i, result=value),separators=(',',':'))+'\n')
        init = time.perf_counter()
        engine = SceneBEvaluator(graph, problem=problem)
        initialization = time.perf_counter()-init
        modes = {}
        for mode in ('cold', 'repeat'):
            rows = []
            for i, plan in enumerate(plans):
                row = engine.evaluate_record(plan, **config)
                rows.append(row)
                if row['route'] == 'e0_fallback':
                    ledger.append(dict(label=f'{case}/{i}/{mode}/fallback', status=row['status'], wall_seconds=row['wall_seconds']))
                    save(out/'e0-ledger.json', ledger)
                assert row['status']=='ok' and row['route']=='native', row
                fields = ('makespan','data_movement_bytes','cross_task_traffic') + (('cache_stats',) if problem==3 else ())
                assert all(equal(row[k], expected[i][k]) for k in fields), (case, i, row)
            modes[mode] = rows
            save(out/f'{case}.{mode}.json', rows)
        # Stronger than makespan: every operation start/end, generated COPY IDs included.
        for i, plan in enumerate(plans):
            d = engine._native_score(plan,dict(config,max_iter=1_000_000),debug=True)['debug']
            want = {(c['core_id'], o['op_id']):(o['start'],o['end']) for c in expected[i]['per_core_timeline'] for o in c['ops']}
            got = {key:(int(d['op_start'][j]),int(d['op_end'][j])) for j,key in enumerate(d['op_keys'])}
            assert equal(got,want), (case,i,'op timeline mismatch')
            if problem == 3:
                for field in ('cache_stats','cache_events','cache_final_entries','cache_used_bytes_final'):
                    assert equal(d[field],expected[i][field]), (case,i,field)
        pool_start = time.perf_counter()
        with E2BatchEvaluator(graph,problem=problem,workers=2,max_tasks_per_worker=8) as pool:
            pool_rows = list(pool.evaluate_batch(plans,**config))
        pool_seconds = time.perf_counter()-pool_start
        assert all(r['route']=='native' and equal(r['makespan'],e['makespan']) for r,e in zip(pool_rows,expected))
        save(out/f'{case}.pool.json',dict(total_wall_seconds=pool_seconds, rows=pool_rows,closed=all(x is None for x in pool._slots)))
        selected = sorted(range(16),key=lambda i:modes['cold'][i]['makespan'])[:4]
        check_seconds = 0
        for i in selected:
            value, sec = truth(graph,plans[i],f'{case}/{i}/shortlist-E0')
            check_seconds += sec
            assert equal(value,expected[i])
        cold = initialization+sum(r['wall_seconds'] for r in modes['cold'])
        repeat = sum(r['wall_seconds'] for r in modes['repeat'])
        summary = dict(case=case,candidates=16,distinct_partitions=4,graph_sha256=sha(graph_file.read_bytes()),
            e0_full_seconds=sum(e0_times),native_cold_seconds=cold,native_repeat_seconds=repeat,
            cold_vs_e0_full=sum(e0_times)/cold,repeat_vs_e0_full=sum(e0_times)/repeat,
            cold_preparation_seconds=sum(r['preparation_seconds'] for r in modes['cold']),
            cold_replay_seconds=sum(r['replay_seconds'] for r in modes['cold']),
            pool_workers=2,pool_end_to_end_seconds=pool_seconds,shortlist_e0_seconds=check_seconds,
            cold_plus_shortlist_e0_seconds=cold+check_seconds,
            numeric_mismatch_count=0,all_operation_times_equal=True,shortlist_regret=0,
            routes=dict(Counter(r['route'] for r in modes['cold'])),cache=engine.cache_stats())
        summaries.append(summary)
        save(out/'summary.json',summaries)
        print(json.dumps(summary),flush=True)
    save(out/'completion.json',dict(completed=True,formal_e0_calls=len(ledger),failed_calls=sum(x['status']!='ok' for x in ledger),
                                   wall_seconds=time.time()-started))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--problem',type=int,choices=(2,3),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.problem,args.output)
