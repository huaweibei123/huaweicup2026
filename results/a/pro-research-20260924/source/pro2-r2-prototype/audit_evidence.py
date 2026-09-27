"""Audit existing artifacts without invoking or changing the official evaluator."""
import json,gzip,hashlib,time,collections,csv
from pathlib import Path
R=Path('/mnt/data/r2_research');O=Path('/mnt/data/r2_bundle/data/raw/a/official')
sha=lambda b:hashlib.sha256(b).hexdigest()
t=time.perf_counter(); errors=[];rows=[];statuses=collections.Counter();problems=collections.Counter();formal=set();uncompressed=0
manifest=json.loads(Path('/mnt/data/r2_bundle/docs/a/source-manifest.json').read_text())
for f in manifest['files']:
 p=O/f['path']
 if not p.exists() or sha(p.read_bytes())!=f['sha256']:errors.append(['official_hash',f['path']])
frozen=json.loads((R/'runs/paired/FROZEN_PROTOCOL.json').read_text())
for p,h in frozen['frozen_source_hashes'].items():
 if sha((R/'src'/p).read_bytes())!=h:errors.append(['frozen_source_hash',p])
for p in sorted((R/'runs').rglob('run.json')):
 d=json.loads(p.read_text());statuses[d['status']]+=1;problems[str(d['problem'])]+=1
 graph=Path(d['graph']);plan=p.parent/'plan.json';gbytes=graph.read_bytes()
 if sha(gbytes)!=d['graph_hash']:errors.append(['graph_hash',str(p)])
 if sha(plan.read_bytes())!=d['plan_hash']:errors.append(['plan_hash',str(p)])
 if graph.name.startswith('case_'):formal.add(graph.stem)
 for name,a in d['artifacts'].items():
  ap=p.parent/name
  if ap.exists(): b=ap.read_bytes()
  elif Path(str(ap)+'.gz').exists():b=gzip.decompress(Path(str(ap)+'.gz').read_bytes())
  else:errors.append(['missing_artifact',str(ap)]);continue
  if sha(b)!=a['sha256'] or len(b)!=a['bytes']:errors.append(['artifact_identity',str(ap)])
  if name.endswith('.json'):obj=json.loads(b)
  if name=='result.json':
   if obj['makespan']!=d.get('makespan'):errors.append(['makespan',str(p)])
  uncompressed+=len(b)
 for x in ['stdout.txt','stderr.txt']:
  if not (p.parent/x).exists():errors.append(['missing_capture',str(p.parent/x)])
 rows.append({'run':str(p.relative_to(R)),'case':graph.stem,'problem':d['problem'],'cores':d['cores'],'status':d['status'],'makespan':d.get('makespan'),'official_cli_seconds':d['official_cli_seconds'],'plan_hash':d['plan_hash'],'graph_hash':d['graph_hash']})
report={'official_files_verified':len(manifest['files']),'official_code_hash':manifest['official_code_hash'],'frozen_source_files_verified':len(frozen['frozen_source_hashes']),'official_cli_calls':len(rows),'statuses':dict(statuses),'calls_by_problem':dict(problems),'formal_case_count':len(formal),'formal_cases':sorted(formal),'artifact_uncompressed_bytes_verified':uncompressed,'errors':errors,'elapsed_seconds':time.perf_counter()-t,'scope':'full saved official JSON/Trace/log identities, original official raw bytes, frozen constructor source; not independent re-execution or all-input proof'}
(R/'audit/final_evidence_audit.json').write_text(json.dumps(report,indent=2)+'\n')
with (R/'analysis/experiment_inventory.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(report,indent=2));raise SystemExit(bool(errors))
