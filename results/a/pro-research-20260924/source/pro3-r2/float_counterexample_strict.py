"""Same arithmetic counterexample with an ordinary DDR input on EVERY chain."""
from runtime import *
from plans import from_blocks
from float_counterexample import make_graph
import inspect,ast
if __name__=='__main__':
 ns=dict(make_graph.__globals__);src=inspect.getsource(make_graph).replace('vs=[];prev=None',"vs=[];a=tensor('DDR',1);prev=tensor('UB',1);op('COPY_IN','PIPE_MTE2',1,[a],[prev])")
 exec(src,ns);gen=ns['make_graph'];e=load();m=e['multicore_cut_evaluate_problem_2'];cfg=settings(e)
 source=Path(m.__file__).read_text();node=next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef)and x.name=='evaluate_scene_b');fn='\n'.join(source.splitlines()[node.lineno-1:node.end_lineno]);before='        advance_ddr_work(now)\n        retired_ddr = False';after='''        if any(item in ddr_remaining_work and end <= now
               for running in executors.values() for item, end in running):
            advance_ddr_work(now)
        retired_ddr = False''';assert fn.count(before)==1
 gl=dict(m.__dict__);exec(fn.replace(before,after),gl);wrong=gl['evaluate_scene_b'];out=ROOT/'results/counterexamples/float_epochs_with_input';out.mkdir(exist_ok=True);(out/'mutation.txt').write_text(before+'\n---\n'+after);rows=[]
 for n in [64,512,1024,2048,3072,4096]:
  g,p=gen(n);r=evaluate(e,2,g,p,cfg);rr=wrong(g,p,bandwidth=cfg['bandwidth'],capacity=cfg['capacity'],cross_core_copy_delay=cfg['cross_core_copy_delay_cycles']);row={'n':n,'E0':r['makespan'],'coalesced':rr['makespan']}
  try:strict_equal(r,rr);row['full_equal']=True
  except AssertionError as ex:
   row.update(full_equal=False,first_difference=str(ex));save_json(out/'graph.json',g);save_json(out/'plan.json',p);save_json(out/'E0.result.json.gz',r);save_json(out/'coalesced.result.json.gz',rr)
  rows.append(row);print(row,flush=True)
  if not row['full_equal']:break
 save_json(out/'summary.json',rows)
