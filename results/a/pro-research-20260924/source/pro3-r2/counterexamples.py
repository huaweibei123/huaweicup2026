"""Small official-domain graphs and isolated arithmetic probes."""
from runtime import *
from word_quotient import WordEvaluator

def export_graph():
 ts=[(100,'DDR',64),(101,'UB',64),(102,'UB',40000),(103,'UB',64),(104,'DDR',40000),(105,'DDR',64)]
 ops=[(1,'COPY_IN','PIPE_MTE2',1),(2,'ADD','PIPE_V',100),(3,'ADD','PIPE_V',1000),(4,'COPY_OUT','PIPE_MTE3',1),(5,'COPY_OUT','PIPE_MTE3',1)]
 edges=[(100,1),(1,101),(101,2),(2,102),(102,3),(3,103),(102,4),(4,104),(103,5),(5,105)]
 return {'tensors':[dict(id=t,pos=p,size=s) for t,p,s in ts],'ops':[dict(id=i,op=o,pipe=p,cycles=c) for i,o,p,c in ops],'edges':[dict(source=a,target=b) for a,b in edges]}

def run_export():
 out=ROOT/'results/counterexamples/export';out.mkdir(parents=True,exist_ok=True);g=export_graph();e=load();plans=[{'node_to_subgraph':{'2':0,'3':0},'core_schedules':[[0],[]]},{'node_to_subgraph':{'2':0,'3':1},'core_schedules':[[0,1],[]]}];save_json(out/'graph.json',g);rows=[]
 for q in [1,2,3]:
  for k,p in enumerate(plans):
   save_json(out/f'plan_{k}.json',p);r=evaluate(e,q,g,p);save_json(out/f'q{q}_plan{k}.result.json',r)
   rows.append({'q':q,'plan':k,'makespan':r['makespan'],'traffic':r['data_movement_bytes'],'ops':r['per_core_timeline'][0]['ops']})
 save_json(out/'summary.json',rows)
 print([(r['q'],r['plan'],r['makespan']) for r in rows])
 for q in [2,3]:
  w=WordEvaluator(e,q,g,plans[0]);rr=[w.evaluate(p) for p in plans];print('words',q,[w.view_and_words(p)[-1] for p in plans])
 return rows
if __name__=='__main__':run_export()
