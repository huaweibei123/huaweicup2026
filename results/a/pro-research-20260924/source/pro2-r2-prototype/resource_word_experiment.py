"""Data-derived FIFO-word constructor; latest graph 084 was not previously E0-tuned.
Three direct constructors, no search; 4 cores, Q2/Q3, preserve full E0 evidence.
"""
import json,time
from pathlib import Path
from scan import ROOT,index_graph
from construct import make
from resource_word import word_plan
from evidence import run_e0
OUT=Path('/mnt/data/r2_research/runs/resource_word');OUT.mkdir(exist_ok=False)
settings=[(8,2),(95,2),(84,2),(84,3)];rows=[]
(OUT/'PROTOCOL.json').write_text(json.dumps({'settings':settings,'cores':4,'constructors':['components','affine0125','word'],'timeout':40,'selection':'all homogeneous M V* M components detected among 100; 084 new E0 graph, 008/095 exploratory'},indent=2))
for case,q in settings:
 graph=ROOT/f'data/case_{case:03d}.json'
 for name in ['components','affine0125','word']:
  start=time.perf_counter();a=index_graph(json.loads(graph.read_text()));extra=None
  if name=='word':plan,extra=word_plan(a,4)
  else:plan=make(a,4,{'kind':'component'} if name=='components' else {'kind':'affine','lag_fraction':.125})
  ctime=time.perf_counter()-start;dest=OUT/f'case_{case:03d}_p{q}_{name}';r=run_e0(graph,plan,q,dest,timeout=40,official=ROOT,compress=True)
  r.update(case=case,name=name,construction_seconds=ctime,total_seconds=time.perf_counter()-start,word=extra);rows.append(r)
  print(case,q,name,r['status'],r.get('makespan'),r.get('movement',{}).get('spill_added_copy_bytes'),flush=True)
  (OUT/'summary.json').write_text(json.dumps(rows,indent=2))
