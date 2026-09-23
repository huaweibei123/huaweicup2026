"""Bounded local verification of the archived Pro kernel on official inputs.

This is a prepared-input experiment, not a replacement official evaluator API.
The C++ kernel is unchanged; the NumPy audit-allocation fix is in PROVENANCE.
All new observations go to a fresh output path.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import platform
import random
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from src.eval_exact import P1Evaluator, read_config
from src.eval_exact._official import OFFICIAL_CODE_HASH, load_problem1_bundle
from src.eval_exact.batch_benchmark import equal
from replay_api import pack_tasks, score, Unsupported, CandidateError


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def measured(fn):
    wall, cpu = time.perf_counter(), time.process_time()
    value = fn()
    return value, dict(wall=time.perf_counter()-wall, cpu=time.process_time()-cpu)


def compare(comp, reference, native, *, audit):
    assert type(reference['makespan']) is int
    assert type(native['makespan']) is int
    assert reference['makespan'] == native['makespan']
    observed_ops, observed_tasks = set(), set()
    tid_index = {t: i for i, t in enumerate(comp.task_ids)}
    for core in reference['per_core_timeline']:
        for op in core['ops']:
            k = comp.index[op['task_id'], op['op_id']]
            assert k not in observed_ops
            observed_ops.add(k)
            assert (int(native['op_start'][k]), int(native['op_end'][k])) == (op['start'], op['end']), op
        for task in core['tasks']:
            k = tid_index[task['task_id']]
            assert k not in observed_tasks
            observed_tasks.add(k)
            assert (int(native['task_start'][k]), int(native['task_end'][k])) == (task['start'], task['end']), task
    assert len(observed_ops) == len(comp.op_keys)
    assert len(observed_tasks) == len(comp.task_ids)
    if audit:
        log = []
        for event in reference['ddr_contention_log']:
            log += [event['time'], comp.index[event['issued']['task_id'], event['issued']['op_id']], event['active_count']]
            for item in event['projected_ends']:
                log += [comp.index[item['task_id'], item['op_id']], item['end']]
        assert native['audit'].tolist() == log


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', nargs='+', default=['002', '003', '008'])
    parser.add_argument('--candidates', type=int, default=3)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    assert 1 <= args.candidates <= 12 and 1 <= args.repeats <= 3
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    build = ['clang++', '-std=c++17', '-O3', '-fPIC', '-shared', '-fno-fast-math', '-ffp-contract=off', '-Wall', '-Wextra', str(HERE/'src/replay.cpp'), '-o', str(HERE/'src/libreplay.so')]
    result = subprocess.run(build, capture_output=True, text=True, check=True)
    (out/'build.txt').write_text(result.stdout + result.stderr)
    config = read_config(ROOT/'data/raw/a/official/data/config.txt')
    oracle, support = load_problem1_bundle('_native_probe_e0')
    generate = support['stub_multicore_cut_and_schedule'].generate_multicore_plan
    metadata = dict(scope='official graphs, fixed partition, prepared internal API; NOT release or general 10x acceptance',
                    git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                    official_code_hash=OFFICIAL_CODE_HASH, python=sys.version, platform=platform.platform(),
                    compiler=subprocess.check_output(['clang++', '--version'], text=True), config=config,
                    lock_sha256=sha((ROOT/'uv.lock').read_bytes()), source_sha256={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in [*HERE.glob('*.py'), HERE/'src/replay.cpp', * (ROOT/'src/eval_exact').glob('*.py')]},
                    build_command=[x.replace(str(ROOT), '.') for x in build], protocol=dict(cases=args.cases,candidates=args.candidates,repeats=args.repeats,seed=260925),
                    limitations=['public development graphs','single macOS arm64 process','no hard RSS or long-run test','no raw native public API','hot timings not end-to-end release evidence'])
    save(out/'run.json', metadata)
    summaries=[]
    for case in args.cases:
        raw=(ROOT/f'data/raw/a/official/data/case_{case}.json').read_bytes()
        graph=json.loads(raw)
        base=generate(graph,num_cores=4,seed=2026,min_subgraph_size=50,max_subgraph_size=100)
        tids=sorted(set(base['node_to_subgraph'].values()))
        plans=[]
        for i in range(args.candidates):
            rng=random.Random(260925+i)
            orders=[[] for _ in range(4)]
            for tid in tids: orders[rng.randrange(4)].append(tid)
            plans.append(dict(node_to_subgraph=base['node_to_subgraph'],core_schedules=orders))
        ids=[sha(json.dumps(p,sort_keys=True).encode()) for p in plans]
        assert len(set(ids))==len(ids)
        with gzip.open(out/f'{case}.plans.json.gz','wt') as fp:json.dump(plans,fp)
        engine, init=measured(lambda:P1Evaluator(graph))
        original=engine._runtime._build_scene_a_tasks
        builder_times=[]
        def timed_builder(*a,**kw):
            value,timing=measured(lambda:original(*a,**kw));builder_times.append(timing);return value
        engine._runtime._build_scene_a_tasks=timed_builder
        refs=[];cold_e1=[];oracle_times=[]
        for index,plan in enumerate(plans):
            r0,t0=measured(lambda:oracle.evaluate_scene_a(graph,plan,**config))
            r1,t1=measured(lambda:engine.evaluate(plan,**config))
            assert equal(r0,r1),'full E0/E1 difference'
            refs.append(r0);oracle_times.append(t0);cold_e1.append(dict(total=t1,builder=builder_times[-1]))
        with gzip.open(out/f'{case}.e0-full.json.gz','wt') as fp:json.dump(refs,fp)
        prep_engine, prep_init=measured(lambda:P1Evaluator(graph))
        prep_engine._runtime.validate_parameters(config['bandwidth'],dict(config['capacity']),1000000,
            cross_core_wait=config['cross_core_wait'],same_core_wait=config['same_core_wait'])
        prepared, local_time=measured(lambda:prep_engine._build_tasks(prep_engine._graph,plans[0],config['bandwidth'],config['capacity']))
        comp, pack_time=measured(lambda:pack_tasks(prepared[0],prep_engine._runtime,config['bandwidth']))
        same,cross=config['same_core_wait'],config['cross_core_wait']
        # Warm dynamic loading separately; do not disguise it as candidate cost.
        _,load_time=measured(lambda:score(comp,plans[0]['core_schedules'],same_wait=same,cross_wait=cross))
        native_receipts=[]
        for index,plan in enumerate(plans):
            for mode in ['audit','serial','coalesced']:
                result=score(comp,plan['core_schedules'],same_wait=same,cross_wait=cross,audit=mode=='audit',project_once=mode=='coalesced')
                compare(comp,refs[index],result,audit=mode=='audit')
                native_receipts.append(dict(candidate=index,mode=mode,makespan=result['makespan'],stats=result['stats'].tolist()))
        save(out/f'{case}.native-checks.json',native_receipts)
        rows=[];permutations=list(itertools.permutations(['e1','serial','coalesced']))
        for repeat in range(args.repeats):
            for index,plan in enumerate(plans):
                order=permutations[(repeat*len(plans)+index)%len(permutations)]
                times={}
                for mode in order:
                    if mode=='e1':
                        value,t=measured(lambda:engine.evaluate(plan,**config));assert equal(value,refs[index]);t['builder']=builder_times[-1]
                    else:
                        value,t=measured(lambda:score(comp,plan['core_schedules'],same_wait=same,cross_wait=cross,project_once=mode=='coalesced'))
                        compare(comp,refs[index],value,audit=False)
                    times[mode]=t
                rows.append(dict(repeat=repeat,candidate=index,order=order,times=times))
        totals={mode:sum(r['times'][mode]['wall'] for r in rows) for mode in ['e1','serial','coalesced']}
        prep=prep_init['wall']+local_time['wall']+pack_time['wall']+load_time['wall']
        native_avg_batch=totals['coalesced']/args.repeats
        first_e1=init['wall']+sum(x['total']['wall'] for x in cold_e1)
        summary=dict(case=case,graph_sha256=sha(raw),plan_hashes=ids,distinct_candidates=len(plans),
            ops=len(comp.op_keys),tasks=len(comp.task_ids),static_array_bytes=comp.static_bytes,
            full_e0_e1_equal=True,native_all_op_task_times_equal=True,native_all_issue_projections_equal=True,
            oracle_times=oracle_times,e1_initialization=init,e1_first_batch=cold_e1,
            native_initialization=prep_init,cold_official_local_compile=local_time,array_pack=pack_time,library_load_and_warmup=load_time,
            cold_preparation_total_wall=prep,hot_totals_wall=totals,hot_speedup_vs_e1=totals['e1']/totals['coalesced'],
            charged_first_batch_speedup=first_e1/(prep+native_avg_batch),
            hot_e1_builder_fraction=sum(r['times']['e1']['builder']['wall'] for r in rows)/totals['e1'],
            rss_process_highwater_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024),
            rss_note='combined experiment process retaining oracle/E1/native objects; not standalone native worker RSS')
        save(out/f'{case}.timings.json',rows);save(out/f'{case}.summary.json',summary)
        summaries.append(summary)
        save(out/'summary.json',summaries)
        print(json.dumps({k:summary[k] for k in ['case','ops','tasks','hot_speedup_vs_e1','charged_first_batch_speedup','hot_e1_builder_fraction','cold_preparation_total_wall']}) ,flush=True)
    print('PASS: E0/E1 full objects; native all operation/task times and DDR issue projections',flush=True)


if __name__=='__main__':
    main()
