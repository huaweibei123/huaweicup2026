"""One bounded 64-distinct-candidate experiment; stream full oracle evidence.

All timing scopes remain explicit. No E0 truth, decoded traces or answer cache
is used by the native scorer. Oracle calls and comparisons are outside timing.
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import resource
import subprocess
import sys
from pathlib import Path

from probe import HERE, ROOT, P1Evaluator, read_config, load_problem1_bundle
from probe import measured, equal, compare, save, sha, pack_tasks, score


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    raw=(ROOT/'data/raw/a/official/data/case_003.json').read_bytes()
    graph=json.loads(raw);cfg=read_config(ROOT/'data/raw/a/official/data/config.txt')
    e0,support=load_problem1_bundle('_native_batch_e0')
    base=support['stub_multicore_cut_and_schedule'].generate_multicore_plan(graph,num_cores=4,seed=2026,min_subgraph_size=50,max_subgraph_size=100)
    tids=sorted(set(base['node_to_subgraph'].values()))
    plans=[]
    for i in range(64):
        rng=random.Random(360924+i);orders=[[] for _ in range(4)]
        for tid in tids:orders[rng.randrange(4)].append(tid)
        plans.append(dict(node_to_subgraph=base['node_to_subgraph'],core_schedules=orders))
    hashes=[sha(json.dumps(x,sort_keys=True).encode()) for x in plans]
    assert len(set(hashes))==64
    with gzip.open(out/'plans.json.gz','wt') as f:json.dump(plans,f)
    prep,init_native=measured(lambda:P1Evaluator(graph))
    def prepare():
        prep._runtime.validate_parameters(cfg['bandwidth'],dict(cfg['capacity']),1000000,cross_core_wait=cfg['cross_core_wait'],same_core_wait=cfg['same_core_wait'])
        tasks,traffic,movement,view=prep._build_tasks(prep._graph,plans[0],cfg['bandwidth'],cfg['capacity'])
        comp=pack_tasks(tasks,prep._runtime,cfg['bandwidth'])
        prep._pending=None
        return comp
    comp,compile_native=measured(prepare)
    e1,init_e1=measured(lambda:P1Evaluator(graph))
    metadata=dict(scope='single official case003 fixed-partition development pool; not full release',
        candidates=64,repeats=1,seed=360924,graph_sha256=sha(raw),config=cfg,
        engine_base='5bfe53a29c1ba05167239f51ea937e602f7f85b4',
        git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        python=sys.version,source_sha256={p.name:sha(p.read_bytes()) for p in [HERE/'batch_probe.py',HERE/'probe.py',HERE/'replay_api.py',HERE/'src/replay.cpp']},
        dynamic_library_sha256=sha((HERE/'src/libreplay.so').read_bytes()),
        lock_sha256=sha((ROOT/'uv.lock').read_bytes()),plan_hashes=hashes,
        native_initialization=init_native,native_official_compilation_and_pack=compile_native,e1_initialization=init_e1,
        timing='parsed same graph; native includes first library load + exact typed schedule checks + all candidate replays; both cold prepared graph engines charged; first E1 call compiles; no process/IO cost included; truth, extra audit replay and byte comparisons outside timers',
        memory='stream one full E0 result at a time into 16-candidate gzip chunks; combined-process RSS is not standalone native RSS')
    save(out/'run.json',metadata)
    rows=[];fp=None
    try:
        for i,plan in enumerate(plans):
            if i%16==0:
                if fp:fp.close()
                fp=gzip.open(out/f'e0-full-{i//16:02d}.jsonl.gz','wt')
            truth,oracle_time=measured(lambda:e0.evaluate_scene_a(graph,plan,**cfg))
            fp.write(json.dumps({'candidate':i,'result':truth},separators=(',',':'))+'\n');fp.flush()
            times={};order=['e1','native'] if i%2==0 else ['native','e1']
            for mode in order:
                if mode=='e1':
                    actual,t=measured(lambda:e1.evaluate(plan,**cfg));assert equal(truth,actual)
                else:
                    actual,t=measured(lambda:score(comp,plan['core_schedules'],same_wait=cfg['same_core_wait'],cross_wait=cfg['cross_core_wait'],project_once=True))
                    compare(comp,truth,actual,audit=False)
                times[mode]=t
                del actual
            debug=score(comp,plan['core_schedules'],same_wait=cfg['same_core_wait'],cross_wait=cfg['cross_core_wait'],audit=True)
            compare(comp,truth,debug,audit=True)
            row=dict(candidate=i,order=order,makespan=truth['makespan'],times=times,e0=oracle_time,
                full_e0_e1_equal=True,native_all_times_equal=True,ddr_projection_log_equal=True)
            rows.append(row);save(out/'rows.json',rows)
            del truth,debug
            if (i+1)%8==0:print(json.dumps(dict(completed=i+1,of=64)),flush=True)
    finally:
        if fp:fp.close()
    baseline_wall=init_e1['wall']+sum(r['times']['e1']['wall'] for r in rows)
    native_wall=init_native['wall']+compile_native['wall']+sum(r['times']['native']['wall'] for r in rows)
    baseline_cpu=init_e1['cpu']+sum(r['times']['e1']['cpu'] for r in rows)
    native_cpu=init_native['cpu']+compile_native['cpu']+sum(r['times']['native']['cpu'] for r in rows)
    best=min(rows,key=lambda r:(r['makespan'],r['candidate']))
    confirm=best['e0']['wall']
    summary=dict(case='003',candidates=64,all_e0_e1_full_equal=True,all_native_times_and_ddr_equal=True,
        charged_e1_wall=baseline_wall,charged_native_wall=native_wall,speedup=baseline_wall/native_wall,
        charged_e1_cpu=baseline_cpu,charged_native_cpu=native_cpu,cpu_reduction=baseline_cpu/native_cpu,
        best_candidate=best['candidate'],best_makespan=best['makespan'],
        confirmation_accounting='add the same measured best-candidate E0 call to both paths; arithmetic cost model, not an independently rerun full search',
        measured_best_e0_wall=confirm,including_same_one_e0_confirmation_speedup=(baseline_wall+confirm)/(native_wall+confirm),
        static_array_bytes=comp.static_bytes,rss_combined_process_highwater_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024),
        limitation='one public graph, one partition, one serial run; score API omits full JSON construction; no cross-platform/RSS/search quality release claim')
    save(out/'summary.json',summary);print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
