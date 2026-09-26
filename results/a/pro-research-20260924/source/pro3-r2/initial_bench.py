from runtime import *
from plans import *
import cProfile,pstats,io,statistics,traceback,gc
out=ROOT/'results/initial';out.mkdir(exist_ok=True)
a=load();b=load(ROOT/'fast_code');cfg=settings(a);rows=[]
for case in ['001','003','025']:
 g=json.loads((OFF/f'data/case_{case}.json').read_bytes())
 p=component_plan(g) if case!='003' else intervals(g,chunks=8)
 save_json(out/f'{case}.plan.json',p)
 for q in [1,2,3]:
  row={'case':case,'q':q}
  for name,engine in [('E0',a),('R2',b)]:
   try:
    gc.collect();t=time.perf_counter();r=evaluate(engine,q,g,p,cfg);dt=time.perf_counter()-t
    save_json(out/f'{case}_q{q}_{name}.json.gz',r);row[name]=dt;row['makespan']=r['makespan']
    if name=='E0':base=r
    else:strict_equal(base,r)
   except Exception as e:row[name+'_error']=str(e);row[name+'_type']=type(e).__name__
  print(row,flush=True);rows.append(row)
 # one profile per case P1
 prof=cProfile.Profile();prof.enable();r=evaluate(a,1,g,p,cfg);prof.disable();prof.dump_stats(str(out/f'{case}.pstats'))
 s=io.StringIO();pstats.Stats(prof,stream=s).strip_dirs().sort_stats('cumtime').print_stats(35);(out/f'{case}.profile.txt').write_text(s.getvalue())
save_json(out/'summary.json',rows)
