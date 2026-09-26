"""Attach frozen official single-core denominators to the completed P3 feed; no scoring."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE='6fcec11ccc472a1a652b21feb6fccf85a4555598'
AREA=ROOT/'results/a/q3-nikolastarx/calendar-full500-20260925-s59'

def blob(path):return subprocess.check_output(['git','show',f'{BASE}:{path}'],cwd=ROOT)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def ref(path):return {'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path.read_bytes())}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 source=a.source.resolve();out=a.output.resolve()
 if not source.is_relative_to(AREA) or out.parent!=source.parent or out.exists():p.error('source/output must share fresh batch directory')
 feed=json.loads(source.read_text());rows=feed['records']
 if len(rows)!=500 or {r['baseline'] for r in rows}!={None}:raise RuntimeError('expected 500 rows without baseline')
 refs={};ids={}
 for n in range(1,101):
  c=f'{n:03d}';base=f'results/benchmark-board/official-singlecore-20260924/{c}'
  rraw=blob(base+'/run.json');zraw=blob(base+'/result.json.gz')
  run=json.loads(rraw);result=json.loads(gzip.decompress(zraw))
  if run['status']!='ok' or run['entrypoint']!='singlecore_evaluate.evaluate_singlecore' or result['scene']!='A' or result['num_cores']!=1 or result['makespan']!=run['makespan_cycles'] or sha(zraw)!=run['artifacts']['result.json']['sha256']:
   raise RuntimeError(f'baseline {c} invalid')
  folder=source.parent/'baseline'/c;folder.mkdir(parents=True,exist_ok=False)
  (folder/'run.json').write_bytes(rraw);(folder/'result.json.gz').write_bytes(zraw)
  refs[c]=ref(folder/'result.json.gz')
  ids[c]=(run['graph_sha256'],run['config_sha256'],run['official_code_hash'])
 for row in rows:
  case=row['case_id'];identity=row['identity']
  if tuple(identity[k] for k in ('graph_sha256','config_sha256','official_sha256'))!=ids[case]:
   raise RuntimeError(f'baseline identity differs: {case}')
  row['baseline']={'graph_sha256':identity['graph_sha256'],'config_sha256':identity['config_sha256'],
                   'official_sha256':identity['official_sha256'],'route':'E0',
                   'entrypoint':'singlecore_evaluate.evaluate_singlecore','result':refs[case]}
  row['notes'].append(f'Official single-core denominator copied byte-for-byte from {BASE}:results/benchmark-board/official-singlecore-20260924/{case}/result.json.gz; no baseline rerun.')
 out.write_text(json.dumps(feed,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'feed':out.relative_to(ROOT).as_posix(),'records':len(rows),'baseline_unique':len(refs),'sha256':sha(out.read_bytes()),'new_calls':0}))
if __name__=='__main__':main()
