"""One isolated paired sample (large-case predeclared n=3); persist each engine."""
from runtime import *
from plans import *
import argparse,resource
ap=argparse.ArgumentParser();ap.add_argument('--rep',type=int,required=True);a=ap.parse_args()
out=ROOT/'results/benchmark/025_isolated';out.mkdir(parents=True,exist_ok=True)
g=json.loads((OFF/'data/case_025.json').read_bytes());p=component_plan(g,cores=4)
row={'rep':a.rep,'warmups':0,'fresh_process':True,'comparison':'complete result object, exact recursive types/values/binary64','timing':'load/parse/plan excluded; all candidate-dependent full evaluator work included; no memoization; GC default','samples_requested':3}
rs=[]
for name in (['E0','R2'] if a.rep%2==0 else ['R2','E0']):
 mods=load(None if name=='E0' else ROOT/'fast_code');cfg=settings(mods)
 print('START',a.rep,name,flush=True);t=time.perf_counter();r=evaluate(mods,1,g,p,cfg);row[name+'_seconds']=time.perf_counter()-t
 rs.append(r);save_json(out/f'rep{a.rep}.json',row);print('END',a.rep,name,row[name+'_seconds'],flush=True)
strict_equal(*rs);row.update(full_equal=True,makespan=rs[0]['makespan'],peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss);save_json(out/f'rep{a.rep}.json',row)
print(row,flush=True)
