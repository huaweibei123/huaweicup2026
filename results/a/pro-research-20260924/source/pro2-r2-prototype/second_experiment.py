import json,time,sys
from pathlib import Path
from scan import ROOT,index_graph
from construct import make
from evidence import run_e0
OUT=Path('/mnt/data/r2_research/runs/heavy')
# Selected single-component and mixed controls BEFORE heavy E0 outputs.
cases=[51,64,69,71,2,19,6,24]
rows=[]
for case in cases:
 graph=ROOT/f'data/case_{case:03d}.json';a=index_graph(json.loads(graph.read_text()))
 for problem in [1,2,3]:
  specs=[('whole',{'kind':'whole'}),('topo4',{'kind':'topo'}),('component',{'kind':'component'}),('topochunk64',{'kind':'topo','chunk':64}),('depthchunk64',{'kind':'topo','chunk':64,'order':'depth'})]
  for tau in [2,64,1024,8192]:specs.append((f'heavy{tau}',{'kind':'heavy','tau':tau,'problem':problem}))
  seen=set()
  for name,spec in specs:
   tt=time.perf_counter();plan=make(a,4,spec);ctime=time.perf_counter()-tt;sig=json.dumps(plan,sort_keys=True)
   if sig in seen:continue
   seen.add(sig)
   r=run_e0(graph,plan,problem,OUT/f'case_{case:03d}_p{problem}_{name}',timeout=25,compress=True)
   r.update(case=case,name=name,spec=spec,construction_seconds=ctime);rows.append(r)
   print(case,problem,name,r['status'],r.get('makespan'),round(r['official_cli_seconds'],3),r.get('movement',{}).get('spill_added_copy_bytes'),flush=True)
   (OUT/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
