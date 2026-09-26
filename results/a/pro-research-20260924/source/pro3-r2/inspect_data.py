from pathlib import Path
import json,sys,time,collections,hashlib,platform,os
ROOT=Path(__file__).resolve().parents[1]; OFF=ROOT/'input_bundle/data/raw/a/official'
sys.path.insert(0,str(OFF/'code'))
from stub_multicore_cut_and_schedule import _build_op_adjacency,_contract_excluded_copy_nodes
rows=[];start=time.perf_counter()
for path in sorted((OFF/'data').glob('case_*.json')):
 g=json.loads(path.read_bytes()); ops={o['id']:o for o in g['ops']}; elig=sorted(k for k,v in ops.items() if v['op'] not in ('COPY_IN','COPY_OUT'))
 ps,ss=_build_op_adjacency(g); p,s=_contract_excluded_copy_nodes(elig,ss)
 seen=set(); comps=[]
 for v in elig:
  if v in seen: continue
  stack=[v];seen.add(v);c=[]
  while stack:
   u=stack.pop(); c.append(u)
   for w in p[u]|s[u]:
    if w not in seen:seen.add(w);stack.append(w)
  comps.append(c)
 row={'case':path.stem,'n_ops':len(ops),'n_eligible':len(elig),'n_tensors':len(g['tensors']),'edges':len(g['edges']), 'op_edges':sum(map(len,s.values())), 'components':len(comps),'component_sizes':dict(collections.Counter(map(len,comps))), 'pipes':dict(collections.Counter(ops[v]['pipe'] for v in elig)), 'total_cycles':sum(ops[v]['cycles'] for v in elig), 'size_distribution':dict(collections.Counter(t['size'] for t in g['tensors'])), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
 rows.append(row)
 print(row['case'],row['n_eligible'],row['components'],row['component_sizes'],flush=True)
(ROOT/'evidence/data_structure_100.json').write_text(json.dumps({'seconds':time.perf_counter()-start,'rows':rows},indent=2))
(ROOT/'evidence/environment.json').write_text(json.dumps({'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),'cpu_count':os.cpu_count(),'cpuinfo':Path('/proc/cpuinfo').read_text().split('\n\n')[0],'hashseed':os.environ.get('PYTHONHASHSEED'),'threading':'single process, single Python thread for timings'},indent=2))
