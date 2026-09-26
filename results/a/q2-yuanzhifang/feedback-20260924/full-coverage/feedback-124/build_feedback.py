"""Read saved JSON only; compare frozen P2 tensor_packet to old contiguous feed."""
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
BASE = ROOT / 'results/a/q2-yuanzhifang/feedback-20260924'
OUT = Path(__file__).resolve().parent
ALGORITHM = 'e64723bdf99669c44f76d8e90ab0379a8578522e'
CAPACITY = 'eb00b1c25fe92cf8b9f835a4f3e8a63ab20a90e8'
BATCHES = {1:['round6a','round6b','round6c'], 2:['round7a','round7b','round7c'],
           4:['round4','round5a','round5b','round5c-recovery']}
OLD = {1:BASE/'goal-baseline/sources/captain-k1/board-feed-full100.json',
       2:BASE/'goal-baseline/sources/captain-k2-k5/board-feed-full400.json',
       4:BASE/'goal-baseline/sources/captain-k2-k5/board-feed-full400.json'}

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def rel(path):
    return path.relative_to(ROOT).as_posix()

def main():
    old_feed = {k:{r['case_id']:r for r in read(p)['records'] if r['cores']==k} for k,p in OLD.items()}
    assert all(len(v)==100 for v in old_feed.values())
    rows = []
    for cores, batches in BATCHES.items():
        runs = {}
        for batch in batches:
            ledger = read(BASE/batch/'ledger.json')
            assert ledger['state']=='completed'
            for path in ledger['attempts']:
                run = read(ROOT/path)
                assert run['status']=='ok' and run['solver_commit']==ALGORITHM and run['cores']==cores
                assert run['case_id'] not in runs
                runs[run['case_id']] = (run,ROOT/path,batch)
        if cores==4:
            path=BASE/'round5c/070-tensor_packet/run.json'
            run=read(path)
            assert run['status']=='ok' and run['solver_commit']==ALGORITHM and run['cores']==4
            assert '070' not in runs
            runs['070']=(run,path,'round5c-070')
        assert set(runs)=={f'{i:03}' for i in range(1,101)}
        for case in sorted(runs):
            run,path,batch = runs[case]
            old = old_feed[cores][case]
            base = read(ROOT/f'results/benchmark-board/official-singlecore-20260924/{case}/run.json')
            assert base['status']=='ok' and old['status']=='ok'
            for key, stored in [('graph_sha256','graph_sha256'),('config_sha256','config_sha256'),('official_sha256','official_code_hash')]:
                assert old['identity'][key]==run['identity'][key]==base[stored], (cores,case,key)
            current=run['metrics']
            move=current['data_movement_bytes']
            report=read(path.parent/'solver.stdout.txt')
            assert report['online_E0_calls']==0
            old_cycles=old['metrics']['makespan_cycles']
            new_cycles=current['makespan_cycles']
            baseline=base['makespan_cycles']
            route=report['selected']
            # capacity_window.build only enters its window branch for these routes;
            # logical_tid and heavy-component guards require more than saved metadata.
            route_gate=route in {'shared_stages','shared_cohorts'}
            row=dict(cores=cores,case_id=case,batch=batch,route=route,route_gate_candidate=route_gate,
                     logical_tid_guard='unverified',heavy_component_guard='unverified' if route=='shared_cohorts' else 'not_applicable',
                     baseline_cycles=baseline,old_cycles=old_cycles,new_cycles=new_cycles,
                     old_speedup=baseline/old_cycles,new_speedup=baseline/new_cycles,
                     contribution=(baseline/new_cycles-baseline/old_cycles)/100,
                     cycle_change=new_cycles-old_cycles,
                     old_spill_bytes=old['metrics']['spill_bytes'],new_spill_bytes=move['spill_added_copy_bytes'],
                     old_extra_ddr_bytes=old['metrics']['extra_ddr_bytes'],new_extra_ddr_bytes=move['added_copy_bytes'],
                     new_partition_extra_bytes=move['partition_added_copy_bytes'],
                     new_scheduled_copy_bytes=move['scheduled_copy_bytes'],
                     new_cross_core_movement_proxy=move['partition_added_copy_bytes']>0,
                     old_source=rel(OLD[cores]),new_run=rel(path),
                     graph_sha256=run['identity']['graph_sha256'],config_sha256=run['identity']['config_sha256'],
                     official_sha256=run['identity']['official_sha256'])
            rows.append(row)
    with (OUT/'case-comparison.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    stats={}
    for k in BATCHES:
        subset=[r for r in rows if r['cores']==k]
        stats[k]=dict(cases=len(subset),new_mean=statistics.mean(r['new_speedup'] for r in subset),
                      old_mean=statistics.mean(r['old_speedup'] for r in subset),
                      posthoc_max_envelope_mean=statistics.mean(max(r['new_speedup'],r['old_speedup']) for r in subset),
                      improvement_count=sum(r['contribution']>0 for r in subset),
                      regression_count=sum(r['contribution']<0 for r in subset),
                      equality_count=sum(r['contribution']==0 for r in subset),
                      routes=dict(Counter(r['route'] for r in subset)),
                      new_spill_positive=sum(r['new_spill_bytes']>0 for r in subset),
                      new_partition_extra_positive=sum(r['new_partition_extra_bytes']>0 for r in subset),
                      regressions_spill_positive=sum(r['contribution']<0 and r['new_spill_bytes']>0 for r in subset),
                      regressions_partition_extra_positive=sum(r['contribution']<0 and r['new_partition_extra_bytes']>0 for r in subset),
                      route_gate_candidates=sum(r['route_gate_candidate'] for r in subset),
                      top_gains=[dict(case=r['case_id'],contribution=r['contribution'],route=r['route'],old=r['old_cycles'],new=r['new_cycles'],spill=r['new_spill_bytes'],partition_extra=r['new_partition_extra_bytes']) for r in sorted(subset,key=lambda r:-r['contribution'])[:12]],
                      top_losses=[dict(case=r['case_id'],contribution=r['contribution'],route=r['route'],old=r['old_cycles'],new=r['new_cycles'],spill=r['new_spill_bytes'],partition_extra=r['new_partition_extra_bytes']) for r in sorted(subset,key=lambda r:r['contribution'])[:12]])
    report=dict(scope='Saved official P2 outputs versus old fixed contiguous feed; posthoc comparison, not central current best or online selector',
                new_algorithm_commit=ALGORITHM,capacity_prototype_commit=CAPACITY,
                baseline='results/benchmark-board/official-singlecore-20260924/<case>/run.json',
                sources={str(k):rel(v) for k,v in OLD.items()},
                all_identities_matched=True,zero_new_solver_E0_calls=True,statistics=stats)
    (OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False))

if __name__=='__main__':
    main()
