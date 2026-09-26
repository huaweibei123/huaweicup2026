import json,time,sys
from pathlib import Path
from scan import ROOT,index_graph
from product import bundle_products
from construct import make
from evidence import run_e0
OUT=Path('/mnt/data/r2_research/runs/first')
# Frozen exploratory matrix, before any E0 values seen. Not a sealed test.
cases=[11,27,37,80,44,78,1,8,51,64]
rows=[]
for case in cases:
 graph=ROOT/f'data/case_{case:03d}.json';g=json.loads(graph.read_text());a=index_graph(g)
 specs=[('whole',{'kind':'whole'}),('topo4',{'kind':'topo'}),('comp_lpt',{'kind':'component'}),('comp_rr',{'kind':'component','assignment':'rr'}),('wave_all_band4',{'kind':'component','band':4}),('wave_all_band16',{'kind':'component','band':16}),('wave4_band4',{'kind':'component','wave':4,'band':4})]
 ps=[p for p in bundle_products(a)['products'] if min(p['shape'])>1]
 if len(ps)==1 and len(ps[0]['jobs'])==len(a['components']):
  R,C=ps[0]['shape']
  for nr,nc in [(4,1),(1,4),(2,2)]:
   if nr<=R and nc<=C:
    for band in [0,2,8]:specs.append((f'grid{nr}x{nc}_band{band}',{'kind':'component','assignment':'product','grid':(nr,nc),'band':band}))
 for problem in [1,2,3]:
  seen=set()
  for name,spec in specs:
   tt=time.perf_counter();plan=make(a,4,spec);ctime=time.perf_counter()-tt
   sig=json.dumps(plan,sort_keys=True)
   if sig in seen:continue
   seen.add(sig)
   out=OUT/f'case_{case:03d}_p{problem}_{name}'
   r=run_e0(graph,plan,problem,out,timeout=25,compress=True);r.update(case=case,name=name,spec=spec,construction_seconds=ctime)
   rows.append(r);print(case,problem,name,r['status'],r.get('makespan'),round(r['official_cli_seconds'],3),r.get('movement',{}).get('spill_added_copy_bytes'),flush=True)
   (OUT/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
