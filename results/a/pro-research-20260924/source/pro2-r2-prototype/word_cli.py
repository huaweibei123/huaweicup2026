"""Public-plan generator for homogeneous M -> V* -> M components.
This is a specialized constructor, not a scheduler/evaluator replacement.
Use --official-evaluate to retain an unmodified E0 result/trace/log.
"""
import argparse,json,time
from pathlib import Path
from scan import index_graph
from resource_word import word_plan
from evidence import run_e0,DEFAULT_OFFICIAL

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('graph',type=Path);p.add_argument('-n','--cores',type=int,required=True)
 p.add_argument('-q','--problem',type=int,choices=[2,3],default=2)
 p.add_argument('--output',type=Path,required=True)
 p.add_argument('--official',type=Path,default=DEFAULT_OFFICIAL)
 p.add_argument('--official-evaluate',action='store_true');p.add_argument('--timeout',type=float,default=60)
 a=p.parse_args()
 if not 1<=a.cores<=5:p.error('cores must be within 1..5')
 start=time.perf_counter();g=json.loads(a.graph.read_text());ix=index_graph(g)
 plan,meta=word_plan(ix,a.cores)
 a.output.mkdir(parents=True,exist_ok=False)
 (a.output/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,separators=(',',':'))+'\n')
 meta.update(construction_seconds=time.perf_counter()-start,problem=a.problem,cores=a.cores,status='plan_generated_not_evaluated')
 if a.official_evaluate:
  e=run_e0(a.graph,plan,a.problem,a.output/'e0',timeout=a.timeout,official=a.official,compress=True)
  meta.update(status=e['status'],makespan=e.get('makespan'))
 meta['total_seconds']=time.perf_counter()-start
 (a.output/'construction.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(meta,ensure_ascii=False))
 return 0 if meta['status'] in ['ok','plan_generated_not_evaluated'] else 2
if __name__=='__main__':raise SystemExit(main())
