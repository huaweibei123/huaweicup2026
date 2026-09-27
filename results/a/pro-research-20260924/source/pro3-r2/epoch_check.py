"""Read-only profile hooks record every shared-pool helper-return state; not a timing benchmark."""
from runtime import *
from plans import component_plan
import sys
NAMES={'advance_ddr_work','reschedule_ddr','reschedule_ddr_ends','advance_pool_work','reschedule_pool'}
FIELDS={'now','time','ddr_last_update','pool_last_update','ddr_remaining_work','pool_remaining_work','remaining_work','pool','pool_name','cursor','active_count'}
def canon(x):
 if isinstance(x,float):return ['float64',x.hex()]
 if isinstance(x,dict):return ['dict',[[canon(k),canon(v)]for k,v in x.items()]]
 if isinstance(x,(tuple,list)):return [type(x).__name__,[canon(y)for y in x]]
 return x

def observe(mods,q,g,p):
 events=[]
 def hook(frame,event,arg):
  if event=='return' and frame.f_code.co_name in NAMES:
   events.append([frame.f_code.co_name,[(k,canon(v))for k,v in sorted(frame.f_locals.items())if k in FIELDS]])
 sys.setprofile(hook)
 try:r=evaluate(mods,q,g,p)
 finally:sys.setprofile(None)
 return r,events
if __name__=='__main__':
 e=load();f=load(ROOT/'fast_code');g=json.loads((OFF/'data/case_001.json').read_bytes());p=component_plan(g,cores=4);out=ROOT/'results/epochs';out.mkdir(exist_ok=True);rows=[]
 for q in [1,2,3]:
  a,ea=observe(e,q,g,p);b,eb=observe(f,q,g,p);strict_equal(a,b);strict_equal(ea,eb)
  sa=save_json(out/f'q{q}.E0.events.json.gz',ea);sb=save_json(out/f'q{q}.R2.events.json.gz',eb)
  rows.append({'q':q,'events':len(ea),'equal':True,'sha256_json':sa,'R2_sha256_json':sb})
 save_json(out/'summary.json',rows);print(rows)
