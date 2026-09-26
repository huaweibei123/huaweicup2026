# Portable post-run reproduction copy; changes and original-copy hash are in root-readback.json.
from pathlib import Path
from datetime import datetime, timezone
import ctypes, gzip, hashlib, json, os, platform, shutil, subprocess, sys, time
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
if (OUT/'run.json').exists():
 raise FileExistsError('sealed static audit: do not overwrite or rerun')
EXPECTED_HEAD='fc2adb027c2e3bfbb1f03b88a38b12ab6eed9238'
MODEL_COMMIT='68fbe66e97f78161bfb6f4f9e83cd2f0977ce7a9'
PINNED={'docs/a/q3-yuanzhifang/STAIR_STATIC_AUDIT.md':EXPECTED_HEAD,'src/q3_yuanzhifang/stair_audit.py':EXPECTED_HEAD}
MODEL_FILES=['tail_stair_model.py','tail_phase_model.py','tail_fifo_bound.py','wave_tail.py','wave_capacity.py','active_stages.py','construct.py','baseline.py']
PINNED.update({'src/q3_yuanzhifang/'+x:MODEL_COMMIT for x in MODEL_FILES})
GRAPH=Path('../huaweicup2026/data/raw/a/official-cases/data/case_067.json')
CONFIG=Path('data/raw/a/official/data/config.txt')
CMD=['.venv/Scripts/python.exe','-X','utf8','-B','-m','src.q3_yuanzhifang.stair_audit',GRAPH.as_posix(),'--cores','5','--config',CONFIG.as_posix(),'--incumbent','12237901']
sha=lambda b:hashlib.sha256(b).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
def gitbytes(rev,path): return subprocess.run(['git','show',f'{rev}:{path}'],cwd=ROOT,capture_output=True,check=True).stdout
def memory_bytes():
 class S(ctypes.Structure):
  _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ('total_phys','avail_phys','total_page','avail_page','total_virtual','avail_virtual','avail_extended')]
 s=S(); s.length=ctypes.sizeof(s)
 if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)): return None
 return s.avail_phys
start_utc=now(); gate={'available_phys_bytes':None,'free_disk_bytes':None,'minimum_phys_bytes':1073741824,'minimum_disk_bytes':268435456,'passed':False}
source_checks={}
for path,rev in PINNED.items():
 b=(ROOT/path).read_bytes(); ref=gitbytes(rev,path)
 source_checks[path]={'commit':rev,'working_sha256':sha(b),'commit_sha256':sha(ref),'matches':b==ref,'bytes':len(b)}
