"""Normalize independently verified raw cache-pair measurements; no experiments."""
import argparse
import csv
import hashlib
import json
import statistics
from pathlib import Path

BASELINE_SHA='554cf090aaf0460465d07b8d52640e098447a3b00cc7b89f4371feb4f2c048d6'


def prepare(verified,baseline,out):
    if hashlib.sha256(baseline.read_bytes()).hexdigest()!=BASELINE_SHA:
        raise ValueError('Fixed official-A baseline source differs')
    with baseline.open(encoding='utf-8-sig',newline='') as f:
        base={r['case_id']:int(r['baseline_cycles']) for r in csv.DictReader(f)}
    records=json.loads(verified.read_text(encoding='utf-8'))
    if len(records)!=500 or {(r['case_id'],r['cores']) for r in records}!={(f'{c:03d}',k) for c in range(1,101) for k in range(1,6)}:
        raise ValueError('Expected complete unique 100×5 grid')
    rows=[]
    for r in records:
        h,m=r['hit_bytes'],r['miss_bytes'];no,cache=r['makespan_no_l2'],r['makespan_cache']
        if any(type(v)!=int or v<=0 for v in [no,cache]) or any(type(v)!=int or v<0 for v in [h,m]):
            raise ValueError('Invalid cycles or bytes')
        rows.append(dict(case=r['case_id'],cores=r['cores'],baseline=base[r['case_id']],no_cache=no,cache=cache,plan_no=r['plan_sha256'],plan_cache=r['plan_sha256'],config_shared_no=r['config_sha256'],config_shared_cache=r['config_sha256'],hit_bytes=h,miss_bytes=m,cache_gain=no/cache,hit_rate=h/(h+m) if h+m else '',graph_sha256=r['graph_sha256'],no_result_sha256=r['no_l2_result_sha256'],cache_result_sha256=r['cache_result_sha256']))
    summary=[]
    for k in range(1,6):
        g=[r for r in rows if r['cores']==k];rates=[r['hit_rate'] for r in g if r['hit_rate']!=''];h=sum(r['hit_bytes'] for r in g);den=sum(r['hit_bytes']+r['miss_bytes'] for r in g)
        summary.append(dict(cores=k,n=len(g),mean_no_cache_speedup=statistics.mean(r['baseline']/r['no_cache'] for r in g),mean_cache_speedup=statistics.mean(r['baseline']/r['cache'] for r in g),mean_cache_gain=statistics.mean(r['cache_gain'] for r in g),mean_byte_hit_rate=statistics.mean(rates) if rates else '',pooled_byte_hit_rate=h/den if den else ''))
    negative=[dict(case=r['case'],cores=r['cores']) for r in rows if r['cache_gain']<1]
    out.mkdir(parents=True,exist_ok=True)
    for name,data,cols in [('pairs.csv',rows,list(rows[0])),('summary.csv',summary,list(summary[0])),('negative.csv',negative,['case','cores'])]:
        with (out/name).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(data)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verified',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();prepare(a.verified,a.baseline,a.out)
