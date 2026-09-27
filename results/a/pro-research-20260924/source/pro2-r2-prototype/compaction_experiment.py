"""Three paired full-E0 trials, include extra prefix construction overhead.
Not part of the frozen previous constructor comparison.
"""
import json,time,gzip,copy
from pathlib import Path
from scan import ROOT
from compact_priorities import compact
from evidence import run_e0
OUT=Path('/mnt/data/r2_research/runs/compaction');OUT.mkdir(exist_ok=False)
# Sources already tested; these trials test behavioral equivalence and host overhead, not new Makespan improvement.
settings=[(8,2,Path('/mnt/data/r2_research/runs/affine/case_008_p2_w0_f0.125/plan.json')),
(89,2,Path('/mnt/data/r2_research/runs/paired/case_089_p2_k4_structured/incumbent.plan.json')),
(95,2,Path('/mnt/data/r2_research/runs/paired/case_095_p2_k4_structured/incumbent.plan.json')),
(80,3,Path('/mnt/data/r2_research/runs/affine/case_080_p3_w0_f0.125/plan.json'))]
# Explicit projection: all native fields except subgroup annotations and input-file metadata.
# This is NOT the E1 full-JSON comparator, and original files stay intact.
def score_behavior(r):
    r=copy.deepcopy(r);r.pop('input_graph',None);r.pop('input_plan',None)
    for core in r['per_core_timeline']:
        core.pop('subgraphs',None)
        for task in core.get('tasks',[]):task.pop('subgraph_ids',None)
        for pipe in core.get('pipes',{}).values():
            for op in pipe:op.pop('subgraph_id',None)
        # Actual E0 places ops in core['ops'].
        for op in core.get('ops',[]):op.pop('subgraph_id',None)
    return r
rows=[]
for case,q,pp in settings:
    graph=ROOT/f'data/case_{case:03d}.json';g=json.loads(graph.read_text());old=json.loads(pp.read_text())
    for repeat in range(3):
        pair={};cert=None
        for mode in (['old','compact'] if repeat%2==0 else ['compact','old']):
            start=time.perf_counter();p=old
            if mode=='compact':p,cert=compact(g,old,ROOT)
            build=time.perf_counter()-start;dest=OUT/f'case_{case:03d}_p{q}_r{repeat}_{mode}'
            r=run_e0(graph,p,q,dest,timeout=25,official=ROOT,compress=True)
            r.update(case=case,mode=mode,repeat=repeat,construction_seconds=build,paired_total_seconds=time.perf_counter()-start,groups=sum(map(len,p['core_schedules'])))
            if cert:(dest/'compaction_certificate.json').write_text(json.dumps(cert,indent=2))
            if r['status']!='ok':raise RuntimeError(r)
            pair[mode]=(r,json.loads(gzip.decompress((dest/'result.json.gz').read_bytes())))
            rows.append(r)
        good=score_behavior(pair['old'][1])==score_behavior(pair['compact'][1])
        if not good:
            # Preserve exact first-level projection difference rather than weakening comparator.
            p0,p1=map(lambda x:score_behavior(x[1]),pair.values())
            (OUT/f'diff_case_{case}_r{repeat}.json').write_text(json.dumps({'different_top_keys':[k for k in p0 if p0[k]!=p1.get(k)]},indent=2))
        for mode in pair:pair[mode][0]['scoring_behavior_equal']=good
        print(case,q,repeat,good,[(m,pair[m][0]['groups'],round(pair[m][0]['paired_total_seconds'],3)) for m in pair],flush=True)
        (OUT/'summary.json').write_text(json.dumps(rows,indent=2))
