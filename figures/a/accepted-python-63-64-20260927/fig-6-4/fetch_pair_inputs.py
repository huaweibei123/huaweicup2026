"""Read-only GitHub source recovery. Requires own gh login. No solver/E0 and no Git writes.
python fetch_pair_inputs.py --out ./verified-inputs --probe
python fetch_pair_inputs.py --out ./verified-inputs
"""
import argparse,base64,gzip,hashlib,json,subprocess,time
from pathlib import Path
from urllib.parse import quote
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);parser.add_argument('--probe',action='store_true');args=parser.parse_args();O=args.out.resolve();O.mkdir(parents=True,exist_ok=True)
REPO='repos/huaweibei123/huaweicup2026/'
F='19bebf35205d23fdd832781540f8879da52eeb62';D='cf4d77a018def540358c3b4667c2d2466390981a';P2='11d5d3ba1820864626bb49acccbeec7a75553e80';OLD='f0ead1a3722f70a59a084acc70700a963945b567'
FB='results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee';DB='results/a/q3-nikolastarx/forest-cachepair-delta-20260925/20260924T2205Z-s3172'
sha=lambda b:hashlib.sha256(b).hexdigest()
def api(path):
 for attempt in range(3):
  r=subprocess.run(['gh','api',REPO+path],capture_output=True)
  if r.returncode==0:return json.loads(r.stdout)
  if attempt==2:raise RuntimeError(r.stderr.decode('utf-8',errors='replace'))
  time.sleep(2)

trees={}
def locate(commit,path):
 if commit not in trees:
  tree=api('git/trees/'+commit+'?recursive=1')
  trees[commit]={r['path']:r for r in tree['tree'] if r['type']=='blob'}
 # A truncated tree is not proof of missing data. Fall back to exact contents metadata.
 return trees[commit].get(path) or api('contents/'+quote(path,safe='/')+'?ref='+commit)
def get(commit,path,want=None,blob=None):
 key=commit+'/'+path;target=O/'bytes'/(sha(key.encode())[:24]+''.join(Path(path).suffixes))
 if target.is_file() and want and sha(target.read_bytes())==want:return target.read_bytes()
 info=locate(commit,path) if blob is None else {'sha':blob}
 value=api('git/blobs/'+info['sha']);assert value['encoding']=='base64'
 raw=base64.b64decode(value['content']);assert len(raw)==value['size']>0
 assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==info['sha']
 assert not want or sha(raw)==want,(path,'SHA256 mismatch')
 target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_name(target.name+'.partial');tmp.write_bytes(raw);tmp.replace(target)
 index_path=O/'source-index.json';index=json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {};index[key]={'local':str(target.relative_to(O)),'sha256':sha(raw),'blob':info['sha'],'bytes':len(raw)};index_path.write_text(json.dumps(index,indent=2),encoding='utf-8')
 return raw
# Empty contents payload is NOT evidence of missing data: always retrieve git/blobs.
summary=get('1c00079aadbd071de62db17686d5ba3fed1da0f2','results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json','083c3f5b603cb61dd8b132718b6437b35c7706ff3aa165bdcdd490617547a2f2','0e027252b773c232d4271a0229d5537f3511641f');json.loads(summary)
m=json.loads(get(D,'results/a/q3-nikolastarx/forest-cachepair-delta-20260925/manifest.json','3c2f7854c88d4d1eb83e47c1b6058394bbc95a550f0cd797612817855116bba8','0b90146b2175fb5aad120653492e8f387f9de439'))
run=json.loads(get(D,DB+'/run.json',blob='cd72a9c6aee583c8f902bfff355f5db28aa51919'));jobs={j['coordinate']:j for j in run['jobs']};assert len(jobs)==24 and all(j['status']=='ok' for j in jobs.values())
feeds=[]
for n in range(1,11):feeds+=json.loads(get(F,FB+f'/revision2-baseline-draft/board-feed-s{n:02}-revision2.json'))['records']
feed={(r['case_id'],r['cores']):r for r in feeds};assert len(feed)==len(feeds)==500
assert all(r['revision']==2 and r['status']=='ok' and r['solver_commit']=='311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1' for r in feeds)
records=m['records'];assert len(records)==500
if args.probe:records=[next(r for r in records if r['action']=='reuse_existing_p2'),next(r for r in records if r['action']!='reuse_existing_p2')]
receipt=[]
for r in records:
 case,k=r['case_id'],r['cores'];coord=f'{case}-k{k}';f=feed[(case,k)];plan=get(F,r['forest_plan']['path'],r['forest_plan']['sha256']);assert f['artifacts']['plan']['sha256']==sha(plan)
 fr=f['artifacts']['result'];raw3=get(F,fr['path'],fr['sha256']);v3=json.loads(gzip.decompress(raw3))
 if r['action']=='reuse_existing_p2':
  oldplan=get(OLD,r['c2_plan']['path'],r['c2_plan']['sha256']);assert oldplan==plan
  z=r['reused_p2'];assert z['source_plan_sha256']==sha(plan);raw2=get(P2,z['path'],z['sha256']);v2=json.loads(gzip.decompress(raw2));assert v2['makespan']==z['historical_no_l2_makespan']
 else:
  j=jobs[coord];assert j['graph_sha256']==r['graph_sha256'] and j['plan_sha256']==sha(plan)
  assert get(D,DB+'/cells/'+coord+'/plan.json',j['plan_sha256'])==plan
  raw2=get(D,DB+'/cells/'+coord+'/result.json.gz',j['result_sha256']);v2=json.loads(gzip.decompress(raw2));assert v2['makespan']==j['makespan']
 assert v2['num_cores']==v3['num_cores']==k and v2['scene']==v3['scene']=='B' and 'cache_stats' not in v2 and v3['problem']==3
 cache=v3['cache_stats'];row=dict(case=case,cores=k,plan_sha256=sha(plan),p2_sha256=sha(raw2),p3_sha256=sha(raw3),no_l2_makespan=v2['makespan'],cache_makespan=v3['makespan'],hit_bytes=cache['hit_bytes'],miss_bytes=cache['miss_bytes']);receipt.append(row)
 (O/('probe-receipt.json' if args.probe else 'verified-pairs.json')).write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(coord,'verified',flush=True)
assert len(receipt)==(2 if args.probe else 500)
print('DONE',len(receipt),'pairs; completed-summary SHA verified; no experiments executed.')
