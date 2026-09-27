"""Load independent evaluator namespaces; original directory is never modified."""
from pathlib import Path
import sys,types,hashlib,json,threading,gzip,time
ROOT=Path(__file__).resolve().parents[1]
OFF=ROOT/'input_bundle/data/raw/a/official'
NAMES=['contest_io','evaluation_validation','schedule_step1','schedule_step2','schedule_step3','stub_multicore_cut_and_schedule','multicore_cut_evaluate_problem_1','multicore_cut_evaluate_problem_2','multicore_cut_evaluate_problem_3','singlecore_evaluate']
HASH='de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0'
_LOCK=threading.RLock()
def verify():
 rows=''.join(f'code/{p.name}\t{hashlib.sha256(p.read_bytes()).hexdigest()}\n' for p in sorted((OFF/'code').iterdir()) if p.is_file())
 assert hashlib.sha256(rows.encode()).hexdigest()==HASH

def load(code_dir=None):
 code_dir=Path(code_dir or OFF/'code')
 verify()
 with _LOCK:
  saved={n:sys.modules.get(n) for n in NAMES}; mods={}
  try:
   for name in NAMES:
    module=types.ModuleType(name);module.__file__=str(code_dir/(name+'.py'))
    sys.modules[name]=module;mods[name]=module
    exec(compile(Path(module.__file__).read_bytes(),module.__file__,'exec'),module.__dict__)
  finally:
   for name,old in saved.items():
    if old is None:sys.modules.pop(name,None)
    else:sys.modules[name]=old
 return mods

def settings(mods, path=None):
 path=Path(path or OFF/'data/config.txt'); v=mods['evaluation_validation']; cfg=v.read_evaluation_config(path)
 for section,keys in [('multicore_scene_a',('task_cross_core_wait_cycles','task_same_core_wait_cycles')),('multicore_scene_b',('cross_core_copy_delay_cycles',)),('problem_3',('cache_capacity_bytes','cache_bandwidth_bytes_per_cycle'))]:
  cfg.update(v.read_required_settings(path,section,keys))
 return cfg

def evaluate(mods,q,g,p,cfg=None):
 cfg=cfg or settings(mods)
 common=dict(bandwidth=cfg['bandwidth'],capacity=cfg['capacity'])
 if q==0:return mods['singlecore_evaluate'].evaluate_singlecore(g,**common,cross_core_wait=cfg['task_cross_core_wait_cycles'],same_core_wait=cfg['task_same_core_wait_cycles'])
 if q==1:return mods['multicore_cut_evaluate_problem_1'].evaluate_scene_a(g,p,**common,cross_core_wait=cfg['task_cross_core_wait_cycles'],same_core_wait=cfg['task_same_core_wait_cycles'])
 if q==2:return mods['multicore_cut_evaluate_problem_2'].evaluate_scene_b(g,p,**common,cross_core_copy_delay=cfg['cross_core_copy_delay_cycles'])
 return mods['multicore_cut_evaluate_problem_3'].evaluate_problem_3(g,p,**common,cross_core_copy_delay=cfg['cross_core_copy_delay_cycles'],cache_capacity_bytes=cfg['cache_capacity_bytes'],cache_bandwidth_bytes_per_cycle=cfg['cache_bandwidth_bytes_per_cycle'])

def strict_equal(a,b,path='$'):
 if type(a) is not type(b):raise AssertionError((path,'type',type(a).__name__,type(b).__name__))
 if isinstance(a,dict):
  if a.keys()!=b.keys():raise AssertionError((path,'keys',a.keys(),b.keys()))
  for k in a:strict_equal(a[k],b[k],f'{path}.{k}')
 elif isinstance(a,(list,tuple)):
  if len(a)!=len(b):raise AssertionError((path,'len',len(a),len(b)))
  for i,(x,y) in enumerate(zip(a,b)):strict_equal(x,y,f'{path}[{i}]')
 elif isinstance(a,float):
  # No tolerance, signed zero also compared (binary64 bytes).
  import struct
  if struct.pack('!d',a)!=struct.pack('!d',b):raise AssertionError((path,'float',a,b))
 elif a!=b:raise AssertionError((path,a,b))

def save_json(path,obj):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 raw=(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
 if path.suffix=='.gz':
  with path.open('wb') as f:
   with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0,compresslevel=1) as z:z.write(raw)
 else:path.write_bytes(raw)
 return hashlib.sha256(raw).hexdigest()
