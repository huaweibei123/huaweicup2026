"""Fresh E0/R2 and original member E1 against the supplied 64 full E0 truths.
No old timings are reused. JSON roundtrip solely converts int dict keys to JSON keys.
"""
from runtime import *
import argparse,importlib.util,sys,types

def team_engine():
 pkg=types.ModuleType('_r3_team');pkg.__path__=[str(ROOT/'input_bundle/src/eval_exact')];sys.modules['_r3_team']=pkg
 spec=importlib.util.spec_from_file_location('_r3_team.problem1',Path(pkg.__path__[0])/'problem1.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--start',type=int,default=0);ap.add_argument('--end',type=int,default=64);a=ap.parse_args()
 e=load();f=load(ROOT/'fast_code');team=team_engine();cfg=settings(e);g=json.loads((OFF/'data/case_001.json').read_bytes());pool=ROOT/'input_bundle/results/a/proxy/r20260923-e2-dev64-gzip';out=ROOT/'results/regression64';out.mkdir(exist_ok=True)
 for i in range(a.start,a.end):
  name=f'candidate-{i:03d}';p=json.loads((pool/'plans'/f'{name}.plan.json').read_bytes());truth=json.loads(gzip.decompress((pool/'e0'/f'{name}.result.json.gz').read_bytes()));row={'candidate':i};results=[]
  for label,fn in [('E0',lambda:evaluate(e,1,g,p,cfg)),('R2',lambda:evaluate(f,1,g,p,cfg)),('member_E1',lambda:team.evaluate_scene_a(g,p,bandwidth=cfg['bandwidth'],capacity=cfg['capacity'],cross_core_wait=cfg['task_cross_core_wait_cycles'],same_core_wait=cfg['task_same_core_wait_cycles']))]:
   t=time.perf_counter();r=fn();row[label+'_seconds']=time.perf_counter()-t;strict_equal(truth,json.loads(json.dumps(r,allow_nan=False)));row[label+'_matches_supplied_JSON']=True;save_json(out/f'{name}.{label}.json.gz',r);results.append(r)
  strict_equal(results[0],results[1]);strict_equal(results[0],results[2]);row.update(fresh_full_equal=True,makespan=results[0]['makespan']);save_json(out/f'{name}.run.json',row);print(i,row['makespan'],row['E0_seconds'],row['R2_seconds'],row['member_E1_seconds'],flush=True)
