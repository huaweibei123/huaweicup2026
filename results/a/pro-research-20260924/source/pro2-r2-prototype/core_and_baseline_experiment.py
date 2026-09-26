"""Additional 2/3/5-core mechanism checks, not a replacement for 100-case coverage."""
import json,time
from pathlib import Path
from scan import ROOT,index_graph
from construct import make
from evidence import run_e0
OUT=Path('/mnt/data/r2_research/runs/core_checks');OUT.mkdir(exist_ok=False);rows=[]
settings=[]
for case in [8,51]:
 for k in [2,3,5]:
  for q in [2,3]:
   settings.append((case,k,q,'components',{'kind':'component'}))
   settings.append((case,k,q,'affine0125' if case==8 else 'heavy2',{'kind':'affine','lag_fraction':.125} if case==8 else {'kind':'heavy','tau':2,'problem':q}))
for alpha in [.03125,.0625]:settings.append((8,4,2,f'affine{alpha}',{'kind':'affine','lag_fraction':alpha}))
for case in [8,44,51,21]:settings.append((case,1,0,'official_singlecore',{'kind':'whole'}))
(OUT/'PROTOCOL.json').write_text(json.dumps(settings,indent=2))
for case,k,q,name,spec in settings:
 start=time.perf_counter();graph=ROOT/f'data/case_{case:03d}.json';a=index_graph(json.loads(graph.read_text()));plan=make(a,k,spec);construct=time.perf_counter()-start
 r=run_e0(graph,plan,q,OUT/f'case_{case:03d}_p{q}_k{k}_{name}',timeout=40,official=ROOT,compress=True)
 r.update(case=case,k=k,name=name,spec=spec,construction_seconds=construct,total_seconds=time.perf_counter()-start)
 rows.append(r);print(case,k,q,name,r['status'],r.get('makespan'),r.get('movement',{}).get('spill_added_copy_bytes'),flush=True)
 (OUT/'summary.json').write_text(json.dumps(rows,indent=2))
