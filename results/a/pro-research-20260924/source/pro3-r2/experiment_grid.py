from runtime import *
from plans import *
from incidence_grid import *
import gc,statistics

def run(case,q,cores):
 out=ROOT/f'results/grid/case_{case}_q{q}_c{cores}';out.mkdir(parents=True,exist_ok=True);e=load();f=load(ROOT/'fast_code');cfg=settings(e);g=json.loads((OFF/f'data/case_{case}.json').read_bytes());start=time.perf_counter();d=detect(g)
 if d is None:raise ValueError('not product')
 candidates=[('component_lpt_bins',component_plan(g,cores=cores))]+rectangle_candidates(d,cores);build=time.perf_counter()-start;rows=[]
 if (out/'summary.json').exists():rows=json.loads((out/'summary.json').read_bytes())['rows']
 for i,(name,p) in enumerate(candidates):
  if any(r['i']==i for r in rows):continue
  save_json(out/f'{i:02d}.plan.json',p);row={'i':i,'name':name,'boundary_input_bytes':exact_boundary_inputs(d,p)}
  try:
   gc.collect();t=time.perf_counter();r=evaluate(e,q,g,p,cfg);row['E0_seconds']=time.perf_counter()-t;save_json(out/f'{i:02d}.E0.json.gz',r)
   gc.collect();t=time.perf_counter();rr=evaluate(f,q,g,p,cfg);row['R2_seconds']=time.perf_counter()-t;save_json(out/f'{i:02d}.R2.json.gz',rr);strict_equal(r,rr)
   row.update(full_equal=True,makespan=r['makespan'],traffic=r['data_movement_bytes'],cache=r.get('cache_stats'))
  except Exception as ex:row.update(error=repr(ex),error_type=type(ex).__name__)
  rows.append(row);save_json(out/'summary.json',{'case':case,'q':q,'cores':cores,'detect_construct_seconds':build,'rows_axis':d['rows'],'cols_axis':d['cols'],'rows':rows});print(case,q,cores,name,row.get('makespan'),row.get('boundary_input_bytes'),row.get('traffic',{}).get('spill_added_copy_bytes'),row.get('E0_seconds'),row.get('R2_seconds'),row.get('error'),flush=True)
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--cases',nargs='+',default=['011','027','037','059','080','097']);ap.add_argument('--questions',nargs='+',type=int,default=[2,3]);ap.add_argument('--cores',type=int,default=4);a=ap.parse_args()
 for case in a.cases:
  for q in a.questions:run(case,q,a.cores)
