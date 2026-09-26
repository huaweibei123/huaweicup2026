#!/usr/bin/env python3
"""Export frozen paper tables. Read-only Git extraction; zero solver/evaluator calls.

Primary metrics for P1/P2/P3 come from author-audited fixed feeds. This script
checks their full grids, denominator bytes/identities and P3 paired E0 bytes.
It does not pretend to rerun the existing full plan/result audit or E0.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import subprocess

P1 = 'a1bb4451cd85c46b32bb928d57c81e22cfeca1a6'
P2 = '00d311ed0eea0fd86f9840df406956041a7c192a'
P3 = '19bebf35205d23fdd832781540f8879da52eeb62'
FINAL = '8416300c7245925795aaa3acc64d4d5b31fa13d5'
ROOT1 = 'results/a/p1-branch-refine-full500-20260925/20260925T1525Z-s6607-branch-full500'
ROOT2 = 'results/a/q2-nikolastarx/hypergap-full500-archive-20260924T233302Z-s8ee'
ROOT3 = 'results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft'
SOLVERS = {'P1':'834d8c957538ee069c66aadac9509552a4cc69d7',
           'P2':'c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f',
           'P3':'311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1'}
EXPECTED = {'P1':[1.0020968223600535,1.9515526412540207,2.7513994578887306,3.4785940988945776,4.055266985790237],
            'P2':[1.2061392350623783,2.3167268583014735,3.2355656076453716,3.9711493100640376,4.549756996698352],
            'P3':[1.1997595678587545,2.312002295129782,3.258687134445883,4.091503001561421,4.7576166788448955]}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[3])
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'data')
    args=parser.parse_args(); registry={}; cache={}; baseline_by_graph={}
    def blob(sha,path):
        b=subprocess.check_output(['git','show',sha+':'+path],cwd=args.repo)
        registry[(sha,path)]={'commit':sha,'path':path,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
        return b
    def decode(b):
        return json.loads(gzip.decompress(b) if b[:2]==b'\x1f\x8b' else b)
    def checked(sha,ref):
        key=(sha,ref['path'])
        if key not in cache:
            b=blob(*key)
            assert hashlib.sha256(b).hexdigest()==ref['sha256'],key
            d=decode(b)
            # Keep scalars only; large per-operation result arrays are not needed.
            cache[key]={k:d[k] for k in ('makespan','num_cores','scene','data_movement_bytes') if k in d}
        return cache[key]
    groups={'P1':[(P1,ROOT1+'/board-feed.json')],
            'P2':[(P2,f'{ROOT2}/cases-{i:03d}-{i+9:03d}/board-feed.json') for i in range(1,101,10)],
            'P3':[(P3,f'{ROOT3}/board-feed-s{i:02d}-revision2.json') for i in range(1,11)]}
    rows=[]
    for problem,sources in groups.items():
        seen=set()
        for sha,path in sources:
            for rec in decode(blob(sha,path))['records']:
                key=(rec['case_id'],rec['cores']); assert key not in seen;seen.add(key)
                assert rec['status']=='ok' and rec['solver_commit']==SOLVERS[problem]
                ident=rec['identity'];base=rec['baseline']
                for f in ('graph_sha256','config_sha256','official_sha256'):assert base[f]==ident[f]
                b=checked(sha,base['result'])['makespan'];assert b>0
                old=baseline_by_graph.setdefault(ident['graph_sha256'],b);assert old==b
                m=rec['metrics'];assert m['makespan_cycles']>0
                row={'problem':problem,'case_id':key[0],'cores':key[1],
                     'baseline_cycles':b,'makespan_cycles':m['makespan_cycles'],
                     'extra_ddr_bytes':m['extra_ddr_bytes'],'scheduled_copy_bytes':m['ddr_bytes'],
                     'spill_bytes':m.get('spill_bytes'),'solver_wall_seconds':m['solver_wall_seconds'],
                     'external_evaluation_seconds':m.get('evaluation_wall_seconds'),
                     'baseline_speedup':b/m['makespan_cycles'],
                     'official_curve_speedup':1.0 if problem in ('P1','P2') and key[1]==1 else b/m['makespan_cycles'],
                     'no_l2_makespan_cycles':None,'no_l2_extra_ddr_bytes':None,'cache_gain':None,
                     'cache_hit_rate_bytes':m.get('cache_hit_rate'),
                     'graph_sha256':ident['graph_sha256'],'plan_sha256':ident['plan_sha256'],
                     'solver_commit':rec['solver_commit'],'source_commit':sha,'feed_path':path}
                if problem=='P3':
                    pair=rec['cache_pair']
                    for f in ('graph_sha256','config_sha256','official_sha256','plan_sha256'):assert pair[f]==ident[f]
                    assert pair['cores']==key[1]
                    result=checked(sha,pair['result'])
                    assert result['scene']=='B' and result['num_cores']==key[1]
                    row.update(no_l2_makespan_cycles=result['makespan'],
                               no_l2_extra_ddr_bytes=result['data_movement_bytes']['added_copy_bytes'],
                               cache_gain=result['makespan']/m['makespan_cycles'])
                rows.append(row)
        assert seen=={(f'{i:03d}',k) for i in range(1,101) for k in range(1,6)},problem
    comp=blob(FINAL,'results/a/q3-nikolastarx/r9f-final-full500-20260926/final-export-20260926/comparison.csv')
    comparison={(x['case_id'],int(x['cores'])):x for x in csv.DictReader(io.StringIO(comp.decode()))}
    for row in rows:
        if row['problem']=='P3':
            c=comparison[(row['case_id'],row['cores'])]
            assert int(c['forest_m3'])==int(c['final_m3'])==row['makespan_cycles']
            assert int(c['forest_m2'])==int(c['final_m2'])==row['no_l2_makespan_cycles']
            assert abs(float(c['cache_hit_rate_bytes'])-row['cache_hit_rate_bytes'])<1e-12
    summary={}
    def stats(values):
        xs=sorted(values)
        return {'n':len(xs),'mean':statistics.fmean(xs),'median':statistics.median(xs),
                'p95_nearest_rank':xs[math.ceil(.95*len(xs))-1],'max':xs[-1]}
    for problem in groups:
        part=[x for x in rows if x['problem']==problem];cores={}
        for k in range(1,6):
            subset=[x for x in part if x['cores']==k];mean=statistics.fmean(x['baseline_speedup'] for x in subset)
            assert abs(mean-EXPECTED[problem][k-1])<1e-10,(problem,k,mean)
            cores[k]={'count':len(subset),'mean_baseline_speedup':mean,
                      'mean_official_curve_speedup':statistics.fmean(x['official_curve_speedup'] for x in subset),
                      'extra_ddr_bytes_sum':sum(x['extra_ddr_bytes'] for x in subset),
                      'solver_wall_seconds':stats([x['solver_wall_seconds'] for x in subset])}
            if problem=='P3':cores[k].update(mean_cache_gain=statistics.fmean(x['cache_gain'] for x in subset),
                  mean_byte_hit_rate=statistics.fmean(x['cache_hit_rate_bytes'] for x in subset),
                  mean_no_l2_baseline_speedup=statistics.fmean(x['baseline_cycles']/x['no_l2_makespan_cycles'] for x in subset))
        summary[problem]={'solver_commit':SOLVERS[problem],'cores':cores,
                          'solver_wall_seconds':stats([x['solver_wall_seconds'] for x in part])}
    args.output.mkdir(parents=True,exist_ok=True)
    with (args.output/'all-results.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(sorted(rows,key=lambda x:(x['problem'],x['case_id'],x['cores'])))
    (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    receipt={'scope':'author-audited feeds; exact grids; raw denominator SHA/identity; raw P3 paired results SHA/identity; cross-check final CSV; no full plan re-audit and no new evaluation',
             'rows':len(rows),'per_problem':500,'solver_calls':0,'evaluator_calls':0,
             'all_results_sha256':hashlib.sha256((args.output/'all-results.csv').read_bytes()).hexdigest(),
             'sources':list(registry.values())}
    (args.output/'source-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'rows':len(rows),'sources_read':len(registry),'status':'passed','evaluator_calls':0}))

if __name__=='__main__':main()
