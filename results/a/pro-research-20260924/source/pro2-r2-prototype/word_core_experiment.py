import json,time
from pathlib import Path
from scan import ROOT,index_graph
from resource_word import word_plan
from evidence import run_e0
out=Path('/mnt/data/r2_research/runs/word_cores');out.mkdir(exist_ok=False);rows=[]
for case in [8,84]:
 for k in [2,3,5]:
  t=time.perf_counter();g=ROOT/f'data/case_{case:03d}.json';a=index_graph(json.loads(g.read_text()));plan,info=word_plan(a,k);prep=time.perf_counter()-t
  r=run_e0(g,plan,2,out/f'case_{case:03d}_k{k}',official=ROOT,timeout=40,compress=True);r.update(case=case,k=k,word=info,construction_seconds=prep,total_seconds=time.perf_counter()-t);rows.append(r);print(case,k,r['status'],r.get('makespan'),flush=True)
  (out/'summary.json').write_text(json.dumps(rows,indent=2))
