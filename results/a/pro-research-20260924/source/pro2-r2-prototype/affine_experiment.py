import json,time
from pathlib import Path
from scan import ROOT,index_graph
from construct import make
from evidence import run_e0
OUT=Path('/mnt/data/r2_research/runs/affine');rows=[]
for case in [8,44,78,80,64]:
 graph=ROOT/f'data/case_{case:03d}.json';a=index_graph(json.loads(graph.read_text()))
 for problem in [2,3]:
  for wave in [0,4]:
   for frac in [.125,.25,.5,1.0]:
    spec={'kind':'affine','wave':wave,'lag_fraction':frac};name=f'w{wave}_f{frac}'
    tt=time.perf_counter();plan=make(a,4,spec);ct=time.perf_counter()-tt
    r=run_e0(graph,plan,problem,OUT/f'case_{case:03d}_p{problem}_{name}',timeout=25,compress=True)
    r.update(case=case,name=name,spec=spec,construction_seconds=ct);rows.append(r)
    print(case,problem,name,r['status'],r.get('makespan'),round(r['official_cli_seconds'],3),r.get('movement',{}).get('spill_added_copy_bytes'),flush=True)
    (OUT/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
