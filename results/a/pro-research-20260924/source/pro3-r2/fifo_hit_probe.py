"""Public bipartite graph: an in-flight cache hit is evicted, then reinserted."""
from runtime import *
import types,ast

def graph_plan():
 ts=[];ops=[];edges=[];i=1
 def tensor(pos,size):
  nonlocal i
  v=i;i+=1;ts.append(dict(id=v,pos=pos,size=size));return v
 def op(kind,pipe,cycles,ins,outs):
  nonlocal i
  v=i;i+=1;ops.append(dict(id=v,op=kind,pipe=pipe,cycles=cycles));edges.extend(dict(source=t,target=v) for t in ins);edges.extend(dict(source=v,target=t) for t in outs);return v
 inputs=[]
 for size in [400000,450000,480000]:
  x=tensor('DDR',size);y=tensor('L1',size);op('COPY_IN','PIPE_MTE2',1,[x],[y]);inputs.append(y)
 cs=[]
 for tid in [inputs[0],inputs[1],inputs[0],inputs[2]]:
  y=tensor('L1',1);z=tensor('DDR',1);c=op('ADD','PIPE_M',1,[tid],[y]);op('COPY_OUT','PIPE_MTE3',1,[y],[z]);cs.append(c)
 g=dict(tensors=ts,ops=ops,edges=edges);p={'node_to_subgraph':{str(v):sg for sg,v in enumerate(cs)},'core_schedules':[[0],[1,2],[3]]}
 return g,p,inputs[0]

def run():
 e=load();m=e['multicore_cut_evaluate_problem_3'];cfg=settings(e);g,p,a=graph_plan();r=evaluate(e,3,g,p,cfg);out=ROOT/'results/counterexamples/hit_reinsert';out.mkdir(parents=True,exist_ok=True)
 src=Path(m.__file__).read_text();tree=ast.parse(src);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='evaluate_problem_3');src='\n'.join(src.splitlines()[node.lineno-1:node.end_lineno]);s0="                if cache_eligible(op['op']):";s1="                if cache_eligible(op['op']) and op_memory_path.get(item) != 'CACHE_READ':";assert src.count(s0)==1
 ns=dict(m.__dict__);exec(compile(src.replace(s0,s1),'<wrong-miss-only-insert>','exec'),ns)
 wrong=ns['evaluate_problem_3'](g,p,bandwidth=cfg['bandwidth'],capacity=cfg['capacity'],cross_core_copy_delay=cfg['cross_core_copy_delay_cycles'],cache_capacity_bytes=cfg['cache_capacity_bytes'],cache_bandwidth_bytes_per_cycle=cfg['cache_bandwidth_bytes_per_cycle'])
 save_json(out/'graph.json',g);save_json(out/'plan.json',p);save_json(out/'E0.result.json',r);save_json(out/'miss_only.result.json',wrong);(out/'mutation.txt').write_text(s0+'\n-->\n'+s1)
 events=[v for v in r['cache_events'] if v['tensor_id']==a or a in v.get('evicted_tensor_ids',[])]
 row={'shared_A_key':a,'E0_makespan':r['makespan'],'wrong_makespan':wrong['makespan'],'events_A':events,'E0_final':r['cache_final_entries'],'wrong_final':wrong['cache_final_entries']};save_json(out/'summary.json',row);print(json.dumps(row,indent=2))
if __name__=='__main__':run()
