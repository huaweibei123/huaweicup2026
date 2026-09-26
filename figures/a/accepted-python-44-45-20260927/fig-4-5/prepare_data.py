"""Read fixed 834d8c9 feed, verify against frozen paper v8, export plotting tables."""
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

p = Path(__file__).resolve().parent
source = p.parent / 'sources'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
receipt = json.loads((source/'paper-source-receipt.json').read_text(encoding='utf-8'))
assert sha(source/'paper-all-results.csv') == receipt['all_results_sha256']
assert sha(source/'board-feed.json') == receipt['sources'][0]['sha256']
feed = json.loads((source/'board-feed.json').read_text(encoding='utf-8'))['records']
with (source/'paper-all-results.csv').open(encoding='utf-8', newline='') as f:
    paper = {(r['case_id'], int(r['cores'])): r for r in csv.DictReader(f) if r['problem']=='P1'}
assert len(feed) == len(paper) == 500
assert {(r['case_id'], r['cores']) for r in feed} == set(paper)
metrics = []
for r in feed:
    t = paper[r['case_id'], r['cores']]
    m = r['metrics']
    assert r['status'] == 'ok' and r['evaluator']['route'] == 'E0'
    assert r['solver_commit'] == t['solver_commit'] == '834d8c957538ee069c66aadac9509552a4cc69d7'
    for field, column in [('makespan_cycles','makespan_cycles'),('solver_wall_seconds','solver_wall_seconds'),('ddr_bytes','scheduled_copy_bytes'),('extra_ddr_bytes','extra_ddr_bytes'),('spill_bytes','spill_bytes')]:
        assert float(t[column]) == m[field], (r['case_id'], r['cores'], field)
    ew = m['evaluation_wall_seconds']
    assert (t['external_evaluation_seconds']=='' and ew is None) or (ew is not None and float(t['external_evaluation_seconds'])==ew)
    assert t['graph_sha256'] == r['identity']['graph_sha256']
    assert t['plan_sha256'] == r['identity']['plan_sha256']
    env = r['provenance']['environment']
    assert env['workers'] == 4 and env['python']=='3.12.13'
    metrics.append(dict(case=r['case_id'], cores=r['cores'], makespan=m['makespan_cycles'],
        extra_ddr=m['extra_ddr_bytes'], ddr_bytes=m['ddr_bytes'], spill_bytes=m['spill_bytes'],
        solver_wall=m['solver_wall_seconds'], evaluation_wall=ew,
        e0_result_reused=(ew is None), platform=env['os'], cpu=env['cpu'], workers=env['workers'],
        timing_scope=r['provenance']['measurement']['solver_scope'],
        attempt_id=r['attempt_id'], revision=r['revision'], run_id=r['run_id'],
        solver_commit=r['solver_commit'], source_result_sha256=r['artifacts']['result']['sha256']))
metrics.sort(key=lambda r:(r['case'],r['cores']))

def row_summary(group, cores):
    vals = sorted(r['solver_wall'] for r in group)
    q=(len(vals)-1)*.95; i=int(q)
    return dict(cores=cores,n=len(vals),mean=statistics.mean(vals),median=statistics.median(vals),
        p95_nearest_rank=vals[math.ceil(.95*len(vals))-1],
        p95_linear=vals[i]+(vals[min(i+1,len(vals)-1)]-vals[i])*(q-i),max=max(vals),
        mean_scheduled_copy_bytes=statistics.mean(r['ddr_bytes'] for r in group),
        mean_extra_ddr_bytes=statistics.mean(r['extra_ddr'] for r in group))

summary=[row_summary([r for r in metrics if r['cores']==k], k) for k in range(1,6)]
assert all(r['n']==100 for r in summary)
quality=json.loads((source/'QUALITY_SUMMARY.json').read_text(encoding='utf-8'))
for s in summary:
    q=quality['by_cores'][str(s['cores'])]
    for ours,theirs in [('mean','mean'),('median','median'),('p95_nearest_rank','p95'),('max','max')]:
        assert math.isclose(s[ours],q['solver_seconds'][theirs],rel_tol=1e-12)
    assert math.isclose(s['mean_extra_ddr_bytes']*100,q['extra_ddr_bytes'],rel_tol=1e-12)
for name,rows in [('metrics.csv',metrics),('summary.csv',summary),('overall-summary.csv',[row_summary(metrics,'all')])]:
    with (p/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
proof=dict(paper_commit='6b1fdf25649b2b5bfc8d267896428187c3469291',
    result_commit='a1bb4451cd85c46b32bb928d57c81e22cfeca1a6',
    solver_commit='834d8c957538ee069c66aadac9509552a4cc69d7',
    verified_cells=500,verified_metric_fields=6,source_feed_sha256=sha(source/'board-feed.json'),
    external_e0_wall_missing_for_reused_results=sum(r['evaluation_wall'] is None for r in metrics),
    solver_calls=0,evaluator_calls=0,status='locally_verified_candidate_pending_user_and_captain',
    quantile_method='nearest-rank for paper comparison; linear quantile retained in separate column',
    scope='Data identity and plotting only; no rerun of solver, evaluator or plan legality checks.',
    summary=summary,overall_summary=row_summary(metrics,'all'))
(p/'data-verification.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof['overall_summary'],indent=2))