head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
graph_bytes=(ROOT/GRAPH).read_bytes(); config_bytes=(ROOT/CONFIG).read_bytes()
base={'schema':'q3-stair-static-supervisor-v1','started_at_utc':start_utc,'finished_at_utc':None,'status':'stopped','head':head,'expected_head':EXPECTED_HEAD,'head_note':'branch HEAD recorded for context; fixed source bytes are verified individually against pinned commits','source_checks':source_checks,'command':CMD,'cwd':'.','timeout_seconds':10,'retries':0,'environment':{'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'TMP':'<output-dir>','PYTHONDONTWRITEBYTECODE':'1'},'graph_sha256':sha(graph_bytes),'expected_graph_sha256':'f49b5087689e18c6bf231843f8f3bbaca238a547ea5309b2492c76d5f170b542','config_sha256':sha(config_bytes),'expected_config_sha256':'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9','resource_gate':gate,'calls':{'static_analysis':0,'submission_constructor':0,'derive':0,'Step':0,'E0':0,'E1':0,'E2':0}}
identity_ok=all(x['matches'] for x in source_checks.values()) and base['graph_sha256']==base['expected_graph_sha256'] and base['config_sha256']==base['expected_config_sha256']
if not identity_ok: base['stop_reason']='fixed source/input identity mismatch'
else:
 try: gate['available_phys_bytes']=memory_bytes(); gate['free_disk_bytes']=shutil.disk_usage(OUT).free
 except Exception as e: gate['error']=type(e).__name__
 gate['passed']=gate['available_phys_bytes'] is not None and gate['available_phys_bytes']>=gate['minimum_phys_bytes'] and gate['free_disk_bytes'] is not None and gate['free_disk_bytes']>=gate['minimum_disk_bytes']
 if gate['passed']:
  env=dict(os.environ,TMP=str(OUT),TEMP=str(OUT),PYTHONDONTWRITEBYTECODE='1'); t=time.perf_counter(); base['process_started_at_utc']=now(); base['calls']['static_analysis']=1
  try:
   p=subprocess.run(CMD,cwd=ROOT,env=env,capture_output=True,timeout=10)
   stdout,stderr,code=p.stdout,p.stderr,p.returncode
  except subprocess.TimeoutExpired as e:
   stdout=e.stdout or b''; stderr=e.stderr or b''; code=None; base['timed_out']=True
  base['external_process_wall_seconds']=time.perf_counter()-t; base['process_finished_at_utc']=now(); base['exit_code']=code
  for name,data in [('stdout.json',stdout),('stderr.txt',stderr)]:
   comp=gzip.compress(data,mtime=0); file=OUT/(name+'.gz'); file.write_bytes(comp)
   base[name]={'path':file.name,'raw_sha256':sha(data),'raw_bytes':len(data),'gzip_sha256':sha(comp),'gzip_bytes':len(comp)}
  if code==0 and not base.get('timed_out'):
   try:
    a=json.loads(stdout); base['analysis']=a; base['body_wall_seconds']=a.get('analysis_body_wall_seconds')
    g=json.loads(graph_bytes); ops={x['id']:x for x in g['ops']}; tids={x['id'] for x in g['tensors']}; edges={(x['source'],x['target']) for x in g['edges']}; adj={}
    for s,d in edges: adj.setdefault(s,set()).add(d)
    orig=[e for e in a['path_edges'] if 'original' in e.get('kinds',[])]
    fifo=[e for e in a['path_edges'] if 'fifo' in e.get('kinds',[])]
    orig_ok=[(e['source'],e['target']) in edges or any(t in tids and (e['source'],t) in edges and (t,e['target']) in edges for t in adj.get(e['source'],())) for e in orig]
    fifo_ok=[e['source'] in ops and e['target'] in ops and e['source']!=e['target'] and ops[e['source']].get('pipe')==ops[e['target']].get('pipe') for e in fifo]
    work=sum(ops[i].get('cycles',0) for i in a['path'] if i in ops and ops[i].get('cycles',0)>0)
    base['readback']={'path_positive_cycles':work,'equals_bound':work==a.get('lower_bound_cycles'),'original_edges_verified':sum(orig_ok),'original_edges_total':len(orig),'fifo_edges_same_pipe_distinct_op':sum(fifo_ok),'fifo_edges_total':len(fifo),'cuts_match_pro':[0,20,44,66,94,124]==a.get('cuts'),'U_match_pro':[6,6,5,5,6]==a.get('U'),'h_match_pro':a.get('h')==2,'first_wave_match_pro':[2,3,4,5,6]==a.get('first_wave_sizes')}
    base['status']='ok' if all(orig_ok) and all(fifo_ok) else 'readback_failed'
   except Exception as e: base['readback_error']=type(e).__name__; base['status']='readback_failed'
  else: base['stop_reason']='static analysis timeout or nonzero exit'
 else: base['stop_reason']='RAM/disk below gate or unknown; no subprocess dispatched'
base['finished_at_utc']=now()
(OUT/'run.json').write_text(json.dumps(base,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
readme='''# Stair static audit\n\nOne 067/k5 compute-order analysis only. This is a necessary-bound certificate, not a plan or E0 result. The run receipt records pinned source/input identity, resource gate, command, process wall, body time, and stdout/stderr raw and gzip hashes. FIFO validation checks endpoint pipes/IDs only; it does not independently prove a full schedule projection. Bound derivation is not reproved here. Future cold construction must recompute this analysis.\n'''
(OUT/'README.md').write_text(readme,encoding='utf-8')
print(json.dumps({'status':base['status'],'stop_reason':base.get('stop_reason'),'gate':gate,'calls':base['calls'],'readback':base.get('readback')},ensure_ascii=False))
