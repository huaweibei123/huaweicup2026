import json,time,statistics
from pathlib import Path
from graph_features import Graph
from memory_certificate import certify
ROOT=Path(__file__).resolve().parents[1];OFF=ROOT.parent/'route4_base/data/raw/a/official'
cache={};rows=[];pairs={}
for p in sorted((ROOT/'runs').glob('*/run.json')):
    r=json.loads(p.read_text())
    if r['status']!='ok' or r['method']=='coarse' or r['problem'] not in [2,3]:continue
    case=r['case']
    if case not in cache:
        path=OFF/'data'/f'case_{case:03d}.json' if case<10000 else ROOT/'synthetic'/f'case_{case:05d}.json'
        cache[case]=Graph(json.loads(path.read_text()))
    g=cache[case];plan=json.loads((p.parent/'plan.json').read_text());tt=[]
    for repeat in range(3):
        t=time.perf_counter();cc=certify(g,plan);tt.append(time.perf_counter()-t)
    ctor=r['constructor']
    if cc['supported']:
        assert cc['bucket_peak_by_core']==ctor['bucket_peak_by_core'],r['label']
    spill=r['data_movement_bytes']['spill_added_copy_bytes']
    row=dict(label=r['label'],case=case,problem=r['problem'],method=r['method'],supported=cc['supported'],
             certificate=cc.get('no_spill_sufficient'),spill_bytes=spill,median_warm_certificate_s=statistics.median(tt),
             e0_full_cli_s=r['e0_cli_wall_s'])
    if cc.get('no_spill_sufficient'):assert spill==0,r['label']
    rows.append(row)
    if r['method'] in ['unguarded','frontier'] and r['gamma']==1:
        key=(case,r['problem'],r['cores'],r['assignment'],r['label'].split('_c')[0])
        pairs.setdefault(key,{})[r['method']]=(cc,plan)
checks=[]
for key,v in pairs.items():
    if set(v)=={'unguarded','frontier'} and v['unguarded'][0].get('no_spill_sufficient'):
        eq=v['unguarded'][1]==v['frontier'][1]
        assert eq,key
        checks.append({'pool':list(key),'plan_objects_identical':eq})
report={'successful_singleton_evaluations':len(rows),'positive_certificates':sum(bool(r['certificate']) for r in rows),
        'positive_certificate_contradictions':sum(bool(r['certificate']) and r['spill_bytes']!=0 for r in rows),
        'negative_certificate_zero_spill_bytes':sum(r['certificate']==False and r['spill_bytes']==0 for r in rows),
        'policy_skip_pairs_checked':len(checks),'rows':rows,'skip_pairs':checks,
        'warm_timing_note':'Graph already parsed/indexed; includes new plan validation and all interval construction, 3 sequential repetitions. Does not estimate makespan.'}
(ROOT/'analysis/certificate_audit.json').write_text(json.dumps(report,indent=2))
print({k:v for k,v in report.items() if k not in ['rows','skip_pairs']})
