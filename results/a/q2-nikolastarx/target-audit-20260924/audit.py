#!/usr/bin/env python3
"""Recompute a read-only P2 target audit from the captured board responses; no evaluator imports."""
from pathlib import Path
import collections, csv, gzip, hashlib, json, math, statistics
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
TARGET={2:2.26,3:3.18,4:3.96,5:4.53}
FANG_RUNS={'20260924T131640Z-s59ee','20260924T1325Z-s59ee'}
def load(name):
    p=HERE/name
    data=gzip.decompress(p.with_suffix(p.suffix+'.gz').read_bytes()) if not p.exists() else p.read_bytes()
    return json.loads(data)
def write(name,obj): (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
manifest=load('capture-manifest.json')
for response in manifest['responses']:
    stored=(HERE/response.get('stored_name',response['name'])).read_bytes()
    if response.get('stored_sha256'): assert hashlib.sha256(stored).hexdigest()==response['stored_sha256']
    raw=gzip.decompress(stored) if response.get('stored_name','').endswith('.gz') else stored
    assert len(raw)==response['bytes'] and hashlib.sha256(raw).hexdigest()==response['sha256']
records=[r for x in manifest['responses'] if x['name'].startswith('p2-records-') for r in load(x['name'])['records']]
latest={}
for r in records:
    if r['attempt_id'] not in latest or r['revision']>latest[r['attempt_id']]['revision']:latest[r['attempt_id']]=r
latest=list(latest.values())
cells=load('p2-cells.json')['cells']
winners=[c['best'] for c in cells if c['best']]
fang=[r for r in latest if r['run_id'] in FANG_RUNS]
assert len(fang)==500 and len(winners)==500
assert {(r['case_id'],r['cores']) for r in fang}=={(f'{c:03}',k) for c in range(1,101) for k in range(1,6)}
# Independently reproduce board selection from highest revisions, successful admitted records only.
for c in cells:
    pool=[r for r in latest if r['case_id']==c['case_id'] and r['cores']==c['cores'] and r['eligible'] and r['status']=='ok']
    expected=min(pool,key=lambda r:(r['metrics']['makespan_cycles'],r['id']))
    assert expected['id']==c['best']['id']
# Verify shared official denominator raw bytes against every reviewed reference and recompute ratios.
baselines={}; checks=[]
for r in fang+winners:
    assert r['eligible'] and r['baseline_verified'] and r['evaluator']['route']=='E0'
    b=r['baseline']; ident=r['identity']
    assert all(b[f'{k}_sha256']==ident[f'{k}_sha256'] for k in ('graph','config','official'))
    key=(b['result']['path'],b['result']['sha256'])
    if key not in baselines:
        source=ROOT/key[0]
        blob=(source if source.exists() else HERE/'baseline-blobs'/key[1]).read_bytes(); assert hashlib.sha256(blob).hexdigest()==key[1]
        value=json.loads(gzip.decompress(blob) if key[0].endswith('.gz') else blob)
        assert value['scene']=='A'
        baselines[key]=value['makespan']
        checks.append({'case_id':r['case_id'],'path':key[0],'sha256':key[1],'makespan_cycles':value['makespan'],'scene':value['scene'],'entrypoint':b['entrypoint'],'graph_sha256':b['graph_sha256'],'config_sha256':b['config_sha256'],'official_sha256':b['official_sha256']})
    ratio=baselines[key]/r['metrics']['makespan_cycles']
    assert math.isclose(ratio,r['metrics']['baseline_speedup'],rel_tol=1e-14,abs_tol=0)
case_denominators={}
for check in checks:
    case=check['case_id']
    assert case not in case_denominators or case_denominators[case]==check['makespan_cycles']
    case_denominators[case]=check['makespan_cycles']
assert len(case_denominators)==100
write('baseline-verification.json',sorted(checks,key=lambda r:r['case_id']))

def sources(rows):
    uniq={json.dumps(r['source'],sort_keys=True) for r in rows}
    return [json.loads(s) for s in sorted(uniq)]
def stats(rows):
    values=[r['metrics']['baseline_speedup'] for r in rows if r.get('baseline_verified')]
    ans={'n':len(rows),'baseline_verified_n':len(values),'mean_individual_baseline_speedup':statistics.mean(values) if values else None,'algorithm_counts':dict(collections.Counter(r['algorithm_id'] for r in rows)), 'solver_commits':sorted({r['solver_commit'] for r in rows})}
    ans['metric_coverage']={m:sum(r['metrics'].get(m) is not None for r in rows) for m in ('solver_wall_seconds','evaluation_wall_seconds','ddr_bytes','extra_ddr_bytes','spill_bytes')}
    for m in ('ddr_bytes','extra_ddr_bytes','spill_bytes'):
        present=[r['metrics'][m] for r in rows if r['metrics'].get(m) is not None]
        ans[m+'_sum']=sum(present) if len(present)==len(rows) else None
    return ans
summary={'schema':'p2-read-only-target-audit-v1','captured_at':manifest['captured_at'],'local_context_head':manifest['root_head'],'central_records_before':manifest['health_records_before'],'central_records_after':manifest['health_records_after'],'p2_history_rows':len(records),'p2_latest_attempts':len(latest),'p2_latest_eligible_attempts':sum(r['eligible'] for r in latest),'calls':{'E0':0,'E1':0,'E2':0},'denominator_check':'All 109 referenced gzip result bytes (100 distinct case denominators) verified against every denominator reference in Fang full-run and historical winner records; ratios independently recomputed. No evaluation rerun.','best_selector_check':'All 500 winner IDs reproduced from captured record pages using highest revision and (makespan,id) ordering.','image_targets':TARGET,'by_core':[]}
for k in range(1,6):
    f=[r for r in fang if r['cores']==k]; w=[r for r in winners if r['cores']==k]
    s={'cores':k,'fang_fixed_contiguous':stats(f),'history_best_combination':stats(w),'image_numeric_target':TARGET.get(k)}
    s['fang_fixed_contiguous']['solver_wall_mean_seconds']=statistics.mean(r['metrics']['solver_wall_seconds'] for r in f)
    s['fang_fixed_contiguous']['evaluation_wall_mean_seconds']=statistics.mean(r['metrics']['evaluation_wall_seconds'] for r in f)
    if k in TARGET:
        s['history_target_deficit']=TARGET[k]-s['history_best_combination']['mean_individual_baseline_speedup']
        s['history_target_relative_increase_required']=TARGET[k]/s['history_best_combination']['mean_individual_baseline_speedup']-1
    summary['by_core'].append(s)
summary['fang_full_sources']=sources(fang)
summary['history_winner_sources']=sources(winners)
summary['history_winner_timing_contexts']=[json.loads(s) for s in sorted({json.dumps({'runtime_id':r['runtime_id'],'run_id':r['run_id'],'timing':{k:r.get('timing',{}).get(k) for k in ('solver_includes_evaluation','evaluation_precision','utc')},'measurement_scope':r.get('provenance',{}).get('measurement',{}).get('solver_scope'),'environment':{k:r.get('provenance',{}).get('environment',{}).get(k) for k in ('os','cpu','python','workers','threads')}},sort_keys=True) for r in winners})]
summary['groups']=[]
for key in sorted({(r['algorithm_id'],r['variant'],r['solver_commit'],r['run_id']) for r in latest}):
    rows=[r for r in latest if (r['algorithm_id'],r['variant'],r['solver_commit'],r['run_id'])==key]
    summary['groups'].append({'algorithm_id':key[0],'variant':key[1],'solver_commit':key[2],'run_id':key[3],'latest_attempts':len(rows),'eligible':sum(r['eligible'] for r in rows),'cases':sorted({r['case_id'] for r in rows}),'cores':sorted({r['cores'] for r in rows}),'sources':sources(rows)})
write('audit-summary.json',summary)
rows=[]
for w in sorted(winners,key=lambda r:(r['cores'],r['case_id'])):
    f=next(r for r in fang if r['cores']==w['cores'] and r['case_id']==w['case_id'])
    rows.append({'case_id':w['case_id'],'cores':w['cores'],'fang_makespan_cycles':f['metrics']['makespan_cycles'],'history_makespan_cycles':w['metrics']['makespan_cycles'],'fang_baseline_speedup':f['metrics']['baseline_speedup'],'history_baseline_speedup':w['metrics']['baseline_speedup'],'history_algorithm':w['algorithm_id'],'history_variant':w['variant'],'history_solver_commit':w['solver_commit'],'history_record_id':w['id'],'history_ddr_bytes':w['metrics'].get('ddr_bytes'),'history_extra_ddr_bytes':w['metrics'].get('extra_ddr_bytes'),'history_solver_wall_seconds':w['metrics'].get('solver_wall_seconds')})
with (HERE/'per-cell.csv').open('w',newline='') as h:
    writer=csv.DictWriter(h,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print(json.dumps({'means':[{'cores':r['cores'],'fang':r['fang_fixed_contiguous']['mean_individual_baseline_speedup'],'history':r['history_best_combination']['mean_individual_baseline_speedup']} for r in summary['by_core']],'baseline_bytes_checked':len(baselines),'winner_ids_checked':len(winners),'p2_latest_attempts':len(latest)},indent=2))
