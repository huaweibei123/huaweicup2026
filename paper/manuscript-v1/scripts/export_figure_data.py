#!/usr/bin/env python3
"""Freeze figure inputs from archived bytes. No solver or evaluator execution."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
from export_tables import P1, P2, P3, ROOT1, ROOT2, ROOT3

OLD1 = '0e0d7cd327c51cc6ac365e01f4b6a7d2b28f9297'
OLDROOT = 'results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[3])
    p.add_argument('--cases-zip',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'data'/'figure-inputs')
    args=p.parse_args(); registry=[]; args.output.mkdir(parents=True,exist_ok=True)
    def read(sha,path,expected=None):
        b=subprocess.check_output(['git','show',sha+':'+path],cwd=args.repo)
        h=hashlib.sha256(b).hexdigest()
        if expected: assert h==expected,(sha,path)
        registry.append(dict(commit=sha,path=path,sha256=h,bytes=len(b)))
        return json.loads(gzip.decompress(b) if b[:2]==b'\x1f\x8b' else b)
    def ref(sha,r): return read(sha,r['path'],r['sha256'])
    def record(sha,path,case,k):
        return next(r for r in read(sha,path)['records'] if r['case_id']==case and r['cores']==k)
    def write(name,d):
        b=(json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n').encode()
        (args.output/(name+'.json.gz')).write_bytes(gzip.compress(b,mtime=0))
    def clean_result(d):
        out={k:v for k,v in d.items() if k not in ('input_graph','input_plan')}
        for c in out['per_core_timeline']:
            for section in ('tasks','subgraphs','ops'):
                for v in c.get(section,[]):
                    assert v['end']>=v['start']>=0
                    assert v['end']-v['start']==v['duration']
                    assert v['end']<=out['makespan']
        assert max(o['end'] for c in out['per_core_timeline'] for o in c['ops'])==out['makespan']
        return out
    zip_sources=[]
    with zipfile.ZipFile(args.cases_zip) as z:
        graphs={}
        for i in range(1,101):
            case=f'{i:03d}'; b=z.read('data/case_'+case+'.json'); g=json.loads(b)
            zip_sources.append(dict(member='data/case_'+case+'.json',sha256=hashlib.sha256(b).hexdigest(),bytes=len(b)))
            if case in ('026','019','021'): graphs[case]=g
        graph_stats=[]
        for item in zip_sources:
            g=json.loads(z.read(item['member'])); eligible=[x for x in g['ops'] if x['op'] not in ('COPY_IN','COPY_OUT')]
            graph_stats.append(dict(case_id=item['member'][-8:-5],ops=len(eligible),tensors=len(g['tensors']),
                edges=len(g['edges']),tensor_bytes=sum(x['size'] for x in g['tensors']),
                matrix_cycles=sum(x['cycles'] for x in eligible if x['pipe']=='PIPE_M'),
                vector_cycles=sum(x['cycles'] for x in eligible if x['pipe']=='PIPE_V')))
    graph_hash={x['member'][-8:-5]:x['sha256'] for x in zip_sources}
    new=record(P1,ROOT1+'/board-feed.json','026',5)
    oldfeed=read(OLD1,OLDROOT+'/board-feed-500.json')
    old=next(r for r in oldfeed['records'] if r['case_id']=='026' and r['cores']==5)
    for f in ('graph_sha256','config_sha256','official_sha256'):
        assert new['identity'][f]==old['identity'][f]
    assert new['identity']['graph_sha256']==graph_hash['026']
    diag=read(P1,ROOT1+'/cells/026-k5/originals/diagnostics.json.gz')
    assert diag['parent_plan_sha256']==old['identity']['plan_sha256']
    p1=dict(case_id='026',cores=5,graph=graphs['026'],parent_matches_old_plan_bytes=True,
       diagnostic={k:diag[k] for k in ('parent_plan_sha256','selected_plan_sha256','parent_objective','selected_objective')},
       constructor=diag['attempt']['constructor_diagnostics'])
    for label,r,s in [('old',old,OLD1),('new',new,P1)]:
        p1[label]=dict(plan=ref(s,r['artifacts']['plan']),result=clean_result(ref(s,r['artifacts']['result'])),identity=r['identity'])
    write('p1-026-k5',p1)
    write('p1-old-metrics',[{k:r[k] for k in ('case_id','cores','metrics')} for r in oldfeed['records']])
    r=record(P2,ROOT2+'/cases-011-020/board-feed.json','019',5)
    assert r['identity']['graph_sha256']==graph_hash['019']
    ledger=read(P2,'results/a/q2-nikolastarx/c04-six-e0-20260926/ledger.json')
    c04=next(x for x in ledger['rows'] if x['case']=='019')
    plan=read(P2,'results/a/q2-nikolastarx/c04-six-pilot-preparation-20260926/019-k5-plan.json',c04['plan_sha256'])
    result=read(P2,'results/a/q2-nikolastarx/c04-six-e0-20260926/019-k5/result.json.gz')
    assert c04['graph_sha256']==r['identity']['graph_sha256']
    assert result['makespan']==c04['makespan']
    write('p2-019-k5',dict(case_id='019',cores=5,graph=graphs['019'],
          control=dict(plan=ref(P2,r['artifacts']['plan']),result=clean_result(ref(P2,r['artifacts']['result'])),identity=r['identity']),
          c04=dict(plan=plan,result=clean_result(result),plan_sha256=c04['plan_sha256'])))
    r=record(P3,ROOT3+'/board-feed-s03-revision2.json','021',3)
    for f in ('graph_sha256','config_sha256','official_sha256','plan_sha256'):
        assert r['cache_pair'][f]==r['identity'][f]
    assert r['identity']['graph_sha256']==graph_hash['021']
    write('p3-021-k3',dict(case_id='021',cores=3,identity=r['identity'],plan=ref(P3,r['artifacts']['plan']),
          no_l2=clean_result(ref(P3,r['cache_pair']['result'])),cache=clean_result(ref(P3,r['artifacts']['result']))))
    auditroot='results/a/q2-nikolastarx/hypergap-full500-audit-20260925'
    write('p2-audit',read(P2,auditroot+'/report.json'))
    completed=read(P2,auditroot+'/completed-summary.json')
    write('p2-comparison',completed['rows'])
    write('dataset',graph_stats)
    manifest=dict(evaluator_calls=0,solver_calls=0,source_objects=registry,graph_members=zip_sources,
      case_selection={'p1':'Smallest compute-op count among branch-aid-selected K5 graphs; representative structure, not maximum gain. Old v4 bytes exactly match selected parent.',
                      'p2':'C04 lower-copy slower counterexample, case 019/K5; six-case negative ablation, not a full new algorithm.',
                      'p3':'First lexicographic negative same-plan Cache case, 021/K3; all 500 points also shown.'})
    (args.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='passed',sources=len(registry),graphs=100,evaluator_calls=0)))

if __name__=='__main__': main()
